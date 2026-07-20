# iMessage Fair Outbound Scheduler Forward-Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace iMessage's serial per-contact outbound long-poll with one iMessage-local fair scheduler that delivers the same contact in FIFO order, delivers different contacts concurrently, retries one contact without blocking another, and meets the agreed real-time bridge SLO without changing Central IM or `/api/im/*`.

**Architecture:** Keep Central IM's existing per-external-session event cursor and ACK as the only durable pending-message truth. Inside `imessage_channel.py`, replace the serial poll loop with non-blocking one-event reads scheduled through at most four shared delivery workers, with one in-flight operation per contact and one runtime round-robin cursor. Persist only iMessage transport retry/failure metadata beside the existing contact binding and GUID links; do not add a second message queue, cross-session IM contract, generic scheduler framework, or per-contact thread.

**Tech Stack:** Python 3.13, `threading`, `concurrent.futures.ThreadPoolExecutor`, existing External IM HTTP API, existing `imsg` command/Message DB confirmation, JSON iMessage channel state, `unittest`/pytest through `./buddyswitch-test focused`.

Date: 2026-07-20

Status: automated implementation and claim-scoped verification complete; real two-contact iMessage validation pending

Branch/worktree: `fea-im` / `/Users/chen/Dev/buddyswitch/.worktrees/fea-im`

---

## 1. FRAME — Product Claim And Scope

### Bottleneck

`ImessageChannelController.poll_outbound_once()` currently loops over every
bound contact and calls `read_events(..., wait_ms=30000)` serially. A silent
contact can therefore consume the entire 30-second wait before a later contact
is inspected. This is the confirmed P2 head-of-line blocking owner.

The current worker split prevents outbound waiting from blocking inbound
`/actors`, but it does not isolate outbound contacts from each other. The
controller's global state lock also spans some HTTP and `imsg.send` calls, so
the implementation must prove that no slow external operation holds the shared
state-file lock.

### Acceptance Sentence

> When Central IM creates an event for iMessage contact B, contact B enters the
> iMessage send path within P95 2 seconds and P99 5 seconds even while contact A
> is idle, sending, or retrying; events for one contact remain FIFO, a delivery
> failure blocks only that contact for at most two minutes, and restart does not
> create an ordinary retry duplicate.

### Product Paths

```text
Actor reply for external user
  -> Central IM immutable message + identity-visible event
  -> existing authenticated GET /api/im/events?limit=1&wait_ms=0
  -> iMessage fair outbound scheduler
  -> one contact-scoped delivery operation
  -> imsg send + route-scoped Messages DB confirmation
  -> persist exact GUID/message/event link
  -> existing POST /api/im/events/ack
  -> user sees the actor reply in the correct iMessage conversation
```

```text
iMessage send/fetch failure
  -> persist retry metadata for that contact only
  -> other contacts continue through available delivery slots
  -> retry with bounded backoff for up to 120 seconds
  -> success: persist GUID link then ACK
  -> terminal failure: persist last_delivery_failure, emit alert, ACK only that
     failed event, and allow the same contact's next Central IM event
```

### Capacity And SLO

- At most 100 bound contacts.
- At most 20 simultaneously active conversations.
- Burst of 50 pending events may queue fairly.
- Maximum four concurrent iMessage delivery operations.
- Discovery/delivery bridge target: P95 at most 2 seconds, P99 at most 5 seconds.
- Same contact: strict FIFO and at most one in-flight event.
- Different contacts: parallel up to the shared limit.

Existing preflight evidence in commit `85a048e` proves the unchanged IM HTTP
path at this capacity:

- 100-session empty sweep P95: 48.4 ms;
- 20 active sessions spread across the scan order: discovery P95 167.1 ms,
  P99 174.0 ms;
- read/get/ACK P99: 13.0 ms;
- 50-event burst drain: 1.057 seconds.

### Protected Contracts

The following are current supported contracts and must remain unchanged:

- `/api/im/events` authenticates exactly one external session per request;
- the server owns each external session cursor;
- `/api/im/events/ack` preserves visibility and strict next-event ordering;
- Central IM remains the only durable pending-event queue;
- existing schema-6 iMessage contact bindings and GUID links are persisted user
  correlation data and must survive the change.

The plan does not introduce old/new coexistence. Schema 6 remains the single
current schema because the two new transport-status fields are optional contact
metadata with canonical empty defaults, not a second payload shape. There is no
dual read, dual write, alias, or migration adapter.

### Explicit Non-Goals

