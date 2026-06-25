# BuddySwitch IM Central Rebuild Execution Prompt

Use this prompt in `fea-daemon` to execute the plan.

```text
Continue in /Users/chen/Dev/buddyswitch/.worktrees/fea-daemon.

Goal: implement the BuddySwitch Central IM rebuild described by:
- docs/memo/buddyswitch-im-gateway-rebuild.md
- docs/memo/buddyswitch-im-central-contract-boundary-review.md
- docs/spec/buddyswitch-im-central-rebuild-test-plan.md
- docs/spec/buddyswitch-im-central-rebuild-development-plan.md

Rules:
1. Follow AGENTS.md and SHARP: solve the current bottleneck, use the shortest validated loop, avoid compatibility-forward dual paths, and verify before claiming completion.
2. Follow docs/bitter/2026-05-26-test-resource-lifecycle-principles.md. Do not run broad service-starting tests until focused lifecycle checks prove cleanup.
3. Use TDD for behavior changes: write or update the failing test, run it and confirm the expected failure, implement the smallest direct change, then rerun focused tests.
4. Rebuild forward. The final path is /api/im/* -> scripts/env IM product core -> state/im/* -> central host wake bridge -> actor runtime. Do not preserve /api/messages/send, fake user actor, send_from_web_user, actor-tool direct repo writes, or message.available as IM delivery.
5. Keep product semantics in scripts/env. Launcher code may parse HTTP, mount routes, list actor reachability, and wake runtime; it must not own participant/message/conversation/event/cursor store rules.

Execution:
1. Start with the first unchecked slice in docs/spec/buddyswitch-im-central-rebuild-development-plan.md.
2. For each slice, run the focused test command from the plan before moving on.
3. After runtime or service-starting tests, inspect residual processes/sockets before broadening verification.
4. When all slices are implemented, run:
   - rg "act-user-local|web-user|send_from_web_user|WebUserActorRuntime|deliver_message_available|/api/messages/send" tools scripts tests
   - rg "message.available" tools scripts tests
   - python -m pytest tests -q
   - node --test tests/*.test.js
5. Perform a final review against the test plan checklist. Completion requires all tests passing, forbidden old-path searches clean or explicitly non-IM, and review acceptance.

If a special problem appears that changes product semantics, external API commitments, security/auth, irreversible data shape, or resource safety, stop and ask the user. Otherwise continue autonomously until the plan is complete and verified.
```

Self-review:

- Prompt is concise enough to hand to another development run.
- Prompt names authoritative docs, commands, TDD loop, resource guard, old-path deletion gates, and final review criteria.
