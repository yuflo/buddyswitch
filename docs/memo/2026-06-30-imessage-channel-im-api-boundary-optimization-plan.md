# iMessage Channel / IM API Boundary Optimization Plan

Date: 2026-06-30

## Task Goal And Standard

Optimize the current iMessage channel delayed `/actors` behavior without weakening the IM architecture boundary.

The target outcome is:

```text
iMessage user sends a normal actor message
  -> BuddySwitch accepts and wakes the actor through the IM API
  -> iMessage user can immediately send /actors or a numeric selection
  -> control replies are returned promptly
  -> actor replies are later projected back to the same iMessage chat
```

The standard is sharper than "make the delay go away":

- iMessage remains only a channel adapter.
- Central IM product semantics stay in the IM API and message service.
- The channel does not import or duplicate Central IM services, repos, cursor rules, reply rules, conversation rules, or disposition rules.
- If IM API consumption semantics are not strong enough, fix the IM API contract first.
- Do not keep old and new behavior as long-lived compatibility tracks.
- Do not add local channel machinery that quietly becomes a second message system.
- Prove the end-to-end contract with tests and scoped residue checks.

This follows the `docs/bitter` lessons:

- Fix the layer that owns the broken contract.
- Small changes at the wrong boundary are still wrong.
- Built-in product semantics live in product core, not interface adapters.
- Sliced work must preserve one end-to-end user-visible contract.
- Semantic replacement requires behavior proof and live-surface residue proof.
- Service-starting verification must include lifecycle cleanup when live smoke is used.

## Current Findings

### Current iMessage Channel Shape

`tools/launcher/imessage_channel.py` already treats the channel as an External IM HTTP client:

- `POST /api/im/connections` creates an external connection.
- `GET /api/im/actors` lists reachable actors.
- `POST /api/im/messages` sends the user message to the selected actor.
- `GET /api/im/events?wait_ms=...` reads actor reply events.
- `GET /api/im/messages/{message_id}` fetches the event message body.

The channel-local state is transport state:

- sender key -> connection key;
- sender key -> active actor id;
- sender key -> pending numeric actor choices;
- inbound iMessage guid dedupe;
- Central IM message id -> iMessage route;
- outbound event ids already sent to Messages.app.

That is mostly the right boundary. The channel does not currently import `env.services.messages` or `env.repos.messages`, and `tests/test_imessage_channel.py::ImessageChannelResidueTests::test_channel_source_does_not_import_central_im_internals` protects that.

### Current Delay Root Cause

`ImessageChannelWorker.run_forever()` is a single serial loop:

```text
for row in imsg.watch_messages():
  handle_inbound_message(row)
  poll_outbound_once(wait_ms=30000)
```

That makes actor reply waiting part of the inbound receive path. A user message followed immediately by `/actors` can wait behind the 30 second External IM long-poll.

It also creates the delayed-reply failure mode that triggered this plan: if the first 30 second outbound poll returns before the actor finishes, the worker returns to `imsg.watch_messages()` and may not poll External IM again until another inbound iMessage arrives. Long-running actor work can therefore complete in Central IM while the phone receives nothing until a later inbound message or a manual outbound poll wakes the projection path.

### Current IM API Event Semantics

The External IM API provides event long-poll, but the current connection cursor advances when events are read:

```text
read_external_connection_events(connection)
  -> read_im_events(cursor=connection.last_event_id)
  -> if events: save connection.last_event_id = events[-1].event_id
```

The HTTP route also rejects caller-supplied cursors, so the connection owns its event cursor:

```text
GET /api/im/events?wait_ms=...
```

This is clean for a browser-style consumer where "read" can reasonably mean "delivered to client", but it is too weak for a transport adapter whose downstream send can fail after the event has been read. If `imsg send` fails after `/api/im/events` advances `last_event_id`, the reply event may not be returned again by the IM API.

Existing channel tests do not fully prove this failure mode because the fake API used by `test_poll_outbound_does_not_mark_event_sent_when_imessage_send_fails` returns the same fake event on repeated reads. The real External IM API advances the connection cursor.

## Architecture Decision

Use IM API event long-poll as the reply source, but replace read-auto-ack with explicit connection event acknowledgement before splitting the iMessage worker loop.

Recommended shape:

```text
Central IM core / message service
  owns messages, conversations, replies, events, connection cursor, disposition

External IM API
  exposes connection-authenticated send, list actors, read events, get message, ack events

iMessage channel adapter
  owns imsg watch/send, sender normalization, chat route, /actors command, numeric choice, iMessage send confirmation
  consumes IM API events and acknowledges them only after channel projection is handled
```

