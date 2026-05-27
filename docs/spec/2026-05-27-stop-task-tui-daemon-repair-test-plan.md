# STOP Task TUI Daemon Repair Test Plan

Date: 2026-05-27

## Objective

Verify the repaired STOP Task TUI daemon path end to end:

1. the launcher owns daemon lifecycle for each buddy instance;
2. daemon startup is only successful after the daemon connects to app-server, initializes, binds the current main thread, and enters notification listening;
3. daemon idle time is normal and does not stop the service;
4. real Codex `turn/completed` notifications trigger exactly one STOP Task TUI `turn/start` for completed user-origin turns;
5. daemon-origin turns do not trigger another STOP prompt;
6. `instance clear` preserves the newly created thread id but fails closed if the new daemon cannot start or bind.

This plan repairs escaped defects in the first daemon implementation. It does not redesign the task system.

## Confirmed Problems

P1. The daemon exits after the normal 15 second RPC timeout while waiting for notifications.

P2. Tests and fake Codex use a flat `turn/completed` payload, but the real Codex schema is:

```json
{
  "method": "turn/completed",
  "params": {
    "threadId": "thread-main",
    "turn": {
      "id": "turn-user-1",
      "status": "completed"
    }
  }
}
```

P3. Current daemon startup does not prove that the daemon is bound to the instance main thread.

P4. `daemon start` only checks that the process survived for 0.05 seconds.

P5. Main-loop and startup exceptions are not recorded in `runtime/daemon/state.json`.

P6. `instance clear` can leave an active buddy instance without a working daemon if the post-clear daemon start fails.

## Product Decisions

- Launcher owns daemon lifecycle.
- Web API calls launcher commands and does not manage daemon directly.
- Daemon does not poll `instance.json` for thread changes.
- `instance clear` stops the old daemon, creates a new thread, writes the new `thread_id`, and starts a new daemon bound to that new thread.
- If daemon start or binding fails after clear, keep the new `thread_id`, stop the active buddy instance runtime, mark the instance inactive, and return command failure.
- The next `instance resume` uses the preserved new `thread_id`.
- Do not add a background retry loop. A short startup readiness wait is allowed and required.

## Non-Scope

- No input Task TUI migration.
- No Codex Stop hook.
- No hook continuation prompt.
- No `turn/steer` fallback in daemon code.
- No background daemon retry loop.
- No daemon-side task completion rules.
- No duplicated task snapshot or task history parsing.
- No rollback to the old thread after clear creates a new thread.

## Functional Requirements

FR1. A daemon process remains alive across notification idle periods longer than the app-server RPC timeout.

FR2. Daemon event parsing accepts the real Codex `turn/completed` shape: `params.threadId`, `params.turn.id`, and `params.turn.status`.

FR3. Daemon event parsing ignores malformed notifications, other-thread notifications, non-completed turn statuses, and daemon-origin turn ids.

FR4. A completed, non-daemon-origin main-thread turn causes one direct app-server `turn/start` on the same `threadId`.

FR5. The STOP prompt is produced by `task_management.current_snapshot(...)` and `task_tui.render_stop_task_tui(...)`.

FR6. The STOP prompt is not wrapped by the input TUI and never routes through `compose_task_context_input(...)`.

FR7. After successful daemon-origin `turn/start`, the returned turn id is recorded and prevents daemon-origin loops.

FR8. On STOP prompt send failure, the daemon records `last_error`, does not retry, does not steer, and continues listening.

FR9. On daemon startup or fatal main-loop failure, `last_error` records the failure reason with no origin turn id.

FR10. Daemon startup binds the current `main_thread_id` before reporting ready.

FR11. `daemon start` succeeds only when the daemon is ready for the same process id and same main thread id.

FR12. The fake Codex app-server only emits daemon test notifications after the daemon has bound a thread through the real app-server protocol.

FR13. `instance clear` daemon-start failure stops active runtime, marks the instance inactive, preserves the new `thread_id`, and returns failure.

FR14. `instance resume` after the clear failure resumes the preserved new `thread_id`.

FR15. Web clear inherits launcher behavior: if launcher clear fails, web clear fails and does not run initialize.

FR16. Existing input behavior remains unchanged.

## Required Automated Tests

### 1. Real Notification Shape Parser

File: `tests/test_stop_task_daemon.py`

Cases:

- `test_real_completed_main_thread_user_turn_is_accepted`
  - Input notification uses `params.threadId` and nested `params.turn`.
  - Expected previous turn: `{"thread_id": "thr-main", "turn_id": "turn-user-1", "status": "completed"}`.

- `test_real_completed_other_thread_is_ignored`
  - Same real shape with `threadId: "thr-side"`.
  - Expected: no previous turn.

