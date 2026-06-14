# Inbound Task Tips InnerTUI Upgrade Phase 2 Execution Prompt

Execute `docs/memo/2026-06-14-inbound-task-tips-inner-tui-upgrade.md` using:

- Test plan: `docs/spec/2026-06-14-inbound-task-tips-inner-tui-upgrade-test-plan.md`
- Development plan: `docs/spec/2026-06-14-inbound-task-tips-inner-tui-upgrade-development-plan.md`

Follow the plan step by step:

1. Write prompt behavior tests before changing renderers.
2. Confirm new prompt tests fail for missing reviewed content or missing section helpers.
3. Replace large prompt literals with small private helpers inside the existing domain modules only.
4. Keep public renderer names and signatures unchanged.
5. Keep handler routing and env-tool semantics unchanged.
6. After each meaningful prompt-renderer block, run the focused tests named in the plan.
7. If a test fails unexpectedly, identify the root cause before changing code.
8. Run the broader relevant message env-tool verification after focused prompt tests pass.
9. Delete the replaced large prompt-literal path; final prompt construction should have one sectioned domain-local path per domain.
10. Do not add `additionalContext`, a generic prompt framework, rule engine, DSL, compatibility switch, or alternate prompt mode.
11. Do not add Track comment `needs_parent`, `absorbed`, or `replied` semantics.
12. Do not edit task tool schemas, task action policy, resource locks, `task.capture`, `message.send`, `message.mark`, `track.add_comment`, `track.list_comments`, or `track.resolve_comment_thread`.
13. If verification starts a daemon, service, persistent process, socket, or port, stop, shrink the verification scope, and add lifecycle cleanup before continuing.
14. If a high-risk issue or required compatibility layer appears, stop and ask the user.

Completion requires focused and broader verification to pass, no process/resource leakage from the test loop, and final review showing this remained a prompt-only rebuild with no semantic drift.
