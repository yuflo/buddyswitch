# Browser Page Lifecycle Systemic Stabilization Plan

Date: 2026-06-25

## Goal

Make BuddySwitch browser pages a managed runtime resource:

> Any browser page opened through BuddySwitch must either be registered into browser idle lifecycle management with a keyed expiry schedule, or be closed immediately and reported as a failed open.

This plan supersedes the earlier `browser-page-idle-lifecycle-*` spec documents for browser page lifecycle work. Those earlier documents must not be used as implementation authority for this task.

## Review #2 Architecture Audit

### Current Findings

The observed failures are systemic, not two isolated cases.

- `search.open_browser` pages were registered in `runtime/browser/page_idle.json`, scheduled through daemon, and expired.
- `chrome-devtools-cockpit.new_page` pages in `act-market-bdd7d4044526` stayed open because they were never registered in browser lifecycle state and never received `browser.page.expired` schedules.
- The cockpit proxy reads instance root from `BUDDYSWITCH_INSTANCE_ROOT`, but the actual MCP registration does not pass that environment to the proxy process.
- Current lifecycle API mixes idle refresh with current-page selection, so background search pages can incorrectly become the protected current page.
- Existing test plans still preserve an old behavior where idle refresh failure after opening a page is reported but not rolled back. That behavior is now rejected because it leaves unmanaged browser resources.
- Daemon scheduling is generic and working for registered schedules, but schedule sweep is tied to daemon loop timing and is not a hard real-time timer.

### Boundary Decision

Browser page lifecycle policy belongs to browser-owned launcher code:

- `scripts/env/cdp_browser_lifecycle.py`
- `scripts/env/tools/search/_impl.py`
- `tools/launcher/chrome_devtools_cockpit_proxy.py`
- `tools/launcher/browser_page_expired_handler.py`
- `tools/launcher/browser_cockpit.sh`

Daemon service must remain generic:

- It may create, upsert, sweep, and dispatch opaque keyed schedules.
- It must not store browser-specific top-level state.
- It must not know what a browser page, current page, TTL, or idle policy means.

### No Dual-Track Compatibility

Do not preserve old runtime behavior as a fallback path.

Remove or replace these patterns in active code and active tests:

- actor-facing `ttl_seconds`;
- `expiry_policy`;
- old TTL naming in tool responses;
- cockpit proxy lifecycle dependency on inherited `BUDDYSWITCH_INSTANCE_ROOT`;
- silent "idle not refreshed" paths after opening a new page;
- a lifecycle helper that both refreshes idle and mutates current page state as one unavoidable operation.

New implementation and tests must use this document as the only active plan. Superseded spec documents must be deleted or explicitly marked superseded before implementation is considered complete.

## Test Plan First

These tests define the expected product result before implementation. Each new or changed test must fail for the expected reason before implementation changes are added.

### Test Rules: No Cheating

- Tests must assert observable behavior: tool responses, daemon schedules, browser target close calls, `page_idle.json`, and generated MCP config.
- Tests must not pass by checking that a mock function was called when the externally visible state would still be wrong.
- Tests for "no unmanaged new page" must prove both sides: the open attempt is reported as failed and the created target is closed or never forwarded.
- Tests must not accept `"Browser page idle not refreshed."` as success for a newly opened page.
- Tests must not preserve old behavior where a new browser page remains open after lifecycle registration fails.
- Tests must not rely on real long waits. Use fakes, temporary directories, short-lived HTTP servers, and explicit daemon state timestamps.

### Expected Test Failures Before Implementation

Run focused tests after adding each test. Expected failures should be caused by missing behavior, not syntax errors.

```bash
python -m unittest \
  tests.test_browser_cockpit_launcher \
  tests.test_buddyswitch_launcher \
  tests.test_browser_cockpit_proxy \
  tests.test_search_env_tool \
  tests.test_cdp_browser_session \
  tests.test_browser_page_expired_handler \
  tests.test_daemon_core
```

### 1. Cockpit MCP Registration Carries Instance Root

Files:

- `tests/test_browser_cockpit_launcher.py`
- `tests/test_buddyswitch_launcher.py`
- `tools/launcher/browser_cockpit.sh`

Expected behavior:

