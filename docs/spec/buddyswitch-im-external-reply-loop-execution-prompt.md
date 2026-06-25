# BuddySwitch IM External Reply Loop Execution Prompt

Use this prompt in `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`.

```text
Implement the external-user Central IM reply loop described by:
- docs/memo/buddyswitch-im-external-reply-loop-task-memo.md
- docs/spec/buddyswitch-im-external-reply-loop-test-plan.md
- docs/spec/buddyswitch-im-external-reply-loop-development-plan.md
- docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md
- docs/bitter/2026-06-25-built-in-product-interface-principles.md
- docs/bitter/2026-06-02-residue-cleanup-principles.md

Rules:
1. Follow AGENTS.md and SHARP forward development.
2. Use TDD for behavior changes: write the focused failing test, run it, implement, rerun.
3. Keep product semantics in scripts/env Central IM product code.
4. Launcher code may parse HTTP, list actors, and wake runtime; it must not own participant/conversation/message/event/cursor rules.
5. Do not preserve or reintroduce fake web-user actor, /api/messages/send, send_from_web_user, WebUserActorRuntime, or message.available as IM delivery.
6. Avoid broad or service-heavy tests until focused in-process tests pass.

Execution:
1. Start with tests/test_im_external_reply_loop.py acceptance coverage.
2. Implement daemon_client.wake_im_actor and delegate WebManagement/ToolContext to it.
3. Implement message.send(reply_to=...) target derivation for actor replies to external participants.
4. Update wake prompts and live message tool schema/semantic text.
5. Implement /api/im/events wait_ms and /api/im/conversations/direct.
6. Add Web UI event polling/fetch rendering.
7. Add tmp/im_reply_console.py only as an ignored local manual smoke harness, not an official BuddySwitch feature.
8. Run:
   - python -m pytest tests/test_im_external_reply_loop.py tests/test_message_tool_im_client.py tests/test_im_http_router.py tests/test_im_product_core.py tests/test_im_wake_handler.py tests/test_web_management.py -q
   - node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
   - python tmp/im_reply_console.py --help
   - rg "act-user-local|web-user|send_from_web_user|WebUserActorRuntime|/api/messages/send" tools scripts tests
   - rg "message.available" tools scripts tests
9. Review against the memo done criteria before claiming completion.

Stop only for product semantics, external API commitment, security/auth, irreversible data-shape, or resource-safety issues that cannot be resolved locally.
```

Self-review:

- The prompt names the focused authoritative memo and bitter lessons.
- It is concise enough to hand to another development run.
- The final gate includes acceptance, UI, smoke-client, and residue checks.
