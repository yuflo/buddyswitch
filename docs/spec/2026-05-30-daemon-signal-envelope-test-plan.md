# Daemon Signal Envelope Test Plan

## Goal

Verify the 2026-05-30 daemon signal iteration:

- daemon cross-actor delivery uses a generic `DaemonSignalEnvelope`;
- daemon mailbox validates only envelope shape and target actor;
- message-specific payload validation moves into `MessageAvailableHandler`;
- Task TUI local notification behavior remains unchanged.

Authoritative input: `docs/memo/2026-05-30-daemon-signal-communication-iteration-task.md`.

## Resource Lifecycle Guard

Follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

- Unit tests should use pure functions, fake clients, and temporary directories.
- Socket tests may start in-process mailbox or central daemon servers only with explicit `close()` and `thread.join(timeout=...)`.
- Do not run the broad suite until focused socket lifecycle tests pass and leave no daemon server thread running.
- Final verification includes a residual process check for `central_daemon.py` and `instance_daemon.py`.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | Daemon signal envelope fields are `signal_id`, `type`, `source_actor_address`, `target_actor_address`, `payload`, and `created_at`. |
| FR2 | Daemon base validation rejects missing/invalid signal fields and requires `payload` to be an object. |
| FR3 | Daemon base validation rejects legacy message-shaped mailbox fields: top-level `message_id`, `from_actor_address`, `to_actor_address`, `from_buddy`, `to_buddy`, `content`, and `message`. |
| FR4 | Central daemon delivery accepts `signal.deliver` with `signal`, routes by `target_actor_address`, and returns `delivery_status` plus `handling_status` where available. |
| FR5 | `event.deliver`, if present, accepts only `DaemonSignalEnvelope` and never a message-specific event. |
| FR6 | Mailbox accepts `mailbox.deliver` with `signal`, validates local target actor, dispatches signal handlers, and returns handled / ignored / failed results. |
| FR7 | Mailbox base code does not know `message.available` or validate `message_id`. |
| FR8 | Signal handlers use `handles(signal)` and `handle_signal(context, state, actions, signal)`. No dynamic subscription system is introduced. |
| FR9 | `MessageAvailableHandler` handles only `signal.type == "message.available"` and validates `payload.message_id` inside the handler. |
| FR10 | `MessageAvailableHandler` submits a read prompt through `ActionGateway` without message body text. |
| FR11 | Instance daemon keeps local runtime notification handlers separate from remote mailbox signal handlers. |
| FR12 | Existing Task TUI notification behavior remains covered by existing daemon/task handler regression tests. |
| FR13 | Runtime tool `DaemonAccess` exposes `deliver_signal` and builds `deliver_message_available` as a generic signal convenience. |
| FR14 | Boundary tests prevent daemon-owned code from reintroducing message-shaped mailbox events or fuzzy target routing. |

## Test Groups

### T1: Daemon Signal Envelope

File: `tests/test_daemon_mailbox.py`

Cases:

- `test_daemon_signal_envelope_is_generic_and_payload_transparent`
  - Build a `message.available` signal using `daemon_signal_envelope`.
  - Assert top-level fields are generic.
  - Assert `message_id` is only under `payload`.
  - Assert no `from_actor_address`, `to_actor_address`, `from_buddy`, `to_buddy`, `content`, or `message`.
- `test_validate_daemon_signal_rejects_legacy_message_event_shape`
  - Pass the old top-level `message_id` / `from_actor_address` / `to_actor_address` shape.
  - Expect `ValueError` mentioning `DaemonSignalEnvelope`.
- `test_validate_daemon_signal_allows_unknown_signal_type_with_object_payload`
  - Pass `type: "task.updated"` and arbitrary object payload.
  - Expect validation success without business-field checks.

### T2: Central Signal Delivery

File: `tests/test_daemon_mailbox.py`, `tests/test_central_daemon_service.py`

Cases:

- `test_signal_deliver_writes_to_mailbox_socket`
  - Start mailbox server in a thread.
  - Register target endpoint kind `daemon_mailbox_socket`.
  - Call central service `signal.deliver` with `signal`.
  - Assert handler received the normalized signal and thread exits after close.
