# Launcher Input Wrapper Boundary Reset

Date: 2026-05-28
Owner perspective: launcher team
Status: implementation memo for one-pass boundary cleanup

## Core Task

按照 daemon、launcher、Task TUI 三个模块独立演进的边界，把 `launcher input` 和 Task TUI 拆干净。

这不是给 `launcher input` 增加一个 Task TUI 参数，也不是保留旧路径再慢慢迁移。

这是一次边界重置：

```text
launcher input becomes the base input API again.
Task TUI becomes an explicit input wrapper.
app-server transport stops knowing Task TUI exists.
```

## Why This Exists

当前问题是 `launcher input` 基础通道被 Task TUI 内建语义污染：

```text
launcher input / app_server input
-> compose_task_context_input(...)
-> task_tui.render_task_tui(...)
-> input_turn(...)
```

这会造成两个架构问题：

- launcher input 不再是独立基础 API，而是隐式 Task TUI input；
- Task TUI team 和 launcher team 的普通变更会反复碰同一条 shared path。

根据 `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`，这类高频共享路径是 architecture feedback，不应靠协作流程解决，而应移动 change boundary。

## Non-Negotiables

本任务一次完成，不做历史残留和过渡兼容。

必须做到：

- 不保留旧的隐式 Task TUI 默认路径；
- 不保留 hidden fallback；
- 不保留 `task-ui` alias，只接受 `task-tui`；
- 不做 plugin system / workflow engine / generic registry；
- 不改 daemon STOP 路径；
- 不让 `app_server.py` import Task TUI；
- 不让 app-server transport 接收 `--instance-json` 来拼 Task TUI context。

## Module Positions

### Launcher Team

Launcher owns the user-facing instance input API.

It provides:

- `buddyswitch-codex instance input`;
- `--text`;
- `--input-wrapper`;
- `--json`;
- instance/thread binding;
- wrapper selection;
- final text delivery into `app_server.input_turn(...)`.

It does not own:

- Task TUI prompt content;
- task snapshot semantics;
- task mutation decision rules;
- daemon checkout behavior.

### App-Server Transport

App-server helper owns only the Codex app-server transport primitives.

It provides:

- socket / JSON-RPC communication;
- `thread/read`;
- thread status inspection;
- idle `turn/start`;
- active `turn/steer`.

It must not know:

- Task TUI;
- input wrappers;
- `[TASK CONTEXT]`;
- `[USER INPUT]`;
- task snapshot state.

### Task TUI Team

Task TUI owns a prompt-level vertical practice.

It provides:

- `task-tui` input wrapper;
- task snapshot read;
- `[TASK CONTEXT]` renderer;
- `[USER INPUT]` envelope;
- prompt-level task interface view for Codex CLI.

It does not own:

- launcher input core;
- app-server transport;
- daemon core.

## Final Public API

```bash
buddyswitch-codex instance input <instance-id> \
  --text <text> \
  [--input-wrapper raw|task-tui] \
  [--json]
```

Default:

```text
--input-wrapper raw
```

Argument meanings:

- `--text`: user text to send.
- `--input-wrapper`: preprocessing mode before sending text to Codex.
- `--json`: output format for the launcher command only; it does not change the text sent to Codex.

## Wrapper Semantics

### `raw`

The default base input channel.

```text
raw user text
-> app_server.input_turn(...)
```

Rules:

- no Task TUI import;
- no task snapshot read;
- no `[TASK CONTEXT]`;
- no `[USER INPUT]` envelope.

### `task-tui`

The explicit Task TUI foreground wrapper.

```text
raw user text
-> [TASK CONTEXT]
   ...

   [USER INPUT]
   raw user text
-> app_server.input_turn(...)
```

Rules:

- reads task snapshot;
- renders Task TUI context;
- owns prompt wording;
- stays outside app-server transport.

## Desired Internal Shape

```text
buddyswitch-codex instance input
  -> parse --input-wrapper
  -> compose final_text through selected wrapper
  -> buddyswitch_app_server_input(thread_id, final_text)
  -> app_server.input_turn(final_text)
```