- No `wait_many`, batch session credential, subscription, group cursor, or new
  `/api/im` route.
- No change to Central IM service/repository, `ExternalImSession`,
  `ImHttpRouter`, browser IM, Task Sys, or actor runtime.
- No asyncio rewrite, WebSocket, event bus, plugin/registry, generic channel
  framework, permanent per-contact thread, or second durable outbox.
- No UI work and no expansion to other message channels.
- No mathematical exactly-once claim across an OS/process crash at the physical
  send boundary. The required guarantee is no duplicate from normal ACK retry
  or restart after the confirmed GUID link has been persisted.

## 2. TRACE — Current Owners And Affected Path

| Responsibility | Current/target owner | Rule |
| --- | --- | --- |
| Immutable messages, visible events, cursor, ACK ordering | Central IM | Unchanged |
| Single-session HTTP authentication/projection | `ExternalImSession` + `ImHttpRouter` | Unchanged |
| Contact binding, iMessage route, GUID correlation | `ImessageChannelController` state | Remains singular |
| One contact's read/fetch/send/link/ACK operation | `ImessageChannelController` | Replace serial all-contact method with one contact operation |
| Cross-contact fairness and max concurrency | `ImessageChannelWorker` | Runtime-only scheduling owner |
| Physical send and Messages DB confirmation | `CommandImsgClient` | Unchanged except a bounded subprocess timeout if RED proves required |
| Retry and terminal delivery failure | iMessage contact state | New iMessage-only metadata |
| Worker start/stop | `ImessageChannelWorker` | Must own scheduler executor cleanup |

Current affected source:

- `tools/launcher/imessage_channel.py`
  - `DEFAULT_REPLY_WAIT_MS = 30000`;
  - `poll_outbound_once()` serial contact loop;
  - `run_outbound_forever()` passes the long-poll wait to every contact;
  - `_state_lock` protects one JSON file but currently spans external work in
    inbound and outbound paths.
- `tests/integration/im/test_imessage_outbound.py`
  - only synchronous, one-contact outbound behavior;
  - send/link-before-ACK and ACK-retry idempotency are already valuable proofs.
- `tests/integration/im/test_imessage_worker.py`
  - proves inbound/outbound loop separation, not cross-contact fairness.
- `tests/integration/im/_imessage_fakes.py`
  - fake event reads must honor the real `limit` argument before new FIFO tests
    can be trusted.
- `tests/integration/im/test_imessage_state.py`
  - owns state normalization/startup/residue proof.
- `tests/integration/im/test_external_event_capacity.py`
  - owns the unchanged IM HTTP capacity baseline and will gain the final
    production-scheduler latency proof.

## 3. Target Architecture

### Runtime Shape

```text
Inbound watch thread
  -> parse one iMessage row
  -> snapshot/update contact state under lock
  -> release lock
  -> HTTP or imsg operation
  -> reacquire lock only to persist the result

Outbound scheduler thread
  -> snapshot eligible contact keys
  -> rotate from runtime round-robin cursor
  -> reserve at most available slots
  -> submit one contact operation per slot

Shared delivery executor (max_workers=4)
  -> read one event with wait_ms=0 and limit=1
  -> fetch message
  -> imsg send/confirm
  -> persist GUID link before ACK
  -> ACK event
  -> release contact reservation
```

The scheduler does not store message payloads or durable work. If no slot is
available, the event stays unacknowledged in Central IM. The runtime
`in_flight_contact_keys` set is only a concurrency reservation and is empty
after restart.

### Concrete Runtime State

`ImessageChannelWorker` adds only:

```python
DEFAULT_OUTBOUND_CONCURRENCY = 4
DEFAULT_OUTBOUND_SCAN_INTERVAL_SECONDS = 0.01

self._outbound_executor: ThreadPoolExecutor | None
self._in_flight_contact_keys: set[str]
self._in_flight_lock: threading.Lock
self._poll_cursor: int
```

No `Lane`, `Queue`, registry, or scheduler base class is introduced.

### Contact State

Existing schema-6 contact state remains canonical and gains two normalized,
bounded fields:

```json
{
  "external_session_key": "imsk-...",
  "external_identity_id": "ext-...",
  "route": {"chat_id": "9", "sender": "user@example.com"},
  "seen_inbound_keys": [],
  "message_links": {
    "IMESSAGE-GUID": {"message_id": "msg-...", "event_id": "imev-..."}
  },
  "outbound_retry": {
    "event_id": "imev-...",
    "message_id": "msg-...",
    "first_failed_at": 1784540000.0,
    "next_attempt_at": 1784540001.0,
    "attempts": 1,
    "last_error": "imessage_send_failed"
  },
  "last_delivery_failure": {
    "event_id": "imev-...",
    "message_id": "msg-...",
    "failed_at": 1784540120.0,
    "attempts": 7,
    "last_error": "imessage_send_failed"
  }
}
```

