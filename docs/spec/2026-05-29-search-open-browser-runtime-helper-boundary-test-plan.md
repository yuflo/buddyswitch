# Search Open Browser Runtime Helper Boundary Test Plan

## Goal

`search.open-browser` must work from a product runtime sparse workspace. Its page-open helper must live under `scripts/env/`, which is projected into the runtime workspace, and it must not depend on launcher-only `tools/launcher/**`.

## Functional Requirements

1. `search.open-browser` opens the planned search URL through Chrome DevTools `Target.createTarget` with `background: true`.
2. `search.open-browser` keeps the existing success contract: `target_url`, `browser_endpoint`, `page_opened: true`, and the `chrome-devtools-cockpit` follow-up hint.
3. `search.open-browser` keeps the existing rejection contract for missing, invalid, unreachable, or failing browser endpoints, including `E_SEARCH_BROWSER_OPEN_FAILED`, `target_url`, and `browser_endpoint` when target creation fails.
4. `scripts/env/tools/search/_impl.py` must not contain `/json/new`.
5. `scripts/env/tools/search/_impl.py` must not reference `tools/launcher`.
6. `scripts/env/tools/search/_impl.py` must execute `scripts/env/cdp_background_page.py`.
7. `scripts/env/cdp_background_page.py` must exist and implement the non-activating CDP helper.
8. `tools/launcher/browser_cockpit.sh` must default `BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL` to `${BUDDYSWITCH_REPO_ROOT}/scripts/env/cdp_background_page.py`.
9. `tools/launcher/browser_cockpit.sh` must not reference `tools/launcher/cdp_background_page.py` or `/json/new?about:blank`.
10. `tools/launcher/cdp_background_page.py` must be removed to avoid two long-lived helper paths.
11. Runtime execution sparse checkout paths must include `scripts/env/`.
12. Runtime execution forbidden entries must include `tools`.
13. A test must prove the search helper path is inside the included `scripts/env/` runtime surface and outside forbidden `tools/`.
14. Existing `chrome-devtools-cockpit` proxy registration must still point at `tools/launcher/chrome_devtools_cockpit_proxy.py`.
15. Tests must not start real Chrome, real Codex, app-server, daemon, broker, or other long-lived services. Fake HTTP/CDP websocket servers and fake helper subprocesses must be owned by the test and cleaned up.

## Focused Test Design

### Search Tool Tests

Modify `tests/test_search_env_tool.py`.

1. Strengthen `test_search_source_has_no_direct_json_new_page_open`.
   - Assert `scripts/env/tools/search/_impl.py` does not contain `/json/new`.
   - Assert it does not contain the path components `"tools"` or `"launcher"` for helper resolution.
   - Assert it does not contain `tools/launcher`.
   - Assert it contains `scripts`, `env`, and `cdp_background_page.py`.
   - Assert `scripts/env/cdp_background_page.py` exists.
   - Assert `tools/launcher/cdp_background_page.py` does not exist.

2. Keep behavior tests that use the owned fake CDP HTTP/websocket server:
   - `test_search_open_browser_creates_background_cdp_target`
   - `test_search_open_browser_encodes_queries_for_supported_engines`
   - `test_search_open_browser_reports_cdp_open_failure_with_target_url`

These behavior tests prove the runtime helper still sends `Target.createTarget` with the correct URL and `background: true`.

### Launcher Tests

Modify `tests/test_browser_cockpit_launcher.py`.

1. Strengthen `test_browser_launcher_source_is_instance_only`.
   - Assert the launcher script references `scripts/env/cdp_background_page.py`.
   - Assert it does not reference `tools/launcher/cdp_background_page.py`.
   - Assert it still references `chrome_devtools_cockpit_proxy.py`.
   - Assert it does not contain `/json/new?about:blank`.

2. Keep ready-page behavior tests:
   - `test_browser_ensure_rejects_endpoint_only_when_background_ready_page_creation_fails`
   - `test_browser_ensure_uses_bounded_timeouts_for_cdp_probes`
   - `test_browser_ensure_repairs_intro_only_with_background_target`

These tests continue to override `BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL` with a fake executable, so no real browser starts.

### Runtime Sparse Boundary Test

Modify `tests/test_buddyswitch_launcher.py`.

1. Add a source-level boundary regression test near the execution workspace tests.
   - Read `tools/launcher/workspace.sh`.
   - Assert `buddyswitch_workspace_execution_sparse_paths` includes `scripts/env/`.
   - Assert `buddyswitch_workspace_execution_forbidden_entries` includes `tools`.
   - Assert `scripts/env/tools/search/_impl.py` references `scripts/env/cdp_background_page.py`.
   - Assert `scripts/env/tools/search/_impl.py` does not reference `tools/launcher`.
   - Assert `scripts/env/cdp_background_page.py` exists.
   - Assert `tools/launcher/cdp_background_page.py` does not exist.

2. Keep existing runtime sparse shape tests, but do not broaden into service-starting suites until focused tests pass.

## Verification Commands

Run focused RED checks after test changes:

```bash
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_source_has_no_direct_json_new_page_open -v
python3 -m unittest tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_launcher_source_is_instance_only -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_search_open_browser_helper_stays_inside_runtime_sparse_surface -v
```

Expected before implementation: failures showing the helper still points at `tools/launcher`.

Run focused GREEN checks after implementation:

```bash
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_source_has_no_direct_json_new_page_open -v
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_creates_background_cdp_target -v
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_encodes_queries_for_supported_engines -v
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_reports_cdp_open_failure_with_target_url -v
python3 -m unittest tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_launcher_source_is_instance_only -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_search_open_browser_helper_stays_inside_runtime_sparse_surface -v
```

Then run related suites:

```bash
python3 -m unittest tests.test_search_env_tool -v
python3 -m unittest tests.test_browser_cockpit_launcher -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_instance_start_execution_workspace_is_sparse_runtime_surface -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_buddy_repairs_intro_only_browser_before_codex_launch -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_buddy_rejects_endpoint_only_browser_before_codex -v
```

Before and after broader launcher verification, run:

```bash
pgrep -fl 'chrome_devtools_cockpit_proxy|fake_upstream.py|fake-chrome|buddyswitch.*app-server|runtime_broker' || true
```

Only run the full discovery suite after the focused and related launcher checks are green and residual checks are clean:

```bash
python3 -m unittest discover tests -v
```

## Review Checklist

- `search.open-browser` runtime code has no dependency on `tools/launcher`.
- The only CDP background helper lives at `scripts/env/cdp_background_page.py`.
- Launcher ready-page repair uses the same helper path through the source checkout.
- `tools/launcher/cdp_background_page.py` is gone.
- Behavior tests still prove `Target.createTarget` and `background: true`.
- Sparse runtime tests prove the helper lives inside included runtime files and outside forbidden launcher files.
- Residual process checks show no leaked browser, broker, app-server, or proxy processes.
