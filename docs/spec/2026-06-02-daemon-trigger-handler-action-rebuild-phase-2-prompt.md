# Phase 2 Execution Prompt

Use this prompt in worktree `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`.

```text
Continue in worktree /Users/chen/Dev/buddyswitch/.worktrees/fea-daemon only. Do not touch main.

Goal: execute the full daemon trigger-handler-action rebuild described by:
- docs/spec/2026-06-02-daemon-trigger-handler-action-rebuild-test-plan.md
- docs/spec/2026-06-02-daemon-trigger-handler-action-rebuild-development-plan.md

Authoritative memos:
- docs/memo/2026-06-02-daemon-trigger-handler-action-dispatch-rebuild.md
- docs/memo/2026-06-02-daemon-api-surface-cleanup-task.md
- docs/memo/2026-06-02-trigger-handler-action-business-adjustments-task.md

Do not use docs/memo/2026-06-02-daemon-message-async-routing-task.md as implementation source of truth.

Rules:
- Follow SHARP forward: replace split dispatch with trigger -> handler -> action; do not keep old methods as fallback.
- Use TDD for every behavior change: write the failing test, run it, implement the smallest direct change, rerun it.
- Keep daemon core business-neutral and central daemon reachability-only.
- Keep task input TUI outside daemon dispatch.
- Business handlers may call only parent_activity, submit_parent_prompt, and submit_side_triage_prompt.
- Replace mailbox.parent_required with mailbox.local_trigger(type="message.parent_required").
- Respect docs/bitter/2026-05-26-test-resource-lifecycle-principles.md. Avoid broad service-starting suites unless
  lifecycle cleanup and residual checks are proven.
- Do not edit buddyswitch/objects/** or buddyswitch/local/private/** directly.

Execution loop:
1. Read the two spec files, the three authoritative memos, the resource lifecycle note, and current implementation.
2. Execute Tasks 1 through 8 in the development plan in order.
3. For each task, run the focused test before implementation and confirm the expected failure.
4. Implement the smallest direct change to pass the focused test.
5. Run the focused test again and keep it green before moving to the next task.
6. After all focused tasks pass, run the broader non-service regression listed in the test plan.
7. Run residual resource checks before and after any service-starting test group.
8. Perform a final review against every success criterion in the three memos and both spec files.

Completion requires:
- all focused tests pass;
- broader relevant regression passes, or any blocked command is reported with exact command and blocker;
- no remaining production use of handle_notification, handle_signal, handle_parent_required, mailbox.parent_required,
  interrupt_and_submit_parent_prompt, start_or_reuse_side_triage, or handler-side require_side_thread;
- final review finds no unmet Phase 1-3 requirement;
- final response states changed files, verification commands, and remaining risk.
```

## Prompt Self-Review

- The prompt is short and executable.
- It references only the new spec files and the three authoritative memos.
- It requires test-first execution, all focused tests, broad non-service regression, resource checks, and final review.
- It explicitly rejects the old transition surfaces and stale async-routing memo as implementation authority.