`outbound_retry` is absent/`None` when no event is waiting for retry.
`last_delivery_failure` keeps only the latest terminal failure per contact, so
state is bounded and restart-observable without becoming an audit ledger.

### Retry Policy

```python
OUTBOUND_RETRY_WINDOW_SECONDS = 120.0
OUTBOUND_RETRY_DELAYS_SECONDS = (1.0, 2.0, 4.0, 8.0, 16.0, 30.0)
```

For attempt number `n`, use the indexed delay, clamp subsequent delays to 30
seconds, and clamp every `next_attempt_at` to the absolute 120-second terminal
deadline. `time.time()` is persisted because the deadline must survive restart;
the controller accepts a clock callable so tests advance time without sleeping.

Rules:

1. First fetch/send failure records the event and schedules retry after 1 s.
2. The contact is not eligible before `next_attempt_at`.
3. Retry success clears `outbound_retry`, saves the GUID link, then ACKs.
4. At or after 120 s from `first_failed_at`, do not send again. Persist
   `last_delivery_failure`, clear retry, emit one structured stderr alert, and
   ACK that event to unblock the next event for the same contact.
5. If terminal-failure ACK fails, the event remains visible. Matching
   `last_delivery_failure.event_id` causes ACK-only retry and never another
   iMessage send.
6. Persisted and logged failure values are allow-listed stage codes, never raw
   transport exception text.
7. A successful send with an ACK failure is already protected by
   `message_links`: the next read performs ACK-only retry.

### Locking Invariants

- `_state_lock` may cover only load, validate, reserve, mutate, and save.
- No HTTP call, `imsg.send`, subprocess wait, long-poll, retry wait, or executor
  wait occurs while `_state_lock` is held.
- State writes remain serialized because the state file has one owner.
- The worker reservation guarantees at most one outbound operation per contact.
- Central IM's strict ACK ordering supplies FIFO; the channel reads `limit=1`
  and does not reproduce cursor logic.

## 4. File Map

```text
tools/launcher/imessage_channel.py
  Replace the serial outbound path; add the local scheduler, contact operation,
  retry/failure normalization, narrow lock boundaries, and bounded cleanup.

tests/integration/im/_imessage_fakes.py
  Make existing doubles match real limit semantics; add controlled blocking,
  concurrency counting, and injected failure doubles used by behavior tests.

tests/integration/im/test_imessage_outbound.py
  Prove one-contact delivery, FIFO, retry persistence, terminal failure,
  ACK-only recovery, and no duplicate normal retry.

tests/integration/im/test_imessage_worker.py
  Prove cross-contact parallelism, max four, fairness, inbound/outbound lock
  isolation, and executor cleanup.

tests/integration/im/test_imessage_state.py
  Prove canonical normalization and source residue absence.

tests/integration/im/test_external_event_capacity.py
  Extend the real HTTP capacity fixture to drive the production scheduler with
  100 bound contacts and 20 active events under the 2-second SLO.
```

No other runtime, API, Web, Task, or actor file is in the planned write set.

## 5. PROVE/BUILD Tasks

### Task 0: Freeze Baseline And Source Identity

**Files:** none

- [x] Record the exact source identity and dirty scope:

```bash
git rev-parse HEAD
git status --short
```

Expected before implementation: only user-owned changes already present are
reported; do not stage, rewrite, or mix them.

- [x] Run the current claim-adjacent baseline:

```bash
./buddyswitch-test focused \
  tests/integration/im/test_external_event_capacity.py \
  tests/integration/im/test_imessage_outbound.py \
  tests/integration/im/test_imessage_worker.py \
  tests/integration/im/test_imessage_state.py
```

Expected: current tests pass. They do not prove multi-contact fairness; that is
the intentional RED added next.

### Task 1: RED — Prove Cross-Contact Isolation And Bounded Concurrency

**Files:**
- Modify: `tests/integration/im/_imessage_fakes.py`
- Modify: `tests/integration/im/test_imessage_worker.py`

- [x] First make `_FakeBuddySwitchImApi.read_events()` mirror the real API by
  returning at most `limit` unacknowledged events. This is test-fixture repair,
  not product behavior:

