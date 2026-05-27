# STOP Task TUI Daemon Development Plan

Date: 2026-05-27

## Goal

Implement the first daemon-backed STOP-stage Task TUI loop for BuddySwitch:

1. run one daemon per buddy instance;
2. listen for completed main-thread turns from the instance Codex app-server;
3. send a real STOP Task TUI prompt through direct app-server `turn/start`;
4. prevent self-triggered STOP prompt loops by recording daemon-origin turn ids;
5. keep the existing input Task TUI path unchanged.

STOP in this document means the BuddySwitch post-turn checkpoint. It is not the Codex Stop hook and not a continuation prompt.

## Core Design

The daemon is a thin observer and prompt sender. It is not a task manager.

Main path:

```text
instance start/resume
  -> app-server running and main_thread_id persisted
  -> daemon starts for this instance
  -> daemon subscribes to app-server notifications for main_thread_id

Codex turn completes
  -> daemon receives turn/completed(status=completed)
  -> daemon filters thread/status/daemon-origin
  -> daemon reads canonical TaskSnapshot
  -> daemon renders STOP Task TUI
  -> daemon sends turn/start(STOP Task TUI)
  -> daemon records returned daemon-origin turn id
```

Codex then decides autonomously:

- if the just-completed work finished the active task, it can use `$task-management` and call `task.propose(type="finish")`;
- if the active task is blocked, it can use `$task-management` and call `task.propose(type="block")`;
- if no task update is needed, it stays silent about task state.

## Non-Goals

- Do not migrate input TUI to daemon in this task.
- Do not introduce a Codex Stop hook.
- Do not add retries.
- Do not add `turn/steer` fallback.
- Do not add daemon-side task completion rules.
- Do not duplicate task history parsing in the daemon.

## Existing Code To Reuse

- `scripts/env/domain/task_management.py`
  - `current_snapshot(...)` is the canonical snapshot function.
- `scripts/env/domain/task_tui.py`
  - current input renderer stays as `render_task_tui(...)`;
  - add a STOP renderer here so input and STOP TUI live together.
- `tools/launcher/task_input_context.py`
  - existing input composer remains unchanged.
- `tools/launcher/app_server.py`
  - reuse `AppServerClient` for WebSocket JSON-RPC.
- `tools/launcher/app_server.sh`
  - existing input shell path remains unchanged.
- `buddyswitch-codex`
  - wire daemon lifecycle into instance start/resume/clear/stop/status.

## Data Contracts

### Daemon State

Path:

```text
<instance_root>/runtime/daemon/state.json
```

Shape:

```json
{
  "instance_id": "inst-...",
  "main_thread_id": "thr_...",
  "daemon_origin_turn_ids": ["turn_..."],
  "last_origin_turn_id": "turn_...",
  "last_stop_tui_turn_id": "turn_...",
  "last_error": {
    "origin_turn_id": "turn_...",
    "message": "...",
    "at": "2026-05-27T12:00:00Z"
  }
}
```

Rules:

- keep the latest 50 daemon-origin turn ids;
- write state atomically with temp file plus replace;
- preserve state across daemon restart;
- record errors without blocking the instance.

### Daemon Runtime Files

Directory:

```text
<instance_root>/runtime/daemon/
```

Files:

- `daemon.pid`
- `daemon.log`
- `state.json`

### STOP Task TUI Prompt

Renderer function:

```python
render_stop_task_tui(snapshot: Mapping[str, Any], previous_turn: Mapping[str, Any]) -> str
```

Target content:

```text
[TASK CHECKOUT]
Previous turn completed: turn_123

Active task
  task-0003-clean-runtime-env
  Status: active
  Progress: task input TUI and task tools are being implemented
  Last event: task.update ...

Decision
  Done      -> $task-management + task.propose(finish)
  Blocked   -> $task-management + task.propose(block)
  Continue  -> no task update

Limits
  No start / switch / confirm in checkout.
  Stay silent if no task update is needed.
```

