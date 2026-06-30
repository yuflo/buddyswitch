# Phase 01: External IM Event Ack Contract

Date: 2026-06-30

## Stage Goal

Replace External IM read-auto-ack with an explicit IM API acknowledgement contract.

Target contract:

```text
read events -> return unacknowledged consumable events after connection.last_event_id
ack event  -> validate connection visibility and sequential cursor position, then advance last_event_id
```

Consumable events for an external connection are visible events not authored by the connection's own external identity. Synchronous `POST /api/im/messages` already returns the sender's created message id and event id, so self-authored send events should not reappear through `/api/im/events`.

## Involved Files

Modify:

- `scripts/env/services/messages.py`
- `tools/launcher/external_im_session.py`
- `tools/launcher/im_http_router.py`
- `tools/launcher/web_management.py`
- `tests/test_im_product_core.py`
- `tests/test_external_im_session.py`
- `tests/test_im_http_router.py`
- `tests/test_web_management.py`

Do not modify in this phase:

- `tools/launcher/imessage_channel.py`, except if a test import helper requires no behavior change.
- `tools/launcher/assets/web-management/app.js`; the browser must not learn ack details.
- `scripts/env/repos/messages.py`, unless service tests prove a missing repository primitive is required.

## Current Code Evidence

- `scripts/env/services/messages.py:365-366` advances `connection.last_event_id` after `send_external_connection_message()`.
- `scripts/env/services/messages.py:372-397` advances `connection.last_event_id` when `read_external_connection_events()` returns any events.
- `tools/launcher/external_im_session.py:96-101` exposes only `read_events()`.
- `tools/launcher/im_http_router.py:85-93` exposes `GET /api/im/events`, rejects caller cursors, and has no ack route.
- `tools/launcher/web_management.py:461-488` reads events, filters by requested actor identity, fetches messages, and returns the payload without ack.
- `tests/test_external_im_session.py:195-219`, `tests/test_im_product_core.py:188-229`, and `tests/test_im_http_router.py:142-158` currently expect read-auto-ack.
- `tests/test_web_management.py:1223-1234` already asserts browser payloads do not expose connection keys, participant tokens, or cursors.
- `tests/test_web_management.py:1236-1297` proves current Web event projection is actor-scoped.

## Target Behavior

Central IM service:

- `send_external_connection_message()` no longer advances `connection.last_event_id`.
- `read_external_connection_events()` returns consumable events after the connection cursor without mutating the connection.
- Self-authored connection events are not returned by External IM event reads.
- `ack_external_connection_event(connection, event_id)` validates the connection participant.
- Ack rejects non-visible events.
- Ack rejects visible but non-consumable self-authored events.
- Ack rejects out-of-order consumable events after the current cursor.
- Ack is idempotent for an already acknowledged visible event at or before the current cursor.
- Ack advances `connection.last_event_id` only when it acknowledges the next consumable event.

External IM session and HTTP router:

- Add `ExternalImSession.ack_event(connection, event_id)`.
- Add `POST /api/im/events/ack` with body `{"event_id": "imev-..."}`.
- Keep `/api/im/events` server-cursor-owned; caller-supplied `cursor` remains rejected.
- Return JSON errors for malformed ack bodies, missing event ids, non-visible events, and out-of-order ack.

Web management:

- `/api/web/im/events` does not expose ack, cursor, connection key, or participant token details.
- It processes returned events in connection order.
- For events matching the requested actor scope, it fetches the message, includes both event and message in the browser payload, then acks the event.
- For off-scope consumable events, it fetches enough detail to classify them, omits them from the selected actor payload, then acks them as consumed by the Web projection.
- Direct conversation restore remains the durable way to show messages for actors that were not selected while their events arrived.

## Not Doing

- No iMessage worker split in this phase.
- No iMessage channel ack-after-send logic in this phase.
- No browser-exposed ack endpoint or cursor parameter.
- No per-actor browser cursors.
- No channel-local or Web-local duplicate event cursor store.
- No compatibility alias where read sometimes auto-acks.
- No generic event bus, async rewrite, or plugin/channel framework.

## Delete Or Replace Old Paths

- Replace read-time `_save_connection_last_event()` in `read_external_connection_events()` with explicit ack.
- Replace send-time cursor advancement in `send_external_connection_message()` with self-event exclusion in External IM reads.
- Replace Web read-auto-ack reliance with explicit session ack calls.

## Test Plan

### 1. Core service repeated read and ack

Modify `tests/test_im_product_core.py::ImProductCoreTests.test_external_connection_reads_actor_reply_once_without_client_cursor`.

Expected new assertions:

- First read returns the actor reply event.
- Second read without ack returns the same actor reply event.
- `message_service.ack_external_connection_event(connection=connection, event_id=actor_reply["event_id"])` returns `ok: true`.
- Third read returns `[]`.
- `connection["last_event_id"]` equals the acked actor reply event id.

Expected failure before implementation:

```text
AssertionError: second read is [] instead of the same actor reply event
AttributeError: module 'env.services.messages' has no attribute 'ack_external_connection_event'
```

Focused command:

```bash
python3 -m pytest -q tests/test_im_product_core.py::ImProductCoreTests::test_external_connection_reads_actor_reply_once_without_client_cursor
```

### 2. Core service rejects non-visible and out-of-order ack

Add tests in `tests/test_im_product_core.py`:

- `test_external_connection_ack_rejects_non_visible_event_without_advancing_cursor`
- `test_external_connection_ack_rejects_out_of_order_consumable_event`

Each test should inspect `connection["last_event_id"]` before and after the failed ack.

Expected failure before implementation:

```text
AttributeError: module 'env.services.messages' has no attribute 'ack_external_connection_event'
```

Focused command:

```bash
python3 -m pytest -q tests/test_im_product_core.py -k "external_connection_ack"
```

### 3. External session exposes ack

Modify `tests/test_external_im_session.py::ExternalImSessionTests.test_session_reads_actor_reply_once_without_client_cursor`.

Expected new assertions:

- Repeated `session.read_events()` returns the same reply before ack.
- `session.ack_event(connection=connection, event_id=actor_reply["event_id"])` returns `ok: true`.
- Read after ack is empty.

Expected failure before implementation:

```text
AssertionError: second read is [] instead of the same actor reply event
AttributeError: 'ExternalImSession' object has no attribute 'ack_event'
```

Focused command:

```bash
python3 -m pytest -q tests/test_external_im_session.py::ExternalImSessionTests::test_session_reads_actor_reply_once_without_client_cursor
```

### 4. HTTP ack route

Modify `tests/test_im_http_router.py::ImHttpRouterTests.test_external_http_contract_send_events_get_and_mark`.

Expected new assertions:

- Reading after the external send still returns `[]` because self-authored events are not consumable.
- Reading the actor reply twice without ack returns the same event.
- `POST /api/im/events/ack` with the reply event id returns `200` and `ok: true`.
- Reading after ack returns `[]`.
- `GET /api/im/events?cursor=...` remains `400`.

Add one HTTP negative ack case:

- Acking a malformed or non-visible event id returns non-`ok` JSON and does not advance the cursor.

Expected failure before implementation:

```text
AssertionError: repeated read is [] instead of the same event
404 NOT_FOUND for POST /api/im/events/ack
```

Focused command:

```bash
python3 -m pytest -q tests/test_im_http_router.py
```

### 5. Web projection acks without leaking details

Modify `tests/test_web_management.py::WebManagementStableImIdentityTests.test_web_im_routes_send_read_events_and_restore_direct_history_without_browser_token`.

Expected new assertions:

- `/api/web/im/events?...` returns the actor reply and message.
- The payload still omits `participant_token`, `connection_key`, `next_cursor`, and `ack`.
- A repeated Web events call for the same actor returns no events because Web projection acked the returned event.

Modify `tests/test_web_management.py::WebManagementStableImIdentityTests.test_web_im_events_are_scoped_to_requested_actor_conversation`.

Expected new assertions:

- If market reply arrives before dev reply and the browser polls dev, the dev payload still returns only dev.
- A later market events poll returns no market event because the earlier off-scope market event was consumed by the Web projection.
- `GET /api/web/im/conversations/direct?identity_id=<market>&limit=20` still returns the market conversation messages.

Expected failure before implementation:

```text
AssertionError: repeated Web event call still returns the same unacked event after read-auto-ack is removed
```

Focused command:

```bash
python3 -m pytest -q tests/test_web_management.py::WebManagementStableImIdentityTests::test_web_im_routes_send_read_events_and_restore_direct_history_without_browser_token tests/test_web_management.py::WebManagementStableImIdentityTests::test_web_im_events_are_scoped_to_requested_actor_conversation
```

### 6. Projection boundary residue

Run after implementation:

```bash
python3 -m pytest -q tests/test_im_web_management_projection.py
rg -n "ack_event|/api/im/events/ack|events/ack|cursor|connection_key|participant_token" tools/launcher/assets/web-management/app.js tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js -S
```

Expected:

- Projection tests pass.
- Browser assets/tests may mention route URLs and payload omission assertions, but must not expose ack controls, connection keys, participant tokens, or cursor details.

