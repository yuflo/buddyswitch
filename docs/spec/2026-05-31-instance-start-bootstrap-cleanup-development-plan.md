# Instance Start Bootstrap Cleanup Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development while changing behavior. Use superpowers:verification-before-completion before claiming completion. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make instance startup tolerate one timeout-like bootstrap cold-start failure and leave failed instances clean, diagnosable, and deletable.

**Architecture:** Keep lifecycle orchestration in `buddyswitch-codex`, app-server RPC timeout behavior in `tools/launcher/app_server.py` and `.sh`, instance record writes in `tools/launcher/env.sh`, and browser ownership checks in `tools/launcher/browser_cockpit.sh`. Add no Web UI special case, registry, daemon coordination path, global npm cache, or global MCP runtime.

**Tech Stack:** Bash launcher helpers, Python app-server helper, Python unittest/pytest launcher tests.

---

## Files

Modify:

- `docs/memo/2026-05-31-instance-start-bootstrap-cleanup-task.md`: update status after implementation.
- `tests/helpers/fake_codex.py`: add deterministic per-method attempt failure support for launcher tests.
- `tests/test_app_server_client.py`: add dedicated bootstrap timeout test.
- `tests/test_buddyswitch_launcher.py`: add/adjust launcher lifecycle regression tests.
- `tools/launcher/app_server.py`: add dedicated `thread-bootstrap --timeout-seconds` path.
- `tools/launcher/app_server.sh`: expose `BUDDYSWITCH_THREAD_BOOTSTRAP_TIMEOUT_SECONDS` to `thread-bootstrap`.
- `tools/launcher/env.sh`: add small helpers for clearing browser port and recording `last_failure`.
- `tools/launcher/browser_cockpit.sh`: add target-owned browser endpoint predicate without changing broad endpoint helper semantics.
- `buddyswitch-codex`: retry timeout-like bootstrap once, call failed-start cleanup, and use owned browser predicate in delete.

Do not modify:

- `tools/launcher/web_management.py` except if a test reveals a non-browser lifecycle display issue. This task should not add Web delete special cases.
- runtime contracts or env tool schema.

## Implementation Steps

### Task 1: Write RED Tests

- [ ] Add fake Codex support in `tests/helpers/fake_codex.py`:
  - maintain `method_attempt_counts` in app-server state;
  - support `error_on_attempts` shaped as:

```json
{
  "thread/inject_items": {
    "1": {
      "code": -32000,
      "message": "timed out waiting for thread/inject_items"
    }
  }
}
```

  - when the configured attempt matches, save state and return that JSON-RPC error;
  - otherwise fall through to normal response and mutation.

- [ ] Add `test_thread_bootstrap_rollout_uses_dedicated_timeout` to `tests/test_app_server_client.py`:
  - start `FakeUnixWebSocketServer`;
  - call `APP_SERVER.thread_bootstrap_rollout(socket_path, "thread-1", timeout_seconds=0.2)` in a thread;
  - respond to initialize/initialized but do not answer `thread/inject_items`;
  - assert `AppServerTimeoutError` mentions `thread/inject_items`;
  - assert elapsed time is less than the default 15 second RPC timeout.

- [ ] Add `test_start_bootstrap_timeout_retries_once_and_succeeds` to `tests/test_buddyswitch_launcher.py`:
  - call `_start_service_instance(..., state_payload={"error_on_attempts": {"thread/inject_items": {"1": {"code": -32000, "message": "timed out waiting for thread/inject_items"}}}})`;
  - assert start return code is 0;
  - assert exactly two `thread/inject_items` calls and one `thread/start`;
  - assert both bootstrap calls use the same thread id;
  - assert instance record is active and daemon resumed after the second bootstrap.

- [ ] Add `test_start_bootstrap_retry_failure_cleans_state_and_records_failure`:
  - configure attempts 1 and 2 for `thread/inject_items` to timeout-like errors;
  - assert start fails;
  - assert exactly two bootstrap calls;
  - assert instance record fields are clean and `last_failure` is present;
  - assert no app-server, runtime broker, daemon, or browser pid markers remain;
  - assert canonical `thread_id` is `None`.

- [ ] Add `test_instance_delete_ignores_foreign_browser_endpoint_on_stale_port`:
  - create PM target record with `browser_port=9333`;
  - create Market record with `browser_port=9333`;
  - create Market `browser/chrome.pid` marker using current process pid;
  - fake `curl` makes `/json/version` on 9333 reachable;
  - delete PM succeeds and leaves Market root/marker intact.

- [ ] Update `test_instance_delete_blocks_live_target_browser_endpoint`:
  - model owned endpoint with a target browser pid marker or with command-line ownership evidence when practical;
  - keep the assertion that target-owned browser blocks delete.

- [ ] Run the new/changed focused tests and confirm they fail for the missing production behavior before implementation.

### Task 2: Add Dedicated Bootstrap Timeout

- [ ] In `tools/launcher/app_server.py`, change:

```python
def thread_inject_items(socket_path: Path, thread_id: str, items: list[dict[str, object]]) -> dict[str, Any]:
```

to accept `timeout_seconds: float = DEFAULT_RPC_TIMEOUT_SECONDS` and pass it into `AppServerClient`.

- [ ] Change:

```python
def thread_bootstrap_rollout(socket_path: Path, thread_id: str) -> dict[str, Any]:
```

to accept `timeout_seconds: float = DEFAULT_RPC_TIMEOUT_SECONDS` and pass it to `thread_inject_items`.

- [ ] Add parser option to `thread-bootstrap`:

```python
thread_bootstrap_parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_RPC_TIMEOUT_SECONDS)
```

- [ ] In `_command_thread_bootstrap`, pass `args.timeout_seconds`.

