# Browser Resource Lifecycle Acceptance Plan

Date: 2026-07-04

## Purpose

This document defines the acceptance checks for the browser resource lifecycle rebuild.

The rebuild is complete only when automated tests, residue scans, actor flow, and host process inspection all agree that actor-owned browser resources are cleaned through one lifecycle path.

## Acceptance Matrix

| Requirement | Proof |
| --- | --- |
| Cockpit is the browser-use surface | `chrome-devtools-cockpit` opens, lists, selects, and snapshots a page without `search.open_browser` |
| No old browser open path remains | live-source residue scan finds no `search.open_browser` or `browser.open_url` implementation path |
| Page TTL still works | expired page targets are closed or forgotten, and page-idle state is updated |
| Empty page set schedules release | page expired handler schedules cockpit release when no tracked pages remain |
| Release cleans owned Chrome without marker PID | regression test with missing `browser/chrome.pid` passes |
| Release cleans owned Chrome when `browser_port` is null | regression test for profile-owned orphaned Chrome passes |
| Release does not lie on failed termination | failed termination returns `ok: false` and does not clear diagnostic state |
| Foreign resources are protected | foreign profile or unknown process is not killed |
| Automatic release protects real pages | release is skipped or blocked when protected user pages remain |
| Explicit cleanup force-cleans actor resources | instance stop or explicit release removes actor-owned Chrome and upstream resources |
| Status exposes orphaned resources | status reports profile-owned orphaned Chrome instead of plain inactive |
| Actor path is stable | market actor can use cockpit search/new-page flow, then resources are reclaimed |

## Focused Automated Tests

Run these focused suites during implementation:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_browser_runtime_manager.py
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_browser_page_expired_handler.py
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_browser_lazy_release_integration.py
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_browser_cockpit_proxy.py
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_cdp_browser_session.py
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_runtime_broker.py
```

Add exact regression tests before changing runtime code:

1. `test_release_cleans_owned_profile_listener_when_pid_marker_missing`
2. `test_release_cleans_owned_profile_listener_when_browser_port_missing`
3. `test_release_failure_preserves_state_until_process_gone`
4. `test_status_reports_orphaned_owned_browser_process`
5. `test_release_handler_fails_when_manager_release_verification_fails`
6. `test_broker_browser_release_cleans_owned_missing_marker_runtime`

The exact test names can change to match local style, but each behavior must be covered.

## Broader Regression Tests

After focused tests pass, run the broader relevant launcher and consistency checks:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_buddyswitch_launcher.py -k 'browser or cockpit or env_browser'
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_env_tool_response_contract.py
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_repo_consistency.py
```

If the `test_buddyswitch_launcher.py` selector becomes too broad or slow, split it into exact tests that cover:

1. env browser release
2. instance stop/reset cleanup
3. live browser endpoint protection
4. cockpit launcher configuration

## Residue Scans

Run live-source scans after implementation:

```bash
rg -n 'search__open_browser|search\.open_browser|browser\.open_url|request_runtime_broker\("browser\.open_url"|BUDDYSWITCH_SEARCH_BROWSER_ENSURE_COMMAND|ensure_browser_url_for_instance' scripts tools/launcher/assets framework/contracts buddyswitch/skills -S
```

Expected result:

No live implementation or role-surface dependency remains.

Historical docs, migration notes, and tests may mention removed names only when they are documenting or asserting removal. They should not be part of a live runtime route.

Run lifecycle ownership scans:

```bash
rg -n 'BUDDYSWITCH_BROWSER_COCKPIT_ENSURE_COMMAND|ensure_browser_url|browser\.open_url|browser\.acquire|browser\.release' tools/launcher scripts/env scripts/runtime_kernel tests -S
```

Expected result:

1. Browser acquire/release are broker control-plane operations.
2. No separate browser open data-plane exists beside cockpit/session.
3. Any `ensure_browser_url` style usage is either deleted or deliberately moved into the rebuilt manager/session path.

## Host Process Inspection

Before and after actor verification, inspect host browser resources:

```bash
ps -axo pid,pgid,command | awk '/--remote-debugging-port=/ && /\.codex-buddyswitch\/instances\// && !/awk/ {print}'
```

Expected result after TTL release or explicit cleanup:

No process remains for the tested actor instance profile.

For a specific instance, use:

```bash
INSTANCE_ID=act-market-REPLACE_ME
ps -axo pid,pgid,command | awk -v id="$INSTANCE_ID" '/--remote-debugging-port=/ && index($0, id) && !/awk/ {print}'
```

Expected result:

No output after cleanup.

Also inspect listener state when a port is known:

```bash
lsof -nP -iTCP:9222 -sTCP:LISTEN || true
```

Use the actual recorded browser port when different from `9222`.

## Manual Actor Verification

Use a fresh market actor instance after automated tests pass.

Manual path:

1. Start a market actor.
2. Instruct it to use only `chrome-devtools-cockpit`.
3. Open a search page through cockpit `search_page` or the new cockpit search-specific action.
4. Confirm `list_pages` returns the opened page.
5. Confirm `select_page` selects it.
6. Confirm `take_snapshot` returns page evidence.
7. Wait longer than page TTL plus release delay.
8. Check instance browser status.
9. Check `instance.json` for cleared `browser_port`.
10. Check `runtime/browser/page_idle.json` is gone or empty.
11. Check no Chrome process remains for that instance profile.

Minimum actor prompt:

```text
请只使用 chrome-devtools-cockpit，不要调用 search.open_browser、search__open_browser 或 search 工具。打开 Bing 搜索页，查询 'BuddySwitch browser resource lifecycle'，然后 list_pages/select_page/take_snapshot 获取页面证据。最后回复是否成功、打开的 URL、页面标题和快照摘要。
```

Acceptance evidence to capture:

1. Actor ID.
2. Opened URL.
3. Page title.
4. `list_pages` output showing idle tracking.
5. `take_snapshot` evidence.
6. Browser status after TTL release.
7. Process inspection showing no profile-owned Chrome remains.

## Failure Rules

Do not accept the rebuild if any of these occur:

1. Product state says browser inactive while a profile-owned Chrome process remains.
2. Release returns handled success after failing to terminate owned Chrome.
3. `browser_port` is cleared before cleanup verification.
4. `search.open_browser` or `browser.open_url` remains as a live route.
5. Automatic idle release can kill a protected real user page.
6. Foreign or unknown browser processes are terminated by default.
7. Actor cockpit search flow regresses.

## Documentation Gate

Before runtime code changes, create a `docs/spec` implementation plan that includes:

1. The failing tests to add first.
2. The manager resource model to implement.
3. The release mode mapping.
4. The files to change.
5. The focused and broader verification commands.
6. The manual actor validation checklist.

Implementation can start only after that plan is clear enough for another agent to execute without hidden context.