```python
available = [
    dict(row)
    for row in self.events_by_key.get(external_session_key, [])
    if str(row.get("event_id") or "") not in acked_ids
]
return {"ok": True, "events": available[:limit]}
```

- [x] Rename `_BlockingReadApi` to `_ControlledBlockingReadApi` and keep it only
  as the current contract double proving that a deliberately stalled External
  IM read cannot stop inbound work or another contact. It must block only keys
  explicitly configured by the test; the old all-reads-block shape is deleted.

- [x] Add a controlled `imsg` double that blocks selected routes and records
  active/max-active send counts under a lock. It must return a unique GUID and
  must not implement scheduling decisions:

```python
class _ControlledSendImsg(_QueueImsg):
    def __init__(self, *, blocked_chat_ids: set[str] | None = None) -> None:
        super().__init__()
        self.blocked_chat_ids = set(blocked_chat_ids or set())
        self.release_by_chat_id = {
            chat_id: threading.Event() for chat_id in self.blocked_chat_ids
        }
        self.send_started_by_chat_id: dict[str, threading.Event] = {}
        self.active_sends = 0
        self.max_active_sends = 0
        self._send_lock = threading.Lock()

    def send(self, *, route: dict[str, Any], text: str) -> _FakeSendReceipt:
        chat_id = str(route.get("chat_id") or "")
        started = self.send_started_by_chat_id.setdefault(chat_id, threading.Event())
        with self._send_lock:
            self.active_sends += 1
            self.max_active_sends = max(self.max_active_sends, self.active_sends)
        started.set()
        try:
            release = self.release_by_chat_id.get(chat_id)
            if release is not None:
                release.wait(timeout=2)
            return super().send(route=route, text=text)
        finally:
            with self._send_lock:
                self.active_sends -= 1
```

- [x] Add these exact worker behavior tests:

```text
test_silent_contact_does_not_delay_ready_contact
test_blocked_contact_send_does_not_block_other_contact
test_same_contact_never_has_two_events_in_flight
test_outbound_scheduler_never_exceeds_four_active_sends
test_round_robin_reaches_contacts_after_the_first_four
```

Each test creates complete bound contact state and real-shaped event/message
payloads. Assertions must observe delivered iMessage rows, ACK calls, FIFO
order, and active send count—not merely executor submission or fake call count.

- [x] Run the RED tests through the only public entry:

```bash
./buddyswitch-test focused \
  tests/integration/im/test_imessage_worker.py::ImessageWorkerTests::test_silent_contact_does_not_delay_ready_contact \
  tests/integration/im/test_imessage_worker.py::ImessageWorkerTests::test_blocked_contact_send_does_not_block_other_contact \
  tests/integration/im/test_imessage_worker.py::ImessageWorkerTests::test_same_contact_never_has_two_events_in_flight \
  tests/integration/im/test_imessage_worker.py::ImessageWorkerTests::test_outbound_scheduler_never_exceeds_four_active_sends \
  tests/integration/im/test_imessage_worker.py::ImessageWorkerTests::test_round_robin_reaches_contacts_after_the_first_four
```

Expected RED: current worker either lacks the new constructor/operation or
serially blocks the later contact. Record the run id and exact expected failure.

### Task 2: GREEN — Replace The Serial Long-Poll With One-Contact Operations

**Files:**
- Modify: `tools/launcher/imessage_channel.py`
- Modify: `tests/integration/im/test_imessage_outbound.py`
- Modify: `tests/integration/im/test_imessage_worker.py`

- [x] Replace `poll_outbound_once(wait_ms, limit)` with two concrete controller
  operations:

```python
def outbound_contact_keys(self, *, now: float | None = None) -> list[str]:
    """Return stable eligible bound contact keys; no network or cursor work."""

def deliver_outbound_contact_once(self, *, sender_key: str) -> dict[str, Any]:
    """Read and handle at most one event for one contact using wait_ms=0."""
```

`deliver_outbound_contact_once` must use the existing sequence:

```text
snapshot binding/route under lock
GET events limit=1 wait_ms=0 outside lock
reload and validate same contact under lock
if existing message_link -> ACK only
if matching terminal failure -> ACK only
GET message outside lock
imsg send outside lock
persist GUID/message/event link under lock
ACK outside lock
```

It returns one of these current statuses and no alternate delivery path:

```text
idle
contact_unavailable
ack_retried
delivered
retry_scheduled
retry_wait
delivery_failed
```

- [x] Replace worker reply-wait configuration with explicit local scheduler
  configuration:

