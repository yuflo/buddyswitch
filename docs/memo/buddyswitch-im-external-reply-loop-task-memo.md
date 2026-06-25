# BuddySwitch IM External Reply Loop Task Memo

Status: gap-closure task memo
Date: 2026-06-25

## Goal

Close the real external-user IM loop:

```text
external input
  -> Central IM send
  -> durable message/event store
  -> real actor runtime wake
  -> actor reads with message tools
  -> actor replies with message.send(reply_to=...)
  -> external subscription receives reply event
  -> external fetches reply message
  -> script/Web UI displays the reply
  -> external user can continue the conversation
```

This is not a one-off script feature. The reusable capability is the Central IM product contract. The Python script and Web UI are clients of that contract.

## Confirmed Architecture Choice

IM product owns:

- external participant identity and bearer token;
- actor/external participant references;
- conversation, message, reply, event cursor, and disposition rules;
- durable JSON store under `state/im/*`;
- HTTP contract shape for register/send/subscribe/fetch/mark.

daemon-service owns:

- actor registry and reachability;
- target actor runtime wake delivery;
- parent/side/innerTUI attention handling after a wake reaches the actor.

The external reply receiving shape should be cursor-backed subscription first:

```text
GET /api/im/events?cursor=...&wait_ms=...
  -> message.created event ids
GET /api/im/messages/{message_id}
  -> message content
```

Client-side callback is built on top of this durable cursor. A server-side webhook platform is not part of this gap closure; it would be a later integration surface after the core loop is proven.

## Code And Spec Confirmation

The following was rechecked before this memo:

| Area | Current evidence | Status |
| --- | --- | --- |
| External participant registration | `tools/launcher/im_http_router.py` handles `POST /api/im/external-participants` and delegates to `message_service.register_external_participant`. | Present |
| External HTTP send | `ImHttpRouter.handle()` maps `POST /api/im/messages` to `message_service.send_im_message(...)`. | Present |
| Durable IM store/events | `scripts/env/services/messages.py` persists conversation, message, message state, and participant-visible events. | Present |
| Wake payload creation | `send_im_message()` builds `type=im.message.created` payload with ids only. | Present |
| Real runtime wake delivery | `tools/launcher/web_management.py::_wake_im_actor()` checks instance status and returns `submitted`; it does not call target mailbox/runtime. | Gap |
| Wake handler | `tools/launcher/im_wake_handler.py` handles `im.message.created` once a trigger reaches the actor daemon. | Present but not reached end-to-end |
| Actor reply to external | Product core can send actor -> external when `to={"kind":"external"}` is supplied, but `scripts/env/tool_runtime/im_client.py::send()` only builds `to` from `target_actor_address`. | Gap |
| Tool schema | `scripts/env/tools/message/tool.py` still requires `target_actor_address` for `message.send`. | Gap |
| External event read | `GET /api/im/events` exists, but `scripts/env/services/messages.py::read_im_events()` deletes `wait_ms`; this is short polling, not long polling. | Partial |
| Web UI receive path | `app.js` stores `imEventCursor`, but does not call `/api/im/events`, fetch messages, or render replies. | Gap |
| HTTP conversation route | Product service has direct conversation read; HTTP router has no `/api/im/conversations/direct` route. | Secondary gap |
| Test plan intent | `docs/spec/buddyswitch-im-central-rebuild-test-plan.md` names `central host wake bridge -> actor runtime parent/side handling`, but current tests do not prove external send -> real wake -> actor tool reply -> external event. | Verification gap |

## Task 1: Add The Missing Acceptance Guard

Purpose: force the implementation to close the actual loop instead of passing isolated route/product tests.

Files:

- Create `tests/test_im_external_reply_loop.py`.
- Update `tests/test_im_http_router.py` only if route helpers need reuse.
- Update `tests/test_message_tool_im_client.py` for actor-client-specific assertions.

Required tests:

- `test_external_send_actor_reply_to_external_visible_via_cursor`
  - register an external participant;
  - external sends `ping` to an actor participant;
  - actor uses `ActorImClient.send({"content": "pong", "reply_to": original_message_id})` with no `target_actor_address`;
  - external reads `/events` from its cursor;
  - external fetches reply message and sees content `pong`.
- `test_external_send_requests_real_runtime_wake_bridge`
  - send external -> actor through HTTP router/WebManagement wake callback;
  - assert the bridge attempts `mailbox.local_trigger` or the selected wake helper, not a fake `submitted` status.
- `test_no_reply_loop_shortcut`
  - assert the acceptance path does not create a fake `role_id=user` actor, does not call old `/api/messages/send`, and does not use `message.available`.

Focused command:

```bash
python -m pytest tests/test_im_external_reply_loop.py tests/test_message_tool_im_client.py tests/test_im_http_router.py -q
```

Expected first result before implementation: at least the reply-to-external and real-wake assertions fail.

## Task 2: Implement A Real IM Runtime Wake Bridge

Purpose: connect durable IM acceptance to the actor daemon runtime.

Preferred shape:

- Add a thin wake helper near runtime/daemon access, for example in `scripts/env/tool_runtime/daemon_client.py` or a focused helper imported by both WebManagement and actor runtime.
- Expose `DaemonAccess.wake_im_actor(payload)` in `scripts/env/tool_runtime/context.py`.
- Replace `WebManagementService._wake_im_actor()` fake status return with the same helper.

Wake bridge behavior:

1. Validate `payload.type == "im.message.created"`.
2. Validate `target_actor_address`, `message_id`, `conversation_id`, and `event_id`.
3. Ask central daemon reachability for the target actor.
4. If target is not online, return:

```json
{"wake_status":"target_not_online","runtime_target":"none","error":"..."}
```

5. Resolve the target actor daemon mailbox socket from the central daemon record.
6. Submit a generic local trigger to the target mailbox:

```text
method: mailbox.local_trigger
actor_address: target actor
type: im.message.created
payload: {message_id, conversation_id, event_id}
origin_id: message_id
correlation_id: wake_id
source_context: {source: central_im}
```

7. Map mailbox/handler response to:

```text
submitted
target_not_online
wake_failed
not_applicable
```

Design constraints:

- Do not use `signal.deliver` as the IM business delivery path.
- Do not invent an external source actor.
- Do not include message content in the wake payload.
- Do not mutate IM disposition from the wake bridge.
- Do not move IM participant/message/conversation rules into launcher code.

Tests:

- Add focused unit tests for the wake helper with fake reachability and fake mailbox request.
- Update `tests/test_web_management.py` so `_wake_im_actor()` proves it calls the real helper.
- Keep `tests/test_im_wake_handler.py` green for parent/side handling once the local trigger arrives.

Focused command:

```bash
python -m pytest tests/test_web_management.py tests/test_im_wake_handler.py tests/test_daemon_mailbox.py tests/test_daemon_core_decoupling.py -q
```

## Task 3: Support Actor Reply-To-External In `message.send`

Purpose: let an actor naturally reply to an external-origin message with `message.send(reply_to=...)`.

Files:

- Modify `scripts/env/tool_runtime/im_client.py`.
- Modify `scripts/env/tools/message/tool.py`.
- Update `tests/test_message_tool_im_client.py`.
- Update `tests/test_env_tool_schema_contract.py` and semantic contract tests if they assert the old required schema.

Behavior:

- `message.send` requires `content`.
- For a new actor-directed message, `target_actor_address` is required.
- For a reply, `reply_to` can be sufficient.
- When `reply_to` is provided and `target_actor_address` is absent:
  - fetch the original message through IM product service;
  - verify the active actor is a participant in that conversation;
  - derive the reply target as the other participant in the direct conversation;
  - allow the other participant to be external or actor;
  - call `message_service.send_im_message(sender_participant=active_actor, to=derived_target, content=..., reply_to=...)`.
- If the conversation is not direct or the target cannot be derived, reject with a clear `E_IM_REPLY_TARGET` style error.

