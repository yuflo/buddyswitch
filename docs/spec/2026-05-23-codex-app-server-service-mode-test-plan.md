# Codex App-server Service Mode Test Plan

Date: 2026-05-23

## Test Goal

Prove BuddySwitch buddies are controlled by per-instance Codex app-server services, with the TUI reduced to an attach client.

Tests must start from product behavior and lifecycle requirements. They must not be written only to match an implementation shortcut. Fakes are allowed only at the external Codex boundary, where they emulate the documented app-server protocol that BuddySwitch must speak.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | `instance start --buddy <buddy>` creates a new active service-mode instance and returns without entering TUI. |
| FR2 | Start prepares the same BuddySwitch runtime surface as before: workspace, project worktree, runtime broker, Codex config, buddy AGENTS, runtime skills, and browser cockpit when required. |
| FR3 | Start launches `codex app-server --listen unix://<socket>` under the instance HOME/CODEX_HOME/XDG_CONFIG_HOME and buddy env. |
| FR4 | Start creates or resumes one app-server thread and stores the thread id in `instance.json`. |
| FR5 | `instance input <id> --text <text>` starts a new turn when the thread is idle. |
| FR6 | `instance input <id> --text <text>` steers the current turn when the thread is active and steerable. |
| FR7 | `instance input` does not create duplicate work when a turn is active but non-steerable; it returns a clear failure. |
| FR8 | `instance attach <id>` opens TUI via `codex resume --remote unix://<socket> <thread_id>` and does not stop the service when TUI exits. |
| FR9 | `instance stop <id>` stops app-server, runtime broker, and instance browser, removes transient service markers, and marks the instance inactive. |
| FR10 | `instance status <id>` and `instance list` report service health from app-server state, not launcher marker files. |
| FR11 | `instance delete`, `env reset`, and `data cleanup` block when a target app-server service is live. |
| FR12 | Old public paths are gone: `instance open` fails, and `instance start --buddy <buddy> -- <codex args>` fails. |
| FR13 | Codex app-server protocol handling uses initialize/initialized, JSON-RPC request ids, WebSocket over Unix socket, text frames, timeouts, server errors, and notifications correctly. |
| FR14 | Browser cockpit ownership is explicit: service start can create it; service stop can stop it; stale browser state does not silently block later delete/reset after a clean stop. |
| FR15 | Runtime durable state remains protected: no direct edits to `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` are introduced. |

## Coverage Matrix

| Requirement | Primary Tests |
| --- | --- |
| FR1 | Launcher start lifecycle test with fake app-server. |
| FR2 | Existing runtime surface tests updated from TUI launch assertions to service-mode assertions. |
| FR3 | Fake codex argv/env capture asserts `app-server --listen unix://...` and instance env. |
| FR4 | Fake app-server `thread/start` response persists `thread_id`. |
| FR5 | Fake app-server idle status plus `instance input` asserts `turn/start`. |
| FR6 | Fake app-server active status plus latest in-progress turn asserts `turn/steer` with `expectedTurnId`. |
| FR7 | Fake app-server non-steerable error asserts no second `turn/start` and clear CLI error. |
| FR8 | Attach test asserts `codex resume --remote unix://... <thread_id>` and instance stays active. |
| FR9 | Stop test asserts app-server pid/socket removed, broker stopped, browser stopped, instance inactive. |
| FR10 | Status/list tests read app-server health and ignore obsolete launcher markers. |
| FR11 | Delete/reset/cleanup tests block on active app-server pid/socket. |
| FR12 | Help and command tests assert old open/passthrough paths are removed. |
| FR13 | Dedicated Python unit tests for WebSocket-over-UDS JSON-RPC client. |
| FR14 | Browser stop tests assert pid kill/cleanup and stale endpoint handling. |
| FR15 | Repo consistency test rejects direct runtime object/buddybox writes in new launcher helpers. |

## Test Structure

### 1. App-server Protocol Client Tests

Create:

- `tests/test_app_server_client.py`

Purpose:

- validate BuddySwitch's local client against the Codex app-server wire contract without launching a real model.

Test cases:

1. `test_initialize_sends_client_info_and_initialized_notification`
   - fake UDS WebSocket server accepts handshake
   - assert first request is `initialize`
   - assert next client message is `initialized`
   - assert `clientInfo.name == "buddyswitch_launcher"`
   - assert `capabilities.experimentalApi is true`

2. `test_request_ignores_notifications_until_matching_response`
   - server sends unrelated `thread/status/changed` notification
   - server then sends response for request id
   - client returns the matching result

3. `test_text_input_payload_shape_is_codex_compatible`
   - client sends `turn/start`
   - assert input is:

```json
[{"type":"text","text":"hello","text_elements":[]}]
```