```python
def __init__(
    self,
    controller: ImessageChannelController,
    *,
    max_outbound_workers: int = DEFAULT_OUTBOUND_CONCURRENCY,
    outbound_scan_interval_seconds: float = DEFAULT_OUTBOUND_SCAN_INTERVAL_SECONDS,
) -> None:
```

- [x] Implement the scheduler directly in `ImessageChannelWorker`:

```python
def _schedule_outbound_contacts(self, contact_keys: list[str]) -> int:
    # Rotate by _poll_cursor, skip reserved keys, reserve no more than free
    # slots, submit deliver_outbound_contact_once, and attach one completion
    # callback that always releases the reservation.

def _finish_outbound_contact(self, sender_key: str, future: Future[Any]) -> None:
    # Report unexpected exceptions, then remove sender_key in finally.
```

The comment above describes the complete permitted behavior; the method must
not enqueue event payloads or create per-contact workers.

- [x] Remove all calls that pass a positive wait to outbound event reads.
`BuddySwitchImApi.read_events` remains unchanged because `wait_ms` is a current
single-session API capability used by other current consumers.

- [x] Update the existing outbound tests to call
`deliver_outbound_contact_once(sender_key="sender:user-a@example.com")` and
preserve their link-before-ACK/no-duplicate assertions.

- [x] Run Task 1 tests and all existing outbound tests:

```bash
./buddyswitch-test focused \
  tests/integration/im/test_imessage_worker.py \
  tests/integration/im/test_imessage_outbound.py
```

Expected GREEN: all selected tests pass; no test sleeps for a 30-second poll.

### Task 3: RED/GREEN — Remove Shared-Lock External I/O

**Files:**
- Modify: `tools/launcher/imessage_channel.py`
- Modify: `tests/integration/im/test_imessage_worker.py`
- Modify: `tests/integration/im/test_imessage_routing.py`

- [x] Add this exact product-boundary test:

```text
test_blocked_inbound_api_for_contact_a_does_not_block_outbound_contact_b
```

The fake API blocks A's `send_to_actor`; B already has a ready actor event.
Start the real worker, push A's inbound message, wait until A is blocked, then
assert B's iMessage send completes before A is released.

- [x] Run the test and record RED caused by `_state_lock` spanning A's HTTP
operation:

```bash
./buddyswitch-test focused \
  tests/integration/im/test_imessage_worker.py::ImessageWorkerTests::test_blocked_inbound_api_for_contact_a_does_not_block_outbound_contact_b
```

- [x] Refactor inbound processing to one concrete snapshot/result pattern:

```python
@dataclass(frozen=True)
class _InboundContext:
    sender_key: str
    external_session_key: str
    route: dict[str, Any]
    inbound_key: str

def _prepare_inbound_context(self, row: dict[str, Any]) -> _InboundContext | dict[str, Any]:
    # Bind/snapshot/dedupe under short lock sections. External session creation
    # happens outside the lock and is persisted before the context is returned.

def _mark_inbound_seen(self, *, sender_key: str, inbound_key: str) -> None:
    # Reload, mutate only that contact, and save while holding _state_lock.
```

All `_handle_*` functions perform HTTP/`imsg` work from immutable context and
call `_mark_inbound_seen` only after the observable operation succeeds. Native
reply GUID lookup snapshots `message_links` under lock before the HTTP reply.

Execution note: the implementation kept this context as four direct local
values instead of introducing `_InboundContext`; this preserves the same short
lock/external-I/O boundary with less live abstraction.

- [x] Re-run the RED and all routing tests:

```bash
./buddyswitch-test focused \
  tests/integration/im/test_imessage_worker.py::ImessageWorkerTests::test_blocked_inbound_api_for_contact_a_does_not_block_outbound_contact_b \
  tests/integration/im/test_imessage_routing.py
```

Expected GREEN: B completes while A is blocked; existing duplicate, parser,
route, and message-link behavior remains exact.

### Task 4: RED/GREEN — Persist Contact-Scoped Retry And Terminal Failure

**Files:**
- Modify: `tools/launcher/imessage_channel.py`
- Modify: `tests/integration/im/test_imessage_outbound.py`
- Modify: `tests/integration/im/test_imessage_state.py`

- [x] Add a mutable wall clock test double and these exact tests:

```text
test_send_failure_persists_retry_without_ack
test_retry_is_ineligible_until_next_attempt_at
test_restart_resumes_due_retry_and_persists_link_before_ack
test_retry_failure_does_not_block_other_contact
test_two_minute_failure_is_persisted_alerted_and_acked
test_terminal_failure_ack_retry_never_resends_imessage
test_success_clears_retry_state
test_schema_6_state_without_retry_fields_normalizes_to_current_empty_state
test_invalid_retry_payload_is_discarded_not_executed
```

