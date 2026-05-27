# Launcher Thread Bootstrap Test Plan

Date: 2026-05-27

## Objective

Verify that BuddySwitch launcher, not Web API, owns new main-thread rollout bootstrap for service-mode buddies.

The required product behavior is:

1. `instance start` creates a Codex main thread and immediately materializes its rollout through Codex `thread/inject_items`.
2. `instance clear` creates a new main thread and materializes that new thread before starting a daemon for it.
3. daemon startup still proves main-thread binding with `thread/resume`.
4. Web create/clear no longer sends a fixed init prompt and no longer exposes an initialize retry surface.
5. empty-rollout threads are no longer created by the normal launcher start/clear path.

This moves the Stage 2 daemon/co-work control path in `docs/memo/2026-05-23-cowork-forward-stages.md` forward without adding a compatibility layer around the old Web-only init workaround.

## Current Code Facts

- `buddyswitch-codex` currently runs `thread/start`, writes the `thread_id`, then starts the daemon.
- `tools/launcher/instance_daemon.py` currently uses `thread/resume` as the daemon bind/ready handshake.
- `tools/launcher/app_server.py` already has a low-level `thread_inject_items(...)` helper, but no launcher bootstrap command uses it for the main thread.
- `tools/launcher/web_management.py` currently owns `INITIALIZE_THREAD_PROMPT`, runs `instance input ... --text <fixed prompt>` after Web create/clear, and exposes `POST /api/instances/<id>/initialize`.
- `tools/launcher/assets/web-management` currently exposes a Retry Initialize action.
- The local Codex app-server contract supports `thread/inject_items`; upstream docs state injected items are persisted to rollout and included in later model requests.

## Functional Requirements

FR1. A newly started BuddySwitch instance has a materialized main-thread rollout before daemon start is considered successful.

FR2. A cleared instance has a materialized new main-thread rollout before the replacement daemon starts.

FR3. The bootstrap uses Codex `thread/inject_items`, not `turn/start`, `instance input`, `turn/steer`, direct JSONL writes, or Web API orchestration.

FR4. The injected item is a minimal internal assistant message with `output_text`; it is not a user message and not an instruction prompt.

FR5. Daemon startup still uses `thread/resume` after bootstrap and reports ready only after binding the same main thread.

FR6. If bootstrap fails during `instance start`, the command fails closed and does not leave an active app-server/browser/runtime-broker/daemon runtime.

FR7. If bootstrap fails during `instance clear`, the new `thread_id` is preserved, active runtime is stopped, the instance is marked inactive, and the command fails.

FR8. If daemon bind/start fails after successful clear bootstrap, the new `thread_id` is preserved, active runtime is stopped, and later `instance resume` uses the new thread.

FR9. Web create delegates to launcher `instance start --json` and does not send an init prompt.

FR10. Web clear delegates to launcher `instance clear <id> --json` and does not send an init prompt.

FR11. The Web initialize retry route and Retry Initialize UI action are removed.

FR12. Normal Web input still sends only user-provided text through `instance input`.

FR13. Existing STOP Task TUI daemon behavior remains unchanged: daemon is observer + prompt sender, STOP prompt uses real main-thread `turn/start`, and daemon-origin turn ids prevent loops.

FR14. Existing input TUI/context behavior remains unchanged.

FR15. Historical stopped empty-rollout instances are not silently repaired by resume; resume still uses `thread/resume` and reports the Codex error when no rollout exists.

## Non-Scope

- No input TUI migration.
- No Codex Stop hook.
- No hook continuation.
- No daemon-side task judgment.
- No background retry loop.
- No daemon polling `instance.json` for thread changes.
- No `turn/start` init prompt.
- No `turn/steer` fallback.
- No side conversation substitute.
- No direct rollout JSONL or sqlite writes.
- No old-thread rollback after clear.

## Coverage Matrix