`app_server.py input` should only accept transport-level arguments:

```text
--socket
--thread-id
--text
--permissions
```

It should not accept:

```text
--instance-json
```

because `--instance-json` exists only for Task TUI context composition and therefore belongs outside app-server transport.

## Suggested File Boundary

The exact file names may follow local style, but the ownership should be:

```text
tools/launcher/app_server.py
  pure app-server transport

tools/launcher/app_server.sh
  pure app-server input invocation

buddyswitch-codex or launcher input shell layer
  parse --input-wrapper
  call wrapper composer
  pass final text to app_server input

tools/launcher/input_wrapper.py
  launcher-owned wrapper selection contract

tools/launcher/input_wrappers/raw.py
  launcher-owned raw wrapper

tools/launcher/input_wrappers/task_tui.py
  Task TUI-owned wrapper implementation
```

Avoid a growing central registry. For this task, a small explicit selection for `raw` and `task-tui` is enough. Do not introduce a generic plugin mechanism.

## Daemon Relationship

This task does not modify daemon STOP behavior.

The daemon path remains:

```text
turn/completed
-> daemon dispatch
-> TaskCheckoutHandler
-> render_stop_task_tui
-> ActionGateway.turn_start
```

This task only resets foreground input:

```text
human input
-> launcher input
-> input wrapper
-> app_server.input_turn
```

## Historical Residue To Remove

Remove the old coupling points completely:

- `app_server.py` import of `task_input_context`;
- `TaskInputContextError` handling inside `app_server.py`;
- `_command_input` implicit `compose_task_context_input(...)`;
- `app_server.py input` `--instance-json`;
- `app_server.sh` passing `--instance-json` into app-server input;
- default Task TUI wrapping on `instance input`;
- any compatibility alias named `task-ui`;
- any fallback that silently applies Task TUI when wrapper is omitted.

Expected scan after cleanup:

```bash
rg "compose_task_context_input|TaskInputContextError|--instance-json|task_input_context" \
  tools/launcher/app_server.py \
  tools/launcher/app_server.sh \
  buddyswitch-codex
```

Expected result: no launcher transport/core hits. Task TUI wrapper modules and tests may still reference Task TUI composition.

## Test Requirements

Add or update focused tests that prove:

1. `instance input` accepts `--input-wrapper raw|task-tui`.
2. omitted `--input-wrapper` means `raw`.
3. `raw` path sends raw text without `[TASK CONTEXT]` or `[USER INPUT]`.
4. `task-tui` path sends text with `[TASK CONTEXT]` and `[USER INPUT]`.
5. unknown wrapper values are rejected.
6. `--json` still affects only command output format.
7. `app_server.py` no longer imports Task TUI / `task_input_context`.
8. `app_server.py input` no longer exposes `--instance-json`.
9. `input_turn(...)` idle start and active steer behavior remains unchanged.
10. daemon STOP tests remain unchanged and green.

## Parallel Development Result

After this task:

```text
launcher team
  can evolve input API, wrapper selection, raw behavior, and app-server transport

Task TUI team
  can evolve task-tui wrapper, prompt rendering, task snapshot usage, and decision cues

daemon team
  can evolve background runtime, handler dispatch, action gateway, and observability
```

Ordinary Task TUI prompt work should not require editing `app_server.py` or launcher transport.

Ordinary launcher input work should not require editing Task TUI prompt modules.

Ordinary daemon runtime work should not require editing either foreground input wrapper code or Task TUI prompt content.

## Definition Of Done

This task is done only when:

- `launcher input` is raw by default;
- `task-tui` is explicit;
- app-server transport is Task TUI-free;
- old implicit Task TUI input behavior is removed, not hidden behind compatibility;
- tests prove raw and task-tui behavior separately;
- no daemon core or STOP checkout behavior is changed;
- the resulting boundary allows launcher and Task TUI teams to advance independently.

## One-Line Version

Reset `launcher input` into a neutral base API with explicit `raw|task-tui` wrapper support, remove all app-server Task TUI coupling, and leave daemon STOP untouched.