The clock is injected through a production-relevant dependency:

```python
class _MutableClock:
    def __init__(self, now: float = 1_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds
```

- [x] Run RED before state/production changes:

```bash
./buddyswitch-test focused \
  tests/integration/im/test_imessage_outbound.py \
  tests/integration/im/test_imessage_state.py
```

Expected RED: retry fields/statuses and clock dependency are absent.

- [x] Add strict normalizers for `outbound_retry` and
`last_delivery_failure`. Reject incomplete, negative, non-finite, or
mismatched values to the canonical empty value; never execute malformed retry
state.

- [x] Implement retry calculation in one controller helper:

```python
def _record_outbound_failure(
    self,
    *,
    sender_key: str,
    event_id: str,
    message_id: str,
    error_code: str,
) -> dict[str, Any]:
    """Persist retry or terminal failure and return its delivery status."""
```

No retry rule may be copied into the worker. The worker only asks
`outbound_contact_keys()` for eligible contacts.

- [x] Emit exactly one terminal alert per event transition, excluding message
content, contact address, session key, and route:

```text
iMessage channel delivery_failed event_id=<id> message_id=<id> attempts=<n> error=<safe-stage-code>
```

- [x] Re-run RED targets for GREEN:

```bash
./buddyswitch-test focused \
  tests/integration/im/test_imessage_outbound.py \
  tests/integration/im/test_imessage_state.py
```

Expected GREEN: retry is durable and contact-scoped; terminal failure unblocks
only after durable record and ACK; logs contain no external-user address.

### Task 5: RED/GREEN — Bound Worker Lifecycle And Transport Hangs

**Files:**
- Modify: `tools/launcher/imessage_channel.py`
- Modify: `tests/unit/im/test_imessage_command_client.py`
- Modify: `tests/integration/im/test_imessage_worker.py`

- [x] Add lifecycle tests:

```text
test_imsg_send_command_timeout_is_retryable_channel_error
test_worker_stop_cancels_unscheduled_work_and_joins_scheduler_threads
test_worker_start_failure_creates_no_executor_or_thread_residue
test_unexpected_delivery_exception_releases_contact_reservation
```

- [x] Run RED:

```bash
./buddyswitch-test focused \
  tests/unit/im/test_imessage_command_client.py \
  tests/integration/im/test_imessage_worker.py
```

- [x] If the timeout RED proves the subprocess itself is unbounded, add one
  iMessage-only constant and map `subprocess.TimeoutExpired` to `ChannelError`:

```python
IMSG_SEND_COMMAND_TIMEOUT_SECONDS = 10.0
```

Do not change Central IM timeouts. `stop()` must set the stop event, stop the
watch process, stop new scheduling, join inbound/scheduler threads, and shut
down the one executor with pending futures canceled. Every started delivery
operation remains bounded by HTTP and iMessage command/status timeouts.

- [x] Re-run for GREEN with clean resource evidence:

```bash
./buddyswitch-test focused \
  tests/unit/im/test_imessage_command_client.py \
  tests/integration/im/test_imessage_worker.py
```

### Task 6: Product Capacity Proof Through The Production Scheduler

**Files:**
- Modify: `tests/integration/im/test_external_event_capacity.py`

- [x] Extend the existing real-HTTP fixture without changing its lower-layer
baseline. Create canonical iMessage state for all 100 external sessions, spread
20 active sessions through the scan order, run the production
`ImessageChannelWorker` against a thread-safe immediate-confirmation `imsg`
double, and measure Central-event availability to recorded iMessage send.

- [x] Assert:

```text
all 20 messages reach their exact routes
no route receives another contact's content
each event is ACKed once
same-contact order is preserved
bridge P95 <= 2.0 seconds
bridge P99 <= 5.0 seconds
worker/executor/server threads are stopped
```

- [x] Run the exact product proof at least three times through the public entry:

```bash
PYTEST_ADDOPTS=-s ./buddyswitch-test focused \
  tests/integration/im/test_external_event_capacity.py
```

Record all three run ids and metric lines. A single outlier above the gate is a
failure to investigate, not a reason to loosen the SLO.

## 6. REPLACE — Remove The Retired Serial Model

### Task 7: Delete Old Behavior And Prove Absence