- New cockpit MCP registration includes `--instance-root=<active instance root>`.
- Existing cockpit MCP config is removed and recreated when it lacks `--instance-root`.
- Existing cockpit MCP config is removed and recreated when `--instance-root` points to a different instance.
- The proxy no longer depends on inherited `BUDDYSWITCH_INSTANCE_ROOT`.

Required tests:

- Add an assertion to cockpit registration helpers that argv contains `--instance-root=<instance_root>`.
- Add a stale-config test where existing MCP args include the correct `--browser-url` and proxy path but omit `--instance-root`; expected result is removal and re-add.
- Add a mismatch test where existing MCP args contain another instance root; expected result is removal and re-add.

Expected pre-implementation failure:

- Registration helper fails because generated argv has only `--browser-url`.
- Stale config is incorrectly accepted as valid.

### 2. Proxy Requires Explicit Instance Root

Files:

- `tests/test_browser_cockpit_proxy.py`
- `tools/launcher/chrome_devtools_cockpit_proxy.py`

Expected behavior:

- Proxy CLI accepts `--instance-root`.
- `run_proxy` passes the parsed instance root through all request and response mutation paths.
- Tests can run the proxy with no `BUDDYSWITCH_INSTANCE_ROOT` env and still observe idle registration.
- A lifecycle-managed page open is rejected if instance root is missing.

Required tests:

- `test_new_page_refreshes_idle_with_explicit_instance_root_without_env`
  - Run proxy with `--instance-root=<temp instance root>`.
  - Do not pass `BUDDYSWITCH_INSTANCE_ROOT` in `extra_env`.
  - `new_page` response includes idle refreshed text.
  - Daemon state contains one `browser.page.expired` schedule for the new target.
- `test_new_page_without_instance_root_is_blocked_before_forwarding`
  - Run proxy without `--instance-root`.
  - Call `new_page` with a URL.
  - Expected response is an MCP tool error.
  - Expected forwarded upstream calls is empty.

Expected pre-implementation failure:

- Explicit instance root is ignored because code reads only `os.environ`.
- Missing instance root currently allows forwarding and can silently produce unmanaged pages.

### 3. Lifecycle API Separates Idle Refresh From Current Page

Files:

- `tests/test_cdp_browser_session.py`
- `scripts/env/cdp_browser_lifecycle.py`

Expected behavior:

- `refresh_page_idle(instance_root, target_id, target_url=None, page_id=None)` registers or refreshes a target idle schedule without changing `current_target_id`.
- `mark_current_page(instance_root, target_id, target_url=None, page_id=None)` records current page identity without scheduling expiry.
- `refresh_current_page_idle(instance_root, target_id, target_url=None, page_id=None)` explicitly combines current-page marking and idle schedule refresh.
- Scheduling happens before durable idle state is written, so a schedule failure does not leave fake managed state in `page_idle.json`.
- Active code no longer uses `touch_page_idle`.

Required tests:

- `test_refresh_page_idle_does_not_set_current_target`
  - Call `refresh_page_idle`.
  - Assert `targets[target_id].last_used_at` exists.
  - Assert `current_target_id` is absent.
  - Assert one keyed daemon schedule exists.
- `test_mark_current_page_does_not_schedule_idle`
  - Call `mark_current_page`.
  - Assert `current_target_id` is set.
  - Assert no daemon schedule file is created.
- `test_refresh_current_page_idle_sets_current_and_schedules`
  - Call `refresh_current_page_idle`.
  - Assert current target, page mapping, target metadata, and keyed schedule all exist.
- `test_refresh_page_idle_schedule_failure_leaves_no_idle_state`
  - Make daemon client raise.
  - Assert the function raises.
  - Assert `runtime/browser/page_idle.json` does not contain the target.
- `test_forget_page_idle_target_removes_target_mapping_and_current`
  - Seed target, page id mapping, and current target.
  - Call `forget_page_idle_target`.
  - Assert target is removed, page id mapping is removed, and current target is cleared.

Expected pre-implementation failure:

- Existing `touch_page_idle` always sets `current_target_id`.
- Schedule failure can leave state written before scheduling.
- No cleanup helper exists.

### 4. Search Open Fails Closed On Lifecycle Registration Failure

Files:

- `tests/test_search_env_tool.py`
- `scripts/env/tools/search/_impl.py`

Expected behavior:

- New search page open succeeds only if lifecycle registration succeeds.
- If lifecycle registration fails after CDP creates a page, search closes that new target and returns an error.
- Exact URL reuse does not close the existing page, but returns a clear failure if idle refresh fails.
- Search background open or reuse refreshes idle but does not mark the page as current.

Required tests:

- Replace `test_search_open_browser_reports_idle_refresh_failure_without_rolling_back_open` with `test_search_open_browser_closes_new_target_when_idle_registration_fails`.
  - Fake `refresh_page_idle` to raise.
  - Assert response `ok` is false.
  - Assert target close RPC is sent for the new target.
  - Assert no success text says idle was refreshed.
  - Assert no unmanaged live target remains in the fake CDP state.
- Add `test_search_open_browser_reuse_idle_registration_failure_returns_error_without_closing_existing_page`.
  - Seed an existing page with exact target URL.
  - Fake `refresh_page_idle` to raise.
  - Assert response `ok` is false.
  - Assert no `Target.closeTarget` call is sent.
  - Assert response includes `page_reused=true` and `idle_refreshed=false`.
- Update new-open and reuse success tests to assert `refresh_page_idle` is called, not current-page marking.

Expected pre-implementation failure:

- Current search open returns success with `idle_refreshed=false` after creating a page.
- Current helper calls `touch_page_idle`, which also mutates current state.

### 5. Cockpit New Page Fails Closed On Lifecycle Registration Failure

Files:

- `tests/test_browser_cockpit_proxy.py`
- `tools/launcher/chrome_devtools_cockpit_proxy.py`

Expected behavior:

- `chrome-devtools-cockpit.new_page` never leaves a newly opened page unmanaged.
- If upstream opens exactly one target but lifecycle registration fails, proxy closes that target and returns a tool error.
- Exact URL reuse must refresh lifecycle; if refresh fails, proxy returns a tool error and does not claim success.
- New page success marks the opened page current and refreshes idle.

Required tests:

- `test_new_page_registration_failure_closes_new_target_and_returns_error`
  - Fake CDP list responses as before and after one new target.
  - Make daemon mailbox unavailable or make lifecycle refresh raise.
  - Fake CDP browser command server records `Target.closeTarget`.
  - Assert upstream `new_page` was forwarded once.
  - Assert response `isError` is true.
  - Assert close command targeted the new target.
- `test_new_page_reuse_registration_failure_returns_error_without_forwarding`
  - Seed exact URL in CDP list.
  - Make lifecycle refresh fail.
  - Assert forwarded calls is empty.
  - Assert response `isError` is true.
- Update success test to assert page idle state has `current_target_id` equal to the new target.

Expected pre-implementation failure:

- Proxy currently appends `"Browser page idle not refreshed."` after success or silently skips when root is absent.
- Proxy does not close a new target after lifecycle registration failure.

### 6. Select Page Resolves Target Without Preexisting Mapping

Files:

- `tests/test_browser_cockpit_proxy.py`
- `tools/launcher/chrome_devtools_cockpit_proxy.py`

Expected behavior:

- Successful `select_page` marks the selected page as current and refreshes idle.
- Resolution must not depend only on a preexisting `page_id_to_target_id` map.
- If upstream response includes a selected URL, proxy resolves that URL to a unique CDP page target.
- If selected URL resolution is ambiguous or absent, proxy reports a visible lifecycle warning and does not update the wrong target.

Required tests:

- `test_select_page_resolves_selected_url_when_page_id_mapping_is_empty`
  - Seed no page id mapping.
  - Fake upstream `select_page` response text with `https://example.com/selected [selected]`.
  - Fake CDP `/json/list` with one page target at that URL.
  - Assert schedule key matches selected target.
  - Assert current target is selected target.
- `test_select_page_ambiguous_selected_url_does_not_refresh_wrong_target`
  - Fake two CDP page targets with same URL.
  - Assert no daemon schedule is created.
  - Assert response contains a lifecycle warning.

Expected pre-implementation failure:

- Current proxy only uses `target_id_for_page_id`, so empty mapping means no refresh.

