# STOP Task TUI Daemon Test Plan

Date: 2026-05-27

## Objective

Verify the first daemon-backed STOP-stage Task TUI path:

1. each buddy instance owns one daemon instance;
2. the daemon observes the bound Codex app-server main thread;
3. after a normal main-thread turn completes, the daemon sends one real STOP Task TUI prompt through `turn/start`;
4. Codex remains responsible for deciding whether to call `$task-management` and `task.propose(finish|block)`;
5. daemon-origin turns do not trigger another STOP Task TUI loop.

This plan intentionally does not test a Codex Stop hook. STOP here means the post-turn daemon checkpoint, implemented as a real new prompt.

## Confirmed Scope

- Build and run a per-instance daemon service.
- Subscribe to Codex app-server notifications for the instance main thread.
- React only to `turn/completed` notifications with `status=completed`.
- Send one STOP Task TUI prompt by direct Codex app-server JSON-RPC `turn/start`.
- Persist daemon-origin turn ids under the instance runtime daemon state.
- Reuse the same canonical task snapshot path used by `task.current` and the existing input Task TUI.
- Keep the existing input Task TUI path unchanged.

## Non-Scope

- No migration of input TUI into daemon.
- No Codex Stop hook continuation prompt.
- No retry loop.
- No `turn/steer` fallback.
- No daemon-side task completion judgment.
- No direct editing of `buddyswitch/objects/**` or old buddybox runtime paths.

## Current Code Facts To Preserve

- `tools/launcher/task_input_context.py` already composes input prompts by calling `task_management.current_snapshot(...)` and `task_tui.render_task_tui(...)`.
- `scripts/env/domain/task_management.py` owns the canonical `current_snapshot(...)` function used by task tools and input TUI.
- `scripts/env/domain/task_tui.py` owns Task TUI rendering.
- `tools/launcher/app_server.py` owns `AppServerClient` and the existing WebSocket JSON-RPC protocol implementation.
- `tools/launcher/app_server.sh` wires `instance input` through `--instance-json`, which must continue to wrap raw user input with input Task TUI.
- `buddyswitch-codex` starts, resumes, clears, stops, and reports instance app-server state.

## Functional Requirements

FR1. Starting or resuming an active buddy instance starts exactly one daemon for that instance.

FR2. Stopping an instance stops the daemon before stopping the app-server.

FR3. Clearing an instance thread rebinds the daemon to the new main thread.

FR4. Daemon status is visible in instance status output.

FR5. The daemon connects to the instance app-server through the existing app-server client protocol code.

FR6. The daemon listens on the bound main thread only.

FR7. A `turn/completed` notification with `status=completed` for the main thread triggers one STOP Task TUI `turn/start`.

FR8. `turn/completed` notifications for other threads are ignored.

FR9. `turn/completed` notifications with `status=failed` or `status=interrupted` are ignored.

FR10. A completed daemon-origin turn is ignored to prevent prompt loops.

FR11. The STOP Task TUI prompt is built from `task_management.current_snapshot(...)` and `task_tui.render_stop_task_tui(...)`.

FR12. The daemon does not read task history or task documents through a separate parser.

FR13. The STOP Task TUI permits only three decisions: finish, block, or no task update.

FR14. The STOP Task TUI does not instruct start, switch, confirm, or arbitrary task mutation.

FR15. The STOP Task TUI is sent directly by `turn/start`, not through the input command or input TUI composer.

FR16. After a successful daemon-origin `turn/start`, the returned turn id is persisted in daemon state.

FR17. On `turn/start` failure, the daemon records the error and does not retry, steer, or block the user.

FR18. Existing input prompt behavior remains unchanged.

## Required Automated Tests

### 1. STOP Task TUI Renderer

File: `tests/test_task_input_context.py` or `tests/test_stop_task_daemon.py`

Cases:

- `render_stop_task_tui(snapshot, previous_turn)` renders `[TASK CHECKOUT]`.
- The rendered text includes previous turn id, active task id, task status, progress/body summary, and last task event when present.
- The rendered text contains the allowed decision cues:
  - `Done -> $task-management + task.propose(finish)`
  - `Blocked -> $task-management + task.propose(block)`
  - `Continue -> no task update`
- The rendered text contains the limit cue: no start, switch, or confirm in checkout.
- The renderer handles no active task by rendering a no-op oriented checkout rather than failing.

### 2. AppServerClient Notification Support

File: `tests/test_app_server_client.py`

Cases:

- `AppServerClient.request(...)` still ignores interleaved server notifications while waiting for the matching response.
- `AppServerClient.read_notification()` returns a server notification with `method` and no `id`.
- `read_notification()` keeps waiting when it receives unrelated response-shaped messages.
- The daemon can set a distinct client identity without changing launcher input behavior.

### 3. Daemon State

File: `tests/test_stop_task_daemon.py`

Cases:

- Missing daemon state initializes to an empty, valid state for the instance id and main thread id.
- Recording a daemon-origin turn persists `last_origin_turn_id`, `last_stop_tui_turn_id`, and the id in `daemon_origin_turn_ids`.
- `daemon_origin_turn_ids` is capped to the latest 50 ids.
- `is_daemon_origin_turn(turn_id)` returns true only for persisted daemon-origin ids.
- Recording an error persists `last_error.origin_turn_id`, `last_error.message`, and timestamp.

### 4. Daemon Event Filtering

File: `tests/test_stop_task_daemon.py`

Cases:

- Other-thread `turn/completed` notifications are ignored.
- Main-thread `turn/completed(status=failed)` is ignored.
- Main-thread `turn/completed(status=interrupted)` is ignored.
- Main-thread completed notification for a daemon-origin turn is ignored.
- Main-thread `turn/completed(status=completed)` for a non-daemon-origin turn is accepted.

### 5. STOP Prompt Send Path

File: `tests/test_stop_task_daemon.py`

Cases:

- Accepted completed turn causes exactly one JSON-RPC `turn/start`.
- The `turn/start` request uses the same main thread id.
- The prompt starts with the STOP Task TUI, not the input Task TUI.
- The prompt is not wrapped in `[USER INPUT]`.
- The daemon calls the shared snapshot/render path, not a copied task-history reader.
- The returned daemon-origin turn id is recorded.

### 6. STOP Prompt Failure Path

File: `tests/test_stop_task_daemon.py`

Cases:

- If `turn/start` returns a protocol error or active-thread error, the daemon records `last_error`.
- The daemon does not call `turn/steer`.
- The daemon does not retry for the same origin turn.
- A later distinct normal completed turn can still trigger a new STOP Task TUI.

### 7. Daemon Process Lifecycle

File: `tests/test_stop_task_daemon.py` or `tests/test_buddyswitch_launcher.py`

Cases:

- `daemon start` creates the runtime daemon directory, pid file, log file, and state file.
- Starting again while the pid is live is idempotent.
- Starting with a stale pid cleans the stale pid and starts a new daemon.
- `daemon stop` terminates the live daemon and removes or invalidates the pid.
- `daemon status --json` reports pid, live state, log path, state path, and last error when present.

### 8. Instance Lifecycle Integration

File: `tests/test_buddyswitch_launcher.py`

Cases:

- `instance start` starts app-server, persists the main thread id, then starts daemon.
- `instance resume` starts daemon after the resumed main thread id is persisted.
- `instance stop` stops daemon before app-server.
- `instance clear` stops the old daemon and starts a daemon bound to the new main thread id.
- `instance status --json` includes daemon status.
- Human status output includes a concise daemon health line.

### 9. Fake Codex Event Stream Integration

File: `tests/test_buddyswitch_launcher.py`

Cases:

- Fake Codex app-server can emit a `turn/completed(status=completed)` notification to the daemon connection.
- The daemon responds with one `turn/start` containing `[TASK CHECKOUT]`.
- When fake Codex emits completion for the daemon-origin turn id, no second STOP Task TUI is sent.

### 10. Existing Input Path Regression

File: `tests/test_buddyswitch_launcher.py` and `tests/test_task_input_context.py`

Cases:

- `instance input` still sends `task_tui.render_task_tui(...) + [USER INPUT] + raw input`.
- `instance input` still chooses `turn/start` or `turn/steer` according to existing active-turn logic.
- STOP daemon code never routes through `compose_task_context_input(...)`.

## Coverage Matrix

| Requirement | Test Groups |
| --- | --- |
| FR1 | 7, 8 |
| FR2 | 7, 8 |
| FR3 | 8 |
| FR4 | 7, 8 |
| FR5 | 2, 5, 9 |
| FR6 | 4, 8 |
| FR7 | 4, 5, 9 |
| FR8 | 4 |
| FR9 | 4 |
| FR10 | 3, 4, 9 |
| FR11 | 1, 5 |
| FR12 | 5, 10 |
| FR13 | 1 |
| FR14 | 1, 5 |
| FR15 | 5, 10 |
| FR16 | 3, 5, 9 |
| FR17 | 6 |
| FR18 | 10 |

## Verification Commands

Focused verification during development:

```bash
python3 -m pytest tests/test_app_server_client.py -q
python3 -m pytest tests/test_task_input_context.py -q
python3 -m pytest tests/test_stop_task_daemon.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Final verification:

```bash
python3 -m pytest tests -q
```

If the full suite exposes unrelated existing failures, capture the failing tests and rerun the focused STOP daemon tests to prove this task's behavior.

## Review Checklist

- Tests are behavior-driven from the requirements above, not shaped only around implementation details.
- STOP prompt is a real new prompt and does not depend on Codex Stop hook behavior.
- Daemon-origin turn id loop prevention is covered.
- Error handling is intentionally one attempt plus record, with no retry loop.
- Input TUI regression coverage proves the existing input path was not migrated or broken.
- The daemon uses the canonical task snapshot path shared with task tools and input TUI.
