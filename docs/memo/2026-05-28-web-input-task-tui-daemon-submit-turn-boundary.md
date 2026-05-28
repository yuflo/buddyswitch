# Web Input Task TUI And Daemon Submit Turn Boundary

Date: 2026-05-28
Status: aligned task memo after architecture discussion
Owner perspective: launcher, daemon, and task runtime boundary

## Core Task

把 BuddySwitch 的用户 input、Task TUI、STOP checkout、daemon、Codex remote transport 边界收敛到一条清晰路径：

1. Web 管理页发送用户 input 时，自动使用 `task-tui`。
2. CLI `instance input` 默认继续保持 `raw`，显式支持 `--input-wrapper task-tui`。
3. STOP checkout 继续使用专用 `[TASK CHECKOUT]` prompt。
4. daemon core 不知道 task、Task TUI、checkout 业务。
5. task checkout handler 不直接知道 app-server / Codex remote transport。
6. Web/CLI input 和 STOP checkout 共用 launcher-owned turn submit 发送能力。

This is a boundary cleanup task, not a compatibility layering task.

## Current Problem

现在存在两条发送链路。

User input path:

```text
Web UI / CLI
-> buddyswitch-codex instance input
-> launcher input wrapper
-> app-server input
-> Codex remote
```

STOP checkout path:

```text
Codex turn/completed
-> daemon_core listens notification
-> task_checkout_handler reads task snapshot and renders Task TUI checkout prompt
-> daemon ActionGateway directly calls app-server turn/start
-> Codex remote
```

问题分两类。

First, Web input currently does not request `task-tui`, so Codex receives raw user text from the Web UI. This means the model may not see task context at the start of the turn.

Second, STOP checkout task business is mostly outside daemon core, but the transport boundary is still mixed:

- `daemon_core.py` owns the app-server client connection and `turn/start` send.
- `task_checkout_handler.py` imports `app_server` to catch transport errors.
- checkout business and daemon transport still meet inside the daemon side of the launcher.

This violates the direction in `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`: high-churn shared files and central technical paths should be split into product-owned slices and small stable contracts.

## Desired Boundary

Introduce a launcher-owned internal submit layer:

```text
launcher submit_turn
```

`submit_turn` owns only one responsibility:

```text
send already-composed text to the target Codex thread
```

It does not own:

- wrapper selection;
- task snapshot reading;
- Task TUI rendering;
- checkout trigger detection;
- task state mutation decisions.

## Module Responsibilities

### task-tui

Owns task prompt rendering.

Input prompt:

```text
[TASK CONTEXT]
...

[USER INPUT]
...
```

STOP checkout prompt:

```text
[TASK CHECKOUT]
...
```

`task-tui` does not send prompts to Codex.

### launcher input

Owns user input orchestration.

Rules:

- Web input defaults to `task-tui`.
- CLI input defaults to `raw`.
- CLI input may explicitly request `--input-wrapper task-tui`.
- launcher input composes the final prompt, then calls `submit_turn`.

It should not own STOP checkout semantics.

### daemon core

Owns daemon runtime mechanics only:

- connect to Codex notification stream;
- bind / resume the main thread;
- receive notifications;
- dispatch notifications to handlers;
- expose an action interface to handlers.

It must not import:

- `task_management`;
- `task_tui`;
- checkout prompt code.

### task checkout handler

Owns the task checkout product slice.

It does:

```text
notification -> trigger check -> task snapshot -> [TASK CHECKOUT] prompt -> action request
```

It should:

- filter `turn/completed`;
- ignore non-main-thread turns;
- ignore non-completed turns;
- ignore daemon-origin turns;
- read the active buddy task snapshot;
- call `task_tui.render_stop_task_tui`;
- request `actions.submit_turn(...)`.

It should not:

- import `app_server`;
- know JSON-RPC transport details;
- directly call Codex remote.

### launcher submit_turn

Owns the shared send contract.

It should handle:

- target thread id;
- prompt text;
- permissions;
- origin metadata where needed;
- app-server / Codex remote request;
- `turn/start` vs existing launcher input send behavior as appropriate;
- return of `turn_id` / action result;
- transport error normalization.

It should not know:

- task snapshot structure;
- Task TUI wording;
- checkout decision rules.

### app-server

Owns only transport adaptation:

- socket / JSON-RPC communication;
- Codex remote methods;
- raw transport errors;
- thread / turn request payload details.

It must not know:

- Task TUI;
- `[TASK CONTEXT]`;
- `[USER INPUT]`;
- `[TASK CHECKOUT]`;
- checkout business;
- task snapshot semantics.

## Target Flows

### Web Input

```text
Web UI
-> POST /api/instances/<id>/input
-> web_management.py calls:
   buddyswitch-codex instance input <id> --text ... --input-wrapper task-tui --json
-> launcher input wrapper renders [TASK CONTEXT] + [USER INPUT]
-> launcher submit_turn
-> app-server / Codex remote
```

### CLI Input

Default:

```text
buddyswitch-codex instance input <id> --text ...
-> raw
-> launcher submit_turn
-> app-server / Codex remote
```

Explicit Task TUI:

```text
buddyswitch-codex instance input <id> --text ... --input-wrapper task-tui
-> [TASK CONTEXT] + [USER INPUT]
-> launcher submit_turn
-> app-server / Codex remote
```

### STOP Checkout

```text
Codex emits turn/completed
-> daemon_core receives notification
-> daemon_core dispatches to task_checkout_handler
-> task_checkout_handler confirms this is a checkout trigger
-> task_checkout_handler reads task_management.current_snapshot(...)
-> task_checkout_handler calls task_tui.render_stop_task_tui(...)
-> task_checkout_handler requests actions.submit_turn(...)
-> daemon action gateway delegates to launcher submit_turn
-> app-server / Codex remote
```

## Handler Semantics

A handler is not a transport sender.

Better definition:

```text
handler = event -> business decision -> action request
```

For task checkout:

```text
turn/completed notification
-> is this a main-thread completed user-origin turn?
-> if yes, generate [TASK CHECKOUT]
-> request submit_turn
```

The handler decides what should happen. The action gateway / launcher submit layer performs the actual send.

## Active Task Semantics

`active task` is not a separate system.

It is the current task in the active buddy's task-tool snapshot. It is created, read, and updated through the runtime task env tool:

```bash
python3 scripts/env/client.py task current ...
python3 scripts/env/client.py task propose ...
python3 scripts/env/client.py task confirm ...
```

It is stored in the instance-local taskbox:

```text
/Users/chen/.codex-buddyswitch/instances/<instance-id>/taskbox/<buddy>/
```

The observed PM vs Market checkout difference came from different task-tool state:

```text
PM input looked like a new task
-> model called task.propose(start)
-> checkout saw active task
-> checkout generated a visible block/update response

Market input looked like a one-off search
-> model did not create a task
-> checkout saw Active task: none
-> checkout prompt said no update should stay silent
-> checkout completed with no visible response
```

This is expected under current prompt semantics. Web input using `task-tui` improves the first-turn task context visibility, but it does not force every one-off user request to become a task.

## Bitter Boundary Implication

Do not replace a central handler function with a central handler config file if every new handler still edits the same file.

Bad shape:

```text
tools/launcher/daemon_handlers.toml
handlers = ["task_checkout", "future_x", "future_y"]
```

This only moves the conflict hotspot from Python to TOML.

Preferred long-term shape, if multiple independent handlers appear:

```text
task checkout slice owns its own daemon hook fragment
future slice owns its own daemon hook fragment
launcher composes stable hook contracts without owning business lists
```

For now there is only one handler, `task_checkout`. Do not introduce a plugin system, registry engine, or discovery framework for hypothetical future handlers. Keep the explicit assembly small, but do not continue expanding it into a central business list.

## Implementation Direction

The implementation should be one focused task, not several speculative refactors.

Do:

1. Add or expose launcher-owned `submit_turn` as the shared sending contract.
2. Route Web input through `--input-wrapper task-tui`.
3. Keep CLI input default as `raw`.
4. Route launcher input send through `submit_turn`.
5. Route daemon checkout action send through `submit_turn`.
6. Remove app-server transport import from `task_checkout_handler.py`.
7. Preserve daemon state fields for observability:
   - `last_origin_turn_id`;
   - `last_action_turn_id`;
   - `last_result`;
   - `last_error`.

Do not:

- make STOP checkout call `buddyswitch-codex instance input`;
- make STOP checkout use `--input-wrapper task-tui`;
- move Task TUI logic into app-server;
- move task checkout business into daemon core;
- add a plugin system;
- create a central handler config file as the new change hotspot.

## Acceptance Criteria

1. Web input sends through launcher input with `--input-wrapper task-tui`.
2. CLI input with omitted `--input-wrapper` remains raw.
3. CLI input with `--input-wrapper task-tui` still sends `[TASK CONTEXT]` plus `[USER INPUT]`.
4. STOP checkout still sends `[TASK CHECKOUT]`.
5. `daemon_core.py` does not import `task_management` or `task_tui`.
6. `task_checkout_handler.py` does not import `app_server`.
7. task checkout handler requests an action; it does not directly know Codex remote transport.
8. daemon action gateway delegates send to launcher `submit_turn`.
9. app-server remains a transport adapter and does not know Task TUI or checkout.
10. Existing daemon STOP behavior remains covered:
    - daemon-origin turns are ignored;
    - main-thread completed user turns trigger checkout;
    - no handler means no checkout turn starts;
    - handler state records origin/action/error fields.
11. Web input task context behavior is covered by launcher or web-management tests.

## Summary

The intended final shape is:

```text
Web input
-> task-tui input wrapper
-> launcher submit_turn
-> app-server / Codex remote

CLI input
-> raw by default, task-tui only when explicit
-> launcher submit_turn
-> app-server / Codex remote

STOP checkout
-> daemon event dispatch
-> task checkout slice
-> task-tui checkout renderer
-> launcher submit_turn
-> app-server / Codex remote
```

The boundary goal is not to make everything generic. The goal is to remove the current choke point: daemon-side checkout should not directly own Codex remote transport, and Web input should not silently miss task context.
