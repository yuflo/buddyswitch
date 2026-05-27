# STOP Task TUI Daemon Repair Development Plan

> **For agentic workers:** Use test-driven development. Add or update tests first, verify they fail for the current implementation, implement the smallest direct repair, and run the focused tests after each task.

**Goal:** Repair the STOP Task TUI daemon so it stays alive, binds the active main thread, handles real Codex completion notifications, reports startup health accurately, records errors, and fails `instance clear` closed without losing the newly created thread id.

**Architecture:** Launcher owns daemon lifecycle. The daemon is a long-running app-server observer: it connects, initializes, rejoins the current main thread with `thread/resume`, marks itself ready, listens for notifications, and sends STOP prompts through `turn/start`. The daemon never manages task state and never performs thread-switch discovery.

**Tech Stack:** Python standard library, existing `tools/launcher/app_server.py` WebSocket JSON-RPC client, shell launcher scripts, fake Codex test server, pytest/unittest.

---

## Current Code Facts

- `tools/launcher/instance_daemon.py` owns daemon state, event parsing, STOP prompt send, process start/stop/status, and run loop.
- `run_daemon()` currently calls `client.read_notification()` forever but does not catch idle `AppServerTimeoutError`.
- `completed_turn_for_stop_tui(...)` currently reads flat notification fields.
- `start_daemon(...)` currently only waits `DAEMON_POLL_SECONDS` and checks `process.poll()`.
- `tools/launcher/app_server.py` already has `AppServerClient.request(...)`, `read_notification()`, and `thread_resume(...)`.
- `tools/launcher/app_server.sh` already sends launcher resume with `thread/resume`, `cwd`, `runtimeWorkspaceRoots`, `permissions`, and `excludeTurns`.
- `tools/launcher/daemon.sh` exposes daemon start/stop/status to `buddyswitch-codex`.
- `buddyswitch-codex` starts daemon after start/resume/clear, stops daemon before stop/clear, and reports daemon status.
- `tools/launcher/web_management.py` calls launcher `instance clear <id> --json` and only initializes after that command succeeds.
- `tests/helpers/fake_codex.py` can record RPC calls and return configured errors, but currently emits daemon notifications after `initialized`, not after thread binding.

## Design Decisions

1. Real Codex notification shape is the source of truth.
   - Accepted completion fields: `params.threadId`, `params.turn.id`, `params.turn.status`.
   - Tests and fake Codex must use that shape for main-path behavior.

2. Daemon binding uses app-server `thread/resume`.
   - The daemon sends `thread/resume` for the current `main_thread_id` before marking ready.
   - Params match launcher resume semantics: `threadId`, `cwd`, `runtimeWorkspaceRoots`, `permissions`, `excludeTurns: True`.
   - If app-server returns a different thread id, daemon startup fails.

3. Readiness is explicit and local.
   - Daemon writes ready state only after successful app-server initialize and thread binding.
   - `daemon start` waits for ready state matching the child pid and current main thread id.
   - A readiness wait is not a retry loop.

4. Idle timeout is not an error.
   - `AppServerTimeoutError` from `read_notification()` means no notification arrived during the current wait.
   - Daemon continues listening.

5. Fatal errors are visible.
   - Startup and fatal main-loop errors write `last_error` with `origin_turn_id: null`.
   - Per-turn STOP prompt errors write `last_error.origin_turn_id` for that user turn and continue listening.

6. Clear failure fails closed.
   - After clear creates and persists the new thread id, daemon start or bind failure stops the active buddy instance runtime and marks the instance inactive.
   - The new `thread_id` remains in the instance record.
   - The next resume uses that new `thread_id`.

## Files To Modify

- `tools/launcher/instance_daemon.py`
  - Parse real notifications.
  - Add daemon binding.
  - Add ready state helpers.
  - Make idle timeout nonfatal.
  - Record startup/main-loop errors.
  - Strengthen `start_daemon` readiness checking.

- `tools/launcher/daemon.sh`
  - No planned change.

- `buddyswitch-codex`
  - Fail closed when daemon start fails after `instance clear`.
  - Ensure daemon failure does not leave active runtime without a ready daemon.

- `tests/helpers/fake_codex.py`
  - Emit real nested `turn/completed` notifications.
  - Emit daemon notifications only after daemon `thread/resume`.
  - Emit daemon-origin completion using real nested shape.

- `tests/test_stop_task_daemon.py`
  - Add focused unit tests for real notification shape, binding, idle listening, readiness, and error recording.

- `tests/test_buddyswitch_launcher.py`
  - Add lifecycle integration tests for ready daemon, fake Codex real schema, clear failure, and resume after clear failure.

- `tests/test_web_management.py`
  - Add web clear failure inheritance test.

