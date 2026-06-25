# BuddySwitch IM Central Rebuild Test Plan

Status: Phase 1 plan artifact.

Source inputs:

- `docs/memo/buddyswitch-im-gateway-rebuild.md`
- `docs/memo/buddyswitch-im-central-contract-boundary-review.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
- Current code inspection of `scripts/env/domain/messages.py`, `scripts/env/repos/messages.py`, `scripts/env/services/messages.py`, `scripts/env/tools/message/_impl.py`, `tools/launcher/web_management.py`, `tools/launcher/central_daemon_core.py`, `tools/launcher/message_available_handler.py`, `tools/launcher/message_inbound.py`, and `scripts/env/tool_runtime/context.py`.

## Current Bottleneck

BuddySwitch still has a direct actor-address message path:

```text
web/actor tool
  -> message service
  -> old messages/*.json row
  -> central signal.deliver
  -> daemon mailbox
  -> message.available
  -> parent/side handler
```

The target is a single Central IM path:

```text
external/web/actor tool
  -> /api/im/*
  -> scripts/env IM product core
  -> state/im/* durable store + participant events
  -> central host wake bridge
  -> actor runtime parent/side handling
```

Tests must prove that the old path is deleted, not wrapped.

## Resource Safety Gate

Do not begin broad suite runs until focused service-starting tests have shown cleanup.

Verification order:

1. Run pure unit/product-core tests first.
2. Run route and handler tests that do not start persistent services.
3. Run one focused service-starting test, if any changed path requires it.
4. Inspect for residual processes, sockets, and pid files.
5. Run the focused changed group.
6. Inspect residuals again.
7. Run broad verification.

Residual inspection commands:

```bash
pgrep -fl "buddyswitch|central_daemon|runtime_broker|app_server|fake_codex|chrome" || true
find /tmp -maxdepth 3 -name '*buddyswitch*' -o -name '*central-daemon*'
```

If residual processes or sockets appear after a focused run, stop and fix lifecycle before running more tests.

## Coverage Matrix

### Product Core and Store

Add or replace tests in `tests/test_message_service.py` and a new `tests/test_im_product_core.py`.

Required tests:

1. External registration returns an `external_id`, bearer token, and initial cursor.
2. External registration writes participant, session, and cursor objects under `state/im/*`.
3. Session store hashes tokens and never writes the raw token.
4. `display_name` and `client_kind` are metadata only and cannot route messages.
5. Actor participants are represented by existing `{role_id, actor_id}` addresses.
6. `role_id=user` is rejected as an actor participant.
7. Direct send persists one conversation, one message, participant message states, and participant-visible events.
8. Send response separates durable delivery from runtime wake: `delivery_status=accepted` and `wake_status=*`.
9. Wake failure or offline target does not delete the durable message.
10. `reply_to` must reference a visible message in the same direct conversation.
11. `GET message` rejects participants that are not in the conversation.
12. `GET replies` returns replies for visible root messages.
13. `GET events` is participant-scoped, cursor-ordered, and stable when called with the same cursor.
14. `PATCH disposition` updates only the authenticated participant message state.
15. External participants can mark messages `absorbed`; actor participants can also use `needs_parent` and `replied`.

### HTTP Contract

Add `tests/test_im_http_router.py` and update `tests/test_web_management.py`.

Required tests:

1. `POST /api/im/external-participants` maps JSON to product-core registration.
2. `GET /api/im/actors?role_id=market` returns actor participants from central registry/reachability.
3. `POST /api/im/messages` authenticates `Authorization: Bearer <token>`.
4. `POST /api/im/messages` rejects a request body that supplies `from`.
5. `GET /api/im/events` returns participant events and `next_cursor`.
6. `GET /api/im/messages/{id}` returns a visible message without leaking session data.
7. `GET /api/im/messages/{id}/replies` returns visible replies.
8. `PATCH /api/im/messages/{id}/disposition` updates participant state.
9. `/api/messages/send` returns 404.
10. WebManagement mounts or delegates `/api/im/*` and does not import or start `web_user_actor`.
11. `tools/launcher/im_http_router.py` calls the IM product service and does not import the IM repo directly.
12. `tools/launcher/central_daemon_core.py` does not import the IM repo for store writes.

### Runtime Wake

Replace `tests/test_message_available_handler.py` with IM wake tests or migrate it to `tests/test_im_wake_handler.py`.

Required tests:

1. Wake payload type is `im.message.created`.
2. Wake payload contains only ids and target actor address, not message content.
3. Wrong target actor is rejected.
4. Idle parent receives the parent handling workflow.
5. Running parent receives side triage.
6. Parent/side prompts tell the actor to fetch with `message__get` and reply with `message__send(reply_to=...)`.
7. Wake handling does not mutate IM message disposition.
8. `message.available` is not registered as the IM delivery contract.
9. `track.comment.added` handler tests remain green.

### Actor Message Tools

Update `tests/test_message_env_tool.py` and add focused client tests for `scripts/env/tool_runtime/im_client.py`.

Required tests:

1. `message__contacts` calls Central IM actor discovery.
2. `message__send` calls Central IM message send as the active actor participant.
3. `message__send` does not call `context.repos.message.create_message`.
4. `message__send` does not call `context.daemon.deliver_message_available`.
5. `message__get` calls Central IM get-message.
6. `message__list` calls a participant-scoped IM query.
7. `message__conversation` calls direct-conversation read.
8. `message__mark` calls Central IM disposition update.
9. Tool responses keep the existing runless result shape where useful: `ok`, `state_changed`, `durability`, `message_id`, and clear rejection payloads.
10. `scripts/env/tools/message/tool.py` describes IM participants, conversations, messages, states, and events, not direct actor-address inbox rows.

### Old Path Deletion

Add or update architecture tests.

Required assertions:

1. `tools/launcher/web_user_actor.py` is removed.
2. No production code imports `web_user_actor`.
3. `send_from_web_user` is removed.
4. `WebUserActorRuntime` is removed.
5. `deliver_message_available` is removed from the IM send path.
6. `EXTERNAL_MESSAGE_ROLE_IDS = {"user"}` is removed.
7. `/api/messages/send` is removed.
8. `message.available` has no IM main-path references.
9. Daemon mailbox remains only as a generic runtime trigger transport for non-IM uses.
10. Track, task, artifact, and comment systems do not import IM repo/service internals.

Required cleanup searches:

```bash
rg "act-user-local|web-user|send_from_web_user|WebUserActorRuntime|deliver_message_available|/api/messages/send" tools scripts tests
rg "message.available" tools scripts tests
```

Expected final result:

- The first search returns no hits.
- The second search returns no IM main-path hits. If any non-IM daemon/mailbox generic contract test still uses the literal string, the test must explain why it is a generic transport example and not IM delivery.

## Focused Verification Commands

Run these as slices while implementing:

```bash
python -m pytest tests/test_message_service.py -q
python -m pytest tests/test_im_product_core.py -q
python -m pytest tests/test_im_http_router.py tests/test_web_management.py -q
python -m pytest tests/test_im_wake_handler.py tests/test_track_comment_added_handler.py -q
python -m pytest tests/test_message_env_tool.py -q
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Broad final verification:

```bash
python -m pytest tests -q
node --test tests/*.test.js
```

Only run the broad commands after the resource safety gate passes.

## Manual Smoke

Use only after automated route/product tests pass.

```bash
./buddyswitch-codex web
```

Then:

```bash
curl -sS -X POST http://127.0.0.1:8765/api/im/external-participants \
  -H 'Content-Type: application/json' \
  -d '{"client_kind":"script","display_name":"local smoke"}'

curl -sS -X POST http://127.0.0.1:8765/api/im/messages \
  -H 'Authorization: Bearer <participant_token>' \
  -H 'Content-Type: application/json' \
  -d '{"to":{"kind":"actor","actor_address":{"role_id":"market","actor_id":"act-market-607eca23170c"}},"content":"ping"}'

curl -sS 'http://127.0.0.1:8765/api/im/events?cursor=<cursor>&wait_ms=1000' \
  -H 'Authorization: Bearer <participant_token>'
```

After manual smoke, stop the web server and run the residual process/socket check before claiming completion.

## Self-Review

- No placeholder requirements remain.
- Tests are requirement-first: they assert product behavior and boundaries, not a particular implementation trick.
- The plan explicitly covers external registration, send, events, replies, disposition, HTTP, actor tools, runtime wake, old path deletion, and resource lifecycle.
- The plan keeps old compatibility paths out of the final success criteria.