No service-starting live smoke is part of Phase 1, so no process lifecycle cleanup check is required for this phase.

## Stage Acceptance

Phase 1 is complete only when:

- The stage tests fail for the expected reasons before implementation.
- Implementation removes read-auto-ack and send-time cursor advancement.
- Explicit ack exists in service, session, and HTTP router.
- Web management explicitly acks consumed events without browser-visible ack/cursor details.
- Focused tests pass:

```bash
python3 -m pytest -q tests/test_external_im_session.py tests/test_im_product_core.py tests/test_im_http_router.py tests/test_im_web_management_projection.py tests/test_web_management.py
```

- Compile check passes:

```bash
python3 -m py_compile scripts/env/services/messages.py tools/launcher/external_im_session.py tools/launcher/im_http_router.py tools/launcher/web_management.py
```

## Risks

- Web actor-scoped event polling is not a general notification queue. Off-scope events consumed by the selected-actor poll remain visible through direct conversation restore, not through later event polling.
- Existing runtime connections may have `last_event_id` values produced by the old send-time cursor path. The new read logic must apply the cursor against the full visible event stream before filtering self-authored events, so those connections can continue reading later consumable replies without a compatibility mode.
- If ack is not sequential, a later ack can skip earlier consumable events. The service must reject out-of-order consumable ack.

## Verification Log

RED, before implementation:

```bash
python3 -m pytest -q tests/test_external_im_session.py::ExternalImSessionTests::test_session_reads_actor_reply_once_without_client_cursor tests/test_im_product_core.py::ImProductCoreTests::test_external_connection_reads_actor_reply_once_without_client_cursor tests/test_im_product_core.py::ImProductCoreTests::test_external_connection_ack_rejects_non_visible_event_without_advancing_cursor tests/test_im_product_core.py::ImProductCoreTests::test_external_connection_ack_rejects_out_of_order_consumable_event tests/test_im_http_router.py::ImHttpRouterTests::test_external_http_contract_send_events_get_and_mark tests/test_web_management.py::WebManagementStableImIdentityTests::test_web_im_routes_send_read_events_and_restore_direct_history_without_browser_token tests/test_web_management.py::WebManagementStableImIdentityTests::test_web_im_events_are_scoped_to_requested_actor_conversation
```

Result:

```text
5 failed, 2 passed
```

Expected failure causes observed:

- `send_external_connection_message()` still advanced `connection.last_event_id`.
- `message_service.ack_external_connection_event` did not exist.
- `POST /api/im/events/ack` returned `404`.

GREEN, focused RED tests after implementation:

```bash
python3 -m pytest -q tests/test_external_im_session.py::ExternalImSessionTests::test_session_reads_actor_reply_once_without_client_cursor tests/test_im_product_core.py::ImProductCoreTests::test_external_connection_reads_actor_reply_once_without_client_cursor tests/test_im_product_core.py::ImProductCoreTests::test_external_connection_ack_rejects_non_visible_event_without_advancing_cursor tests/test_im_product_core.py::ImProductCoreTests::test_external_connection_ack_rejects_out_of_order_consumable_event tests/test_im_http_router.py::ImHttpRouterTests::test_external_http_contract_send_events_get_and_mark tests/test_web_management.py::WebManagementStableImIdentityTests::test_web_im_routes_send_read_events_and_restore_direct_history_without_browser_token tests/test_web_management.py::WebManagementStableImIdentityTests::test_web_im_events_are_scoped_to_requested_actor_conversation
```

Result:

```text
7 passed in 0.11s
```

Focused phase suite:

```bash
python3 -m pytest -q tests/test_external_im_session.py tests/test_im_product_core.py tests/test_im_http_router.py tests/test_im_web_management_projection.py tests/test_web_management.py
```

Result:

```text
86 passed, 74 subtests passed in 110.83s
```

Compile:

```bash
python3 -m py_compile scripts/env/services/messages.py tools/launcher/external_im_session.py tools/launcher/im_http_router.py tools/launcher/web_management.py
```

Result: passed.

Browser residue scan:

```bash
rg -n "ack_event|/api/im/events/ack|events/ack|cursor|connection_key|participant_token" tools/launcher/assets/web-management/app.js tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js -S
```

Result: only existing browser tests that assert no cursor state and no participant token exposure; no app/browser ack route or ack control.

Adjacent IM/iMessage regression check:

```bash
python3 -m pytest -q tests/test_im_external_reply_loop.py tests/test_external_im_projection_contract.py tests/test_imessage_channel.py
```

Result:

```text
26 passed in 0.28s
```