**Files:**
- Modify: `tools/launcher/imessage_channel.py`
- Modify: `tests/integration/im/_imessage_fakes.py`
- Modify: `tests/integration/im/test_imessage_state.py`
- Modify: affected iMessage tests listed above

- [x] Delete, rather than retain as aliases:

```text
DEFAULT_REPLY_WAIT_MS
reply_wait_ms
poll_outbound_once
positive wait_ms calls from the iMessage worker
_BlockingReadApi (replaced by the contact-scoped _ControlledBlockingReadApi)
tests that teach one serial all-contact outbound loop
```

- [x] Extend `ImessageForwardResidueTests` with exact forbidden source terms:

```python
for retired in (
    "DEFAULT_REPLY_WAIT_MS",
    "reply_wait_ms",
    "poll_outbound_once",
):
    self.assertNotIn(retired, source)
```

- [x] Run repository residue inspection excluding historical memos/plans:

```bash
rg -n \
  "DEFAULT_REPLY_WAIT_MS|reply_wait_ms|poll_outbound_once|wait_ms=30000" \
  tools scripts tests docs/arch \
  --glob '!docs/memo/**' \
  --glob '!docs/superpowers/**'
```

Expected: no current runtime, test, or architecture surface teaches the retired
serial model. Historical memos may retain history and are not live policy.

- [x] Prove no iMessage scheduling/retry semantics leaked outward:

```bash
rg -n \
  "outbound_retry|last_delivery_failure|DEFAULT_OUTBOUND_CONCURRENCY|delivery_failed" \
  scripts/env tools/launcher/external_im_session.py \
  tools/launcher/im_http_router.py tools/launcher/web_management.py docs/arch
```

Expected: no matches. `web_management.py` remains start/stop composition only
and requires no modification.

## 7. VERIFY — Claim-Scoped Evidence

### Task 8: Focused Verification And Acceptance Audit

- [x] Discover current affected targets before running; do not hard-code a
  stale broad suite:

```bash
rg -l "imessage_channel|ImessageChannel|BuddySwitchImApi" \
  tests/unit tests/integration tests/process | sort
```

- [x] Run all directly affected iMessage targets through the sole public entry.
At minimum the candidate command is:

```bash
./buddyswitch-test focused \
  tests/unit/im \
  tests/integration/im \
  tests/unit/web/test_management_service.py \
  tests/process/launcher/test_public_cli.py
```

Do not run `./buddyswitch-test full` unless the branch is frozen for merge,
the user explicitly requests repository-wide acceptance, or the affected-risk
review discovers a repository-wide contract.

- [x] Verify syntax/diff/boundary hygiene:

```bash
git diff --check
git status --short
git diff --name-only
git diff -- tools/launcher/im_http_router.py \
  tools/launcher/external_im_session.py scripts/env/services/messages.py
```

Expected last diff: empty.

- [x] Audit proof classes:

| Proof class | Required evidence |
| --- | --- |
| Product | 100/20 scheduler latency test and two-contact real iMessage check |
| Contract | FIFO, max four, retry timing, terminal failure, ACK-only recovery |
| Architecture | only iMessage source/tests changed; state lock never spans external I/O |
| Replacement | serial names/calls absent from all live surfaces |
| Operations | executor/watch/server cleanup; bounded command timeout; structured terminal alert |

- [x] Inspect the final diff against the acceptance sentence. If any material
  proof is absent, leave the implementation unaccepted and name the exact
  remaining owner/action.

## 8. ACCEPT — Real iMessage Validation Requiring User Participation

Automated implementation does not require user participation. Stop before this
task and obtain an explicit test window because it sends real external
iMessages.

### Task 9: Guided Two-Contact Device Check

- [ ] Confirm two consenting test contacts and a five-minute send window.
- [ ] Start the current `fea-im` service through the normal launcher; do not
  reuse an unknown worker from another worktree.
- [ ] Run these cases with timestamps and exact event/message/GUID correlation:

```text
1. A remains silent while B receives an actor reply; B bridge latency < 2 s.
2. A's send is intentionally delayed/fails while B receives normally.
3. Two replies for A remain ordered while one reply for B is interleaved.
```

- [ ] Confirm Messages DB rows for every physical send:

```text
error=0
is_sent=1
is_delivered=1 when the platform supplies delivery confirmation
one Central event -> one visible iMessage bubble
correct chat/handle for both contacts
```

- [ ] Stop the task-owned service and prove no process, socket, executor thread,
  lock, or temporary state remains.

## 9. Execution Evidence Contract