This avoids two bad alternatives:

1. **Channel-only pending outbox over read-auto-ack.**
   This can mask the symptom, but it makes the channel responsible for recovering Central IM event consumption after the IM API has already advanced. That is a message lifecycle workaround in the adapter.

2. **Full asyncio rewrite.**
   It can solve the concurrency symptom, but it does not fix the event consumption contract. It also increases implementation scope without changing the ownership boundary.

The first product improvement should be explicit event acknowledgement in the IM API plus separated channel inbound/outbound workers.

## Target End-To-End Contract

One contract sentence must stay alive through implementation and verification:

```text
An iMessage sender can send a normal message, immediately send /actors while the actor reply is still pending, receive the actor list promptly, and later receive the original actor reply in the same iMessage chat exactly once.
```

Layer tests are not enough. At least one focused worker test must prove the handoff from iMessage inbound to IM API event consumption back to iMessage outbound.

## Planned Replacement

### Phase 1: Make External IM Event Consumption Acknowledged

Replace the current External IM connection event read contract:

```text
read events -> advance last_event_id immediately
```

with:

```text
read events -> return unacknowledged events after last_event_id
ack event  -> validate visibility and advance last_event_id
```

Concrete changes:

- Add message service operation:

```text
ack_external_connection_event(connection, event_id)
```

- Add External IM session method:

```text
ExternalImSession.ack_event(connection, event_id)
```

- Add HTTP projection:

```text
POST /api/im/events/ack
body: {"event_id": "imev-..."}
```

- Keep cursor ownership server-side. Do not expose arbitrary client cursors on `/api/im/events`.
- Validate that the acked event is visible to the authenticated connection participant.
- Advance `connection.last_event_id` only through the ack operation.
- Update Web IM projection to explicitly ack events after it has fetched and returned the visible projected messages for the requested actor scope.
- Update tests that currently expect `/api/im/events` to auto-advance.

Acceptance for this phase:

- Reading events twice without ack returns the same event.
- Acking the event makes the next read empty.
- Acking a non-visible event is rejected and does not advance the connection cursor.
- Browser/Web projection does not expose connection keys, cursors, or ack details to the browser.
- No Central IM cursor logic appears in `imessage_channel.py`.

### Phase 2: Split iMessage Worker Responsibilities

Replace the serial worker loop with two independent loops sharing the same controller:

```text
Inbound worker:
  imsg.status()
  for row in imsg.watch_messages():
    controller.handle_inbound_message(row)

Outbound worker:
  while not stopped:
    controller.poll_outbound_once(wait_ms=DEFAULT_REPLY_WAIT_MS)
```

Important boundaries:

- `handle_inbound_message()` stays the only inbound iMessage path.
- `poll_outbound_once()` stays the only outbound actor-reply projection path.
- `poll_outbound_once()` consumes IM API events and calls IM API ack after transport handling.
- The worker split must not introduce an in-process message bus, plugin system, generic channel framework, or asyncio rewrite.

Threading details:

- Use a small controller-level lock around channel state load/mutate/save.
- Do not hold the state lock while doing a long-poll wait.
- Re-load state after event long-poll returns before route lookup and mutation.
- Keep `imsg.send` route confirmation before local sent tracking or IM API ack.

Acceptance for this phase:

- A blocked or long-running outbound event wait does not prevent `/actors` from being processed by the inbound worker.
- `stop()` terminates both inbound and outbound workers and still calls the underlying `imsg.stop()`.
- Worker startup failure still leaves Web management available when `imsg` is unavailable.

### Phase 3: Ack Only After iMessage Projection

For each External IM event visible to the iMessage connection:

```text
read event
fetch message via /api/im/messages/{id}
derive reply_to
look up iMessage route by reply_to
send to Messages.app with the existing [Message From ...] prefix
confirm route-scoped Messages.app send status
record channel transport sent event id
ack event through /api/im/events/ack
```

Failure semantics:

- If `imsg.send` fails, do not ack the IM event.
- If `imsg.send` succeeds but IM API ack fails, do not send a duplicate iMessage on the next loop. Use the channel's local sent-event record only as transport idempotency, then retry ack.
- If the event has no route because the channel never sent the original `reply_to` message, acknowledge it as not projectable after fetching enough detail to prove it is not routeable. This preserves forward progress and avoids a permanently poisoned connection cursor.
- If the message body cannot be fetched due to a transient API error, do not ack.

