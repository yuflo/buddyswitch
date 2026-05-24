# Buddy Web Management Test Audit

Date: 2026-05-24

## Goal

Before building a web page for buddy management, make the existing BuddySwitch service-mode control path test-bound and green.

The web page should sit on top of the existing launcher/app-server control surface. Therefore the required proof is:

```text
instance start -> status/list -> input -> attach/interrupt -> stop/delete/reset/cleanup guards
```

This document records the tests that must be green first, the tests that are already green and should remain in the gate, and the missing web-specific tests that should be added when the web layer is implemented.

## Current Verification Snapshot

Commands run in this worktree:

```bash
python3 -m pytest tests/test_app_server_client.py -q
```

Result:

```text
9 passed
```

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'start_with_buddy_starts_app_server_service_and_returns or input_ or attach_ or stop_ or status_reports_app_server_health_and_thread_metadata or list_includes_app_server_health_and_thread_id or interrupt_' -q
```

Result:

```text
8 failed, 7 passed, 116 deselected
```

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'instance_delete_blocks_active_app_server or data_cleanup_is_blocked_when_active_app_server_exists or reset_is_blocked_when_active_app_server_exists' -q
```

Result:

```text
3 failed, 128 deselected
```

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_optional_browser_bootstrap_failure_continues_active_instance -q
```

Result:

```text
1 failed
```

```bash
python3 -m pytest tests/test_browser_cockpit_launcher.py tests/test_cleanup_system.py -q
```

Result:

```text
18 passed
```

## Current Non-Green Tests

### P0: App-server Health Reuse After Start

These tests all start a service instance successfully, then a later command sees the app-server as unhealthy or inactive.

Existing failing tests:

- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_status_reports_app_server_health_and_thread_metadata`
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_list_includes_app_server_health_and_thread_id`
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_input_starts_turn_when_thread_idle`
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_input_steers_in_progress_turn`
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_input_reports_non_steerable_active_turn`
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_attach_invokes_remote_resume_without_stopping_service`
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_interrupt_interrupts_active_turn`
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_interrupt_rejects_when_no_active_turn_exists`

Observed failure pattern:

- `input`, `attach`, and `interrupt` return code `3`.
- Error text is `unhealthy or inactive`.
- `status` and `list` report the stored active instance as `app_server.healthy == false`.

Required test proof:

- A started fake app-server remains healthy across a second launcher command.
- `instance status --json` reports `app_server.healthy == true`.
- `instance list` reports `healthy`.
- `instance input` reaches `thread/read`, then `turn/start` or `turn/steer`.
- `instance attach` reaches `codex resume --remote unix://<socket> <thread_id>`.
- `instance interrupt` reaches `thread/turns/list` and `turn/interrupt` when an in-progress turn exists.
- Non-steerable active turns fail at `turn/steer` with a clear retry-or-interrupt message, not at the health gate.
- No-active-turn interrupt failures fail with `no active in-progress turn`, not at the health gate.

### P0: Active App-server Guards

These tests should block destructive operations while an app-server is live. They currently do not block, which matches the same health-detection failure surface.

Existing failing tests:

- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_delete_blocks_active_app_server`
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_data_cleanup_is_blocked_when_active_app_server_exists`
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_reset_is_blocked_when_active_app_server_exists`

Observed failure pattern:

- Expected return code is `3`.
- Actual return code is `0`.
- Delete/reset/cleanup proceed because the active app-server is not counted as active.

Required test proof:

- Active app-server count sees a live service after start.
- `instance delete <id> --yes` refuses to delete the active instance.
- `env reset --yes` refuses to reset while any service is active.
- `data cleanup --all-data --yes --json` refuses cleanup while any service is active.
- Browser markers removed from the test setup must not hide the live app-server guard.

### P1: Optional Browser Failure Start Path

Existing failing test:

- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_optional_browser_bootstrap_failure_continues_active_instance`

Observed failure pattern:

- Expected return code is `0`.
- Actual return code is `255`.

Required test proof:

- For a buddy whose browser cockpit is optional, browser bootstrap failure does not prevent a service-mode instance from becoming active.
- The instance record is active and contains app-server fields.
- Browser-related fields or MCP setup failures are represented as optional capability loss, not service startup failure.
- For a buddy whose browser cockpit is required, the required-browser failure path must still stop runtime broker and avoid launching app-server.

## Existing Green Tests To Keep In The Gate

These tests are not the current blocker, but they protect the web-management foundation and should remain in the focused verification set.

### App-server Protocol Client

Command:

```bash
python3 -m pytest tests/test_app_server_client.py -q
```

Currently green:

- WebSocket-over-Unix-socket handshake
- `initialize` plus `initialized`
- matching JSON-RPC response ids
- notification skipping
- text input payload shape
- `turn/steer` expected turn id validation
- explicit permissions requirement for input
- error/timeout/close behavior covered by the current protocol tests
- long socket path fallback behavior

### Start/Stop And Old Public Path Removal

Existing green tests from the current focused runs:

- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_starts_app_server_service_and_returns`
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_rejects_codex_args_passthrough`
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_is_removed`
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_locked_old_open_entrypoint_removed`
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_stop_active_instance_stops_service_broker_browser_and_marks_inactive`
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_stop_is_idempotent_for_stale_service`

Required continued proof:

- `instance start --buddy <buddy>` starts service mode and returns.
- `instance start --buddy <buddy> -- <codex args>` is rejected.
- `instance open` stays removed.
- Locked old open bootstrap remains removed.
- `instance stop` clears app-server pid/socket/marker and marks inactive.
- Stale service stop remains idempotent.