Expected actor tool examples:

```json
{"content":"pong","reply_to":"msg-..."}
```

```json
{"target_actor_address":{"role_id":"dev","actor_id":"act-dev-..."},"content":"new topic"}
```

Design constraints:

- Do not require actors to know external participant ids to reply.
- Do not reintroduce `role_id=user`.
- Do not make external participants actor contacts.
- Preserve actor-to-actor direct send.

Focused command:

```bash
python -m pytest tests/test_message_tool_im_client.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py -q
```

## Task 4: Correct Wake Prompts And Tool Contract Language

Purpose: prevent the runtime prompt from telling actors to use an actor-only target for external replies.

Files:

- Modify `tools/launcher/im_wake_handler.py`.
- Modify `scripts/env/tools/message/tool.py`.
- Update `tests/test_im_wake_handler.py`.
- Update runtime skill/schema tests that inspect message tool text.

Required prompt semantics:

- Actor should first call `message__get(message_id=...)`.
- If context is needed, use `message__conversation`.
- If replying to the received message, call `message__send(content=..., reply_to=message_id)`.
- `target_actor_address` is only for a new actor-directed message.
- If no reply is needed, call `message__mark(disposition="absorbed")`.
- If side triage needs parent, call `message__mark(disposition="needs_parent", reason=...)`.

Focused command:

```bash
python -m pytest tests/test_im_wake_handler.py tests/test_runtime_skills.py tests/test_env_tool_schema_contract.py -q
```

## Task 5: Complete Subscription Semantics

Purpose: make `/api/im/events?wait_ms=...` behave like a subscription endpoint, not only a short-poll read.

Files:

- Modify `scripts/env/services/messages.py::read_im_events`.
- Keep `tools/launcher/im_http_router.py` route shape.
- Add or update tests in `tests/test_im_product_core.py` and `tests/test_im_http_router.py`.

Behavior:

- `wait_ms=0` returns immediately.
- `wait_ms>0` waits until new participant-visible events exist or the bounded timeout expires.
- Repeated calls with the same cursor remain stable.
- `next_cursor` advances only to the last returned event.
- Message content is still fetched through `GET /api/im/messages/{id}`.

Implementation note:

- Use a simple bounded polling loop with `time.monotonic()` and small sleep intervals.
- Keep this local and concrete; do not introduce a generic event bus.

Focused command:

```bash
python -m pytest tests/test_im_product_core.py tests/test_im_http_router.py -q
```

## Task 6: Add The Missing HTTP Conversation Read

Purpose: align HTTP with the documented Central IM contract and support UI/client context reads without bypassing the route.

Files:

- Modify `tools/launcher/im_http_router.py`.
- Add tests in `tests/test_im_http_router.py`.

Route:

```text
GET /api/im/conversations/direct?kind=actor&role_id=<role>&actor_id=<actor_id>&limit=20
```

Rules:

- Authenticated participant is derived from bearer token.
- Target can be actor in Phase 1.
- Response delegates to `message_service.get_im_direct_conversation(...)`.
- Do not duplicate conversation rules in the router.

Focused command:

```bash
python -m pytest tests/test_im_http_router.py -q
```

## Task 7: Build The Python Smoke Client

Purpose: provide a runnable external-user client that exercises the real contract.

File:

- Create `tmp/im_reply_console.py`.

Command shape:

```bash
python tmp/im_reply_console.py --actor-id act-market-... --role market --base-url http://127.0.0.1:8765
```

Behavior:

- Require `--actor-id`.
- Accept `--role`, defaulting to the actor's role only if discovery can prove a single match.
- Register an external participant with `client_kind=script`.
- Keep token and cursor in memory for the session.
- Start a background poll loop:
  - call `/api/im/events?cursor=...&wait_ms=15000`;
  - update cursor;
  - for each `message.created` event from an actor, fetch `/api/im/messages/{id}`;
  - print a compact line containing sender, reply_to, and message content.