This keeps responsibilities clean:

- IM API owns event cursor and message visibility.
- iMessage channel owns transport delivery idempotency and route projection.
- Neither layer owns both.

### Phase 4: Remove Old Serial Semantics And Residue

Do not keep a compatibility mode where one worker loop still does:

```text
handle inbound -> wait for reply
```

Replacement requirements:

- `ImessageChannelWorker.run_forever()` no longer calls `poll_outbound_once()` after every inbound row.
- There is no config flag that toggles old serial behavior.
- Tests and docs no longer describe reply waiting as part of inbound processing.
- Live surfaces describe the current contract: command handling is prompt; actor replies return asynchronously.

Scoped residue terms for live surfaces:

- `handle_inbound_message(row)` followed by `poll_outbound_once(wait_ms=...` in the same loop;
- prose that says iMessage waits for the actor reply before handling subsequent iMessage input;
- any new direct import in `imessage_channel.py` from `env.services.messages` or `env.repos.messages`;
- any new channel-local code that reads Central IM object files directly.

Historical `docs/memo` files do not need cleanup unless they are the current plan being created or edited.

## Implementation Plan

### Task 1: Lock The IM API Ack Contract With Failing Tests

Files:

- Modify: `tests/test_external_im_session.py`
- Modify: `tests/test_im_http_router.py`
- Modify: `tests/test_im_web_management_projection.py`
- Modify: `tests/test_web_management.py`

Test cases:

- External session read without ack returns the same actor reply event twice.
- External session ack advances the connection cursor and the next read is empty.
- HTTP `/api/im/events` rejects caller cursors as today, but no longer auto-acks.
- HTTP `POST /api/im/events/ack` validates the authenticated connection and visible event.
- Web management event endpoint still returns scoped messages for the selected actor and does not leak ack/cursor details to the browser.

Run focused expected-failing tests before implementation:

```bash
python3 -m pytest -q tests/test_external_im_session.py tests/test_im_http_router.py tests/test_im_web_management_projection.py tests/test_web_management.py
```

Expected before implementation: failures around repeated read/ack route because current code auto-advances and has no ack operation.

### Task 2: Implement IM API Explicit Ack

Files:

- Modify: `scripts/env/services/messages.py`
- Modify: `tools/launcher/external_im_session.py`
- Modify: `tools/launcher/im_http_router.py`
- Modify: `tools/launcher/web_management.py`

Required behavior:

- `read_external_connection_events()` returns events without mutating `connection.last_event_id`.
- `ack_external_connection_event()` validates event visibility and updates `connection.last_event_id`.
- `ExternalImSession.ack_event()` delegates to message service.
- `POST /api/im/events/ack` exposes the operation.
- Web IM projection calls `ack_event()` only for events it returned to the browser projection.

Do not:

- expose client-controlled cursors;
- create a parallel iMessage-only event cursor;
- read or write IM repo files from the HTTP router or Web projection.

Focused verification:

```bash
python3 -m pytest -q tests/test_external_im_session.py tests/test_im_http_router.py tests/test_im_web_management_projection.py tests/test_web_management.py
```

### Task 3: Add iMessage Worker Nonblocking Regression Tests

Files:

- Modify: `tests/test_imessage_channel.py`

Test cases:

- A fake outbound `read_events(wait_ms=30000)` blocks until released while inbound `/actors` is still processed and sends an actor list.
- A normal iMessage actor message is received, the first outbound poll returns no events or times out, the actor reply appears later without any new inbound iMessage, and the outbound worker still polls again and sends the reply to Messages.app.
- Actor reply event is acked only after `imsg.send` succeeds.
- If `imsg.send` fails, the event is not acked.
- If `imsg.send` succeeded but ack fails, the next poll retries ack without sending a duplicate iMessage.
- Worker `stop()` stops both loops.

The tests should use fakes and synchronization primitives, not real `imsg`, real Web server, or sleeps longer than a short condition wait.

Focused expected-failing command before implementation:

```bash
python3 -m pytest -q tests/test_imessage_channel.py
```

Expected before implementation: the nonblocking worker test fails because the current worker processes outbound long-poll inside the inbound loop.

### Task 4: Refactor iMessage Worker To Two Loops

Files:

- Modify: `tools/launcher/imessage_channel.py`

Required behavior:

- `ImessageChannelWorker.start()` starts inbound and outbound worker threads.
- `run_forever()` either becomes the inbound loop or is replaced by explicit `run_inbound_forever()` and `run_outbound_forever()` methods.
- Background error capture reports which loop stopped.
- `stop()` sets one stop flag, calls `imsg.stop()`, and joins all started worker threads.
- `poll_outbound_once()` calls IM API ack after successful projection.
- Controller state mutation is protected by a lock, but long-poll waits do not hold that lock.

Do not:

- introduce asyncio;
- introduce generic channel abstractions;
- introduce a separate event bus;
- keep the old serial loop as an alternate mode.

Focused verification:

```bash
python3 -m py_compile tools/launcher/imessage_channel.py tools/launcher/external_im_session.py tools/launcher/im_http_router.py tools/launcher/web_management.py
python3 -m pytest -q tests/test_imessage_channel.py tests/test_external_im_session.py tests/test_im_http_router.py tests/test_im_web_management_projection.py tests/test_web_management.py
```

### Task 5: Residue And End-To-End Contract Verification

Files:

- Modify if needed: `tests/test_imessage_channel.py`
- Modify if needed: `docs/spec/imessage-channel-smoke-runbook.md`

Required checks:

- Extend residue tests so live runtime/test/spec surfaces do not teach old serial iMessage semantics.
- Keep existing protection that channel semantics stay out of Web HTTP and Central IM core.
- Update the smoke runbook to include the delayed-control regression scenario:

```text
send normal message
immediately send /actors
expect actor-list before or independently of the actor's eventual reply
expect original actor reply to still arrive once
```

Focused verification:

```bash
python3 -m pytest -q tests/test_imessage_channel.py::ImessageChannelResidueTests
rg -n "poll_outbound_once\\(wait_ms=.*reply_wait_ms|waits? for the actor reply before|serial iMessage" tools tests docs/spec -S
```

Expected:

- residue tests pass;
- scoped scan returns no live-surface stale semantics except negative assertions or current plan references that explicitly describe the old behavior as replaced.

### Task 6: Optional Live Smoke

Only run live smoke after focused tests pass and the service lifecycle is controlled.

Command:

```bash
./buddyswitch-codex web --port 8765
```

Manual smoke:

```text
1. Send /actors.
2. Select an actor.
3. Send a normal question.
4. Immediately send /actors again.
5. Confirm actor-list returns promptly.
6. Confirm the actor reply to the original question still arrives once in the same chat.
7. Stop Web and confirm no Web-owned imsg watch process remains.
```

This is not a substitute for automated tests. It is a final product-path confidence check.

## Acceptance Criteria

- `/actors` is no longer blocked by actor reply long-poll.
- Actor replies produced after the first `reply_wait_ms` window are delivered without requiring another iMessage from the user.
- iMessage actor replies still return to the original chat route exactly once.
- External IM events are not acknowledged merely by reading.
- IM event cursor advancement is owned by IM API ack, not channel-local Central IM state.
- iMessage channel does not import Central IM service or repo internals.
- Web IM projection continues to work without exposing browser cursors, connection keys, or ack details.
- No old serial worker path remains.
- No compatibility flag or dual old/new worker mode is introduced.
- Focused behavior tests pass.
- Scoped residue checks over live surfaces pass.
- Any live smoke used for verification includes process cleanup evidence.

## Remaining Risks

- Explicit event ack changes the External IM HTTP contract. Current in-repo consumers must be updated in the same change set, with no compatibility alias.
- If multiple unacked events are returned and a later event is acked before an earlier event, cursor advancement could skip the earlier event. The ack implementation should either process events sequentially or reject out-of-order ack relative to the connection cursor.
- If `imsg.send` succeeds but the process crashes before local sent-event state or IM API ack is saved, duplicate outbound delivery is still possible after restart. The existing route-scoped Messages.app send confirmation reduces false success but cannot make cross-system delivery atomic.
- Route-missing events need a deliberate policy. This plan chooses acknowledge-as-not-projectable after confirming no route exists, because retrying forever cannot create the missing route.

## Plan Verification Checklist

- The plan reads `docs/bitter` principles into concrete constraints.
- The plan states the current task goal and architecture requirements.
- The plan uses IM API as the message capability owner.
- The plan does not make iMessage channel a second message system.
- The plan replaces old serial semantics instead of keeping a compatibility track.
- The plan names concrete files, tests, commands, residue scans, and acceptance criteria.
- The plan preserves an end-to-end user-visible contract.
