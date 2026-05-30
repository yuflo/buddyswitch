# Phase 2 Execution Prompt

Work only in `/Users/chen/Dev/buddyswitch/.worktrees/fea-skill`.

Execute `docs/spec/2026-05-29-browser-owned-nonactivating-page-open-development-plan.md` until it satisfies `docs/spec/2026-05-29-browser-owned-nonactivating-page-open-test-plan.md`.

Rules:

1. Do not touch `main` or any checkout outside this worktree.
2. Follow TDD: write the focused failing test, run it, then implement the smallest direct change.
3. Do not keep `/json/new?...` as a BuddySwitch-owned page-open path.
4. Keep headed browser support; do not solve this by switching to headless.
5. Keep `chrome-devtools-cockpit` registered through the existing BuddySwitch proxy.
6. Keep changes inside `tools/launcher/**`, `scripts/env/tools/search/**`, directly related `tests/**`, and `docs/spec/**` or `docs/memo/**`.
7. Do not modify skill, daemon, runtime actor profile, auth, permission, broker, or app-server protocol layers.
8. Do not start real Chrome, real Codex, broad daemons, or service suites until focused tests pass.
9. If a test starts a subprocess or fake server, the test must own shutdown and cleanup.
10. Before broader verification, run the residual process check.
11. Completion requires focused tests, relevant broader launcher tests, final source/behavior review, and a clean residual process check.

Execute in this loop:

```bash
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_creates_background_cdp_target -v
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_encodes_queries_for_supported_engines -v
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_reports_cdp_open_failure_with_target_url -v
python3 -m unittest tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_ensure_rejects_endpoint_only_when_background_ready_page_creation_fails -v
python3 -m unittest tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_ensure_uses_bounded_timeouts_for_cdp_probes -v
python3 -m unittest tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_ensure_repairs_intro_only_with_background_target -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_buddy_repairs_intro_only_browser_before_codex_launch -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_buddy_rejects_endpoint_only_browser_before_codex -v
pgrep -fl 'chrome_devtools_cockpit_proxy|fake_upstream.py|fake-chrome|buddyswitch.*app-server|runtime_broker' || true
```

After those pass cleanly, run:

```bash
python3 -m unittest tests.test_search_env_tool -v
python3 -m unittest tests.test_browser_cockpit_proxy -v
python3 -m unittest tests.test_browser_cockpit_launcher -v
python3 -m unittest tests.test_buddyswitch_launcher -v
pgrep -fl 'chrome_devtools_cockpit_proxy|fake_upstream.py|fake-chrome|buddyswitch.*app-server|runtime_broker' || true
```

Only run `python3 -m unittest discover tests -v` after focused and broader launcher verification are clean.
