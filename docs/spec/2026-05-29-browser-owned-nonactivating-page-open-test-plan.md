# BuddySwitch-Owned Non-Activating Page Open Test Plan

## Goal

BuddySwitch-owned browser entry points must create headed Chrome pages without default foreground activation. The already-implemented `chrome-devtools-cockpit` proxy remains required, and the remaining direct CDP HTTP `/json/new` paths must be replaced by non-activating `Target.createTarget` calls with `background: true`.

## Functional Requirements

1. `search.open_browser` must open the planned search URL through the launcher-managed browser without using `/json/new?...`.
2. `search.open_browser` must send CDP `Target.createTarget` with the exact target URL and `background: true`.
3. `search.open_browser` must keep its existing success contract: `target_url`, `browser_endpoint`, `page_opened: true`, and the follow-up hint to continue through `chrome-devtools-cockpit`.
4. `search.open_browser` must keep actionable failure feedback when the browser endpoint is missing, invalid, unreachable, lacks a browser websocket URL, or rejects target creation.
5. Launcher ready-page repair must not use `/json/new?about:blank`.
6. Launcher ready-page repair must avoid creating a page when `/json/list` already contains a usable page.
7. If launcher ready-page repair must create a page, it must use non-activating CDP `Target.createTarget` with `url: about:blank` and `background: true`.
8. `chrome-devtools-cockpit` registration must continue to point at `tools/launcher/chrome_devtools_cockpit_proxy.py`.
9. No skill, daemon, runtime actor profile, auth, permission, broker, or app-server protocol code may change.
10. Tests must not start real Chrome, real Codex, daemon, app-server, broker, or long-lived service processes. Fake HTTP/CDP websocket servers and short subprocesses must be fully owned by each test.

## Focused Tests

### Search Tool Tests

Modify `tests/test_search_env_tool.py`.

1. `test_search_open_browser_creates_background_cdp_target`
   - Start an owned fake CDP HTTP/websocket server.
   - `/json/version` returns `webSocketDebuggerUrl`.
   - The websocket records the JSON-RPC request.
   - Dispatch `search.open_browser` for Google.
   - Assert the result is ok and preserves `page_opened: true`, `target_url`, and `browser_endpoint`.
   - Assert the fake server did not receive `/json/new`.
   - Assert one websocket request used `method: Target.createTarget`.
   - Assert `params.url` equals the expected search URL.
   - Assert `params.background is True`.

2. `test_search_open_browser_encodes_queries_for_supported_engines`
   - Keep the existing engine matrix.
   - Assert each target URL is encoded exactly as before.
   - Assert each open request uses `Target.createTarget` with `background: true`.
   - Assert no request path is `/json/new`.

3. `test_search_open_browser_reports_cdp_open_failure_with_target_url`
   - Configure the fake CDP websocket to return a JSON-RPC error for `Target.createTarget`.
   - Assert `E_SEARCH_BROWSER_OPEN_FAILED`.
   - Assert `target_url` and `browser_endpoint` remain in the rejection payload.

4. Add a source-shape guard:
   - `scripts/env/tools/search/_impl.py` must not contain `/json/new`.
   - It should reference `Target.createTarget` or the non-activating helper.

### Launcher Tests

Modify `tests/test_browser_cockpit_launcher.py`.

1. Update fake ready-page helpers:
   - Replace the fake `/json/new?about:blank` success path with a fake background opener command.
   - The fake command records `Target.createTarget` with `url: about:blank` and `background: true`.
   - It updates the fake `/json/list` state to include `about:blank` only when configured to allow background page creation.

2. Update ready-page tests:
   - `test_browser_ensure_rejects_endpoint_only_when_background_ready_page_creation_fails`
   - Assert launcher returns non-zero.
   - Assert Codex MCP setup does not run.
   - Assert the fake background opener was attempted.
   - Assert `/json/new?about:blank` was not called.

3. Update timeout/probe test:
   - Keep timeout assertions for `/json/version` and `/json/list` curl probes.
   - Assert the ready-page creation path is the fake background opener, not `/json/new`.

4. Update intro-only repair test:
   - Assert `Target.createTarget` happens before MCP/Codex setup.
   - Assert the fake state now contains an `about:blank` page.
   - Assert no GET or PUT `/json/new?about:blank` call exists.

5. Update source-shape guard:
   - `tools/launcher/browser_cockpit.sh` must not contain `/json/new?about:blank`.
   - It must invoke `tools/launcher/cdp_background_page.py` through a configurable helper path.
   - It must still reference `chrome_devtools_cockpit_proxy.py`.

### Broader Launcher Tests

Modify the existing relevant assertions in `tests/test_buddyswitch_launcher.py`.

1. For required-buddy intro-only repair:
   - Assert `Target.createTarget` for `about:blank` occurs before the first Codex argv capture.
   - Assert no `/json/new?about:blank` call exists.

2. For endpoint-only rejection:
   - Assert background page creation was attempted.
   - Assert no `/json/new?about:blank` call exists.
   - Assert Codex does not launch.

3. Keep existing proxy registration assertions intact.

## Verification Commands

Run in this order:

```bash
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_creates_background_cdp_target -v
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_encodes_queries_for_supported_engines -v
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_reports_cdp_open_failure_with_target_url -v
python3 -m unittest tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_ensure_rejects_endpoint_only_when_background_ready_page_creation_fails -v
python3 -m unittest tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_ensure_uses_bounded_timeouts_for_cdp_probes -v
python3 -m unittest tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_ensure_repairs_intro_only_with_background_target -v
```

Then run:

```bash
python3 -m unittest tests.test_search_env_tool -v
python3 -m unittest tests.test_browser_cockpit_proxy -v
python3 -m unittest tests.test_browser_cockpit_launcher -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_buddy_repairs_intro_only_browser_before_codex_launch -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_buddy_rejects_endpoint_only_browser_before_codex -v
```

Run the resource check after focused runs and before broader runs:

```bash
pgrep -fl 'chrome_devtools_cockpit_proxy|fake_upstream.py|fake-chrome|buddyswitch.*app-server|runtime_broker' || true
```

If focused and residual checks are clean, run:

```bash
python3 -m unittest tests.test_buddyswitch_launcher -v
pgrep -fl 'chrome_devtools_cockpit_proxy|fake_upstream.py|fake-chrome|buddyswitch.*app-server|runtime_broker' || true
```

Only run `python3 -m unittest discover tests -v` after the focused and broader launcher suite are clean.

## Review Checklist

- `search.open_browser` has no direct `/json/new` page-open path.
- Launcher ready-page creation has no direct `/json/new?about:blank` path.
- `Target.createTarget` requests are behavior-tested with `background: true`.
- Existing output contracts and launcher MCP proxy registration still hold.
- Tests own fake servers and subprocesses and leave no matching residual processes.
- Changed files stay inside the memo-approved scope.