| Requirement | Primary Tests |
| --- | --- |
| FR1 | `test_start_bootstraps_main_thread_rollout_before_daemon_resume` |
| FR2 | `test_clear_bootstraps_new_thread_before_daemon_resume` |
| FR3 | `test_start_bootstrap_uses_inject_items_not_turn_start` |
| FR4 | `test_thread_bootstrap_marker_is_minimal_assistant_output_text` |
| FR5 | existing daemon ready tests plus launcher call-order assertions |
| FR6 | `test_start_bootstrap_failure_fails_closed_without_ready_daemon` |
| FR7 | `test_clear_bootstrap_failure_preserves_new_thread_and_stops_runtime` |
| FR8 | existing clear daemon failure tests updated for bootstrap materialization |
| FR9 | `test_create_instance_delegates_to_launcher_start_without_initialize_input` |
| FR10 | `test_clear_route_delegates_to_launcher_clear_without_initialize_input` |
| FR11 | `test_initialize_route_is_removed`, UI state tests, static review gate |
| FR12 | existing Web input tests plus fixed-prompt absence check |
| FR13 | existing `tests/test_stop_task_daemon.py` and launcher daemon integration tests |
| FR14 | existing `tests/test_task_input_context.py` and input launcher tests |
| FR15 | `test_instance_resume_reports_no_rollout_for_unmaterialized_legacy_thread` |

## Required Automated Tests

### 1. App-server Bootstrap Helper

File: `tests/test_app_server_client.py`

Cases:

- `test_thread_bootstrap_rollout_injects_minimal_marker`
  - Use `FakeUnixWebSocketServer`.
  - Call the new app-server helper for `thread-1`.
  - Expected RPC sequence: `initialize`, `initialized`, `thread/inject_items`.
  - Expected params:
    - `threadId == "thread-1"`
    - exactly one item
    - item `type == "message"`
    - item `role == "assistant"`
    - content has one `{"type": "output_text", "text": "[BuddySwitch internal bootstrap marker]"}` entry
  - Expected no `turn/start`.

- `test_thread_bootstrap_rollout_propagates_inject_items_error`
  - Server responds to `thread/inject_items` with a JSON-RPC error.
  - Expected helper raises `AppServerRequestError`.
  - Expected no retry.

### 2. Fake Codex Empty-Rollout Model

File: `tests/helpers/fake_codex.py`, `tests/test_buddyswitch_launcher.py`

Cases:

- `test_fake_codex_thread_start_is_unmaterialized_until_inject_or_turn_start`
  - Start fake app-server state with no turns.
  - `thread/start` creates a thread with `rollout_materialized == false`.
  - `thread/resume` for that thread returns `no rollout found for thread id <id>` until materialized.

- `test_fake_codex_inject_items_materializes_target_thread`
  - `thread/inject_items` appends the marker to target thread state.
  - Target thread `rollout_materialized == true`.
  - Subsequent `thread/resume` succeeds.

- `test_fake_codex_turn_start_still_materializes_thread`
  - Existing user input path sends `turn/start`.
  - Target thread becomes materialized, preserving current input/resume behavior.

### 3. Launcher Start Bootstrap

File: `tests/test_buddyswitch_launcher.py`

Cases:

- `test_start_bootstraps_main_thread_rollout_before_daemon_resume`
  - Run `instance start --buddy pm`.
  - Expected fake RPC order for main path:
    - launcher `thread/start`
    - launcher `thread/inject_items`
    - daemon `thread/resume`
  - Expected daemon ready state matches the started `thread_id`.

- `test_start_bootstrap_uses_inject_items_not_turn_start`
  - Run `instance start --buddy pm`.
  - Expected no launcher `turn/start` before daemon startup.
  - Expected no `instance input` command or fixed init prompt appears in calls.

- `test_thread_bootstrap_marker_is_minimal_assistant_output_text`
  - Inspect `thread/inject_items` params.
  - Assert exact item shape and marker text.
  - Assert item role is not `user`.

- `test_start_bootstrap_failure_fails_closed_without_ready_daemon`
  - Configure fake Codex to fail `thread/inject_items`.
  - `instance start --buddy pm --json` returns nonzero.
  - Instance record is inactive if it exists.
  - app-server pid/socket/log fields are cleared.
  - daemon pid is absent or not live.
  - browser and runtime broker are stopped.

### 4. Launcher Clear Bootstrap

File: `tests/test_buddyswitch_launcher.py`

Cases:

- `test_clear_bootstraps_new_thread_before_daemon_resume`
  - Start an instance, then clear it with fake `clear_thread_id == "thread-cleared"`.
  - Expected order for the clear phase:
    - old daemon stop
    - launcher `thread/start` with `sessionStartSource == "clear"`
    - launcher `thread/inject_items` for `thread-cleared`
    - daemon `thread/resume` for `thread-cleared`
  - Expected new daemon ready state matches `thread-cleared`.

