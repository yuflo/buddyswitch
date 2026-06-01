# Phase 2 Execution Prompt

Use this prompt in worktree `fea-daemon`.

```text
Continue the Actor Identity Role / Actor rebuild in /Users/chen/Dev/buddyswitch/.worktrees/fea-daemon.

Read first:
- AGENTS.md
- docs/bitter/2026-05-26-test-resource-lifecycle-principles.md
- docs/memo/2026-06-01-actor-identity-role-actor-upgrade-task.md
- docs/spec/2026-06-01-actor-identity-test-plan.md
- docs/spec/2026-06-01-actor-identity-development-plan.md

Goal:
Finish the full rebuild to Actor Identity -> Role / Actor. Do not keep buddy_id, active_buddy, --buddy, public instance_id identity, compatibility aliases, adapters, or dual paths in live runtime code.

Execution rules:
1. Stay in worktree fea-daemon. Do not touch main.
2. Use TDD. For each behavior group, update or add the focused test first, run it, and confirm the expected legacy failure.
3. Implement the smallest direct replacement.
4. Run the focused test until green before moving on.
5. Be careful with tests that start daemons, app servers, brokers, browsers, or fake Codex. Follow docs/bitter/2026-05-26-test-resource-lifecycle-principles.md. Run focused service tests before broad launcher tests, and inspect residual processes after.
6. Keep the product name BuddySwitch. Remove buddy identity concepts from live runtime semantics.
7. Historical docs under docs/memo and docs/bitter may retain old terms. Live code, live contracts, live skills, launcher, schemas, and tests may not.

Implementation order:
1. Actor Identity core.
2. Manifest roles and role auth.
3. Runtime dispatch, ToolContext, and result shape.
4. Central daemon and signals.
5. Message tool and PM-to-PM same-role behavior.
6. Object repositories and env tools.
7. Private workspace, evidence, search.
8. Launcher, MCP registration, and web management.
9. Live skill/contract/profile/docs cleanup.
10. Residual scan and final review.

Required final verification:
- Run the focused test groups in docs/spec/2026-06-01-actor-identity-test-plan.md.
- Run service-sensitive launcher/web checks only after cleanup coverage is confirmed.
- Run residual process inspection after service-sensitive tests:
  ps -axo pid,ppid,command | rg 'buddyswitch|runtime_broker|app_server|central_daemon|chrome|fake_codex' || true
- Run live residual scan:
  rg -n 'buddy_id|active_buddy|--buddy|\bbuddy\b|instance_id' scripts tools framework buddyswitch tests README.md AGENTS.md -g '!docs/**' -g '!**/__pycache__/**'

Completion requires:
- all required tests pass,
- PM-to-PM same-role different-Actor messaging works,
- same-Actor self-send is rejected,
- residual scan has no disallowed live identity hits,
- review finds no compatibility residue.

If a command repeatedly fails because the target behavior or data shape needs a product decision, stop and report the exact blocker with file paths, failing command, and observed output.
```
