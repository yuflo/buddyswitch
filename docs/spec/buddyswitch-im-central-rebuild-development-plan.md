# BuddySwitch IM Central Rebuild Development Plan

Status: Phase 1 plan artifact.

Goal: rebuild BuddySwitch direct messaging into one Central IM product path under `scripts/env`, projected through `/api/im/*`, actor tools, WebManagement, and runtime wake, with the fake user actor and old `message.available` IM path removed.

## Non-Negotiable Decisions

1. IM product core lives in `scripts/env/domain/messages.py`, `scripts/env/repos/messages.py`, and `scripts/env/services/messages.py`.
2. HTTP, WebManagement, actor tools, and runtime wake are projections of the product core.
3. `tools/launcher` may host routing and wake orchestration, but it must not own IM participant, conversation, message, state, event, cursor, or session truth.
4. External participants are not actors and are not registered in central daemon actor registry.
5. `role_id=user` is not accepted as an actor role escape.
6. Durable message acceptance is independent from runtime wake success.
7. The final main path must not use `send_from_web_user`, `WebUserActorRuntime`, `/api/messages/send`, direct actor-tool repo writes, or `message.available`.

## File Map

Create:

- `tools/launcher/im_http_router.py`: HTTP request parsing, auth extraction, response shaping, and delegation to IM product service.
- `tools/launcher/im_wake_handler.py`: runtime wake handler for `im.message.created`.
- `scripts/env/tool_runtime/im_client.py`: actor-tool projection client for Central IM operations.
- `tests/test_im_product_core.py`: focused product-core and repo behavior tests.
- `tests/test_im_http_router.py`: HTTP contract tests.
- `tests/test_im_wake_handler.py`: runtime wake tests.

Modify:

- `scripts/env/domain/messages.py`: participant model validation, IM prompt rendering, actor role validation, direct conversation/reply/disposition rules.
- `scripts/env/repos/messages.py`: central `state/im/*` JSON store helpers.
- `scripts/env/services/messages.py`: registration, session auth, send/read/reply/events/disposition, and wake delegation.
- `scripts/env/tools/message/_impl.py`: route all actor-facing message actions through `im_client`.
- `scripts/env/tools/message/tool.py`: update user-facing tool contract text to IM semantics.
- `scripts/env/tool_runtime/context.py`: remove old message repo send/list projection from active tool path and expose IM client dependencies where needed.
- `tools/launcher/web_management.py`: remove fake user actor import/startup and mount `/api/im/*`.
- `tools/launcher/message_inbound.py`: replace IM registration with `im.message.created`.
- `tools/launcher/instance_daemon.py`: ensure default inbound registrations use IM wake plus non-IM comment triggers.
- `tools/launcher/assets/web-management/app.js`: replace `/api/messages/send` calls with `/api/im/*` flow.
- Existing tests under `tests/` that assert the old path.

Delete:

- `tools/launcher/web_user_actor.py`
- `tests/test_web_user_actor.py`

## Implementation Slices

### Slice 1: IM Store and External Participant Registration

Tests first:

- `tests/test_im_product_core.py::test_register_external_participant_writes_participant_session_and_cursor`
- `tests/test_im_product_core.py::test_external_registration_does_not_register_actor_or_create_mailbox`
- `tests/test_im_product_core.py::test_session_store_hashes_token_without_plaintext_secret`

Implementation:

- Add `state/im` paths in `scripts/env/repos/messages.py`.
- Add normalized participant keys:
  - `actor:<role_id>:<actor_id>`
  - `external:<external_id>`
- Add create/read helpers for participants, sessions, cursors, conversations, messages, message states, and events.
- Add `register_external_participant` in `scripts/env/services/messages.py`.

Verification:

```bash
python -m pytest tests/test_im_product_core.py -q
```

### Slice 2: Direct Send, Event Cursor, Reads, Replies, Disposition

Tests first:

- direct send persists conversation, message, state, and events;
- offline/wake failure still returns `delivery_status=accepted`;
- event reads are participant-scoped and cursor-stable;
- message/reply reads enforce conversation visibility;
- disposition updates participant message state only.

Implementation:

- Implement direct-conversation lookup/create.
- Implement durable message creation with `to` as a one-item list in Phase 1.
- Create state rows for recipients and sender-visible event rows where required.
- Implement `read_events`, `get_message`, `list_replies`, `get_direct_conversation`, and `update_disposition`.
- Keep wake as an injected callback at service boundary so product tests avoid service processes.

