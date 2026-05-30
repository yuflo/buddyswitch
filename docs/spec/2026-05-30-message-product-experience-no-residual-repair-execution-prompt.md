# Message Product Experience No-Residual Repair Execution Prompt

Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`

Execute:

- `docs/spec/2026-05-30-message-product-experience-no-residual-repair-test-plan.md`
- `docs/spec/2026-05-30-message-product-experience-no-residual-repair-development-plan.md`

Rules:

1. Stay in this worktree; do not touch main.
2. Use TDD for behavior changes: write the focused failing test, observe it fail, implement the smallest direct fix, then rerun the focused test.
3. Do not add old message payload aliases (`to_buddy`, `actor_address`, `message`) or compatibility adapters.
4. Keep `message.list` inbox-only; add `message.conversation` for bidirectional visible context.
5. Keep resource lifecycle safe. Run pure env-tool tests before daemon/launcher tests. After daemon/launcher or real-instance checks, run:

```bash
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex" || true
```

6. If a broad service-starting test leaks processes or sockets, stop and fix lifecycle before expanding.
7. Completion requires focused tests, broad relevant tests, review checklist, and real PM/market path verification or a clearly reported blocker.

Execution order:

1. Fix shared message skill and runtime materialization tests.
2. Fix `message.contacts` sendability and next-action response.
3. Add and implement `message.conversation`.
4. Update context message cues.
5. Add mailbox handler observability to daemon status.
6. Audit/fix product-mode permission entrypoints.
7. Run focused regression, then broader tests, then real PM/market path.
8. Stop/delete test instances or explicitly record retained ones.

Final report must state:

- what changed;
- exact tests/commands run and results;
- residual process check result;
- PM/market verification result or blocker;
- remaining risk.
