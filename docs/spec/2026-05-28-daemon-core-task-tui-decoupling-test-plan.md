# Daemon Core / Task TUI Decoupling Test Plan

Date: 2026-05-28

## Objective

Verify the first daemon-team refactor:

1. daemon core becomes an independent instance-level background container;
2. STOP Task TUI behavior remains available through a separate Task Checkout Handler;
3. launcher still owns thread bootstrap / empty-rollout repair;
4. no plugin system, event bus, compatibility wrapper, or message-team feature is introduced;
5. behavior is preserved while code ownership and dependency direction become measurable.

This is a refactor with architecture assertions. The tests must prove behavior and boundaries, not just renamed functions.

## Current Code Facts

- `tools/launcher/instance_daemon.py` currently imports `task_management` and `task_tui` directly.
- The same file owns daemon lifecycle, app-server binding, notification loop, daemon-origin tracking, STOP Task TUI filtering, prompt rendering, and `turn/start`.
- `tools/launcher/task_input_context.py` is the launcher input path and already uses `task_management.current_snapshot(...)` plus `task_tui.render_task_tui(...)`.
- `scripts/env/domain/task_tui.py` owns Task TUI rendering, including `render_stop_task_tui(...)`.
- Launcher bootstrap is already native to launcher/app-server through `thread-bootstrap` / `thread/inject_items`; daemon only binds after bootstrap with `thread/resume`.

## Functional Requirements

FR1. Daemon core must not import `env.domain.task_management`, `env.domain.task_tui`, or Task TUI modules.

FR2. Daemon CLI behavior stays stable: `run`, `start`, `stop`, and `status` continue to work through `tools/launcher/instance_daemon.py`.

FR3. Daemon core still owns runtime path helpers, state load/save, pid/log/status, start/stop readiness, app-server client setup, main-thread bind, notification loop, daemon-origin tracking, and error recording.

FR4. Daemon core dispatches notifications to an explicit in-process handler list.

FR5. Task Checkout Handler owns all STOP Task TUI business logic: completed-turn filtering, snapshot read, STOP prompt render, `turn/start`, checkout turn id recording, and checkout errors.

FR6. A completed, non-daemon-origin main-thread turn still triggers exactly one STOP Task TUI `turn/start`.

FR7. Other-thread, malformed, non-completed, and daemon-origin turn notifications are ignored.

FR8. Daemon-origin turn ids still prevent self-triggered loops.

FR9. Handler exceptions are isolated by daemon core: the loop records an error and continues to later notifications.

FR10. Removing Task Checkout Handler from the explicit handler list leaves daemon core able to start, bind, listen, and report ready/status, but no STOP Task TUI prompt is sent.

FR11. Launcher start/clear bootstrap remains launcher-owned; daemon never calls `thread/inject_items`, `thread/start`, or bootstrap helpers to repair rollout.

FR12. Existing input Task TUI remains unchanged and never routes through daemon.

FR13. `instance start`, `resume`, `clear`, `stop`, and `status` integration behavior remains unchanged from the user perspective.

FR14. State has clear ownership: daemon generic state remains generic, while task checkout fields live under a handler-owned namespace or equivalent clearly separated handler state.

## Required Automated Tests

### 1. Architecture Boundary Tests

File: `tests/test_daemon_core_decoupling.py`

Cases:

- `test_daemon_core_imports_without_task_domain_modules`
  - Temporarily block imports of `env.domain.task_management` and `env.domain.task_tui`.
  - Import `tools/launcher/daemon_core.py`.
  - Expected: import succeeds.
  - Purpose: proves daemon core does not depend on Task TUI.

- `test_task_checkout_handler_is_the_only_daemon_side_task_import`
  - Inspect daemon-side launcher modules with `ast`.
  - Expected: only `tools/launcher/task_checkout_handler.py` imports `task_management` / `task_tui`.
  - Expected: `tools/launcher/daemon_core.py` has no string or import reference to `task_tui`, `task_management`, or `stop_tui`.

- `test_daemon_core_can_dispatch_to_noop_handler`
  - Run core notification dispatch with a fake handler that records the notification and returns `False`.
  - Expected: handler is called once; no task prompt is sent.