Verification:

```bash
python -m pytest tests/test_im_product_core.py tests/test_message_service.py -q
```

### Slice 3: HTTP Projection

Tests first:

- `POST /api/im/external-participants`
- `GET /api/im/actors`
- `POST /api/im/messages`
- `GET /api/im/events`
- `GET /api/im/messages/{id}`
- `GET /api/im/messages/{id}/replies`
- `PATCH /api/im/messages/{id}/disposition`
- `/api/messages/send` returns 404.

Implementation:

- Create `tools/launcher/im_http_router.py`.
- Use bearer token auth for external callers.
- Use central registry only for actor discovery and wake target status.
- Mount router from `WebManagementService.handle_api`.
- Remove `_send_message_http` and related old web-message sender wiring.

Verification:

```bash
python -m pytest tests/test_im_http_router.py tests/test_web_management.py -q
```

### Slice 4: Runtime Wake Replacement

Tests first:

- idle parent receives IM parent handling prompt;
- running parent receives IM side triage prompt;
- wake payload has ids only;
- wrong target rejected;
- wake does not mutate IM state;
- `track.comment.added` remains green.

Implementation:

- Create `tools/launcher/im_wake_handler.py`.
- Replace prompt titles and trigger checks from `message.available` to `im.message.created`.
- Keep the existing parent/side behavior and prompt steps.
- Update inbound registration to `im.message.created`.
- Keep daemon mailbox as generic trigger transport, not IM message store.

Verification:

```bash
python -m pytest tests/test_im_wake_handler.py tests/test_notification_center.py tests/test_track_comment_added_handler.py -q
```

### Slice 5: Actor Tool Migration

Tests first:

- each actor message tool calls `scripts/env/tool_runtime/im_client.py`;
- actor send does not call repo create or daemon signal;
- get/list/conversation/mark use IM client operations;
- tool schema and descriptions use IM terms.

Implementation:

- Create `scripts/env/tool_runtime/im_client.py` with methods for actor discovery, send, get, list/events, direct conversation, and disposition.
- Replace `scripts/env/tools/message/_impl.py` direct repo/service use with client calls.
- Keep existing result envelope shape but populate it from IM response.
- Update `tool.py` text.

Verification:

```bash
python -m pytest tests/test_message_env_tool.py tests/test_env_native_mcp_server.py tests/test_runtime_skills.py -q
```

### Slice 6: Web UI Projection

Tests first:

- JS contract tests reject `/api/messages/send`.
- UI registers an external participant before sending.
- UI sends through `/api/im/messages`.
- UI polls `/api/im/events`.

Implementation:

- Update `tools/launcher/assets/web-management/app.js` to keep a local external participant token/cursor in browser state.
- Replace old message mutation with register/send/poll flow.
- Keep UI minimal and operational; do not add a landing page or unrelated styling work.

Verification:

```bash
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

### Slice 7: Delete Old Path and Architecture Gates

Tests first:

- architecture search tests for forbidden symbols.
- old route returns 404.
- no production import of `web_user_actor`.

Implementation:

- Delete `tools/launcher/web_user_actor.py`.
- Delete `tests/test_web_user_actor.py` or replace with external participant tests already covered.
- Remove `send_from_web_user`.
- Remove `deliver_message_available` from the IM send path and runtime context if no non-IM caller remains.
- Remove `EXTERNAL_MESSAGE_ROLE_IDS`.
- Rewrite old tests that asserted `message.available` as IM behavior.

Verification:

```bash
rg "act-user-local|web-user|send_from_web_user|WebUserActorRuntime|deliver_message_available|/api/messages/send" tools scripts tests
rg "message.available" tools scripts tests
python -m pytest tests -q
node --test tests/*.test.js
```

## Final Review Gate

Before completion:

1. Re-read both memos and this plan.
2. Build a requirement checklist from the test plan.
3. Confirm every checklist item has file or command evidence.
4. Run focused verification.
5. Run resource residual checks.
6. Run broad verification.
7. Run forbidden-string searches.
8. Do a code-review pass focused on boundary violations:
   - product semantics in launcher;
   - direct repo writes from actor tools;
   - old fake user path residue;
   - message content in wake payload;
   - wake failure deleting durable messages.

## Self-Review

- The plan covers the complete rebuild, including old path deletion.
- The order starts with product truth, then projections, then runtime and cleanup.
- Each slice has explicit test-first work and focused verification.
- No compatibility-forward route is listed as acceptable final behavior.
