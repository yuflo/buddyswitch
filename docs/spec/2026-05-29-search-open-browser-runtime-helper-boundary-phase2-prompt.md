# Phase 2 Execution Prompt

Work only in `/Users/chen/Dev/buddyswitch/.worktrees/fea-skill`.

Execute `docs/spec/2026-05-29-search-open-browser-runtime-helper-boundary-development-plan.md` until it satisfies `docs/spec/2026-05-29-search-open-browser-runtime-helper-boundary-test-plan.md`.

Rules:

1. Do not touch `main` or any checkout outside this worktree.
2. Follow TDD: add the focused failing boundary tests, run them red, then implement the smallest direct change.
3. Do not keep `tools/launcher/cdp_background_page.py` as a wrapper or compatibility path.
4. Do not add `tools/launcher/**` to the product runtime sparse workspace.
5. Keep `search.open-browser` public success and failure contracts unchanged.
6. Keep headed browser support; do not solve this by switching to headless.
7. Keep `chrome-devtools-cockpit` registered through `tools/launcher/chrome_devtools_cockpit_proxy.py`.
8. Keep changes inside `scripts/env/**`, `tools/launcher/browser_cockpit.sh`, directly related `tests/**`, and `docs/spec/**` or `docs/memo/**`.
9. Do not modify skill, daemon, runtime actor profile, auth, permission, broker, app-server protocol, or runtime object layers.
10. Do not start real Chrome, real Codex, broad daemons, or service suites until focused tests pass.
11. If a test starts a subprocess or fake server, the test must own shutdown and cleanup.
12. Before broader verification, run the residual process check.
13. Completion requires focused tests, relevant related tests, source-boundary review, residual process check, and final review against the test plan.

Execution loop:

```bash
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_source_has_no_direct_json_new_page_open -v
python3 -m unittest tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_launcher_source_is_instance_only -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_search_open_browser_helper_stays_inside_runtime_sparse_surface -v
```

After those fail for the expected helper-boundary reason, implement:

- create `scripts/env/cdp_background_page.py`
- change `scripts/env/tools/search/_impl.py` to call `scripts/env/cdp_background_page.py`
- change `tools/launcher/browser_cockpit.sh` to default to `${BUDDYSWITCH_REPO_ROOT}/scripts/env/cdp_background_page.py`
- delete `tools/launcher/cdp_background_page.py`

Then run:

```bash
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_source_has_no_direct_json_new_page_open -v
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_creates_background_cdp_target -v
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_encodes_queries_for_supported_engines -v
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_reports_cdp_open_failure_with_target_url -v
python3 -m unittest tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_launcher_source_is_instance_only -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_search_open_browser_helper_stays_inside_runtime_sparse_surface -v
```

After focused tests pass, run:

```bash
python3 -m unittest tests.test_search_env_tool -v
python3 -m unittest tests.test_browser_cockpit_launcher -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_instance_start_execution_workspace_is_sparse_runtime_surface -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_buddy_repairs_intro_only_browser_before_codex_launch -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_buddy_rejects_endpoint_only_browser_before_codex -v
pgrep -fl 'chrome_devtools_cockpit_proxy|fake_upstream.py|fake-chrome|buddyswitch.*app-server|runtime_broker' || true
rg -n 'tools/launcher/cdp_background_page|/json/new|Target\.activateTarget|Page\.bringToFront' scripts/env tools/launcher
rg -n 'tools/launcher/cdp_background_page' tests/test_search_env_tool.py tests/test_browser_cockpit_launcher.py tests/test_buddyswitch_launcher.py || true
git diff -- docs/spec scripts/env tools/launcher tests
git status --short
```

If any broader test starts leaking processes or the residual check shows BuddySwitch-owned leftovers, stop and fix cleanup before running broader suites.