- `test_clear_bootstrap_failure_preserves_new_thread_and_stops_runtime`
  - Configure fake Codex to fail `thread/inject_items` during clear.
  - Expected command failure.
  - Expected `instance.json.thread_id == "thread-cleared"`.
  - Expected status `inactive`.
  - Expected app-server fields cleared and daemon not live.

- `test_clear_daemon_failure_after_bootstrap_preserves_materialized_new_thread`
  - Configure fake Codex so `thread/inject_items` succeeds but daemon `thread/resume` fails.
  - Expected clear fails closed and preserves `thread-cleared`.
  - Remove the fake daemon resume failure.
  - `instance resume <id> --json` succeeds and uses `thread-cleared`.

### 5. Resume Boundaries

File: `tests/test_buddyswitch_launcher.py`

Cases:

- `test_instance_resume_does_not_bootstrap_existing_thread`
  - Stop a materialized instance and resume it.
  - Expected `thread/resume` is used.
  - Expected no `thread/inject_items` during resume.

- `test_instance_resume_reports_no_rollout_for_unmaterialized_legacy_thread`
  - Seed an inactive instance record with a thread id that fake Codex marks unmaterialized.
  - Run `instance resume <id> --json`.
  - Expected nonzero result and stderr includes `no rollout found`.
  - Expected no bootstrap fallback is attempted.

### 6. Web API Removal Of Init Workaround

File: `tests/test_web_management.py`

Cases:

- `test_create_instance_delegates_to_launcher_start_without_initialize_input`
  - Ordered runner receives:
    - `["instance", "buddies", "--json"]`
    - `["instance", "start", "--buddy", "pm", "--json"]`
    - `["instance", "status", "inst-pm-demo", "--json"]`
  - Expected no `["instance", "input", ..., INITIALIZE_THREAD_PROMPT, ...]`.
  - Response includes `ok: true`, `instance_id`, and refreshed instance status.

- `test_create_instance_returns_launcher_start_error_without_initialize_retry`
  - Launcher start returns command failure.
  - Expected Web returns structured `COMMAND_FAILED`.
  - Expected no input/initialize command is run.

- `test_clear_route_delegates_to_launcher_clear_without_initialize_input`
  - Ordered runner receives:
    - `["instance", "clear", "inst-pm-demo", "--json"]`
    - `["instance", "status", "inst-pm-demo", "--json"]`
  - Expected no input command.
  - Response preserves `previous_thread_id` and `thread_id`.

- `test_initialize_route_is_removed`
  - `POST /api/instances/inst-pm-demo/initialize` returns 404 `NOT_FOUND`.
  - Expected no launcher command is run.

- `test_user_input_does_not_use_internal_bootstrap_marker`
  - Normal Web input sends the user text exactly as supplied.
  - Expected no fixed init prompt or bootstrap marker in runner calls.

### 7. Web UI Removal

File: `tests/web_management_ui_state.test.js`, `tools/launcher/assets/web-management/index.html`, `tools/launcher/assets/web-management/app.js`

Cases:

- Update action-state expectations so returned state no longer has `canInitialize`.
- `active healthy idle` instances allow send/stop/clear, not initialize.
- `inactive` instances still allow resume/delete.
- Static UI review verifies no `initialize-button`, `Retry Initialize`, `canInitialize`, or `/initialize` fetch path remains.

### 8. Regression Suites

Run after implementation:

```bash
python3 -m pytest tests/test_app_server_client.py -q
python3 -m pytest tests/test_stop_task_daemon.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py -q
python3 -m pytest tests/test_web_management.py -q
node tests/web_management_ui_state.test.js
python3 -m pytest tests -q
```

## Review Gates

After all tests pass, run:

```bash
rg -n 'INITIALIZE_THREAD_PROMPT|Initialize this BuddySwitch thread|Reply exactly: ready|Retry Initialize|canInitialize|/initialize' tools tests
rg -n 'thread/inject_items|thread-bootstrap|internal bootstrap marker' tools tests
rg -n 'turn/start|instance input' tools/launcher/web_management.py tests/test_web_management.py
```

Expected:

- First command finds no matches.
- Second command finds the launcher bootstrap helper, side-conversation existing use, and tests.
- Third command finds only normal user input behavior, not Web init behavior.

Manual review must confirm:

- bootstrap is in launcher start/clear, not Web API.
- daemon remains observer + prompt sender.
- STOP Task TUI still uses real main-thread `turn/start`.
- input TUI path remains unchanged.
- no retry loop, daemon polling, gate, fallback, side workaround, or direct rollout writer was added.
