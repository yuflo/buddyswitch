# Track Comment Added Daemon State Root Fix Phase 2 Execution Prompt

Execute `docs/memo/2026-06-12-track-comment-added-daemon-state-root-fix.md` using:

- Test plan: `docs/spec/2026-06-12-track-comment-added-daemon-state-root-fix-test-plan.md`
- Development plan: `docs/spec/2026-06-12-track-comment-added-daemon-state-root-fix-development-plan.md`

Follow the plan step by step:

1. Write or select the test that defines each behavior.
2. When a new test can fail first, run it and confirm the failure is the expected missing behavior.
3. Implement the smallest direct daemon runtime setup change.
4. After each meaningful modification block, run the focused verification named in the plan.
5. If verification fails, identify the root cause before changing code.
6. After focused tests pass, run broader relevant verification.
7. Delete or replace any old logic that keeps daemon object reads unbound to `<shared-root>/state`.
8. Keep one single runtime object-read path: repositories read from `BUDDYSWITCH_STATE_ROOT=<shared-root>/state`.
9. Do not add fallback object root lookup, compatibility switches, adapters, or Track-comment-specific state binding.
10. Do not weaken `TrackCommentAddedHandler._comment(...)`; a genuinely missing exact comment row must still fail.
11. Do not edit `buddyswitch/objects/**`, `buddyswitch/local/private/**`, or real runtime instance state.
12. If a test starts a daemon, service, persistent process, socket, or port, stop, shrink the verification scope, and add lifecycle cleanup before continuing.
13. If a high-risk issue or required compatibility layer appears, stop and ask the user.

Completion requires focused and broader verification to pass, no process/resource leakage from the test loop, and final review showing no dual path or fallback behavior.
