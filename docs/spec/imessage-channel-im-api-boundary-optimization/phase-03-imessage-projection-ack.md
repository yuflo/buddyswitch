# Phase 03: Ack Only After iMessage Projection

Date: 2026-06-30

## Stage Goal

Make the iMessage channel explicitly acknowledge External IM events only after the event has been handled at the iMessage transport boundary.

Target contract:

```text
read event
fetch message
derive reply_to
look up iMessage route
send to Messages.app
record transport idempotency
ack IM event
```

## Involved Files

Modify:

- `tools/launcher/imessage_channel.py`
- `tests/test_imessage_channel.py`
- `docs/spec/imessage-channel-im-api-boundary-optimization/phase-03-imessage-projection-ack.md`

Do not modify in this phase:

- Central IM service ack semantics from Phase 1.
- Worker split lifecycle from Phase 2, except where `poll_outbound_once()` needs ack behavior.
- Web management projection.

## Current Code Evidence

- `tools/launcher/imessage_channel.py:125-132` has `read_events()` but no HTTP client method for `/api/im/events/ack`.
- `tools/launcher/imessage_channel.py:431-465` sends iMessage replies and records `sent_outbound_event_ids`, but never acks IM events.
- `tools/launcher/imessage_channel.py:447-448` skips already-sent local event ids entirely, so it cannot retry IM API ack after an ack failure.
- `tests/test_imessage_channel.py:254-284` proves a reply is sent once through local sent-event dedupe, but does not prove IM ack.
- `tests/test_imessage_channel.py:285-310` proves failed `imsg.send` does not record local sent state, but does not prove no IM ack.

## Target Behavior

- Add `BuddySwitchImApi.ack_event(connection_key, event_id)`.
- `poll_outbound_once()` calls `ack_event()` after successful iMessage projection.
- If `imsg.send` fails, do not record local sent-event state and do not ack the IM event.
- If `imsg.send` succeeds, record `sent_outbound_event_ids` and save state before ack.
- If ack fails after send, return without duplicating the iMessage; later polls retry ack because the event id is in local sent-event state.
- If a later poll sees an event id already in `sent_outbound_event_ids`, retry `ack_event()` and do not send another iMessage.
- If the event message is fetched but has no route for its `reply_to`, ack it as not projectable and do not send iMessage.
- If message fetch fails, do not ack.

## Not Doing

- No channel-local event cursor.
- No Central IM service/repo import.
- No local outbox beyond existing transport idempotency.
- No retry scheduler beyond the outbound polling loop.
- No route synthesis for missing routes.

## Test Plan

### 1. Successful iMessage projection acks the event

Modify `tests/test_imessage_channel.py::ImessageChannelTests.test_actor_reply_is_prefixed_and_sent_to_recorded_route_once`.

Expected assertions:

- First poll sends the prefixed iMessage reply.
- First poll calls `api.ack_event(connection_key="imck-1", event_id="imev-reply-1")`.
- Second poll sends nothing because the fake API no longer returns acked events.

Expected failure before implementation:

```text
AssertionError: ack call list is empty
```

Focused command:

```bash
python3 -m pytest -q tests/test_imessage_channel.py::ImessageChannelTests::test_actor_reply_is_prefixed_and_sent_to_recorded_route_once
```

### 2. Failed iMessage send does not ack

Modify `tests/test_imessage_channel.py::ImessageChannelTests.test_poll_outbound_does_not_mark_event_sent_when_imessage_send_fails`.

Expected assertions:

- Local sent-event state remains empty.
- `api.ack_event()` is not called.

Expected failure before implementation:

```text
No failure until ack implementation exists; this is a regression guard for the GREEN step.
```

### 3. Ack failure after send does not duplicate iMessage

Add `tests/test_imessage_channel.py::ImessageChannelTests.test_poll_outbound_retries_ack_without_duplicate_imessage_after_ack_failure`.

Test shape:

- Configure fake API so the first ack for the reply event returns `ok: false`.
- First poll sends one iMessage, records the event id locally, and attempts ack once.
- Second poll receives the same event, retries ack, and sends no second iMessage.
- After second poll, fake API marks the event acked.

Expected failure before implementation:

```text
AssertionError: ack call list is empty
```

Focused command:

```bash
python3 -m pytest -q tests/test_imessage_channel.py::ImessageChannelTests::test_poll_outbound_retries_ack_without_duplicate_imessage_after_ack_failure
```

### 4. Missing route is acked as not projectable

Add `tests/test_imessage_channel.py::ImessageChannelTests.test_poll_outbound_acks_unrouteable_event_after_fetch`.

Expected assertions:

- Event message is fetched.
- No iMessage is sent.
- IM event is acked.

Expected failure before implementation:

```text
AssertionError: ack call list is empty
```

### 5. Fetch failure does not ack

Add `tests/test_imessage_channel.py::ImessageChannelTests.test_poll_outbound_does_not_ack_when_message_fetch_fails`.

Expected assertions:

- `poll_outbound_once()` sends nothing.
- `api.ack_event()` is not called.

Expected failure before implementation:

```text
No failure until ack implementation exists; this is a regression guard for the GREEN step.
```

## Stage Acceptance

Phase 3 is complete only when:

- New and modified tests fail for expected reasons before implementation.
- `BuddySwitchImApi` exposes HTTP ack.
- `poll_outbound_once()` saves local transport idempotency before ack.
- Ack failure does not duplicate iMessage delivery.
- Focused tests pass:

```bash
python3 -m pytest -q tests/test_imessage_channel.py
```

- Compile check passes:

```bash
python3 -m py_compile tools/launcher/imessage_channel.py
```

## Risks

- If the process crashes after `imsg.send` succeeds but before local state is saved, duplicate delivery is still possible. This phase narrows the known failure after local save and before/around IM API ack.
- If `ack_event()` repeatedly fails for a route-missing event, the connection cursor remains blocked. That is correct because the owning IM API has not accepted consumption.

## Verification Log

RED, before implementation:

```bash
python3 -m pytest -q tests/test_imessage_channel.py::ImessageChannelTests::test_actor_reply_is_prefixed_and_sent_to_recorded_route_once tests/test_imessage_channel.py::ImessageChannelTests::test_poll_outbound_does_not_mark_event_sent_when_imessage_send_fails tests/test_imessage_channel.py::ImessageChannelTests::test_poll_outbound_retries_ack_without_duplicate_imessage_after_ack_failure tests/test_imessage_channel.py::ImessageChannelTests::test_poll_outbound_acks_unrouteable_event_after_fetch tests/test_imessage_channel.py::ImessageChannelTests::test_poll_outbound_does_not_ack_when_message_fetch_fails
```

Result:

```text
3 failed, 2 passed
```

Expected failure cause observed:

- iMessage channel did not call `api.ack_event()` after projection or for unrouteable fetched events.

GREEN, focused Phase 3 tests after implementation:

```bash
python3 -m pytest -q tests/test_imessage_channel.py::ImessageChannelTests::test_actor_reply_is_prefixed_and_sent_to_recorded_route_once tests/test_imessage_channel.py::ImessageChannelTests::test_poll_outbound_does_not_mark_event_sent_when_imessage_send_fails tests/test_imessage_channel.py::ImessageChannelTests::test_poll_outbound_retries_ack_without_duplicate_imessage_after_ack_failure tests/test_imessage_channel.py::ImessageChannelTests::test_poll_outbound_acks_unrouteable_event_after_fetch tests/test_imessage_channel.py::ImessageChannelTests::test_poll_outbound_does_not_ack_when_message_fetch_fails
```

Result:

```text
5 passed in 0.04s
```

Full iMessage channel suite:

```bash
python3 -m pytest -q tests/test_imessage_channel.py
```

Result:

```text
22 passed in 0.17s
```

Compile:

```bash
python3 -m py_compile tools/launcher/imessage_channel.py
```

Result: passed.

Broader IM/Web focused regression:

```bash
python3 -m pytest -q tests/test_external_im_session.py tests/test_im_product_core.py tests/test_im_http_router.py tests/test_im_web_management_projection.py tests/test_web_management.py tests/test_im_external_reply_loop.py tests/test_external_im_projection_contract.py
```

Result:

```text
95 passed, 74 subtests passed in 112.92s
```
