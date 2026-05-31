# Native-First Env Tool Surface Cleanup Execution Prompt

Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`

Execute these specs:

- `docs/spec/2026-05-31-native-first-env-tool-surface-cleanup-test-plan.md`
- `docs/spec/2026-05-31-native-first-env-tool-surface-cleanup-development-plan.md`

Rules:

1. Stay in `fea-daemon`; do not touch `main`.
2. Use TDD for behavior changes: write or update the focused test, observe the expected failure, implement the smallest direct fix, rerun the focused test.
3. Do not add compatibility wrappers, old CLI aliases, tool packs, plugin systems, generated prose catalogs, or a second action manifest.
4. Preserve the registry-owned native MCP path: 9 tools / 40 actions from `env.tool_runtime.registry`.
5. Replace active CLI-first guidance directly. CLI remains only a debug/test harness.
6. Keep resource lifecycle safe. Run pure/prose/native tests first. Run launcher tests only with focused selection and then run:

```bash
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex|chrome_devtools_cockpit_proxy.py" || true
```

Execution order:

1. Confirm native projection/server baseline.
2. Make `message.available` tip native-only.
3. Convert shared runtime skill tests, then rewrite shared skills.
4. Convert AGENTS/contract tests, then rewrite buddy AGENTS and role contracts.
5. Convert Market/search tests, then rewrite Market and role skill runtime wording.
6. Add active-guidance residual scan.
7. Run focused and broad relevant verification.
8. Perform final review against the test plan and residual scans.

Completion requires:

- focused tests pass;
- relevant broad tests pass;
- launcher focused verification passes or any blocker is reported with evidence;
- residual active-guidance scan has no CLI-first hits;
- no residual test-owned daemon/app-server/broker/fake Codex/browser processes after launcher tests;
- final review confirms the 2026-05-31 requirements are met or states concrete unmet risks.

Final report must state:

- what changed;
- exact tests/commands run and results;
- residual process check result if launcher/service tests ran;
- whether active guidance is native-first across all required surfaces;
- remaining risk.
