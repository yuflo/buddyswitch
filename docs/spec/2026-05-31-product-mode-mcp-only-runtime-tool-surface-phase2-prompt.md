# Phase 2 Execution Prompt

Use this prompt in worktree `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`.

```text
Execute the plan in docs/spec/2026-05-31-product-mode-mcp-only-runtime-tool-surface-development-plan.md.

Constraints:
- Work only in the fea-daemon worktree. Do not touch main.
- Follow SHARP: solve the current bottleneck, take the shortest validated loop, avoid speculative abstraction, replace old baggage directly, and verify every meaningful change.
- Follow docs/bitter/2026-05-26-test-resource-lifecycle-principles.md. Do not run broad service-starting tests until focused tests pass and lifecycle is clean.
- Use TDD for behavior changes: write or update the failing test first, run it and confirm the expected failure, implement the smallest direct fix, then rerun.
- Do not preserve env CLI as a product-mode runtime action fallback. Keep only explicit admin/debug or runtime diagnostic paths.
- Do not push MCP/CLI transport checks into per-tool service packages.
- Tool feedback must expose semantic next-action options, not hardcoded workflow scripts.

Loop:
1. Read the memo and both spec docs:
   - docs/memo/2026-05-31-product-mode-mcp-only-runtime-tool-surface.md
   - docs/spec/2026-05-31-product-mode-mcp-only-runtime-tool-surface-test-plan.md
   - docs/spec/2026-05-31-product-mode-mcp-only-runtime-tool-surface-development-plan.md
2. Execute the development plan task by task.
3. For each task:
   - update the relevant tests first;
   - run the focused test and confirm RED;
   - implement the minimal direct change;
   - run the focused test and confirm GREEN;
   - do not move to the next task while the focused test is failing.
4. After all tasks, run the broad verification command from the test plan.
5. Run the residual process check from the test plan.
6. Perform a review against the functional requirements FR1-FR14.

Completion requires:
- all focused tests pass;
- the broad relevant verification passes or any intentionally narrowed scope is justified by the resource lifecycle principle;
- residual process check is clean or shows only unrelated pre-existing user processes;
- review confirms every functional requirement has evidence.

If a test starts leaking processes, or the implementation requires changing product semantics outside this plan, stop and ask the user.
```