- `test_no_task_handler_means_no_checkout_turn_start`
  - Run daemon loop with an empty handler list and a real-shape `turn/completed` notification.
  - Expected: app-server fake records only `thread/resume`, no `turn/start`.

### 2. Daemon Core State And Lifecycle Tests

File: `tests/test_daemon_core.py`

Cases:

- Missing state initializes valid generic state:
  - `instance_id`
  - `main_thread_id`
  - `daemon_origin_turn_ids: []`
  - `ready: None`
  - `last_error: None`
  - handler state container present or initialized lazily.

- Recording daemon-origin turn persists the id and caps the list to the latest 50 ids.

- `is_daemon_origin_turn(...)` returns true only for persisted daemon-origin ids.

- Recording ready state persists pid, main thread id, and timestamp.

- `ready_for(pid, thread_id)` rejects wrong pid or thread id.

- `bind_main_thread(...)` uses `thread/resume` with:
  - current `main_thread_id`
  - instance workspace cwd
  - instance workspace plus shared project workspace roots
  - `permissions: buddyswitch-runtime`
  - `excludeTurns: True`

- `bind_main_thread(...)` fails on wrong returned thread id.

- `start_daemon(...)` creates daemon runtime dir, log file, pid file, state file, and waits for matching ready state before success.

- `start_daemon(...)` is idempotent when an existing live pid is ready for the same main thread.

- `start_daemon(...)` replaces stale or live-unready pid before starting a new daemon.

- `start_daemon(...)` fails closed if process exits before ready or readiness times out.

- `stop_daemon(...)` terminates a live pid and removes the pid file.

- `daemon_status(...)` reports live, pid, ready, ready main thread, log path, state path, and last error.

### 3. Daemon Core Run Loop Tests

File: `tests/test_daemon_core.py`

Cases:

- Idle notification timeout is normal:
  - Fake client raises `AppServerTimeoutError`, then sends a valid notification.
  - Expected: timeout is ignored, later notification is dispatched, no idle error is written.

- Fatal app-server error exits nonzero:
  - Fake client raises `AppServerUnavailableError`.
  - Expected: result is `1`, `last_error.origin_turn_id is None`.

- Handler exception is isolated:
  - First handler call raises `RuntimeError("handler exploded")`.
  - Second notification succeeds through a fake handler.
  - Expected: loop continues, top-level `last_error` records first notification turn id and message.

- Multiple handlers are called in explicit order:
  - Use two fake handlers.
  - Expected: both receive the same notification unless the design intentionally stops after handled; the chosen rule must be asserted.
  - Recommended rule for Step 1: call every handler and let each decide ignore/handle, because no generic event bus is being introduced.

### 4. Task Checkout Handler Filter Tests

File: `tests/test_task_checkout_handler.py`

Use real Codex notification shape:

```json
{
  "method": "turn/completed",
  "params": {
    "threadId": "thr-main",
    "turn": {
      "id": "turn-user-1",
      "status": "completed"
    }
  }
}
```

Cases:

- Completed main-thread user-origin turn is accepted.
- Other-thread completed turn is ignored.
- `failed`, `interrupted`, and `inProgress` statuses are ignored.
- Missing `params`, missing `turn`, missing turn id, or missing thread id are ignored.
- Daemon-origin turn id is ignored.

### 5. Task Checkout Handler Send Path Tests

File: `tests/test_task_checkout_handler.py`

Cases:

- Accepted completed turn sends exactly one app-server `turn/start`.
- `turn/start` uses the same main thread id and `buddyswitch-runtime` permissions.
- Prompt starts with `[TASK CHECKOUT]`.
- Prompt does not contain `[TASK CONTEXT]` or `[USER INPUT]`.
- Handler calls `task_management.current_snapshot(...)` and then `task_tui.render_stop_task_tui(...)`.
- Returned daemon-origin turn id is recorded through daemon state.
- Handler-owned state records origin turn id and checkout turn id under the task checkout namespace.
- If `turn/start` returns no turn id, handler records an error and returns failure.
- If `turn/start` raises `AppServerRequestError`, handler records an error, does not retry, does not call `turn/steer`, and a later distinct completed turn can still trigger a prompt.

### 6. Entry Point Wiring Tests

File: `tests/test_instance_daemon_entrypoint.py`

Cases:

- `instance_daemon.py run` passes the explicit handler list containing Task Checkout Handler to daemon core.
- `instance_daemon.py start/status/stop` keep the same CLI output shape expected by shell integration.
- `daemon.sh` continues to call `tools/launcher/instance_daemon.py`.

### 7. Launcher Integration Regression Tests

File: `tests/test_buddyswitch_launcher.py`

Keep or update existing integration tests to assert:

- `instance start` starts a ready daemon for the persisted main thread.
- `instance resume` starts a ready daemon for the original main thread.
- `instance clear` stops the old daemon, bootstraps the new thread, then starts a daemon bound to the new thread.
- `instance stop` stops daemon before app-server.
- `instance status --json` includes daemon status.
- Human status output includes daemon health.
- Start/clear bootstrap calls `thread/inject_items` before daemon `thread/resume`.
- Bootstrap failure fails closed without a ready daemon.
- Daemon failure after clear preserves the new thread id and marks the instance inactive as currently specified.

### 8. Fake Codex Event Stream Integration Tests

File: `tests/test_buddyswitch_launcher.py`

Cases:

- Fake Codex emits daemon notifications only after daemon has bound through `thread/resume`.
- Real completed event triggers one STOP Task TUI prompt.
- Fake Codex emits completion for daemon-origin turn and no second prompt is sent.
- Completed event from another thread is ignored.

### 9. Input Task TUI Regression Tests

Files:

- `tests/test_task_input_context.py`
- `tests/test_buddyswitch_launcher.py`

Cases:

- `compose_task_context_input(...)` still renders `[TASK CONTEXT]`, wraps `[USER INPUT]`, and uses raw user text.
- `instance input` still chooses `turn/start` or `turn/steer` according to thread status.
- Daemon checkout code never calls `compose_task_context_input(...)`.

## Coverage Matrix

| Requirement | Test Groups |
| --- | --- |
| FR1 | 1 |
| FR2 | 6, 7 |
| FR3 | 2, 3 |
| FR4 | 1, 3 |
| FR5 | 4, 5 |
| FR6 | 5, 8 |
| FR7 | 4, 8 |
| FR8 | 2, 4, 8 |
| FR9 | 3 |
| FR10 | 1, 3 |
| FR11 | 7 |
| FR12 | 9 |
| FR13 | 7, 8 |
| FR14 | 2, 5 |

## Anti-Cheating Rules

- Do not test only flat legacy notification shapes; tests must use the real nested Codex shape.
- Do not satisfy boundary tests with comments or naming only; import and AST checks must prove the dependency boundary.
- Do not mock away app-server action behavior in handler tests; fake clients must record actual `request(method, params)` calls.
- Do not make daemon core tests import Task TUI modules indirectly.
- Do not add compatibility wrappers that keep Task TUI logic in daemon core while also calling a handler.
- Do not make launcher bootstrap tests pass by daemon-side repair; assert `thread/inject_items` happens before daemon `thread/resume`.

## Verification Commands

Focused verification:

```bash
python3 -m pytest \
  tests/test_daemon_core_decoupling.py \
  tests/test_daemon_core.py \
  tests/test_task_checkout_handler.py \
  tests/test_instance_daemon_entrypoint.py \
  -q
```

Integration verification:

```bash
python3 -m pytest \
  tests/test_buddyswitch_launcher.py -k 'daemon or bootstrap or task_tui or input_context' \
  tests/test_app_server_client.py \
  tests/test_task_input_context.py \
  -q
```

Final relevant verification:

```bash
python3 -m pytest \
  tests/test_daemon_core_decoupling.py \
  tests/test_daemon_core.py \
  tests/test_task_checkout_handler.py \
  tests/test_instance_daemon_entrypoint.py \
  tests/test_app_server_client.py \
  tests/test_task_input_context.py \
  tests/test_buddyswitch_launcher.py \
  -q
```

## Plan Review

- Requirement coverage: every functional requirement maps to at least one test group.
- Forward principle: tests validate the new clean boundary directly; they do not preserve the old all-in-one daemon structure.
- Scope control: no message handler, plugin registry, event bus, or generalized workflow engine is tested.
- Risk focus: the plan covers behavior preservation, daemon independence, handler extraction, loop guard, launcher bootstrap boundary, and input TUI regression.
