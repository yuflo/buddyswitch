# BuddySwitch IM External Reply Loop Test Plan

Status: Phase 1 focused plan artifact for `docs/memo/buddyswitch-im-external-reply-loop-task-memo.md`.

## Current Bottleneck

The user-visible contract is:

```text
external input -> Central IM durable send -> real actor runtime wake -> actor message.send(reply_to=...) -> external cursor event -> external fetch/display reply
```

Layer-only tests are insufficient. At least one acceptance test must cross the HTTP/product/actor-client/event-fetch boundary.

## Resource Safety

Use focused tests before any broad run. Avoid starting long-lived daemons unless the focused in-process tests are green.

Focused commands:

```bash
python -m pytest tests/test_im_external_reply_loop.py tests/test_message_tool_im_client.py tests/test_im_http_router.py tests/test_im_product_core.py tests/test_im_wake_handler.py tests/test_web_management.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py -q
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Only after those pass, inspect residue:

```bash
pgrep -fl "buddyswitch|central_daemon|runtime_broker|app_server|fake_codex|chrome" || true
find /tmp -maxdepth 3 \( -name '*buddyswitch*' -o -name '*central-daemon*' \)
```

## Required Coverage

### End-To-End Acceptance

`tests/test_im_external_reply_loop.py::test_external_send_actor_reply_to_external_visible_via_cursor`

- Register an external participant through `/api/im/external-participants`.
- Send external -> actor through `/api/im/messages`.
- Assert durable delivery and real wake callback request.
- Reply as the actor with `ActorImClient.send({"content": "pong", "reply_to": original_message_id})` and no `target_actor_address`.
- Read external `/api/im/events` from the send cursor.
- Fetch the reply with `/api/im/messages/{message_id}` and assert content/reply linkage.

### Runtime Wake Bridge

- `tests/test_im_external_reply_loop.py::test_wake_bridge_submits_local_im_trigger_to_target_mailbox`
- `tests/test_im_external_reply_loop.py::test_wake_bridge_reaches_real_mailbox_socket_and_im_handler`

- Validate `im.message.created` payload ids.
- Check central reachability.
- Resolve `daemon_mailbox_socket`.
- Submit `mailbox.local_trigger` with ids only and `source_context={"source":"central_im"}`.
- Never include message content.
- Prove the helper can reach an actual mailbox socket and drive the `ImMessageCreatedHandler` runtime prompt path.

Offline target coverage:

- `target_not_online` is returned.
- No mailbox request is attempted.

### Actor Reply-To-External

`tests/test_message_tool_im_client.py::test_actor_can_reply_to_external_origin_message_with_reply_to_only`

- Original external -> actor message creates actor-visible state.
- Actor reply with only `reply_to` derives the external target from the direct conversation.
- Reply remains in the same conversation.
- The original actor-visible message state becomes `replied`.

### Prompt And Tool Contract

- `tests/test_im_wake_handler.py` asserts parent/side wake prompts tell actors to use `message__get`, optional `message__conversation`, and `message__send(content=..., reply_to=...)`.
- `tests/test_env_tool_schema_contract.py` asserts `message.send` requires only `content`; `target_actor_address` is only required for new actor-directed messages.
- `tests/test_env_tool_semantic_contract.py` asserts live tool language describes Central IM participants/conversations/messages/events and keeps the Track-comment boundary explicit.

### Subscription And Conversation Reads

- `tests/test_im_product_core.py::test_read_im_events_waits_for_new_visible_events_until_timeout` proves `wait_ms` long-poll semantics.
- `tests/test_im_http_router.py` proves `GET /api/im/conversations/direct?kind=actor&role_id=...&actor_id=...` delegates to product core.

### Web UI Receive Loop

`node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js`

- Production assets include `/api/im/events` and `/api/im/messages/{id}` fetch paths.
- UI has a compact `im-conversation` render target.
- State helpers record sent messages, actor replies, delivery status, wake status, and reply ids.
- External echo events are ignored by the reply renderer.

### Manual Smoke Harness

`tmp/im_reply_console.py` is not a BuddySwitch product feature, official CLI, or stable public interface. It is a local manual test harness for the external reply loop and stays under ignored `tmp/`.

Manual help check:

```bash
python tmp/im_reply_console.py --help
```

Manual smoke after focused tests:

```bash
./buddyswitch-codex web --port 8765
python tmp/im_reply_console.py --actor-id <actor_id> --role <role_id> --base-url http://127.0.0.1:8765
```

Expected:

- `[sent] msg-... delivery=accepted wake=submitted`
- `[reply] role/actor...: ...`

## Cleanup Searches

```bash
rg "act-user-local|web-user|send_from_web_user|WebUserActorRuntime|/api/messages/send" tools scripts tests
rg "message.available" tools scripts tests
```

Expected:

- No active external reply loop surface uses fake web-user actor, old send route, or `message.available`.
- Remaining `message.available` hits, if any, must be generic legacy daemon-test naming outside the active Central IM path.

## Self-Review

- The test plan starts from functional requirements rather than current implementation details.
- The acceptance guard crosses the critical handoffs.
- Resource-heavy service runs are deferred until focused tests pass.
- No compatibility-forward old path is accepted as final behavior.