If there is no active task, render a short checkout that says no active task is present and no task update is needed by default.

### Event Filter

Use this exact first-version behavior:

```text
on turn/completed:
  if thread_id != main_thread_id: pass
  if status != completed: pass
  if turn_id is daemon-origin: pass
  else: send STOP Task TUI via turn/start
```

No retries and no fallback calls.

## Implementation Steps

### 1. Add STOP TUI Renderer

Modify:

- `scripts/env/domain/task_tui.py`
- `tests/test_task_input_context.py` or `tests/test_stop_task_daemon.py`

Work:

1. Add `render_stop_task_tui(snapshot, previous_turn)`.
2. Reuse existing small formatting helpers where possible.
3. Keep `render_task_tui(...)` unchanged for input.
4. Add renderer tests before or alongside implementation.

Acceptance:

- STOP renderer tests pass.
- Existing input renderer tests still pass.

### 2. Extend AppServerClient For Notifications

Modify:

- `tools/launcher/app_server.py`
- `tests/test_app_server_client.py`

Work:

1. Add optional client identity parameters to `AppServerClient` so the daemon can identify itself as `buddyswitch_daemon`.
2. Add `read_notification()` to return server notifications with `method` and no `id`.
3. Keep `request(...)` behavior compatible: interleaved notifications are ignored while waiting for the matching response.

Acceptance:

- Existing app-server client tests pass.
- New notification tests pass.
- Existing launcher input behavior is unchanged.

### 3. Implement Daemon State Helpers

Create:

- `tools/launcher/instance_daemon.py`
- `tests/test_stop_task_daemon.py`

Work:

1. Implement `DaemonState` load/save helpers inside `instance_daemon.py`.
2. Implement daemon runtime path helpers from `instance_root`.
3. Implement origin-turn recording and last-error recording.
4. Implement latest-50 retention for daemon-origin turn ids.

Acceptance:

- State tests pass.
- State writes are atomic.
- State shape matches the contract above.

### 4. Implement Daemon Event Handling

Modify:

- `tools/launcher/instance_daemon.py`
- `tests/test_stop_task_daemon.py`

Work:

1. Implement event parsing for `turn/completed` notifications.
2. Implement the exact event filter.
3. Implement STOP prompt construction through:

```python
snapshot = task_management.current_snapshot(...)
prompt = task_tui.render_stop_task_tui(snapshot, previous_turn)
```

4. Implement direct app-server `turn/start` on the same main thread.
5. Record returned daemon-origin turn id.
6. On `turn/start` error, record error and continue listening.

Acceptance:

- Event filter tests pass.
- Send-path tests pass.
- Failure-path tests pass.

### 5. Implement Daemon CLI

Modify:

- `tools/launcher/instance_daemon.py`

Commands:

```bash
python3 tools/launcher/instance_daemon.py run --instance-json <path>
python3 tools/launcher/instance_daemon.py start --instance-json <path>
python3 tools/launcher/instance_daemon.py stop --instance-json <path>
python3 tools/launcher/instance_daemon.py status --instance-json <path> --json
```

Work:

1. `run` keeps one persistent app-server connection open and listens for notifications.
2. `start` spawns `run` as a background process, writes pid, and opens daemon log.
3. `stop` terminates the pid if live.
4. `status --json` reports pid, live state, log path, state path, and last error.
5. Stale pid files are cleaned on start/status.

Acceptance:

- Process lifecycle tests pass.
- Manual status JSON is readable and deterministic.

### 6. Add Shell Wrapper

Create:

- `tools/launcher/daemon.sh`

Functions:

```bash
buddyswitch_daemon_start
buddyswitch_daemon_stop
buddyswitch_daemon_status_json
```

Work:

1. Use `BUDDYSWITCH_INSTANCE_JSON` from the bound instance environment.
2. Call `instance_daemon.py` commands.
3. Return non-zero on failed start.
4. Treat stop as best-effort during cleanup.

Acceptance:

- Shell wrapper can start, stop, and report status for a bound instance in tests.

### 7. Wire Instance Lifecycle

Modify:

- `buddyswitch-codex`

Work:

1. Source `tools/launcher/daemon.sh`.
2. In `start_locked_bootstrap`, start daemon after app-server state and main thread id are persisted.
3. In `instance_resume`, start daemon after resumed app-server state and main thread id are persisted.
4. In `instance_set_inactive_locked`, stop daemon before app-server stop.
5. In `instance_clear`, stop daemon before clearing/replacing the thread, then start daemon after the new main thread id is persisted.
6. In status JSON, include daemon status.
7. In human status, add one concise daemon health line.

Failure handling:

- If daemon start fails during start/resume/clear, fail that command and cleanly stop runtime services started for that command.
- If daemon stop fails during instance stop, continue cleanup and report a warning.

Acceptance:

- Launcher lifecycle tests pass.
- Instance commands stay deterministic.

### 8. Extend Fake Codex For Event Stream Tests

Modify:

- `tests/helpers/fake_codex.py`
- `tests/test_buddyswitch_launcher.py`

Work:

1. Allow fake app-server to emit configured server notifications to the daemon connection.
2. Record daemon `turn/start` calls in the existing calls log.
3. Support a fixture where fake Codex emits:

```json
{
  "method": "turn/completed",
  "params": {
    "thread_id": "thr_main",
    "turn_id": "turn_user_1",
    "status": "completed"
  }
}
```

4. Support a second completion notification for the daemon-origin turn id to verify loop prevention.

Acceptance:

- Integration test proves one user-origin completed turn produces one STOP Task TUI prompt.
- Integration test proves daemon-origin completion produces no second STOP prompt.

### 9. Verify Existing Input Path

Run and preserve:

```bash
python3 -m pytest tests/test_task_input_context.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Check:

- `instance input` still wraps raw input with input Task TUI and `[USER INPUT]`.
- daemon STOP prompt is not wrapped with `[USER INPUT]`.
- no launcher path routes STOP prompt through `compose_task_context_input(...)`.

### 10. Final Verification And Review

Run:

```bash
python3 -m pytest tests/test_app_server_client.py -q
python3 -m pytest tests/test_task_input_context.py -q
python3 -m pytest tests/test_stop_task_daemon.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py -q
python3 -m pytest tests -q
```

Review:

1. Daemon is a thin observer and prompt sender.
2. STOP TUI uses canonical task snapshot.
3. Input TUI remains unchanged.
4. Loop prevention is turn-id based.
5. Failure handling is one attempt plus record.
6. Lifecycle wiring is clear and local.
7. No speculative framework or broad abstraction was added.

## Development Order

Use this sequence:

1. Renderer tests and `render_stop_task_tui`.
2. AppServerClient notification tests and implementation.
3. Daemon state tests and implementation.
4. Daemon event handling tests and implementation.
5. Daemon CLI lifecycle tests and implementation.
6. Launcher lifecycle integration tests and wiring.
7. Fake Codex event stream integration tests.
8. Full verification and review.

Do not start by wiring launcher lifecycle before the daemon behavior has focused tests.

## Expected Files Changed

Likely new files:

- `tools/launcher/instance_daemon.py`
- `tools/launcher/daemon.sh`
- `tests/test_stop_task_daemon.py`

Likely modified files:

- `scripts/env/domain/task_tui.py`
- `tools/launcher/app_server.py`
- `buddyswitch-codex`
- `tests/test_app_server_client.py`
- `tests/test_task_input_context.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/helpers/fake_codex.py`

## Plan Review

This plan follows the forward path:

- it solves the current STOP-stage bottleneck directly;
- it does not move input TUI in this version;
- it reuses existing snapshot and app-server protocol code;
- it avoids gate, retry, and hook complexity;
- it defines test coverage before implementation;
- it leaves Codex as the task decision-maker instead of moving task judgment into daemon.
