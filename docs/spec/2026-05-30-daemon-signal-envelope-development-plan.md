# Daemon Signal Envelope Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development while implementing behavior changes. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace the message-specific daemon mailbox event shape with a generic `DaemonSignalEnvelope`.

**Architecture:** Keep the current central daemon, registry, reachability, and mailbox socket infrastructure. Replace the delivery payload from message-shaped event to generic signal envelope. Keep Task TUI on local runtime notifications; only remote mailbox ingress becomes signal-based.

**Tech Stack:** Python stdlib Unix sockets, existing `runtime_kernel.protocol` framing, `RuntimeActorAddress`, pytest/unittest.

---

## File Structure

- Modify `tools/launcher/daemon_mailbox.py`
  - Replace `message_available_event(...)` and `validate_mailbox_event(...)` with:
    - `daemon_signal_envelope(...)`
    - `validate_daemon_signal(...)`
  - Keep mailbox server protocol method `mailbox.deliver`, but params must contain `signal`.
  - Dispatch handlers through `handles(signal)` and `handle_signal(...)`.
- Modify `tools/launcher/central_daemon_core.py`
  - Add `signal.deliver` as the primary delivery method.
  - Route by `signal["target_actor_address"]`.
  - Return `delivery_status` and propagated `handling_status`.
  - Make `event.deliver` reject legacy message-shaped events or delegate only when params contain a generic `signal`.
- Modify `scripts/env/tool_runtime/daemon_client.py`
  - Add `deliver_signal(signal=...)`.
  - Stop using `deliver_event` in main-path code.
- Modify `tools/launcher/message_available_handler.py`
  - Rename mailbox handler methods to signal handler methods.
  - Validate `payload.message_id` inside the handler.
- Modify `tools/launcher/instance_daemon.py`
  - Keep separate default local notification handlers and remote mailbox signal handlers.
- Modify `scripts/env/tool_runtime/context.py`
  - Add `DaemonAccess.deliver_signal(...)`.
  - Make `deliver_message_available(...)` construct a generic signal with `payload.message_id`.
- Modify tests:
  - `tests/test_daemon_mailbox.py`
  - `tests/test_message_available_handler.py`
  - `tests/test_central_daemon_service.py`
  - `tests/test_runtime_actor_profile.py`
  - `tests/test_daemon_communication_boundary.py`
  - Keep existing daemon/task regression tests green.

## Task 1: Write Failing Generic Signal Tests

- [x] Update `tests/test_daemon_mailbox.py` for generic `DaemonSignalEnvelope`, `signal.deliver`, mailbox `signal` params, ignored/failed handling status, and legacy event rejection.
- [x] Update `tests/test_message_available_handler.py` to call `handles(signal)` and `handle_signal(...)` with `payload.message_id`.
- [x] Update `tests/test_runtime_actor_profile.py` to expect `deliver_signal(...)` and generic signal payloads.
- [x] Update `tests/test_daemon_communication_boundary.py` so daemon base files cannot contain message-shaped mailbox logic.
- [x] Run:

```bash
python3 -m pytest tests/test_daemon_mailbox.py tests/test_message_available_handler.py tests/test_runtime_actor_profile.py tests/test_daemon_communication_boundary.py -q
```

Expected: fail against the current message-specific implementation.

## Task 2: Implement Generic Signal Envelope and Mailbox Dispatch

- [x] In `daemon_mailbox.py`, implement `daemon_signal_envelope(...)`.
  - Validate `signal_id` as a non-empty id.
  - Validate `type` as a non-empty string.
  - Validate `source_actor_address` and `target_actor_address` through `RuntimeActorAddress.from_payload`.
  - Require `payload` to be a dict and copy it without business validation.
  - Require `created_at` to be a non-empty string.
- [x] In `daemon_mailbox.py`, implement `validate_daemon_signal(...)`.
  - Reject unsupported top-level fields, including the old message-shaped event fields.
  - Return a normalized signal with only generic envelope fields.
- [x] Update `DaemonMailboxServer.dispatch(...)`.
  - Read `params["signal"]`.
  - Validate target actor against local actor.
  - For each handler, call `handles(signal)` when present.
  - Call `handle_signal(context, state, actions, signal)` only for matching handlers.
  - Return `handling_status: handled | ignored`.
  - Return `handling_status: failed` with `handling_error` when any matching handler fails or raises.
- [x] Run:

```bash
python3 -m pytest tests/test_daemon_mailbox.py -q
```

Expected: pass after implementation.