- `test_real_non_completed_statuses_are_ignored`
  - Real shapes with `status: "failed"`, `"interrupted"`, and `"inProgress"`.
  - Expected: no previous turn.

- `test_real_daemon_origin_turn_is_ignored`
  - State already records `turn-daemon-1`.
  - Real notification has `params.turn.id: "turn-daemon-1"`.
  - Expected: no previous turn.

Flat notification fixtures must be removed from the daemon main-path tests. The repaired behavior is judged by real nested Codex notification fixtures.

### 2. STOP Prompt Send Path With Real Notification

File: `tests/test_stop_task_daemon.py`

Cases:

- `test_real_completed_turn_sends_one_stop_prompt`
  - Feed a real-shape notification into `handle_notification(...)`.
  - Fake client records one `turn/start`.
  - Request params use `threadId: "thr-main"` and permissions `buddyswitch-runtime`.
  - Prompt starts with `[TASK CHECKOUT]`.
  - Prompt does not contain `[TASK CONTEXT]` or `[USER INPUT]`.
  - Snapshot/render call sequence is `current_snapshot(...)` then `render_stop_task_tui(...)`.
  - Returned daemon-origin turn id is persisted.

- `test_turn_start_failure_records_error_without_retry_or_steer`
  - Real-shape notification.
  - Fake client raises `AppServerRequestError`.
  - Expected one `turn/start`, zero `turn/steer`, no retry for the same origin turn, and `last_error.origin_turn_id == "turn-user-1"`.
  - A later distinct real completed turn still triggers a new STOP prompt.

### 3. Daemon Thread Binding

File: `tests/test_stop_task_daemon.py`

Cases:

- `test_bind_main_thread_uses_thread_resume_for_current_instance_thread`
  - Daemon context has `thread_id: "thr-main"` and `workspace_dir`.
  - Fake app-server client records a `thread/resume` request before readiness.
  - Request contains:
    - `threadId: "thr-main"`
    - `cwd` equal to instance `workspace_dir`
    - `runtimeWorkspaceRoots` containing instance workspace and shared project workspace
    - `permissions: "buddyswitch-runtime"`
    - `excludeTurns: True`
  - Response thread id must match `thr-main`.

- `test_bind_main_thread_fails_on_wrong_resumed_thread_id`
  - Fake response returns `thread.id: "thr-other"`.
  - Expected: daemon startup fails and records `last_error`.

- `test_bind_main_thread_fails_on_thread_resume_error`
  - Fake client raises `AppServerRequestError("thread/resume", ...)`.
  - Expected: daemon startup fails and records `last_error`.

### 4. Daemon Idle Listening

File: `tests/test_stop_task_daemon.py`

Cases:

- `test_run_daemon_continues_after_notification_idle_timeout`
  - Fake daemon client returns `AppServerTimeoutError` from `read_notification()` once, then returns a real completed notification, then stops via a controlled test sentinel.
  - Expected: timeout is treated as idle, the later notification is processed, and no `last_error` is written for the idle timeout.

- `test_run_daemon_records_fatal_app_server_error`
  - Fake daemon client raises `AppServerUnavailableError` after readiness.
  - Expected: daemon exits nonzero and `last_error.origin_turn_id is None`.

- `test_run_daemon_records_notification_handler_exception_and_continues`
  - Fake renderer raises for one real completed notification.
  - Later notification succeeds.
  - Expected: `last_error.origin_turn_id` is the failed user turn id, daemon continues, and later STOP prompt is sent.

### 5. Daemon Start Readiness

File: `tests/test_stop_task_daemon.py`

Cases:

- `test_start_waits_for_ready_state_before_success`
  - Fake process pid is live.
  - Simulate child writing ready state with matching pid and main thread id.
  - Expected: `start_daemon(...)` returns `live: true`, `ready: true`, and matching pid.

- `test_start_fails_when_process_exits_before_ready`
  - Fake process exits before ready state.
  - Expected: pid file removed, command raises, `last_error` available in state if child wrote it.

- `test_start_fails_when_ready_times_out`
  - Fake process remains live but never writes matching ready state.
  - Expected: process is terminated, pid file removed, and start fails.

- `test_start_replaces_live_unready_pid`
  - Existing pid is live but state is not ready for that pid/main thread.
  - Expected: old daemon is stopped and a new daemon is started.

- `test_status_reports_ready_and_last_error`
  - Status JSON includes `live`, `pid`, `ready`, `ready_main_thread_id`, `log_path`, `state_path`, and `last_error`.

### 6. Fake Codex Event Stream Integration

File: `tests/helpers/fake_codex.py`, `tests/test_buddyswitch_launcher.py`

Cases:

- `test_fake_codex_requires_daemon_thread_resume_before_notifications`
  - Fake Codex records daemon `thread/resume`.
  - Configured daemon notifications are emitted only after that request succeeds.
  - Expected call order: daemon `initialize`, `initialized`, `thread/resume`, then daemon receives notifications.

- `test_fake_codex_real_completed_event_triggers_one_stop_task_tui_prompt`
  - Configured notification uses real Codex shape.
  - Daemon responds with one `turn/start` containing `[TASK CHECKOUT]`.
  - Prompt does not contain `[USER INPUT]`.

- `test_daemon_origin_completion_real_shape_does_not_loop`
  - Fake emits a real-shape completion for the daemon-origin turn id returned by `turn/start`.
  - Expected exactly one daemon `turn/start` total.

- `test_daemon_ignores_other_thread_real_completion_in_fake_codex`
  - Fake emits one other-thread completion and one main-thread completion.
  - Expected exactly one STOP prompt for the main-thread completion.

### 7. Launcher Lifecycle Readiness

File: `tests/test_buddyswitch_launcher.py`

Cases:

- `test_start_with_buddy_starts_ready_daemon_for_main_thread`
  - `instance start` succeeds.
  - Daemon state has matching `main_thread_id`.
  - Daemon ready state matches pid and main thread id.
  - Fake calls include daemon `thread/resume`.

- `test_instance_resume_starts_ready_daemon_for_original_thread`
  - Stop instance, then resume.
  - Daemon ready state matches the preserved thread id.
  - Fake calls include `thread/resume` for the daemon.

- `test_clear_restarts_ready_daemon_for_new_main_thread`
  - Clear returns new thread id.
  - Daemon ready state matches the new thread id.
  - Old daemon pid is no longer live.

- `test_clear_daemon_start_failure_preserves_new_thread_and_stops_runtime`
  - Configure fake Codex so daemon `thread/resume` fails after clear creates `thread-cleared`.
  - Expected:
    - clear command returns nonzero;
    - instance record `thread_id == "thread-cleared"`;
    - instance record `status == "inactive"`;
    - app-server pid/socket/log fields are cleared;
    - app-server is not healthy;
    - daemon is not live.

- `test_resume_after_clear_daemon_failure_uses_new_thread`
  - Continue from the previous state.
  - Remove the fake daemon failure.
  - Run `instance resume`.
  - Expected daemon and app-server bind/resume `thread-cleared`.

- `test_active_runtime_not_left_without_daemon_when_daemon_start_fails`
  - Any launcher path that reports daemon start failure must not leave status active with app-server healthy and daemon not ready.

### 8. Web Clear Inherits Launcher Failure

File: `tests/test_web_management.py`

Cases:

- `test_clear_route_returns_command_failure_when_launcher_clear_fails`
  - Fake command runner returns nonzero for `instance clear <id> --json`.
  - Expected API error code `COMMAND_FAILED`.
  - Expected no later `instance input <id> --text ...` initialization command.

- `test_clear_route_initializes_only_after_successful_launcher_clear`
  - Existing success behavior remains: web clear runs launcher clear first, then initialize.

### 9. Input Path Regression

Files: `tests/test_task_input_context.py`, `tests/test_buddyswitch_launcher.py`

Cases:

- Existing input tests continue to prove `[TASK CONTEXT]`, `[USER INPUT]`, and raw user text ordering.
- STOP daemon tests assert no call to `compose_task_context_input(...)`.
- Daemon code does not introduce `turn/steer`.

## Coverage Matrix

| Finding | Covered by |
| --- | --- |
| P1 idle timeout exits daemon | Test groups 4, 5, 6 |
| P2 real protocol shape mismatch | Test groups 1, 2, 6 |
| P3 unproven main-thread binding | Test groups 3, 5, 6, 7 |
| P4 shallow startup health check | Test groups 5, 7 |
| P5 missing runtime error state | Test groups 2, 3, 4, 5 |
| P6 clear failure leaves broken active runtime | Test groups 7, 8 |

## Verification Commands

Focused loop:

```bash
python3 -m pytest tests/test_stop_task_daemon.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py -q
python3 -m pytest tests/test_web_management.py -q
python3 -m pytest tests/test_task_input_context.py -q
```

Final verification:

```bash
python3 -m pytest tests -q
```

## Review Checklist

- Every completed main-thread STOP trigger test uses the real nested Codex notification shape.
- Fake Codex does not emit daemon notifications before daemon thread binding.
- Daemon start success means ready, not merely process-live.
- `instance clear` failure preserves the new thread id and leaves the buddy instance inactive.
- No launcher or daemon background retry loop is introduced.
- Input TUI path remains unchanged.
- Daemon remains a thin observer and prompt sender.