### 7. Page-Scoped Cockpit Tools Refresh Only A Known Current Page

Files:

- `tests/test_browser_cockpit_proxy.py`
- `tools/launcher/chrome_devtools_cockpit_proxy.py`

Expected behavior:

- Successful page-scoped tools refresh the current target only if current target is known.
- If current target is absent, page-scoped tool response contains a visible lifecycle warning.
- Failed page-scoped responses still do not refresh idle.

Required tests:

- Keep existing failed response test.
- Add `test_page_scoped_success_without_current_page_reports_lifecycle_warning`.
  - Seed no current target.
  - Call `take_snapshot`.
  - Assert upstream call is forwarded.
  - Assert no schedule is created.
  - Assert response includes a browser lifecycle warning.

Expected pre-implementation failure:

- Current code silently returns the unmodified response when current target is missing.

### 8. Expiry Handler Cleans Browser Lifecycle State

Files:

- `tests/test_browser_page_expired_handler.py`
- `scripts/env/cdp_browser_lifecycle.py`
- `tools/launcher/browser_page_expired_handler.py`

Expected behavior:

- When an expired page is closed or already gone, browser lifecycle state forgets that target.
- When current-page protection applies, handler refreshes idle using the explicit idle API and keeps current target.
- Stale browser errors remain handled, but target state is cleared only when the target is known gone or close succeeds.

Required tests:

- `test_expiry_close_forgets_idle_target`
  - Seed page idle state with target, page map, and current target.
  - Fake close returns `{"status": "closed"}`.
  - Assert target and mapping are removed.
- `test_expiry_already_gone_forgets_idle_target`
  - Fake close returns `{"status": "already_gone"}`.
  - Assert target and mapping are removed.
- Update current-page protection test to assert `refresh_current_page_idle` or `refresh_page_idle` is called through the new explicit API.

Expected pre-implementation failure:

- Handler closes target but leaves stale `page_idle.json` entries.

### 9. Close Target Confirms CDP Close Result

Files:

- `tests/test_cdp_browser_session.py`
- `scripts/env/cdp_browser_lifecycle.py`

Expected behavior:

- `close_page_target` treats CDP `Target.closeTarget` result `success=false` as failure.
- `close_page_target` returns `already_gone` without RPC when target is absent.
- `close_page_target` returns `closed` only when CDP close succeeds.

Required tests:

- Add `test_close_page_target_false_success_is_failure`.
  - Fake browser command response `{"success": false}`.
  - Assert `BrowserLifecycleError`.
- Keep missing-target and close-failure tests.

Expected pre-implementation failure:

- Current helper ignores the returned `success` field.

### 10. Daemon Sweep Is Generic And Not Starved By Notifications

Files:

- `tests/test_daemon_core.py`
- `tools/launcher/daemon_core.py`

Expected behavior:

- Daemon still sweeps due schedules on app-server read timeout.
- Daemon also sweeps due schedules after handling a notification, so a busy notification stream cannot indefinitely delay due schedules.
- This remains generic; no browser-specific code is added to daemon core.

Required tests:

- Extend existing daemon loop sweep tests to simulate a notification followed by loop continuation.
- Assert `sweep_due_scheduled_triggers` is called after notification dispatch.
- Assert daemon state still contains only generic scheduled trigger rows and no browser-specific top-level fields.

Expected pre-implementation failure:

- Current run loop sweeps only on `AppServerTimeoutError`.

### 11. Active Surface Has No Old TTL Or Policy Terms

Files:

- env tool schema contract tests
- `tests/test_search_env_tool.py`
- `tests/test_browser_cockpit_proxy.py`
- active runtime code under `scripts/` and `tools/`

Expected behavior:

- No active tool schema exposes `ttl_seconds`.
- No active tool result exposes `ttl_registered`, `ttl_seconds`, `expiry_policy`, schedule ids, or old TTL wording.
- No active code path uses `register_browser_page_ttl`.

Required command:

```bash
rg -n 'register_browser_page_ttl|BROWSER_PAGE_TTL_SECONDS|ttl_seconds|ttl_registered|expiry_policy|Browser page TTL|touch_page_idle' scripts tools tests
```

Expected result after implementation:

- No hits in active source or tests.
- Superseded docs do not remain as active execution plans.

