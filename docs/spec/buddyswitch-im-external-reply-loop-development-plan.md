# BuddySwitch IM External Reply Loop Development Plan

Status: Phase 1 focused development plan artifact.

Goal: close the external-user IM loop through the Central IM product contract without fake user actors, old `/api/messages/send`, or `message.available` delivery.

## Architecture

Central IM product core under `scripts/env` owns participants, direct conversations, messages, replies, events, cursors, sessions, and dispositions. Launcher code only projects HTTP and bridges accepted IM events into the target actor daemon mailbox. Web UI is a product client of `/api/im/*`; `tmp/im_reply_console.py` is only an ignored local manual smoke harness, not a BuddySwitch feature.

## Implementation Slices

### Slice 1: Acceptance Guard

Files:

- Create `tests/test_im_external_reply_loop.py`.
- Update `tests/test_message_tool_im_client.py`.

Steps:

1. Add `test_external_send_actor_reply_to_external_visible_via_cursor`.
2. Add wake bridge unit tests with fake reachability and fake mailbox request.
3. Add actor reply-to-external regression coverage.
4. Run:

```bash
python -m pytest tests/test_im_external_reply_loop.py tests/test_message_tool_im_client.py -q
```

Expected first failure before implementation:

- `ActorImClient.send(reply_to=...)` cannot derive the external target.
- `daemon_client.wake_im_actor` is missing.

### Slice 2: Real Runtime Wake Bridge

Files:

- Modify `scripts/env/tool_runtime/daemon_client.py`.
- Modify `scripts/env/tool_runtime/context.py`.
- Modify `tools/launcher/web_management.py`.

Steps:

1. Implement `daemon_client.wake_im_actor(payload, ...)`.
2. Validate ids and `type=im.message.created`.
3. Call central reachability.
4. Resolve target `daemon_mailbox_socket`.
5. Submit `mailbox.local_trigger` with ids only.
6. Return `submitted`, `target_not_online`, `wake_failed`, or `not_applicable`.
7. Expose `DaemonAccess.wake_im_actor`.
8. Replace WebManagement fake submitted return with the helper.

Focused verification:

```bash
python -m pytest tests/test_im_external_reply_loop.py tests/test_web_management.py tests/test_daemon_mailbox.py -q
```

### Slice 3: Actor Reply-To-External

Files:

- Modify `scripts/env/services/messages.py`.
- Modify `scripts/env/tool_runtime/im_client.py`.
- Modify `scripts/env/tools/message/tool.py`.
- Update schema/semantic contract tests.

Steps:

1. Allow `send_im_message(..., to=None, reply_to=...)`.
2. Fetch the original message and direct conversation in product core.
3. Verify the sender is a participant.
4. Derive the other participant as target; it may be actor or external.
5. Preserve actor-to-actor new sends with explicit `target_actor_address`.
6. Mark the original sender-visible message state `replied` after successful reply creation.
7. Update `message.send` schema so only `content` is always required.

Focused verification:

```bash
python -m pytest tests/test_message_tool_im_client.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py -q
```

### Slice 4: Prompt And Subscription Contract

Files:

- Modify `tools/launcher/im_wake_handler.py`.
- Modify `scripts/env/services/messages.py`.
- Modify `tools/launcher/im_http_router.py`.

Steps:

1. Update parent/side prompts to use `message__send(content=..., reply_to=message_id)`.
2. Implement bounded `wait_ms` polling in `read_im_events`.
3. Add `GET /api/im/conversations/direct?kind=actor&role_id=...&actor_id=...`.
4. Keep conversation rules delegated to product core.

Focused verification:

```bash
python -m pytest tests/test_im_wake_handler.py tests/test_im_product_core.py tests/test_im_http_router.py -q
```

### Slice 5: Web UI Client Surface And Manual Smoke Harness

Files:

- Modify `tools/launcher/assets/web-management/index.html`.
- Modify `tools/launcher/assets/web-management/app.js`.
- Modify `tools/launcher/assets/web-management/styles.css`.
- Create `tmp/im_reply_console.py`.
- Update JS contract/state tests.

Steps:

1. Add compact Web UI conversation render target.
2. After external participant registration, poll `/api/im/events?cursor=...&wait_ms=15000`.
3. Fetch actor reply messages through `/api/im/messages/{id}`.
4. Render sent status and actor replies.
5. Keep polling after wake failure because durable messages still exist.
6. Add the ignored local script smoke harness with register/send/poll/fetch loop; do not present it as an official BuddySwitch CLI or feature.

Focused verification:

```bash
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
python tmp/im_reply_console.py --help
```

## Final Gate

Run:

```bash
python -m pytest tests/test_im_external_reply_loop.py tests/test_message_tool_im_client.py tests/test_im_http_router.py tests/test_im_product_core.py tests/test_im_wake_handler.py tests/test_web_management.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py -q
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
python tmp/im_reply_console.py --help
rg "act-user-local|web-user|send_from_web_user|WebUserActorRuntime|/api/messages/send" tools scripts tests
rg "message.available" tools scripts tests
```

Then inspect resource residue before any broad run.

## Self-Review

- The slices preserve one forward IM path.
- No compatibility wrapper or dual IM path is introduced.
- Product semantics stay in `scripts/env/services/messages.py`.
- Launcher changes are route/wake projections only.
- Each slice has focused verification.
