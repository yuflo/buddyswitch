# Instance Start Bootstrap Cleanup Test Plan

Date: 2026-05-31

## Goal

Verify the lifecycle behavior described in `docs/memo/2026-05-31-instance-start-bootstrap-cleanup-task.md`.

The tests must prove product behavior, not implementation convenience:

- cold `thread/bootstrap` timeout-like failure gets exactly one retry;
- retry success produces a normal active instance and starts the daemon only after bootstrap;
- retry exhaustion leaves an inactive, diagnosable, cleanly deletable instance;
- canonical `thread_id` is not persisted for a start thread whose bootstrap never succeeded;
- stale `browser_port` does not make another instance's browser block delete;
- target-owned browser resources still protect the target instance from delete;
- broad cleanup/reset browser protections remain conservative.

## Resource Boundary

Follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

Use existing fake launcher paths in `tests/test_buddyswitch_launcher.py` and `tests/helpers/fake_codex.py`. Do not launch real Chrome, real Codex, real MCP servers, or real npm installs in regression tests.

Required test hygiene:

- each test uses `tempfile.TemporaryDirectory`;
- fake processes are registered through `BUDDYSWITCH_TEST_PROCESS_REGISTRY`;
- focused tests run before broad suites;
- process marker files, sockets, and pid files are asserted absent after failed startup cleanup;
- no test-owned app-server, broker, daemon, or browser process remains after focused runs.

## Functional Requirements

### FR1: Bootstrap Timeout-Like Failure Retries Once

Given a new product instance start reaches `thread/start`, and the first `thread/bootstrap` attempt fails with a timeout-like error, the launcher retries `thread/bootstrap` once for the same thread.

Expected:

- two `thread/inject_items` calls for the same `threadId`;
- no second `thread/start`;
- instance becomes `active` if the second bootstrap succeeds;
- `thread_id` equals the started thread;
- daemon `thread/resume` happens after the successful bootstrap;
- no non-timeout error is retried.

Test location:

- add to `tests/test_buddyswitch_launcher.py`.

Fake support:

- extend `tests/helpers/fake_codex.py` with per-method attempt counting and `error_on_attempts`;
- configure `thread/inject_items` to fail on attempt 1 with message containing `timed out waiting for thread/inject_items`;
- allow attempt 2 to use normal behavior.

Focused command:

```bash
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_bootstrap_timeout_retries_once_and_succeeds -v
```

### FR2: Non-Timeout Bootstrap Failure Does Not Retry

Given `thread/bootstrap` fails with a protocol/request error that is not timeout-like, the launcher fails closed without retry.

Expected:

- exactly one `thread/inject_items` call;
- startup returns non-zero;
- instance remains `inactive`;
- no ready daemon pid is present.

This can extend the existing `test_start_bootstrap_failure_fails_closed_without_ready_daemon` assertions.

Focused command:

```bash
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_bootstrap_failure_fails_closed_without_ready_daemon -v
```

### FR3: Bootstrap Retry Exhaustion Cleans Failed Startup State

Given both bootstrap attempts fail with timeout-like errors, startup fails closed and the instance record is cleaned.

Expected instance record:

- `status == "inactive"`;
- `app_server_pid is None`;
- `app_server_socket is None`;
- `app_server_log is None`;
- `browser_port is None`;
- canonical `thread_id is None`;
- `last_failure.phase == "thread_bootstrap"`;
- `last_failure.thread_id` contains the diagnostic started thread id;
- `last_failure.browser_port` contains the stale port for diagnostics;
- `last_failure.message` contains the timeout failure;
- `last_failure.failed_at` is present.

Expected filesystem/process state:

- `runtime/app-server.pid` absent;
- `runtime/app-server.sock` absent if it was created;
- `runtime/app-server.socket` absent;
- `runtime/runtime-broker.pid` absent;
- `browser/chrome.pid` absent;
- `runtime/daemon/daemon.pid` absent.

Test location:

- add to `tests/test_buddyswitch_launcher.py`.

Focused command:

```bash
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_bootstrap_retry_failure_cleans_state_and_records_failure -v
```

### FR4: Delete Ignores Foreign Browser Endpoint On Stale Port

Given a failed PM instance has stale `browser_port=9333`, and another Market instance owns the live browser endpoint on port `9333`, deleting PM must not be blocked by Market's endpoint.

Expected:

- `instance delete inst-pm-stale-port --yes` succeeds;
- PM instance root is removed;
- Market instance root remains;
- Market `browser/chrome.pid` remains;
- the endpoint probe alone is not treated as target ownership.

Test location:

- add to `tests/test_buddyswitch_launcher.py`.

Focused command:

```bash
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_instance_delete_ignores_foreign_browser_endpoint_on_stale_port -v
```

### FR5: Delete Blocks Target-Owned Browser

Given the target instance owns a browser via live pid marker or owned endpoint, delete remains blocked.

Expected:

- live target `browser/chrome.pid` blocks delete;
- target-owned endpoint with `--user-data-dir=<target>/browser/profile` blocks delete;
- instance root remains.

Existing coverage:

- `test_instance_delete_blocks_active_target_browser_pid`
- update `test_instance_delete_blocks_live_target_browser_endpoint` so it models target ownership, not raw endpoint reachability.

Focused commands:

```bash
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_instance_delete_blocks_active_target_browser_pid -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_instance_delete_blocks_live_target_browser_endpoint -v
```

### FR6: App-Server Bootstrap Has A Dedicated Timeout Path

`tools/launcher/app_server.py` must support a dedicated timeout for `thread-bootstrap` without changing every app-server RPC timeout.

Expected:

- parser accepts `thread-bootstrap --timeout-seconds <float>`;
- `thread_bootstrap_rollout(..., timeout_seconds=...)` passes that timeout to the inject call;
- an unresponsive fake websocket raises `AppServerTimeoutError` for `thread/inject_items` within the configured timeout.

Test location:

- add to `tests/test_app_server_client.py`.

Focused command:

```bash
python3 -m unittest tests.test_app_server_client.AppServerClientTests.test_thread_bootstrap_rollout_uses_dedicated_timeout -v
```

### FR7: Broad Cleanup/Reset Remains Conservative

Existing reset/data cleanup checks must still use broad browser activity checks where appropriate. The new delete ownership helper must not replace `buddyswitch_browser_any_recorded_instance_endpoint_is_active` or `buddyswitch_browser_is_active` semantics.

Focused commands:

```bash
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_launcher_help_and_reset_flow -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_reset_blocks_active_instance_browser -v
```

If the exact reset test name differs, run the existing reset/browser-focused tests selected by:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'reset and browser' -q
```

## Review Checks

After implementation, inspect the diff and verify:

- no Web UI special case was added for delete;
- no global npm cache or global MCP process was introduced;
- no new daemon/registry/lifecycle state machine was added;
- old broad endpoint reachability helper semantics remain available;
- delete uses an ownership-specific helper;
- failed startup cleanup clears `browser_port`;
- failed startup writes `last_failure`;
- start does not persist canonical `thread_id` before successful bootstrap.

## Verification Sequence

Run focused tests first:

```bash
python3 -m unittest tests.test_app_server_client.AppServerClientTests.test_thread_bootstrap_rollout_uses_dedicated_timeout -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_bootstrap_timeout_retries_once_and_succeeds -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_bootstrap_retry_failure_cleans_state_and_records_failure -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_instance_delete_ignores_foreign_browser_endpoint_on_stale_port -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_instance_delete_blocks_live_target_browser_endpoint -v
```

Then run relevant groups:

```bash
python3 -m pytest tests/test_app_server_client.py tests/test_buddyswitch_launcher.py -k 'bootstrap or delete or browser or reset' -q
```

Then run broad verification only after focused resource cleanup is clean:

```bash
python3 -m pytest -q
git diff --check
```