4. `test_turn_steer_requires_expected_turn_id`
   - helper refuses to call `turn/steer` without a non-empty expected turn id

5. `test_server_error_is_reported_without_retrying_mutating_call`
   - server returns JSON-RPC error for `turn/steer`
   - client exits non-zero or raises a typed error
   - assert the request was sent exactly once

6. `test_client_times_out_when_socket_never_responds`
   - fake server accepts connection but sends no response
   - client reports timeout with socket path and method

7. `test_close_ping_and_unexpected_binary_frames_are_safe`
   - ping gets pong or is ignored according to client design
   - close frame produces a controlled unavailable error
   - binary frame is rejected as protocol error

8. `test_long_socket_path_uses_tmp_fallback`
   - path helper returns `/tmp/buddyswitch-app-server-<digest>.sock` when the instance socket path is too long

Expected failure before implementation:

```bash
python3 -m pytest tests/test_app_server_client.py -q
```

Expected: file or helper missing.

### 2. Start Lifecycle Tests

Modify:

- `tests/test_buddyswitch_launcher.py`

Replace TUI-first expectations.

Test cases:

1. `test_start_with_buddy_starts_app_server_service_and_returns`
   - fake `codex` captures argv/env and acts as a minimal app-server over UDS
   - command:

```bash
./buddyswitch-codex instance start --buddy pm
```

   - assert stdout includes instance id, workspace, input, attach, stop, delete commands
   - assert fake codex argv starts with `["app-server", "--listen", "unix://..."]`
   - assert no prompt args are accepted
   - assert `BUDDYSWITCH_ACTIVE_BUDDY`, `BUDDYSWITCH_INSTANCE_ID`, `BUDDYSWITCH_INSTANCE_JSON`, and `BUDDYSWITCH_RUNTIME_BROKER_SOCKET` are present in app-server env
   - assert `instance.json.status == "active"`
   - assert `thread_id`, `app_server_pid`, `app_server_socket`, and `app_server_log` are present
   - assert runtime broker socket is allowed in generated Codex config

2. `test_start_rejects_codex_args_passthrough`
   - command:

```bash
./buddyswitch-codex instance start --buddy pm -- debug prompt-input x
```

   - assert return code `2`
   - assert stderr says start no longer accepts Codex args and to use `instance input`
   - assert no instance root is created

3. `test_start_browser_failure_stops_broker_and_does_not_start_app_server`
   - keep existing browser failure setup
   - assert no app-server pid/socket/log marker
   - assert runtime broker stopped
   - assert instance inactive

4. `test_start_stale_app_server_socket_is_cleaned_before_launch`
   - seed stale socket marker and stale regular file
   - start service
   - assert new fake app-server is launched and marker points to the new socket

### 3. Input Tests

Modify:

- `tests/test_buddyswitch_launcher.py`

Test cases:

1. `test_input_starts_turn_when_thread_idle`
   - seed active instance with healthy fake app-server and `thread_id`
   - fake server responds to `thread/read` with idle status
   - fake server responds to `turn/start`
   - command:

```bash
./buddyswitch-codex instance input inst-pm-service --text "Draft brief"
```

   - assert one `turn/start`, no `turn/steer`
   - assert text payload shape is Codex-compatible
   - assert CLI output includes started turn id

2. `test_input_steers_in_progress_turn`
   - fake server returns active thread status
   - fake `thread/turns/list` returns latest turn with `status == "inProgress"` and id `turn-123`
   - assert `turn/steer.expectedTurnId == "turn-123"`
   - assert no `turn/start`

3. `test_input_reports_non_steerable_active_turn`
   - fake server returns active status and app-server returns non-steerable error for `turn/steer`
   - assert return code non-zero
   - assert no fallback `turn/start`
   - assert stderr suggests retry later or interrupt

4. `test_input_rejects_inactive_or_unhealthy_instance`
   - inactive record or stale socket
   - assert no app-server API call is attempted

5. `test_input_requires_text`
   - no `--text` fails with usage
   - stdin input is not part of this task

### 4. Attach Tests

Modify:

- `tests/test_buddyswitch_launcher.py`

Test cases:

1. `test_attach_invokes_remote_resume_without_stopping_service`
   - seed active instance with `thread_id` and app-server socket
   - fake `codex` captures argv and exits
   - command:

```bash
./buddyswitch-codex instance attach inst-pm-service
```

   - assert argv equals:

```json
["resume", "--remote", "unix://<socket>", "<thread_id>"]
```

   - assert instance remains `active`
   - assert app-server pid/socket marker remains

2. `test_attach_rejects_missing_thread_id`
   - active app-server without thread id in record
   - assert clear repair guidance: stop/delete and start new instance