The execution evidence below is part of this memo. It records the source-bound
RED/GREEN and acceptance state without creating another evidence ledger.

```text
source commit
task and claim
RED run id + expected failure
GREEN run id + exact selected target result
capacity run ids + metric lines
residue command + result
real iMessage event/message/GUID/route evidence
cleanup result
omitted checks and residual risk
```

Do not claim completion from a broad suite alone, from mock call counts, or
before the real two-contact product check is either passed or explicitly
reported as pending user participation.

## 10. Execution Evidence — 2026-07-20

Source commit before implementation: `2494ec4c5fa796b974ffa27224c4abb3932a300f`.

Automated implementation write scope is exactly:

```text
tools/launcher/imessage_channel.py
tests/integration/im/_imessage_fakes.py
tests/integration/im/test_external_event_capacity.py
tests/integration/im/test_imessage_outbound.py
tests/integration/im/test_imessage_state.py
tests/integration/im/test_imessage_worker.py
tests/unit/im/test_imessage_command_client.py
this memo
```

No Central IM, `ExternalImSession`, router, Web management, Task Sys, actor
runtime, or architecture file changed.

### RED/GREEN Evidence

| Claim | RED | GREEN |
| --- | --- | --- |
| Cross-contact fairness, FIFO, max four | `d3747eda57bc413bb7e6cfa92d06e641` — five expected constructor/behavior failures | `3180399473314253a53fa56568676676` — 5 passed |
| Shared lock does not span A's blocked inbound HTTP while B delivers | `6d4f94100b994bb686c4aaeb93568d2f` — B blocked | `4a774449edb74ecaaa0c80b4bdaff180` — 16 passed including routing |
| Durable retry, restart, two-minute terminal failure, ACK-only recovery | `f7e40c2c64114dc09a5f32a4c3bb8bf5` — 7 expected failures | `ebb4f64a1591456491fb97f5588f12d9` — 7 passed |
| Bounded `imsg send` and worker lifecycle | `6756db0c39054a9a8b02ccc21f84bae8` — unwrapped/unbounded send timeout | `aa5055a5861f49baadb2fcf6d9d37b29` — 8 passed |
| Retired serial model absent | `bae16ec6a7b646f4bef5ed24bbce86f0` — old constant/method found | `2a57d4b764b543048534e9cb96cd0226` — 13 passed, 10 residue subtests passed |
| Independent-review edge cases: absolute deadline, fetch exception, hard cap, partial startup, safe errors | `fa15257234fd41feab73acef2c38abaa` — five expected failures | `7e68636b068c467381766138de35f3c0` — 5 passed, 4 subtests passed |
| Persisted free-form error rejection | `587781d09b5c44e79a773e7f93eaeb29` — raw detail accepted | `8bafc98410dc4f60b10b19795377dd01` — 2 passed, 4 subtests passed |

Baseline run `aa9af47de855484da25648a37bd8990d`: 19 passed, 7
subtests passed. Final affected-surface run on the reviewed source
`4960ab4049574d5d8f1a3ba1d396ca12`: 182 passed, 117 subtests
passed. Independent re-review confirmed all five Important findings resolved
with no remaining Critical or Important issue.

### Production-Scheduler Capacity Evidence

All final runs used 100 real HTTP external sessions, 20 active contacts, four
iMessage workers, two additional FIFO events on one contact, exact route
assertions, single-ACK assertions, and clean worker/server shutdown:

| Run id | P95 | P99 | Result |
| --- | ---: | ---: | --- |
| `bfbe86227e194fa9b600683387c86651` | 288.9 ms | 499.5 ms | pass |
| `8264aa63acef415b8704934d8313c927` | 281.8 ms | 486.2 ms | pass |
| `73f6f03118e64b8f94de8883010e98f0` | 293.2 ms | 499.7 ms | pass |

### Replacement And Boundary Evidence

- `git diff --check`: clean.
- Runtime/API boundary diff for `im_http_router.py`,
  `external_im_session.py`, and `scripts/env/services/messages.py`: empty.
- Scheduler/retry owner terms are absent from `scripts/env`, External IM,
  router, Web management, and `docs/arch`.
- The only live-tree matches for retired names are the scoped negative residue
  assertions in `test_imessage_state.py`, which are permitted safety guards.

### Pending Product Evidence

Task 9 remains pending explicit user participation because it sends real
iMessages. Until the two-contact check passes, automated architecture and
capacity acceptance is complete, but final product acceptance is not claimed.
No repository-wide full suite was run because the change is iMessage-local and
the affected-surface run was clean.