## Task 3: Implement Central Signal Delivery and Client API

- [x] In `central_daemon_core.py`, route `signal.deliver` to `_deliver_signal`.
- [x] Normalize the signal with `validate_daemon_signal`.
- [x] Check reachability using `signal["target_actor_address"]`.
- [x] Send mailbox request `{"signal": signal}`.
- [x] Return:
  - `delivery_status: "invalid_signal"` for invalid envelope;
  - `delivery_status: "target_not_online"` for offline / missing target;
  - `delivery_status: "delivery_failed"` for mailbox connection or mailbox error;
  - `delivery_status: "delivered"` plus `handling_status` for successful mailbox response.
- [x] In `daemon_client.py`, add `deliver_signal(...)`.
- [x] Leave `event.deliver` only as a generic-signal bridge if needed; it must reject the legacy message-shaped event.
- [x] Run:

```bash
python3 -m pytest tests/test_daemon_mailbox.py tests/test_central_daemon_service.py -q
```

Expected: pass.

## Task 4: Migrate MessageAvailableHandler to SignalHandler

- [x] In `message_available_handler.py`, implement:
  - `handles(signal) -> bool`;
  - `handle_signal(context, state, actions, signal) -> HandlerResult`.
- [x] Accept only `signal["type"] == "message.available"`.
- [x] Validate `payload` is an object and `payload["message_id"]` is a valid runtime id.
- [x] Validate `target_actor_address` equals the local actor address.
- [x] Submit this prompt through `ActionGateway.submit_turn`:

```text
[MESSAGE AVAILABLE]
message_id: <message_id>
Use message.list to read the message when ready.
```

- [x] Do not include message body or content in the prompt.
- [x] Run:

```bash
python3 -m pytest tests/test_message_available_handler.py -q
```

Expected: pass.

## Task 5: Update Runtime Access and Entrypoint Wiring

- [x] In `context.py`, add `DaemonAccess.deliver_signal(...)`.
- [x] Make `deliver_message_available(...)` call `deliver_signal(...)` with a generic envelope:

```json
{
  "signal_id": "sig-...",
  "type": "message.available",
  "source_actor_address": {"buddy_id": "...", "instance_id": "..."},
  "target_actor_address": {"buddy_id": "...", "instance_id": "..."},
  "payload": {"message_id": "msg-..."},
  "created_at": "..."
}
```

- [x] Keep `instance_daemon.default_handlers()` for Task TUI notifications.
- [x] Keep `instance_daemon.default_mailbox_handlers()` for remote signal handlers.
- [x] Run:

```bash
python3 -m pytest tests/test_runtime_actor_profile.py tests/test_instance_daemon_entrypoint.py -q
```

Expected: pass.

## Task 6: Boundary Cleanup and Focused Regression

- [x] Remove or rename message-shaped daemon base helpers and tests:
  - no `message_available_event` in `daemon_mailbox.py`;
  - no `validate_mailbox_event`;
  - no `handle_mailbox_event`;
  - no `from_actor_address` / `to_actor_address` in daemon base delivery files.
- [x] Keep `message.available` and `message_id` references only in `MessageAvailableHandler`, message business code, tests, and docs.
- [x] Run:

```bash
python3 -m pytest tests/test_daemon_communication_boundary.py -q
python3 -m pytest tests/test_daemon_core.py tests/test_daemon_core_decoupling.py tests/test_daemon_service_contract.py tests/test_task_checkout_handler.py tests/test_instance_daemon_entrypoint.py -q
python3 -m pytest tests/test_message_env_tool.py tests/test_runtime_broker.py -q
```

Expected: pass.

## Task 7: Final Verification and Review

- [x] Run:

```bash
git diff --check
python3 -m pytest tests -q
pgrep -fl "central_daemon.py|instance_daemon.py" || true
```

- [x] Review against the memo:
  - daemon mailbox base code does not validate `message_id`;
  - daemon mailbox base code does not special-case `message.available`;
  - central daemon primary delivery API is signal-based;
  - delivery result distinguishes invalid signal, target not online, delivery failed, handled, ignored, and failed;
  - Task TUI local notification path is unchanged;
  - no service-starting test leaked daemon processes.

## Self Review

- Scope matches P1-P5 in the memo and excludes the listed non-goals.
- The plan replaces the current message-shaped mailbox path instead of layering compatibility around it.
- Tests start from functional behavior and boundary invariants, not from the current helper implementation.
- Resource lifecycle constraints are explicit before broad verification.
