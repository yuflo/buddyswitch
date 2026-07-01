# Cockpit Browser Session Upgrade Acceptance

## Accepted Result

BuddySwitch browser use is now cockpit-first:

```text
actor browser work
  -> chrome-devtools-cockpit
  -> browser-session core
  -> Chrome DevTools browser/runtime lifecycle
```

`search.open_browser` remains as a search-specific query-to-URL wrapper. It no longer owns browser ensure, endpoint parsing, direct CDP `Target.createTarget`, page-limit gating, idle TTL registration, or cleanup.

## Material Changes

- `scripts/env/cdp_browser_session.py` now owns deterministic launcher env derivation, browser URL ensure/read helpers, and `open_or_reuse_page()`.
- `tools/launcher/chrome_devtools_cockpit_proxy.py` routes `new_page` through browser-session, rejects blank/isolated unsupported opens locally, and appends browser-session state to actor-visible responses.
- `scripts/env/tools/search/_impl.py` delegates browser mutation to browser-session and keeps only query validation, URL construction, and search-specific ToolResult mapping.
- Role AGENTS, the market contract, and market P0 skills now teach `chrome-devtools-cockpit` as the browser page entrypoint and describe `search__open_browser` only as a query-to-URL wrapper.
- Browser lifecycle tests now restore shared monkeypatches so broad suite order no longer pollutes later CLI/search tests.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_cdp_browser_session.py tests/test_browser_cockpit_proxy.py tests/test_browser_cockpit_launcher.py tests/test_browser_page_expired_handler.py tests/test_browser_lazy_release_integration.py tests/test_search_env_tool.py tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py tests/test_runtime_skills.py tests/test_repo_consistency.py
```

Result: `222 passed, 9 skipped, 878 subtests passed`.

```bash
git diff --check
```

Result: passed.

```bash
rg -n "_ensure_browser_runtime|_browser_endpoint|_reload_instance_payload|_open_browser_page|BUDDYSWITCH_SEARCH_BROWSER_ENSURE_COMMAND|cdp_background_page\\.py|Target\\.createTarget|refresh_page_idle\\(|close_page_target\\(|evaluate_page_open_gate\\(" scripts/env/tools/search/_impl.py
```

Result: no matches.

```bash
rg -n "Start discovery from native `search__open_browser`|use native `search__open_browser` with a focused query, then continue discovery|Use search\\.open_browser for browser-native discovery|Call search\\.open_browser to open the target in the instance browser" tools/launcher/assets/roles framework/contracts buddyswitch/skills/market scripts/env/tools/search
```

Result: no matches.

## Residual Risk

- `tests/test_search_env_tool.py` still contains skipped obsolete direct-CDP search tests as historical context. Active tests and residue scans enforce the new wrapper ownership.
- Browser URL normalization remains intentionally narrow; broad URL canonicalization was outside this upgrade.