- [ ] In `tools/launcher/app_server.sh`, add:

```bash
--timeout-seconds "${BUDDYSWITCH_THREAD_BOOTSTRAP_TIMEOUT_SECONDS:-${BUDDYSWITCH_APP_SERVER_RPC_TIMEOUT_SECONDS:-30}}"
```

to `buddyswitch_app_server_thread_bootstrap`.

The default may be longer than general RPC timeout, but it applies only to bootstrap.

### Task 3: Add Instance Record Cleanup Helpers

- [ ] In `tools/launcher/env.sh`, add `buddyswitch_instance_clear_browser_port <instance_id>`:
  - validate record exists and id matches;
  - set `browser_port` to `None`;
  - update `updated_at`.

- [ ] Add `buddyswitch_instance_record_failure <instance_id> <phase> <message> [thread_id] [browser_port]`:
  - set small `last_failure` object with `phase`, `message`, `failed_at`;
  - include `thread_id` only when non-empty;
  - include `browser_port` only when numeric;
  - update `updated_at`.

- [ ] Add a narrow shell helper in `buddyswitch-codex`, for example `instance_start_failure_cleanup <instance_id> <phase> <message> [thread_id] [browser_port]`, that:
  - stops app-server;
  - stops runtime broker;
  - stops the instance browser;
  - clears app-server fields with inactive status;
  - clears `browser_port`;
  - records `last_failure`;
  - never deletes the instance directory.

### Task 4: Retry Bootstrap Once

- [ ] In `buddyswitch-codex`, add a helper that classifies timeout-like bootstrap failure:

```bash
buddyswitch_thread_bootstrap_failure_is_timeout_like() {
  local message="$1"
  [[ "${message}" == *"timed out waiting for thread/inject_items"* ]] ||
    [[ "${message}" == *"timed out waiting for thread/bootstrap"* ]] ||
    [[ "${message}" == *"AppServerTimeout"* ]]
}
```

- [ ] Add `buddyswitch_start_thread_bootstrap_with_retry <thread_id>`:
  - call `buddyswitch_app_server_thread_bootstrap`;
  - on success return 0;
  - on failure capture output;
  - if output is timeout-like, call `buddyswitch_app_server_thread_bootstrap` once more for the same thread id;
  - return success if retry succeeds;
  - on final failure print captured output and return non-zero;
  - do not retry non-timeout failure.

- [ ] Replace the direct bootstrap call in `start_locked_bootstrap` with this helper.

- [ ] On final bootstrap failure in `start_locked_bootstrap`, call the failed-start cleanup helper with:
  - phase `thread_bootstrap`;
  - message from the failed bootstrap output or `Thread bootstrap failed for <thread_id>.`;
  - diagnostic thread id;
  - current `BUDDYSWITCH_BROWSER_PORT`.

- [ ] Do not call `buddyswitch_instance_set_thread_id` before bootstrap succeeds. The canonical `thread_id` should still be written only through `buddyswitch_instance_set_app_server` after successful bootstrap.

### Task 5: Add Browser Ownership Predicate

- [ ] In `tools/launcher/browser_cockpit.sh`, keep `buddyswitch_browser_instance_endpoint_is_active` unchanged.

- [ ] Add `buddyswitch_browser_instance_endpoint_is_owned_active <instance_id>`:
  - read target record `browser_port`;
  - return false when no port is recorded or CDP endpoint is unreachable;
  - return true when target pid marker is active;
  - if no target pid marker is active, try to determine the process listening on the recorded port and inspect its command line;
  - return true only if command line contains `--user-data-dir=<target-instance-root>/browser/profile`;
  - return false for a reachable endpoint whose command line clearly belongs to another instance or cannot be associated with target ownership.

- [ ] Keep this helper local and concrete. Do not add a global ownership registry.

### Task 6: Wire Delete Guard

- [ ] In `buddyswitch-codex instance_delete_locked`, keep the active app-server block.

- [ ] Keep the pid-marker block.

- [ ] Replace raw endpoint block:

```bash
if buddyswitch_browser_instance_endpoint_is_active "${instance_id}"; then
```

with:

```bash
if buddyswitch_browser_instance_endpoint_is_owned_active "${instance_id}"; then
```

- [ ] Do not change Web UI delete handling.

### Task 7: Verify And Review

- [ ] Run the focused tests from the test plan.
- [ ] Run relevant launcher/app-server group:

```bash
python3 -m pytest tests/test_app_server_client.py tests/test_buddyswitch_launcher.py -k 'bootstrap or delete or browser or reset' -q
```

- [ ] Run full suite only after focused tests prove cleanup:

```bash
python3 -m pytest -q
```

- [ ] Run:

```bash
git diff --check
```

- [ ] Review diff for non-goals:
  - no Web UI special case;
  - no global npm cache or global MCP process;
  - no new daemon/registry/state machine;
  - no direct edits to runtime object stores;
  - no canonical `thread_id` before successful bootstrap.

- [ ] Update the memo status from proposed to implemented after verification passes.

## Acceptance Checklist

- [ ] `thread/bootstrap` has a dedicated timeout path.
- [ ] Timeout-like bootstrap failure retries exactly once.
- [ ] Non-timeout bootstrap failure does not retry.
- [ ] Retry success keeps one thread and starts daemon after bootstrap.
- [ ] Retry failure clears app-server fields, browser port, pid markers, sockets, and daemon marker.
- [ ] Retry failure records `last_failure`.
- [ ] Retry failure does not persist canonical `thread_id`.
- [ ] Delete ignores a foreign live endpoint on a stale target port.
- [ ] Delete blocks target-owned browser resources.
- [ ] Broad reset/cleanup browser guards remain conservative.
- [ ] Focused tests, relevant group tests, full tests, and `git diff --check` pass.