- Main input loop:
  - read user input;
  - send to selected actor through `/api/im/messages`;
  - print `message_id`, `delivery_status`, and `wake_status`;
  - support continued turns until `/quit` or EOF.

Print shape:

```text
target actor: market/act-market-...
external participant: ext-...
> ping
[sent] msg-... delivery=accepted wake=submitted
[reply] market/act-market-...: pong
```

Constraints:

- Do not print full JSON by default.
- Do not call old `/api/messages/send`.
- Do not simulate actor replies.
- If wake is `target_not_online` or `wake_failed`, print that clearly and continue polling because the durable message still exists.

Manual command:

```bash
python tmp/im_reply_console.py --actor-id <actor_id> --role <role_id> --base-url http://127.0.0.1:8765
```

## Task 8: Make Web UI Reuse The Same Receive Loop

Purpose: turn WebManagement from send-only into a minimal IM client.

Files:

- Modify `tools/launcher/assets/web-management/app.js`.
- Update `tests/web_management_ui_contract.test.js`.
- Update `tests/web_management_ui_state.test.js`.

Behavior:

- Reuse the same external participant registration state already started in `app.js`.
- After participant registration, poll `/api/im/events?cursor=...&wait_ms=...`.
- Fetch message content for reply events.
- Render a compact conversation/status area for sent messages and actor replies.
- Keep the UI operational and minimal; do not add unrelated layout redesign.

Constraints:

- Web UI must not own IM rules.
- Web UI must not use old `/api/messages/send`.
- Web UI should tolerate wake failure by showing send status and continuing the subscription loop.

Focused command:

```bash
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

## Task 9: Final Verification Gate

Run focused tests first:

```bash
python -m pytest tests/test_im_external_reply_loop.py tests/test_message_tool_im_client.py tests/test_im_http_router.py -q
python -m pytest tests/test_web_management.py tests/test_im_wake_handler.py tests/test_daemon_mailbox.py tests/test_daemon_core_decoupling.py -q
python -m pytest tests/test_im_product_core.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py -q
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Run cleanup searches:

```bash
rg "act-user-local|web-user|send_from_web_user|WebUserActorRuntime|deliver_message_available|/api/messages/send" tools scripts tests
rg "message.available" tools scripts tests
```

Expected search result:

- no active IM main-path usage of old fake user or old send route;
- no `message.available` dependency in IM delivery.

Run manual smoke:

```bash
./buddyswitch-codex web --port 8765
python tmp/im_reply_console.py --actor-id <actor_id> --role <role_id> --base-url http://127.0.0.1:8765
```

Acceptance:

- script sends a message;
- actor runtime receives wake;
- actor can call message tools to reply with only `reply_to`;
- script prints the actor reply content;
- Web UI can use the same event/fetch flow to display replies.

## Execution Order

1. Add the acceptance tests from Task 1 and confirm they fail for the current gaps.
2. Implement the real wake bridge from Task 2.
3. Implement actor reply-to-external from Task 3.
4. Correct prompts/tool schema from Task 4.
5. Complete event subscription and conversation HTTP route from Tasks 5 and 6.
6. Add the Python smoke client from Task 7.
7. Add Web UI receive/render reuse from Task 8.
8. Run Task 9 verification.

This order attacks the current bottleneck first: the system cannot be considered usable until a real actor reply can travel back to an external participant through the subscribed event path.

## Non-Goals For This Gap Closure

- No server-side webhook platform.
- No generic pub/sub framework.
- No external participant actor daemon.
- No `role_id=user` actor escape.
- No P2P actor message store.
- No broad Web UI redesign.
- No group conversation implementation in this slice.

## Done Criteria

The work is done only when:

- external send creates durable IM state;
- runtime wake reaches the target actor daemon, not just a fake `submitted` return;
- actor `message.send(reply_to=...)` can reply to an external-origin message without `target_actor_address`;
- external `/api/im/events` exposes the reply event through a cursor;
- external client fetches the reply message content and displays it;
- Web UI uses the same receive loop;
- focused tests and cleanup searches pass;
- manual smoke proves the loop with a real selected actor.
