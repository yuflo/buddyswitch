# Runtime Actor Address Message/Daemon Boundary Execution Prompt

Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-inst`

Task: execute the full plan for `docs/memo/2026-05-29-runtime-actor-address-message-daemon-boundary.md`.

Read first:

- `AGENTS.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
- `docs/memo/2026-05-29-runtime-actor-address-message-daemon-boundary.md`
- `docs/spec/2026-05-29-runtime-actor-address-message-daemon-boundary-test-plan.md`
- `docs/spec/2026-05-29-runtime-actor-address-message-daemon-boundary-development-plan.md`

Rules:

1. Stay in `fea-inst`; do not touch main or another worktree.
2. Use TDD: write the focused failing test, run it red, implement the smallest direct change, run it green.
3. Keep the identity owner narrow: `actor_profile` owns only `RuntimeActorAddress` and profile projection.
4. Keep presence/routing/delivery outside `actor_profile`.
5. Keep durable message creation independent of online notification result.
6. Do not add a plugin system, event bus, routing engine, workflow engine, permission framework, or compatibility dual path.
7. Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.
8. Be careful with resource-heavy tests. Do not run broad service-starting suites until focused unit tests are green. Stop if residual process or resource-limit warning signs appear.

Implementation order:

1. Add and verify `RuntimeActorAddress` tests.
2. Implement `RuntimeActorAddress` and `RuntimeActorProfile.actor_address`.
3. Add and verify daemon presence registry tests.
4. Implement daemon presence registry and daemon registration helpers.
5. Add and verify message notification status/event tests.
6. Implement `ToolContext` daemon access and message notification wiring.
7. Run focused combined verification and boundary search.
8. Run broad verification only after focused proof is green and no resource lifecycle warning signs are present.
9. Review the final diff against the test plan before declaring completion.

Completion requires:

- focused tests pass;
- broad relevant tests pass or any resource blocker is reported with exact command/output;
- boundary search has been inspected;
- durable message behavior and daemon/message boundary tests prove the memo requirements;
- final response states what changed, verification evidence, and remaining risk.