3. `test_attach_rejects_unhealthy_app_server`
   - stale pid or missing socket
   - assert no TUI launch

### 5. Stop Tests

Modify:

- `tests/test_buddyswitch_launcher.py`
- `tests/test_browser_cockpit_launcher.py` if browser stop is best isolated there

Test cases:

1. `test_stop_active_instance_stops_service_broker_browser_and_marks_inactive`
   - seed fake live app-server pid/socket, runtime broker pid/socket, and browser pid marker
   - command:

```bash
./buddyswitch-codex instance stop inst-pm-service
```

   - assert app-server pid no longer live
   - assert app-server socket and marker removed
   - assert runtime broker pid/socket/marker removed
   - assert browser pid marker removed
   - assert `instance.json.status == "inactive"`

2. `test_stop_is_idempotent_for_stale_service`
   - stale pid, stale socket, active status
   - stop cleans local markers and marks inactive
   - return code `0`

3. `test_stop_rejects_unknown_or_traversal_instance`
   - preserve current path safety behavior

### 6. Active Guard Tests

Modify:

- `tests/test_buddyswitch_launcher.py`
- `tests/test_cleanup_system.py` if cleanup behavior is split there

Test cases:

1. `test_instance_delete_blocks_active_app_server`
   - seed target instance with live app-server pid/socket
   - assert delete returns `3` and does not remove root

2. `test_instance_delete_ignores_obsolete_launcher_marker`
   - seed old launcher marker only
   - assert marker is removed or ignored
   - delete proceeds if no app-server/browser/broker is active

3. `test_env_reset_blocks_active_app_server`
   - active app-server under shared root
   - assert reset returns `3`

4. `test_data_cleanup_blocks_active_app_server_for_buddy`
   - active PM service blocks PM cleanup
   - active PM service does not block Dev-only cleanup unless shared browser or shared state requires all-data block

5. `test_status_reports_unhealthy_stale_service`
   - pid file points to dead pid or socket missing
   - status reports unhealthy and instance is not treated as active for delete after safe cleanup

### 7. Old Path Removal Tests

Modify:

- `tests/test_buddyswitch_launcher.py`

Test cases:

1. `test_instance_open_is_removed`
   - command:

```bash
./buddyswitch-codex instance open inst-pm-example
```

   - assert return code `2`
   - assert stderr says use `instance attach`

2. `test_help_shows_service_mode_commands_only`
   - assert help contains start/input/attach/stop/status/list/delete
   - assert help does not contain `instance open`
   - assert help does not contain `[-- codex args...]`

3. `test_locked_old_open_entrypoint_removed`
   - direct `__locked-instance-open-bootstrap` invocation returns removed/unknown

### 8. Real Smoke Test

Add an optional integration smoke test gated by an environment variable:

```bash
BUDDYSWITCH_REAL_CODEX_APP_SERVER_SMOKE=1 python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_real_codex_app_server_start_input_status_stop_smoke -q
```

Behavior:

- uses installed `codex`
- starts one buddy service with a temporary HOME
- sends a tiny input that should not modify product files
- reads status
- stops service
- asserts no app-server/broker/browser markers remain

This test is not the main CI proof because it depends on local auth and Codex availability. It is the final manual verification gate for this migration.

## Required Verification Commands

Focused during development:

```bash
python3 -m pytest tests/test_app_server_client.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py -q
python3 -m pytest tests/test_browser_cockpit_launcher.py -q
python3 -m pytest tests/test_cleanup_system.py -q
```

Broader before done:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py tests/test_browser_cockpit_launcher.py tests/test_cleanup_system.py tests/test_runtime_broker.py -q
python3 -m pytest tests/test_clean_runtime_environment.py tests/test_repo_consistency.py -q
```

Manual smoke after automated tests:

```bash
tmp_home="$(mktemp -d)"
HOME="${tmp_home}" ./buddyswitch-codex instance start --buddy pm
./buddyswitch-codex instance list
./buddyswitch-codex instance input <instance-id> --text "Say ok and do not edit files."
./buddyswitch-codex instance status <instance-id>
./buddyswitch-codex instance stop <instance-id>
./buddyswitch-codex instance delete <instance-id> --yes
```

## Test Anti-cheat Rules

- Do not assert only that a shell function was called. Assert the user-visible lifecycle result and instance state.
- Do not fake app-server by writing final instance JSON directly. The launcher must still perform the protocol calls.
- Do not use launcher marker files as active service proof.
- Do not let tests pass if both old TUI path and new app-server path coexist.
- Do not skip browser and runtime broker lifecycle assertions in service stop.
- Do not make a test pass by accepting any Codex argv. Assert the exact service-mode command shape.
