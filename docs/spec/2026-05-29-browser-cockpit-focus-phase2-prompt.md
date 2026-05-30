# Phase 2 Execution Prompt

Work in `/Users/chen/Dev/buddyswitch/.worktrees/fea-skill` only.

Implement `docs/spec/2026-05-29-browser-cockpit-focus-development-plan.md` exactly enough to satisfy `docs/spec/2026-05-29-browser-cockpit-focus-test-plan.md`.

Rules:

1. Do not touch main or any checkout outside this worktree.
2. Follow TDD: write the focused failing test first, run it, then implement the smallest direct change.
3. Do not preserve raw `chrome-devtools-mcp` as a Codex-visible `chrome-devtools-cockpit` registration path.
4. Keep the public MCP name `chrome-devtools-cockpit`.
5. Keep changes inside launcher/tool implementation and tests. Do not modify skill, daemon, runtime actor profile, or auth layers.
6. Do not start real Chrome, real Codex, broad daemons, or service suites until focused tests pass.
7. Before any broad test run, run the residual process check from the test plan.
8. If a test starts a subprocess, it must own process exit and cleanup.
9. Completion requires focused tests, relevant broad launcher tests, final review, and clean residual process check.

Execute in this loop:

```bash
python3 -m unittest tests.test_browser_cockpit_proxy -v
python3 -m unittest tests.test_browser_cockpit_launcher -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_repairs_stale_cockpit_mcp_browser_url -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_buddy_wires_instance_env_and_lifecycle -v
pgrep -fl 'chrome_devtools_cockpit_proxy|fake_upstream.py|fake-chrome|buddyswitch.*app-server|runtime_broker' || true
```

After those pass cleanly, run the broader relevant suite:

```bash
python3 -m unittest tests.test_buddyswitch_launcher -v
pgrep -fl 'chrome_devtools_cockpit_proxy|fake_upstream.py|fake-chrome|buddyswitch.*app-server|runtime_broker' || true
```

Only run `python3 -m unittest discover tests -v` after the broad launcher suite and residual check are clean.
