# Web User Actor Message Network Phase 2 Execution Prompt

Execute `docs/memo/2026-06-23-web-user-actor-message-network.md` using:

- Test plan: `docs/spec/2026-06-23-web-user-actor-message-network-test-plan.md`
- Development plan: `docs/spec/2026-06-23-web-user-actor-message-network-development-plan.md`

Follow the plan step by step:

1. Write the focused failing tests before production changes.
2. Confirm the new tests fail for the expected missing behavior.
3. Factor existing message-owned send semantics; do not duplicate create/reachability/deliver/cleanup logic in web code.
4. Allow `user` only as an external message participant. Do not add `user` to manifest roles or launcher role startup.
5. Implement `tools/launcher/web_user_actor.py` as the only web-user adapter and reply sink owner.
6. Add `POST /api/instances/<actor_id>/messages` in `web_management.py` as HTTP adaptation only.
7. Switch the live web UI selected-instance send path to `/messages`.
8. Keep daemon, central-daemon, mailbox, daemon-client, and trigger modules generic; do not add web/user/message business branches there.
9. After each meaningful block, run the focused tests named in the plan.
10. If a test fails unexpectedly, identify root cause before changing code.
11. If verification starts any daemon, app-server, broker, browser, persistent process, socket, or port, stop and prove cleanup before broad verification.
12. Run the broader verification commands from the plan only after focused tests pass.
13. Perform a final review against the memo hard gates, the test plan, and the development plan.

Completion requires focused and broader verification to pass, the final review to show no boundary drift, and no process/socket/resource residue from the test loop.