### 12. Superseded Spec Documents Are Removed From The Active Plan Set

Files:

- `docs/spec/browser-page-idle-lifecycle-test-plan.md`
- `docs/spec/browser-page-idle-lifecycle-development-plan.md`
- `docs/spec/browser-page-idle-lifecycle-phase2-prompt.md`
- `docs/spec/browser-page-lifecycle-systemic-stabilization-plan.md`

Expected behavior:

- There is one active browser page lifecycle stabilization plan: this document.
- Earlier `browser-page-idle-lifecycle-*` spec files cannot be mistaken for current implementation authority.
- If retained for audit, they are moved out of the active spec path or renamed with an explicit superseded marker.

Required test/check:

```bash
find docs/spec -maxdepth 1 -type f -name 'browser-page-idle-lifecycle-*' -print
```

Expected result after implementation:

- No active superseded browser page lifecycle spec files remain under `docs/spec`.
- If the user explicitly wants audit retention, retained files must live outside the active spec set and include `SUPERSEDED` in the filename and first heading.

## Implementation Plan

Execute tasks in order. Each task starts from the tests above.

### Task 1: Make Cockpit MCP Instance Root Explicit

Files:

- Modify: `tools/launcher/browser_cockpit.sh`
- Modify: `tests/test_browser_cockpit_launcher.py`
- Modify: `tests/test_buddyswitch_launcher.py`

Steps:

1. Add failing tests for `--instance-root` in cockpit MCP registration.
2. Add failing tests for stale cockpit MCP config that omits or mismatches `--instance-root`.
3. Update `buddyswitch_browser_ensure_cockpit_mcp` to include `--instance-root="$(buddyswitch_browser_instance_root)"`.
4. Add config extraction for recorded `--instance-root`.
5. Treat correct browser URL plus missing/mismatched instance root as invalid config and re-register.
6. Run:

```bash
python -m unittest tests.test_browser_cockpit_launcher tests.test_buddyswitch_launcher
```

Expected pass condition:

- Registration includes proxy path, upstream command, browser URL, and instance root.
- Stale configs are removed and recreated.

### Task 2: Require Instance Root In Cockpit Proxy

Files:

- Modify: `tools/launcher/chrome_devtools_cockpit_proxy.py`
- Modify: `tests/test_browser_cockpit_proxy.py`

Steps:

1. Add failing proxy tests for explicit `--instance-root` without env.
2. Add failing proxy test for `new_page` without instance root being blocked before forwarding.
3. Add `--instance-root` to proxy CLI parsing.
4. Pass parsed instance root into `run_proxy`, `mutate_client_message`, and `upstream_to_client`.
5. Remove direct reads of `os.environ.get("BUDDYSWITCH_INSTANCE_ROOT")` from request and response paths.
6. Run:

```bash
python -m unittest tests.test_browser_cockpit_proxy
```

Expected pass condition:

- Proxy lifecycle works without inherited env when CLI arg is present.
- Proxy does not open a new page when instance root is absent.

### Task 3: Split Browser Lifecycle API

Files:

- Modify: `scripts/env/cdp_browser_lifecycle.py`
- Modify: `tests/test_cdp_browser_session.py`

Steps:

1. Add failing tests for `refresh_page_idle`, `mark_current_page`, `refresh_current_page_idle`, schedule failure state consistency, and `forget_page_idle_target`.
2. Implement `refresh_page_idle` as schedule-first idle registration.
3. Implement `mark_current_page` as current identity mutation without scheduling.
4. Implement `refresh_current_page_idle` as explicit composition.
5. Implement `forget_page_idle_target`.
6. Replace active code references to `touch_page_idle` in subsequent tasks, then remove `touch_page_idle`.
7. Run:

```bash
python -m unittest tests.test_cdp_browser_session
```

Expected pass condition:

- Idle refresh and current-page identity are separate operations.
- Schedule failure does not leave fake managed state.

### Task 4: Make Search Open Fail Closed

Files:

- Modify: `scripts/env/tools/search/_impl.py`
- Modify: `tests/test_search_env_tool.py`

Steps:

1. Replace the old no-rollback idle failure test with the fail-closed test.
2. Add reuse failure test.
3. Update success tests to use `refresh_page_idle`.
4. On new target lifecycle failure, call `close_page_target` for the new target.
5. Return a structured error for failed lifecycle registration.
6. On exact reuse lifecycle failure, return a structured error without closing the existing target.
7. Run:

```bash
python -m unittest tests.test_search_env_tool
```

Expected pass condition:

- New search pages never remain open unmanaged after lifecycle failure.
- Reused pages are not closed as rollback for an action that did not create them.

### Task 5: Make Cockpit New Page Fail Closed

Files:

- Modify: `tools/launcher/chrome_devtools_cockpit_proxy.py`
- Modify: `tests/test_browser_cockpit_proxy.py`

Steps:

1. Add failing tests for new target registration failure cleanup.
2. Add failing tests for exact reuse registration failure.
3. After upstream `new_page` success and target diff, call `refresh_current_page_idle`.
4. If lifecycle registration fails for a newly opened target, call `close_page_target` and return a tool error.
5. For exact URL reuse, call `refresh_current_page_idle`; on failure return a tool error and do not forward upstream.
6. Run:

```bash
python -m unittest tests.test_browser_cockpit_proxy
```

Expected pass condition:

- Newly opened cockpit pages are managed or closed.
- Exact reuse is visible and lifecycle-managed before success is reported.

### Task 6: Resolve Select Page Robustly

Files:

- Modify: `tools/launcher/chrome_devtools_cockpit_proxy.py`
- Modify: `tests/test_browser_cockpit_proxy.py`

Steps:

1. Add failing tests for selected URL resolution with empty page map.
2. Add failing ambiguous URL test.
3. Parse selected URL from successful upstream response content when available.
4. Resolve selected URL to exactly one CDP target from `/json/list`.
5. On unique match, call `refresh_current_page_idle` with page id and target URL.
6. On ambiguous or missing match, append a visible lifecycle warning and do not mutate current page.
7. Run:

```bash
python -m unittest tests.test_browser_cockpit_proxy
```

Expected pass condition:

- `select_page` no longer depends only on pre-seeded page id mapping.
- Ambiguous resolution cannot refresh the wrong target.

### Task 7: Make Page-Scoped Use Observable

Files:

- Modify: `tools/launcher/chrome_devtools_cockpit_proxy.py`
- Modify: `tests/test_browser_cockpit_proxy.py`

Steps:

1. Add failing test for successful page-scoped call without current target.
2. Keep failed response and non-use tests.
3. On page-scoped success with known current target, call `refresh_page_idle`.
4. On page-scoped success without current target, append a visible lifecycle warning.
5. Run:

```bash
python -m unittest tests.test_browser_cockpit_proxy
```

Expected pass condition:

- Page-scoped actions either refresh a known current page or make the lifecycle gap visible.

### Task 8: Clean Browser State On Expiry

Files:

- Modify: `tools/launcher/browser_page_expired_handler.py`
- Modify: `scripts/env/cdp_browser_lifecycle.py`
- Modify: `tests/test_browser_page_expired_handler.py`

Steps:

1. Add failing tests for state cleanup after `closed` and `already_gone`.
2. Update handler to call `forget_page_idle_target` after close status `closed` or `already_gone`.
3. Update current-page protection to call the new explicit idle refresh API.
4. Run:

```bash
python -m unittest tests.test_browser_page_expired_handler
```

Expected pass condition:

- Expired targets do not remain in browser lifecycle state after successful cleanup.

### Task 9: Confirm CDP Close Success

Files:

- Modify: `scripts/env/cdp_browser_lifecycle.py`
- Modify: `tests/test_cdp_browser_session.py`

Steps:

1. Add failing test for `Target.closeTarget` returning `success=false`.
2. Treat false success as `BrowserLifecycleError`.
3. Keep absent target as `already_gone`.
4. Run:

```bash
python -m unittest tests.test_cdp_browser_session
```

Expected pass condition:

- `closed` means CDP accepted close successfully.

### Task 10: Sweep Due Schedules After Notifications

Files:

- Modify: `tools/launcher/daemon_core.py`
- Modify: `tests/test_daemon_core.py`

Steps:

1. Add failing daemon loop test showing due sweep after notification dispatch.
2. Call `sweep_due_scheduled_triggers` after `dispatch_notification` in the daemon loop.
3. Keep existing timeout-based sweep.
4. Run:

```bash
python -m unittest tests.test_daemon_core tests.test_daemon_trigger_router
```

Expected pass condition:

- Generic due schedules are swept during busy notification activity.
- No browser-specific daemon state appears.

### Task 11: Remove Active Historical Surface

Files:

- Modify active tests and code touched above.

Steps:

1. Run the active-surface grep command.
2. Remove active references to `touch_page_idle`, old TTL terms, and old no-rollback expectations.
3. Confirm no active code or active tests preserve old lifecycle terminology or behavior.
4. Run:

```bash
rg -n 'register_browser_page_ttl|BROWSER_PAGE_TTL_SECONDS|ttl_seconds|ttl_registered|expiry_policy|Browser page TTL|touch_page_idle' scripts tools tests
```

Expected pass condition:

- No active source or active test hits.

### Task 12: Remove Superseded Active Spec Plans

Files:

- Delete or move out of `docs/spec`: `docs/spec/browser-page-idle-lifecycle-test-plan.md`
- Delete or move out of `docs/spec`: `docs/spec/browser-page-idle-lifecycle-development-plan.md`
- Delete or move out of `docs/spec`: `docs/spec/browser-page-idle-lifecycle-phase2-prompt.md`
- Modify if audit retention is explicitly chosen: retained superseded files outside active specs

Steps:

1. Remove the old `browser-page-idle-lifecycle-*` spec files from the active `docs/spec` directory, or move them to a clearly superseded audit location if user approval requires retention.
2. If any file is retained for audit, rename it with `SUPERSEDED` and make the first heading start with `SUPERSEDED`.
3. Run:

```bash
find docs/spec -maxdepth 1 -type f -name 'browser-page-idle-lifecycle-*' -print
```

Expected pass condition:

- The command prints nothing.
- There is no active second plan for the same browser page lifecycle work.

## Verification Plan

Focused verification:

```bash
python -m unittest \
  tests.test_browser_cockpit_launcher \
  tests.test_buddyswitch_launcher \
  tests.test_browser_cockpit_proxy \
  tests.test_search_env_tool \
  tests.test_cdp_browser_session \
  tests.test_browser_page_expired_handler \
  tests.test_daemon_core \
  tests.test_daemon_trigger_router \
  tests.test_daemon_mailbox
```

Broad Python verification:

```bash
python -m unittest discover tests
```

JavaScript repository verification:

```bash
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Resource residual inspection after service-starting tests:

```bash
ps -axo pid,ppid,pgid,command | rg 'buddyswitch|fake_codex|chrome-devtools|runtime_broker|app_server' || true
```

Expected inspection result:

- No unexplained process owned by the test run remains.
- Existing user/runtime processes are identified separately and not killed by tests.

## Runtime Acceptance Checks

After tests pass, run one controlled actor/browser scenario or an equivalent local fake flow:

1. Ensure cockpit MCP config includes `--instance-root`.
2. Open a page through `search.open_browser`.
3. Open a page through `chrome-devtools-cockpit.new_page`.
4. Inspect `<instance_root>/runtime/browser/page_idle.json`.
5. Inspect `<instance_root>/runtime/daemon/state.json`.

Expected result:

- Both pages have browser lifecycle state.
- Both pages have keyed pending `browser.page.expired` schedules.
- `search.open_browser` page is not marked current unless selected through cockpit.
- Cockpit-selected page is marked current.
- No new page is open without either state and schedule or an explicit failure result.

## Review #2 Plan Result

This plan is ready for implementation after user confirmation.

Review findings:

- Test plan comes before implementation and is result-driven.
- The direct `act-market` root cause is covered by explicit instance-root propagation.
- The actor TTL validation findings are covered by idle refresh, select-page reliability, and daemon sweep semantics.
- New unmanaged page creation is blocked by fail-closed behavior.
- Current-page protection is corrected by splitting current identity from idle refresh.
- Daemon-service remains generic.
- Old no-rollback behavior is explicitly rejected.
- No old TTL or policy surface is preserved in active code.
- Superseded browser page lifecycle spec files are removed from the active spec set.