- `tests/test_task_input_context.py`
  - Run existing input/STOP renderer tests unchanged; update only if the repair reveals missing regression coverage.

## Implementation Tasks

### Task 1: Replace Flat Completion Tests With Real Codex Shape

**Files:**
- Modify: `tests/test_stop_task_daemon.py`

- [ ] Add a local helper that builds real Codex completion notifications:

```python
def _completed(
    self,
    *,
    thread_id: str = "thr-main",
    turn_id: str = "turn-user-1",
    status: str = "completed",
) -> dict[str, object]:
    return {
        "method": "turn/completed",
        "params": {
            "threadId": thread_id,
            "turn": {
                "id": turn_id,
                "items": [],
                "itemsView": "summary",
                "status": status,
                "error": None,
                "startedAt": 0,
                "completedAt": 1 if status != "inProgress" else None,
                "durationMs": 1 if status != "inProgress" else None,
            },
        },
    }
```

- [ ] Update all daemon filter and send-path tests to use the helper.

- [ ] Add explicit cases for `failed`, `interrupted`, and `inProgress`.

- [ ] Run:

```bash
python3 -m pytest tests/test_stop_task_daemon.py -q
```

Expected before implementation: real-shape accepted-path tests fail because the daemon reads flat fields.

### Task 2: Parse Real `turn/completed` Notifications

**Files:**
- Modify: `tools/launcher/instance_daemon.py`

- [ ] Update `completed_turn_for_stop_tui(...)` to read:
  - `params["threadId"]`
  - `params["turn"]["id"]`
  - `params["turn"]["status"]`

- [ ] Return the same internal previous-turn shape already used by STOP rendering:

```python
{"thread_id": thread_id, "turn_id": turn_id, "status": status}
```

- [ ] Do not add task logic or fallback event types.

- [ ] Run:

```bash
python3 -m pytest tests/test_stop_task_daemon.py -q
```

Expected after implementation: parser and send-path tests pass up to the not-yet-added binding/readiness tests.

### Task 3: Add Daemon Thread Binding Tests

**Files:**
- Modify: `tests/test_stop_task_daemon.py`

- [ ] Extend daemon test instance payloads with a real workspace path. Keep using the current instance record shape; do not require `project_workspace_dir` in the instance JSON.

- [ ] Add a fake app-server client for startup binding:

```python
class FakeBindingClient:
    def __init__(self, *, result: dict[str, object] | None = None, error: BaseException | None = None) -> None:
        self.result = result or {"thread": {"id": "thr-main"}}
        self.error = error
        self.requests: list[dict[str, object]] = []

    def request(self, method: str, params: dict[str, object] | None) -> dict[str, object]:
        self.requests.append({"method": method, "params": params or {}})
        if self.error is not None:
            raise self.error
        return self.result
```

- [ ] Add tests named:
  - `test_bind_main_thread_uses_thread_resume_for_current_instance_thread`
  - `test_bind_main_thread_fails_on_wrong_resumed_thread_id`
  - `test_bind_main_thread_fails_on_thread_resume_error`

- [ ] Run:

```bash
python3 -m pytest tests/test_stop_task_daemon.py -q
```

Expected before implementation: binding tests fail because no binding helper exists.

### Task 4: Implement Daemon Thread Binding

**Files:**
- Modify: `tools/launcher/instance_daemon.py`

- [ ] Add `workspace_dir` and `project_workspace_dir` to `DaemonContext`.

- [ ] In `load_daemon_context(...)`:
  - read `workspace_dir` from instance JSON;
  - compute shared project workspace as `<shared_root>/project/workspace`, where `shared_root` is `instance_root.parent.parent`;
  - fail if `workspace_dir` is missing.

- [ ] Add `bind_main_thread(context, client) -> None` that calls:

```python
client.request(
    "thread/resume",
    {
        "threadId": context.main_thread_id,
        "cwd": str(context.workspace_dir),
        "runtimeWorkspaceRoots": [
            str(context.workspace_dir),
            str(context.project_workspace_dir),
        ],
        "permissions": context.permissions,
        "excludeTurns": True,
    },
)
```

- [ ] Validate returned `result["thread"]["id"] == context.main_thread_id`.

- [ ] Raise `AppServerProtocolError` if the response does not contain the expected thread id.

- [ ] Run:

```bash
python3 -m pytest tests/test_stop_task_daemon.py -q
```

Expected after implementation: binding tests pass.

### Task 5: Add Ready State Tests

**Files:**
- Modify: `tests/test_stop_task_daemon.py`

- [ ] Add state tests for recording ready state:
  - ready pid is persisted;
  - ready main thread id is persisted;
  - ready state for another pid or thread is not accepted as current readiness.

- [ ] Add lifecycle tests:
  - `test_start_waits_for_ready_state_before_success`
  - `test_start_fails_when_ready_times_out`
  - `test_start_replaces_live_unready_pid`
  - `test_status_reports_ready_and_last_error`

