# Phase 2 Execution Prompt

Use this prompt in worktree `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`.

```text
Continue in worktree /Users/chen/Dev/buddyswitch/.worktrees/fea-daemon only. Do not touch main.

Goal: implement docs/spec/2026-06-02-daemon-message-async-routing-development-plan.md against docs/spec/2026-06-02-daemon-message-async-routing-test-plan.md and docs/memo/2026-06-02-daemon-message-async-routing-task.md.

Rules:
- Follow SHARP forward: replace the old unconditional message parent-submit path; do not preserve it as compatibility behavior.
- Use TDD: write each meaningful failing test first, run it to confirm the expected failure, implement the smallest direct change, then rerun the focused test.
- Keep daemon core business-neutral. Message semantics and prompts stay in message_available_handler. Central daemon remains reachability-only.
- Respect docs/bitter/2026-05-26-test-resource-lifecycle-principles.md. Avoid broad service-starting suites until focused fake-client tests pass and resources are checked.
- Use app-server helper primitives already owned by tools/launcher/app_server.py. Do not call Codex internals or codex-remote directly.
- Do not edit buddyswitch/objects/** or old private runtime paths directly.

Execution loop:
1. Read the memo, test plan, development plan, and current implementation.
2. Implement Task 1 through Task 8 in order.
3. For every task, run the focused test named in the plan before and after implementation.
4. If a focused test failure exposes a real mismatch, fix the root cause instead of weakening the test.
5. After focused tests pass, run the broader non-service regression listed in the test plan.
6. Run the residual resource checks before and after any service-starting test group.
7. Perform a final review against every requirement in the memo and both spec files.

Completion requires:
- all focused tests pass;
- broader relevant regression passes or any blocked command is reported with exact blocker;
- final review finds no unmet Phase 1-3 requirement;
- final response states changed files, verification commands, and remaining risk.
```

## Prompt Self-Review

- The prompt is short enough to execute directly.
- It references the authoritative memo, test plan, development plan, and resource lifecycle warning.
- It requires tests to pass before completion and requires final review.
- It preserves the full task scope without asking for a transition or compatibility path.
