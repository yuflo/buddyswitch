# Env Tool Native Discovery Execution Prompt

Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`

Execute these specs:

- `docs/spec/2026-05-30-env-tool-native-discovery-test-plan.md`
- `docs/spec/2026-05-30-env-tool-native-discovery-development-plan.md`

Rules:

1. Stay in this worktree. Do not touch main.
2. Use TDD for every behavior change: write focused failing test, observe it fail, implement the smallest direct fix, rerun focused test.
3. Implement A+ directly. Do not create a domain gateway, contextual pack engine, handwritten native action manifest, per-role tool pack, or MCP action switch.
4. Native MCP specs must be generated from `env.tool_runtime.registry` and per-tool `ActionDefinition`.
5. The MCP server must be generic: `tools/list` from projection, `tools/call` decode native name and dispatch through the existing runtime broker as `env.tool`.
6. Keep context discovery and CLI as fallback/diagnostic surfaces. Do not remove them.
7. Keep resource lifecycle safe. Prefer pure projection/server/prose tests first. Before broad service tests, inspect cleanup. After service-starting tests run:

```bash
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex|chrome_devtools_cockpit_proxy.py" || true
```

8. Completion requires focused tests, relevant broad tests, A+ source audit, and review against the functional requirements.

Execution order:

1. Build native projection tests and implementation.
2. Build generic stdio MCP server tests and implementation.
3. Add product-mode MCP registration tests and implementation.
4. Add prose drift tests and update AGENTS/skills/runtime tips.
5. Run focused verification after each block.
6. Run relevant broad verification and residual process check.
7. Perform final source audit for forbidden A+ shapes.

Final report must state:

- what changed;
- exact tests/commands run and results;
- residual process check result if service tests ran;
- whether all A+ requirements are met;
- remaining risks.