- [ ] Keep tests deterministic by patching sleep/time or readiness polling helpers; do not make tests wait real seconds.

- [ ] Run:

```bash
python3 -m pytest tests/test_stop_task_daemon.py -q
```

Expected before implementation: readiness tests fail.

### Task 6: Implement Ready State And Stronger `daemon start`

**Files:**
- Modify: `tools/launcher/instance_daemon.py`

- [ ] Add constants:

```python
DAEMON_READY_TIMEOUT_SECONDS = 5.0
DAEMON_READY_POLL_SECONDS = 0.05
```

- [ ] Extend `DaemonState` with:
  - `record_ready(pid: int, main_thread_id: str) -> None`
  - `ready_for(pid: int, main_thread_id: str) -> bool`

- [ ] Store ready state in `state.json` as:

```json
{
  "ready": {
    "pid": 12345,
    "main_thread_id": "thr-main",
    "at": "2026-05-27T12:00:00Z"
  }
}
```

- [ ] Include ready fields in `daemon_status(...)`:
  - `ready`
  - `ready_main_thread_id`

- [ ] Update `run_daemon(...)`:
  - create client;
  - bind main thread;
  - record ready for `os.getpid()`;
  - enter notification loop.

- [ ] Update `start_daemon(...)`:
  - if an existing pid is live and ready for current main thread, return idempotent success;
  - if an existing pid is live but not ready, stop it and start a fresh daemon;
  - after spawning, wait until state reports ready for the child pid and current main thread id;
  - if the child exits before ready, remove pid and fail;
  - if ready times out, terminate the child, remove pid, and fail.

- [ ] Run:

```bash
python3 -m pytest tests/test_stop_task_daemon.py -q
```

Expected after implementation: readiness tests pass.

### Task 7: Add Idle And Runtime Error Tests

**Files:**
- Modify: `tests/test_stop_task_daemon.py`

- [ ] Add a run-loop fake client that can return this sequence:
  - idle `AppServerTimeoutError`;
  - real completion notification;
  - controlled sentinel exception to stop the test.

- [ ] Add tests:
  - `test_run_daemon_continues_after_notification_idle_timeout`
  - `test_run_daemon_records_fatal_app_server_error`
  - `test_run_daemon_records_notification_handler_exception_and_continues`

- [ ] Ensure idle timeout does not write `last_error`.

- [ ] Run:

```bash
python3 -m pytest tests/test_stop_task_daemon.py -q
```

Expected before implementation: idle/main-loop tests fail.

### Task 8: Implement Idle Handling And Error Recording

**Files:**
- Modify: `tools/launcher/instance_daemon.py`

- [ ] Change `DaemonState.record_error(...)` to accept `origin_turn_id: str | None`.

- [ ] Add a small helper to extract an origin turn id from a real notification for error reporting.

- [ ] In the notification loop:
  - catch `app_server.AppServerTimeoutError` from `read_notification()` and continue;
  - catch exceptions from `handle_notification(...)`, record `last_error` with the notification turn id when available, and continue;
  - catch fatal app-server/protocol errors around startup or the outer loop, record `last_error` with `origin_turn_id: None`, and return nonzero.

- [ ] Do not retry `turn/start`.

- [ ] Do not add `turn/steer`.

- [ ] Run:

```bash
python3 -m pytest tests/test_stop_task_daemon.py -q
```

Expected after implementation: all focused daemon unit tests pass.

### Task 9: Make Fake Codex Model Real Daemon Binding