- `test_signal_deliver_reports_delivery_failed_for_unreachable_mailbox`
  - Register a target endpoint pointing to a missing socket.
  - Assert `delivery_status == "delivery_failed"` and registry row remains online.
- `test_signal_deliver_reports_target_not_online`
  - Register then unregister target.
  - Assert `delivery_status == "target_not_online"`.
- `test_event_deliver_rejects_legacy_message_event_shape`
  - Call `event.deliver` with the old message-shaped event.
  - Assert `delivery_status == "invalid_signal"`.

### T3: Mailbox Signal Dispatch

File: `tests/test_daemon_mailbox.py`

Cases:

- `test_mailbox_rejects_signal_for_other_actor`
  - Deliver a valid signal whose `target_actor_address` is not local.
  - Expect mailbox error `wrong_target_actor`.
- `test_mailbox_reports_ignored_when_no_handler_handles_signal`
  - Use a handler whose `handles()` returns false.
  - Assert `handling_status == "ignored"` and `handled_count == 0`.
- `test_mailbox_reports_failed_when_handler_fails`
  - Use a handler returning `HandlerResult.failed(...)` or a dict with `status: failed`.
  - Assert mailbox delivery succeeds at the protocol layer and result has `handling_status == "failed"` plus a handling error.

### T4: Message Available Signal Handler

File: `tests/test_message_available_handler.py`

Cases:

- `test_message_available_handler_ignores_non_message_available_signals`
- `test_message_available_handler_rejects_signal_for_other_actor_address`
- `test_message_available_handler_rejects_missing_payload_message_id`
- `test_message_available_handler_submits_read_prompt_through_action_gateway`
- `test_message_available_handler_records_failed_submit_turn_as_handler_failure`

### T5: Entrypoint and Runtime Access

Files: `tests/test_instance_daemon_entrypoint.py`, `tests/test_runtime_actor_profile.py`

Cases:

- Instance daemon `run` passes Task TUI notification handlers separately from mailbox signal handlers.
- `ToolContext.daemon.deliver_signal(...)` calls daemon client `deliver_signal`.
- `ToolContext.daemon.deliver_message_available(...)` builds a generic signal with `payload.message_id`.

### T6: Boundary Review Tests

File: `tests/test_daemon_communication_boundary.py`

Cases:

- Daemon-owned mailbox and central delivery code do not contain `message_available_event`, `validate_mailbox_event`, `handle_mailbox_event`, `from_actor_address`, `to_actor_address`, or top-level message-specific delivery terms.
- `MessageAvailableHandler` is the only daemon-owned code allowed to contain `message.available` and `message_id`.
- Daemon delivery path contains `signal.deliver` / `deliver_signal` and no `to_buddy` fuzzy routing or `ambiguous_online_actor`.

## Verification Commands

Focused red/green commands:

```bash
python3 -m pytest tests/test_daemon_mailbox.py -q
python3 -m pytest tests/test_message_available_handler.py -q
python3 -m pytest tests/test_central_daemon_service.py -q
python3 -m pytest tests/test_runtime_actor_profile.py -q
python3 -m pytest tests/test_daemon_communication_boundary.py -q
```

Focused daemon regression:

```bash
python3 -m pytest tests/test_daemon_core.py tests/test_daemon_core_decoupling.py tests/test_daemon_service_contract.py tests/test_task_checkout_handler.py tests/test_instance_daemon_entrypoint.py -q
```

Existing message/runtime smoke:

```bash
python3 -m pytest tests/test_message_env_tool.py tests/test_runtime_broker.py -q
```

Final gates:

```bash
git diff --check
python3 -m pytest tests -q
pgrep -fl "central_daemon.py|instance_daemon.py" || true
```

The residual process check must show no test-owned daemon processes. Existing developer shell processes are not failures if they are unrelated to this test run.

## Plan Review

- Requirements are derived from the memo's P1-P5 scope and acceptance criteria, not from the current message-shaped implementation.
- The test plan exercises behavior first: generic envelope, routing, mailbox dispatch, handler semantics, runtime access, and boundary search.
- Broad verification is held until focused socket lifecycle tests pass.
- Non-goals are excluded: no message durable rewrite, no offline queue, no subscription engine, no Task TUI signal rewrite.
