# iMessage Channel / IM API Boundary Optimization Master Plan

Date: 2026-06-30

## Goal

Complete the optimization described in `docs/memo/2026-06-30-imessage-channel-im-api-boundary-optimization-plan.md` while preserving the Central IM ownership boundary:

```text
iMessage sender sends a normal actor message
  -> BuddySwitch accepts and wakes the actor through the IM API
  -> the sender can immediately send /actors or a numeric selection
  -> control replies are returned promptly
  -> the actor reply is later projected back to the same iMessage chat exactly once
```

The iMessage channel remains a transport adapter. Central IM product semantics stay in `scripts/env/services/messages.py`, `tools/launcher/external_im_session.py`, `tools/launcher/im_http_router.py`, and the owning Web projection. The channel must not import Central IM repos/services, read Central IM object files, or create a second local message system.

## Required Source Review

Read before this plan:

- `AGENTS.md`
- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`
- `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`
- `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`
- `docs/memo/2026-06-30-imessage-channel-im-api-boundary-optimization-plan.md`

Relevant constraints from those sources:

- Fix the layer that owns the broken contract.
- Prove both behavior and live-surface residue when replacing semantics.
- Keep one end-to-end user-visible contract alive through sliced implementation.
- Do not start broad live/service verification without lifecycle cleanup proof.
- Avoid wrappers, dual tracks, compatibility flags, generic channel frameworks, or adapter-local product semantics.

## Current Code Evidence

The memo still matches this worktree.

- `tools/launcher/imessage_channel.py:125` exposes only `GET /api/im/events`; there is no `ack_event` client method.
- `tools/launcher/imessage_channel.py:431` reads outbound events, fetches messages, sends to Messages.app, then records only local `sent_outbound_event_ids`.
- `tools/launcher/imessage_channel.py:438-464` has no IM API ack after iMessage projection.
- `tools/launcher/imessage_channel.py:586-592` runs a serial worker loop: `status()`, `watch_messages()`, `handle_inbound_message(row)`, then `poll_outbound_once(wait_ms=reply_wait_ms)`.
- `tools/launcher/imessage_channel.py:410-429` keeps inbound control handling in `handle_inbound_message()`, which is the path that must remain prompt after the split.
- `scripts/env/services/messages.py:334-343` contains `_save_connection_last_event()`.
- `scripts/env/services/messages.py:372-397` reads external connection events and advances `connection.last_event_id` on read.
- `scripts/env/services/messages.py:365-366` also advances the connection cursor after the external sender posts a message, so reply reads start after the sender's own event.
- `tools/launcher/external_im_session.py:96-101` only delegates `read_events`; it has no ack operation.
- `tools/launcher/im_http_router.py:85-93` exposes `GET /api/im/events` and rejects client cursors, but does not expose `/api/im/events/ack`.
- `tools/launcher/web_management.py:461-488` reads events, filters by actor identity, fetches matching messages, and returns `events` plus `messages` without acking returned events.
- `scripts/env/repos/messages.py:279-334` already stores events per `visible_to_identity_id` and can list visible events for one participant, so service-level ack can validate visibility before cursor advancement.

Existing tests that currently encode old semantics:

- `tests/test_external_im_session.py:195-219` expects the second read to be empty without ack.
- `tests/test_im_product_core.py:188-229` expects external connection reads to consume reply events.
- `tests/test_im_http_router.py:142-158` expects repeated HTTP event read to be empty without ack.

Existing tests already protecting the target boundary:

- `tests/test_imessage_channel.py:397-405` prevents `imessage_channel.py` from importing Central IM internals.
- `tests/test_imessage_channel.py:435-453` keeps iMessage channel semantics out of Web HTTP and Central IM core.
- `tests/test_im_web_management_projection.py:92-115` prevents HTTP/Web projections from owning External IM session internals directly.
- `tests/test_web_management.py:1223-1234` proves Web IM events do not expose connection keys, participant tokens, or cursors.
- `tests/test_web_management.py:1236-1297` proves current Web IM events are actor-scoped.

Live surface evidence:

- `docs/spec/imessage-channel-smoke-runbook.md:41-52` proves the normal `/actors` -> selection -> normal message -> reply path and A/B isolation.
- The runbook does not yet cover the new delayed-control regression: normal message, immediate `/actors`, prompt actor list, later original reply.

Baseline verification before implementation:

```bash
python3 -m pytest -q tests/test_external_im_session.py tests/test_im_http_router.py tests/test_im_web_management_projection.py tests/test_web_management.py tests/test_imessage_channel.py
```

Result on 2026-06-30:

```text
93 passed, 69 subtests passed in 111.49s
```

## Phase Order

### Phase 0: Orientation And Source Review

Output this master plan. Do not change business code.

Gate:

- Required guidance and memo are read.
- Current code and tests are surveyed.
- Current baseline verification is recorded.
- Open policy tension is identified before implementation.

### Phase 1: External IM Event Ack Contract

Plan file:

- `docs/spec/imessage-channel-im-api-boundary-optimization/phase-01-external-im-event-ack.md`

Owning boundary:

- Central IM service owns event visibility and connection cursor advancement.
- External IM session and HTTP router expose the service operation.
- Web management consumes the operation without exposing ack/cursor details to the browser.

Target behavior:

- Reading events does not advance `connection.last_event_id`.
- `ack_external_connection_event(connection, event_id)` validates the event is visible to the authenticated connection participant.
- Ack advances the connection cursor through the IM API only.
- `POST /api/im/events/ack` accepts `{"event_id": "imev-..."}` for authenticated connections.
- Web IM projection acks only events whose messages it successfully returns or deliberately consumes under the policy below.

Required tests:

- Repeated read without ack returns the same event.
- Ack then read returns empty.
- Non-visible ack is rejected and does not advance the cursor.
- HTTP cursor rejection remains.
- HTTP ack route is authenticated and validates visibility.
- Web projection still returns scoped messages and does not expose ack/cursor details.

Focused command:

```bash
python3 -m pytest -q tests/test_external_im_session.py tests/test_im_product_core.py tests/test_im_http_router.py tests/test_im_web_management_projection.py tests/test_web_management.py
```

### Phase 2: Split iMessage Worker Responsibilities

Plan file:

- `docs/spec/imessage-channel-im-api-boundary-optimization/phase-02-imessage-worker-split.md`

Owning boundary:

- iMessage channel owns transport watch/send loops and per-sender channel state.
- It must continue to consume only the External IM HTTP API.

Target behavior:

- Inbound loop handles `imsg.watch_messages()` rows through `handle_inbound_message()`.
- Outbound loop continuously calls `poll_outbound_once(wait_ms=DEFAULT_REPLY_WAIT_MS)` until stopped.
- Long-poll waits do not hold the channel state lock.
- `stop()` stops both loops, joins worker threads, and calls `imsg.stop()`.
- Web management can still start when `imsg.status()` fails.

Required tests:

- A blocked outbound long-poll does not block inbound `/actors`.
- A reply created after the first outbound poll still sends without a new inbound iMessage.
- `stop()` terminates both loops.
- Startup failure reporting identifies the failed loop and keeps Web management lifecycle behavior intact.

Focused command:

```bash
python3 -m pytest -q tests/test_imessage_channel.py tests/test_web_management.py
```

### Phase 3: Ack Only After iMessage Projection

Plan file:

- `docs/spec/imessage-channel-im-api-boundary-optimization/phase-03-imessage-projection-ack.md`

Owning boundary:

- IM API owns event cursor.
- iMessage channel owns transport delivery idempotency and route projection.

Target behavior:

- `poll_outbound_once()` reads events, fetches each message, maps `reply_to` to the stored iMessage route, sends to Messages.app, records local transport idempotency, then acks the IM event.
- If `imsg.send` fails, the IM event is not acked and local sent-event state is not recorded.
- If `imsg.send` succeeds but ack fails, the next poll retries ack without sending a duplicate iMessage.
- If no route exists after the message is fetched, the event is acked as not projectable so the connection cursor is not poisoned.
- If message fetch fails transiently, the event is not acked.

Required tests:

- Actor reply event is acked only after successful `imsg.send`.
- Failed `imsg.send` leaves the event unacked.
- Ack failure after send does not duplicate iMessage delivery on retry.
- Missing route is acked as not projectable after message fetch.
- Message fetch failure does not ack.

Focused command:

```bash
python3 -m pytest -q tests/test_imessage_channel.py
```

### Phase 4: Remove Serial Semantics And Live-Surface Residue

Plan file:

- `docs/spec/imessage-channel-im-api-boundary-optimization/phase-04-residue-live-surface.md`

Owning boundary:

- Tests and docs/spec prove current live behavior and stop teaching the old serial worker semantics.

Target behavior:

- `ImessageChannelWorker.run_forever()` no longer performs `handle inbound -> poll outbound`.
- No config flag toggles the old serial behavior.
- Live surfaces describe prompt control handling and asynchronous actor replies.
- Historical memo files are not cleanup targets.

Required checks:

```bash
python3 -m pytest -q tests/test_imessage_channel.py::ImessageChannelResidueTests
rg -n "poll_outbound_once\\(wait_ms=.*reply_wait_ms|waits? for the actor reply before|serial iMessage" tools tests docs/spec -S
```

Expected scan result: no live-surface stale semantics except negative assertions or the current optimization plan describing replaced behavior.

### Phase 5: Final Acceptance

Output:

- `docs/spec/imessage-channel-im-api-boundary-optimization/99-final-acceptance.md`

Required contents:

- Memo task completion matrix.
- Stage documents and final status.
- Added/modified tests list.
- Focused verification commands and results.
- Broader verification commands and results.
- Residue scans and results.
- Live smoke result if run, including startup, shutdown, and residual process checks.
- Remaining risks.
- Explicit statement on old serial semantics, compatibility tracks, and adapter-local Central IM semantics.

Final focused verification:

```bash
python3 -m py_compile tools/launcher/imessage_channel.py tools/launcher/external_im_session.py tools/launcher/im_http_router.py tools/launcher/web_management.py scripts/env/services/messages.py
python3 -m pytest -q tests/test_external_im_session.py tests/test_im_product_core.py tests/test_im_http_router.py tests/test_im_web_management_projection.py tests/test_web_management.py tests/test_imessage_channel.py
python3 -m pytest -q tests/test_imessage_channel.py::ImessageChannelResidueTests
rg -n "poll_outbound_once\\(wait_ms=.*reply_wait_ms|waits? for the actor reply before|serial iMessage" tools tests docs/spec -S
```

Optional live smoke, only after automated gates pass:

```bash
./buddyswitch-codex web --port 8765
```

Manual contract:

```text
1. Send a normal actor message.
2. Immediately send /actors.
3. Confirm the actor list returns promptly.
4. Confirm the original actor reply still arrives once in the same chat.
5. Stop Web.
6. Confirm no Web-owned imsg watch process remains.
```

## Boundary Rules

Allowed in iMessage channel:

- Sender normalization.
- iMessage route storage.
- Pending numeric actor choice state.
- Active actor selection per sender.
- iMessage inbound GUID dedupe.
- External IM message id to iMessage route mapping.
- Outbound event transport idempotency after Messages.app send success.
- HTTP calls to External IM API.

Forbidden in iMessage channel:

- Imports from `env.services.messages` or `env.repos.messages`.
- Reads or writes of Central IM object files.
- Connection cursor calculation.
- Central IM conversation, reply, disposition, or visibility rules.
- An iMessage-only event cursor.
- A local channel outbox that compensates for IM API read-auto-ack.
- Old/new worker compatibility modes.
- A generic event bus, plugin framework, channel framework, or asyncio rewrite.

Allowed in External IM API/service:

- Event visibility validation.
- Authenticated connection cursor ownership.
- Explicit event ack.
- HTTP/session projection of core IM operations.

Forbidden in External IM API/service:

- Client-controlled cursors for `/api/im/events`.
- Browser-exposed connection keys, participant tokens, or ack details.
- iMessage-specific route or Messages.app semantics.

## Policy Tension To Resolve In Phase 1

Evidence:

- Web UI polls `buildImEventsUrl(target.identity_id, 15000)` in `tools/launcher/assets/web-management/app.js:904-924`.
- Web management requires actor scope for events in `tests/test_web_management.py:1298-1322`.
- Current Web management filters returned events by `identity_id` in `tools/launcher/web_management.py:461-488`.
- The memo requires explicit connection-level ack and warns that acking a later event before an earlier unacked event can skip the earlier event.

Tension:

```text
single connection cursor + actor-scoped Web event endpoint + strict in-order ack
```

can block a selected actor's later event behind an earlier off-scope event. Acking the selected actor's later event would skip the earlier event. Acking filtered-out off-scope events would violate the memo's "ack events returned to the projection" intent.

Settled Phase 1 resolution:

- Keep the IM API ack contract connection-scoped and sequential.
- Do not expose cursors or ack to the browser.
- Define External IM consumable events as visible events not authored by the connection identity, so synchronous sends do not reappear through `/api/im/events`.
- In Web management, process events in connection order:
  - Return and ack matching selected-actor events after their messages are included in the payload.
  - Fetch enough detail to classify off-scope events, omit them from the selected-actor payload, and ack them as consumed by the Web projection.
  - Rely on direct conversation restore as the durable source for actors that were not selected while their events arrived.
  - If product needs cross-actor event fanout later, add a core-owned Web event projection model in a separate task rather than smuggling per-actor cursors into the browser or iMessage adapter.

This is captured in `phase-01-external-im-event-ack.md` and is the policy for Phase 1 implementation.

## Global Acceptance

The work is complete only when all of these are proven:

- External IM events are not acknowledged by read.
- Ack advances `connection.last_event_id` only through the IM API operation.
- Non-visible event ack is rejected.
- Web projection still works without exposing connection keys, cursors, or ack details.
- `/actors` is not blocked by outbound long-poll.
- Actor replies produced after an earlier long-poll timeout are still delivered without another inbound iMessage.
- iMessage actor replies return to the original chat route exactly once.
- Failed iMessage sends do not ack IM events.
- Ack failures after iMessage send do not duplicate iMessage delivery.
- No old serial worker path, compatibility flag, or dual mode remains.
- No Central IM cursor logic or repo/service imports appear in `tools/launcher/imessage_channel.py`.
- Live surfaces no longer teach old serial reply-wait semantics.
- `99-final-acceptance.md` records verification evidence and remaining risk.