**Files:**
- Modify: `tests/helpers/fake_codex.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] Change configured daemon notifications in tests to real nested `turn/completed` shape.

- [ ] In fake Codex, track daemon connection state:
  - daemon client identity comes from `initialize.clientInfo.name == "buddyswitch_daemon"`;
  - daemon is not subscribed on `initialized`;
  - daemon becomes subscribed after successful `thread/resume`;
  - store the subscribed thread id from `thread/resume.params.threadId`.

- [ ] Emit configured daemon notifications only after successful daemon `thread/resume`.

- [ ] Emit daemon-origin completion with real nested shape after daemon `turn/start`.

- [ ] Add launcher integration tests from the test plan group 6.

- [ ] Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_fake_codex_real_completed_event_triggers_one_stop_task_tui_prompt -q
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Expected after implementation: fake Codex proves daemon binding before notifications and STOP prompt loop prevention with real schema.

### Task 10: Add Launcher Clear Failure Tests

**Files:**
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] Add `test_clear_daemon_start_failure_preserves_new_thread_and_stops_runtime`.

- [ ] Configure fake Codex so:
  - clear creates `thread-cleared`;
  - daemon `thread/resume` fails after clear.

- [ ] Assert:
  - clear returns nonzero;
  - instance record keeps `thread_id == "thread-cleared"`;
  - instance record status is `inactive`;
  - app-server pid/socket/log fields are `null`;
  - daemon status is not live.

- [ ] Add `test_resume_after_clear_daemon_failure_uses_new_thread`.

- [ ] Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Expected before implementation: clear failure test fails because current code returns failure without stopping active runtime.

### Task 11: Implement Clear Fail-Closed Behavior

**Files:**
- Modify: `buddyswitch-codex`

- [ ] In `instance_clear()`, keep the existing order:
  - require active service thread;
  - remember previous thread id;
  - stop old daemon;
  - create clear thread through app-server;
  - parse new thread id;
  - write new thread id.

- [ ] Replace the daemon-start failure branch after `buddyswitch_instance_set_thread_id` with fail-closed cleanup:

```bash
if ! buddyswitch_daemon_start >/dev/null; then
  echo "Daemon start failed for ${instance_id}." >&2
  buddyswitch_app_server_stop || true
  buddyswitch_runtime_broker_stop
  buddyswitch_browser_instance_stop "${instance_id}" || true
  buddyswitch_instance_clear_app_server "${instance_id}" "inactive"
  return 1
fi
```

- [ ] Do not write the old thread id back.

- [ ] Do not add retry.

- [ ] Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Expected after implementation: clear failure and resume-after-failure tests pass.

### Task 12: Add Web Clear Failure Test

**Files:**
- Modify: `tests/test_web_management.py`

- [ ] Add `test_clear_route_returns_command_failure_when_launcher_clear_fails`.

- [ ] Use the existing fake runner pattern to return nonzero for `["instance", "clear", instance_id, "--json"]`.

- [ ] Assert:
  - API returns a command failure error;
  - no initialize command is run after failed clear.

- [ ] Run:

```bash
python3 -m pytest tests/test_web_management.py -q
```

Expected after implementation: web behavior remains a wrapper over launcher clear.

### Task 13: Regression Guard For Input Path And Forbidden Complexity

**Files:**
- Modify only tests if a missing regression guard is discovered.

- [ ] Run:

```bash
python3 -m pytest tests/test_task_input_context.py -q
python3 -m pytest tests/test_app_server_client.py -q
```

- [ ] Search for forbidden daemon additions:

```bash
rg -n "turn/steer|retry|Stop hook|hook/completed|compose_task_context_input|render_task_tui" tools/launcher/instance_daemon.py
```

Expected:
  - no `turn/steer` in daemon;
  - no retry loop language or code in daemon;
  - no Stop hook or hook continuation path;
  - no input composer or input TUI renderer in daemon.

### Task 14: Final Verification And Review

**Files:**
- No new implementation files.

- [ ] Run focused suites:

```bash
python3 -m pytest tests/test_stop_task_daemon.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py -q
python3 -m pytest tests/test_web_management.py -q
python3 -m pytest tests/test_task_input_context.py -q
python3 -m pytest tests/test_app_server_client.py -q
```

- [ ] Run full suite:

```bash
python3 -m pytest tests -q
```

- [ ] Review against these required conclusions:
  - input TUI path unchanged;
  - daemon is observer plus prompt sender only;
  - STOP Task TUI is sent through real `turn/start`;
  - daemon uses the canonical task snapshot path;
  - daemon-origin turn id prevents loops;
  - launcher owns lifecycle and clear fail-closed behavior;
  - no gate, hook continuation, retry loop, or `turn/steer` fallback was added.

## Manual Smoke Check

After automated tests pass, run one local product-mode smoke check if the local Codex app-server is available:

```bash
./buddyswitch-codex instance status <instance-id> --json
```

Expected:

- `app_server.healthy == true` for an active instance;
- `daemon.live == true`;
- `daemon.ready == true`;
- daemon log does not show idle timeout exit;
- after a user turn completes, one STOP Task TUI prompt is sent.

If no active instance exists, this smoke check can be skipped after the full automated suite passes.

## Final Acceptance

The repair is complete only when:

- all tests listed above pass;
- `python3 -m pytest tests -q` passes;
- review confirms every finding P1-P6 is covered;
- no new transition workaround or background retry mechanism exists;
- the branch remains isolated in the `clean-runtime-env` worktree.

## Finding Coverage Review

- P1 daemon idle exit is covered by Tasks 7 and 8.
- P2 real protocol shape mismatch is covered by Tasks 1, 2, and 9.
- P3 unproven main-thread binding is covered by Tasks 3, 4, and 9.
- P4 shallow daemon start health check is covered by Tasks 5, 6, and 9.
- P5 missing runtime error state is covered by Tasks 7 and 8.
- P6 clear failure cleanup is covered by Tasks 10, 11, and 12.