### Browser And Cleanup Baseline

Command:

```bash
python3 -m pytest tests/test_browser_cockpit_launcher.py tests/test_cleanup_system.py -q
```

Currently green:

- Browser cockpit status/ensure helpers.
- Browser endpoint readiness behavior.
- Browser stop helper behavior.
- Cleanup system baseline behavior outside the active app-server guard path.

## Missing Or Under-Specified Tests

This audit found existing failing tests for the CLI service-mode path. It also found several web-management-specific tests that do not exist yet because the web layer has not been built.

### P1: Web API Shell

Add when the web service is introduced.

Required tests:

- `GET /api/buddies` returns manifest buddies without starting any instance.
- `GET /api/instances` returns the same rows as `instance list`, including `app_server_health`, `thread_id`, `browser_port`, and `workspace_dir`.
- `GET /api/instances/<id>/status` returns the same JSON shape as `instance status <id> --json`.
- `POST /api/instances/start` validates buddy id and starts exactly one instance.
- `POST /api/instances/<id>/input` validates non-empty text and delegates to the same input path as CLI.
- `POST /api/instances/<id>/interrupt` delegates to the same interrupt path as CLI.
- `POST /api/instances/<id>/stop` delegates to the same stop path as CLI.
- `DELETE /api/instances/<id>` refuses active instances and deletes only inactive instances.

Acceptance rule:

- Web tests must not call Codex app-server directly.
- Web tests must use the same launcher/app-server boundary as the CLI so there is one control path.

### P1: Local-Only Web Safety

Add when the web service is introduced.

Required tests:

- Default bind address is `127.0.0.1`.
- Non-local bind requires an explicit flag or is rejected.
- Mutating routes reject malformed JSON.
- Mutating routes reject path traversal instance ids.
- The web server never writes `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.

### P2: Concurrent Operation Guard

Add if the web page can trigger multiple operations quickly.

Required tests:

- Two simultaneous starts do not corrupt shared launcher state.
- Input while stop is in progress returns a clear busy/stopped error.
- Delete while stop is in progress either waits under the runtime lock or returns a clear locked/busy error.
- Status remains read-only and can run while another operation holds the runtime lock.

### P2: Status Refresh Behavior

Add when the UI has polling or server-sent updates.

Required tests:

- Repeated status polling does not mutate instance records except documented stale-marker cleanup.
- Polling an unhealthy instance returns structured error metadata rather than a 500.
- A stopped instance appears inactive after refresh.

### P2: Real Codex Smoke

The existing service-mode test plan asks for a real smoke test, but no matching collected test was found in this worktree.

Missing test name from prior plan:

- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_real_codex_app_server_start_input_status_stop_smoke`

Required behavior:

- Gate behind `BUDDYSWITCH_REAL_CODEX_APP_SERVER_SMOKE=1`.
- Use installed `codex`.
- Start one buddy with a temporary HOME.
- Send one harmless input.
- Read status.
- Stop service.
- Assert app-server, broker, and browser transient markers are cleaned.

This should not be a normal CI gate because it depends on local Codex availability and auth.

## Focused Verification Gate Before Web Work

The minimum green gate before implementing the web management page:

```bash
python3 -m pytest tests/test_app_server_client.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'start_with_buddy_starts_app_server_service_and_returns or input_ or attach_ or stop_ or status_reports_app_server_health_and_thread_metadata or list_includes_app_server_health_and_thread_id or interrupt_' -q
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'instance_delete_blocks_active_app_server or data_cleanup_is_blocked_when_active_app_server_exists or reset_is_blocked_when_active_app_server_exists' -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_optional_browser_bootstrap_failure_continues_active_instance -q
python3 -m pytest tests/test_browser_cockpit_launcher.py tests/test_cleanup_system.py -q
```

Expected before web work proceeds:

- all commands pass;
- destructive operations block live app-server services;
- started services remain healthy across later launcher invocations;
- optional browser failure semantics are clear and tested.

## Omission Audit

Reviewed sources:

- `docs/spec/2026-05-23-codex-app-server-service-mode-test-plan.md`
- `tests/test_app_server_client.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_browser_cockpit_launcher.py`
- `tests/test_cleanup_system.py`

Coverage status:

| Area | Covered Now | Current Status | Gap |
| --- | --- | --- | --- |
| App-server wire protocol | Yes | Green | None found for web MVP. |
| Service start | Yes | Mostly green | Optional browser failure path is red. |
| Service status/list | Yes | Red | Health reuse after start. |
| Input idle/active/non-steerable | Yes | Red | Blocked at health gate. |
| Attach | Yes | Red | Blocked at health gate. |
| Interrupt | Yes | Red | Blocked at health gate. |
| Stop | Yes | Green | Keep in gate. |
| Delete/reset/cleanup active guards | Yes | Red | Active app-server count misses live service. |
| Browser cockpit baseline | Yes | Green | Keep in gate. |
| Old TUI public path removal | Yes | Green | Keep in gate. |
| Real Codex smoke | No collected test found | Missing | Add optional smoke test. |
| Web API endpoints | Not applicable yet | Missing by design | Add with web implementation. |
| Web local-only safety | Not applicable yet | Missing by design | Add with web implementation. |
| Web concurrent operations | Not applicable yet | Missing by design | Add if UI can issue concurrent mutations. |

Audit conclusion:

The immediate missing work is not broad test invention. The current suite already names the main service-mode behaviors. The blocker is making the existing red service-health and active-guard tests pass. After that, the next omitted test surface is web-specific API and local-only safety coverage.
