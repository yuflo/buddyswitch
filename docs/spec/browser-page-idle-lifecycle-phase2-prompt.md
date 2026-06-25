# Browser Page Idle Lifecycle Phase 2 Prompt

Use this prompt in `fea-tool` to execute the test and development plan:

```text
Work in /Users/chen/Dev/buddyswitch/.worktrees/fea-tool.

Implement docs/spec/browser-page-idle-lifecycle-development-plan.md against docs/spec/browser-page-idle-lifecycle-test-plan.md and docs/memo/2026-06-25-browser-page-idle-lifecycle.md.

Rules:
- Follow AGENTS.md sharp-forward guidance.
- Follow docs/bitter/2026-05-26-test-resource-lifecycle-principles.md; use focused tests before broad suites and inspect resource residuals after service-starting tests.
- Use TDD whenever practical: add the behavior test, verify it fails for the right reason, implement the smallest direct code change, verify it passes.
- Do not preserve the old TTL/notify/expiry_policy model as a compatibility path.
- Do not add actor-facing TTL parameters or browser-specific daemon core state.
- Completion requires all focused browser idle lifecycle tests, the broader relevant suite, JS tests, and final review to pass.

Loop:
1. Read the memo, test plan, development plan, and relevant code.
2. Add or update one behavior test from the test plan.
3. Run the focused test and confirm the expected failure.
4. Implement the smallest direct change.
5. Run the focused test until it passes.
6. Repeat until the plan is implemented.
7. Run the focused browser idle lifecycle command.
8. Run broad verification only after focused tests pass and cleanup looks safe.
9. Review the final diff against the memo and plans.
10. Report changed files, verification commands, and remaining risk.
```
