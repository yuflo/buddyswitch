# New Daemon Communication Upgrade Test Plan

## Goal

Verify the daemon-owned communication layer described in `docs/memo/2026-05-29-new-daemon-communication-architecture.html`:

- central daemon is an independent shared-root process;
- central daemon is the only writer of presence registry state;
- instance daemon registers through `RuntimeActorAddress`;
- daemon exposes contacts, reachability, event delivery, mailbox consumption, and `message.available` action trigger;
- the old direct file append / fuzzy `to_buddy` / `ambiguous_online_actor` daemon path is removed.

This plan is for the daemon upgrade. It does not implement the full `message.contacts` / `message.send` / `message.list` business rewrite.

## Resource Lifecycle Guard

The resource lesson in `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md` is mandatory.

Service-starting tests must prove:

- every spawned process has a pid file or captured pid;
- teardown terminates process groups or calls the service stop path;
- sockets, pid files, and marker files are removed;
- broad tests run only after focused lifecycle tests pass;
- post-run residual checks verify no central daemon or mailbox server process remains from tests.

Unit tests for lifecycle should prefer fake `subprocess.Popen`. Socket integration tests must start servers in-process with explicit `close()` and `join()` rather than detached daemons.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | `central_daemon` provides start/status/stop/serve lifecycle for one shared root. |
| FR2 | central daemon exposes a Unix socket request API and returns structured JSON envelopes. |
| FR3 | registration records use `actor_address` from actor_profile and keep endpoint/heartbeat/status outside identity. |
| FR4 | registry write operations happen only inside central daemon service code, not in tool-runtime helper code. |
| FR5 | unregister and heartbeat preserve registration facts and express `online` / `registered_offline`. |
| FR6 | `contacts.list` returns online sendable actor records and supports optional `buddy_id` filtering. |
| FR7 | `actor.check_reachability` accepts explicit `target_actor_address` and returns `online`, `registered_offline`, `never_registered`, or `invalid_actor_address`. |
| FR8 | `event.deliver` accepts only reference-only event payloads and rejects message body / `from_buddy` / `to_buddy`. |
| FR9 | event delivery targets a mailbox socket, not a file append endpoint. |
| FR10 | target instance daemon owns a mailbox server and validates `to_actor_address` before handling events. |
| FR11 | `message.available` mailbox event triggers an ActionGateway prompt for the target buddy to read messages. |
| FR12 | daemon status includes central registration/mailbox observability without moving message data into daemon. |
| FR13 | daemon code contains no main-path `to_buddy` resolution, `ambiguous_online_actor`, or direct notification file append. |

## Test Groups

### T1: Central Daemon Lifecycle

File: `tests/test_central_daemon_service.py`

Cases:

- `test_central_daemon_lifecycle_paths_are_shared_root_scoped`
  - Build paths under a temp shared root.
  - Assert socket, pid, log, registry paths live under that root.
- `test_start_daemon_spawns_independent_process_and_status_reads_ready`
  - Patch `subprocess.Popen`, pid liveness, and ping.
  - Assert `start` writes pid/marker/log paths and returns `started: true`.
- `test_stop_daemon_terminates_process_and_cleans_runtime_files`
  - Seed pid/socket marker.
  - Patch termination.
  - Assert pid/socket marker cleanup.
- `test_socket_server_ping_round_trip_closes_cleanly`
  - Start server in a background thread.
  - Send `daemon.ping`.
  - Close server and assert thread exits.

### T2: Registry and Presence Semantics

File: `tests/test_central_daemon_service.py`

Cases:

- `test_register_projects_actor_address_and_presence_fields`
  - Request `daemon.register`.
  - Assert row shape:
    - `actor_address == {"buddy_id": "dev", "instance_id": "inst-dev-daemon"}`;
    - endpoint/heartbeat/status/last_seen_at are sibling fields;
    - no `buddy`, `daemon_buddy`, or `target_buddy_instance`.
- `test_register_rejects_presence_fields_inside_actor_address`
  - Send actor_address containing `endpoint` or `status`.
  - Expect protocol rejection.
- `test_unregister_marks_registered_offline_instead_of_deleting`
  - Register then unregister.
  - Assert row remains with `status: registered_offline`.
- `test_heartbeat_restores_online_status`
  - Register, unregister, heartbeat.
  - Assert row returns to `online` with updated `last_seen_at`.

### T3: Contacts and Reachability

File: `tests/test_central_daemon_service.py`

Cases:

- `test_contacts_list_returns_only_online_actor_addresses`
  - Register one online dev and one offline design.
  - Assert contacts returns only online.
- `test_contacts_list_filters_by_buddy_id_without_resolving_send_target`
  - Register dev and pm.
  - Query `buddy_id=dev`.
  - Assert only dev rows are returned.
- `test_reachability_distinguishes_online_offline_never_registered_invalid`
  - Online row returns `online`.
  - Offline row returns `registered_offline`.
  - Valid unknown address returns `never_registered`.
  - Invalid payload returns `invalid_actor_address`.
- `test_reachability_has_no_ambiguous_online_actor_status`
  - Register two different actor addresses under the same buddy id.
  - Check each explicit address independently.
  - Assert no `ambiguous_online_actor` appears.

### T4: Event Delivery and Mailbox Contract

File: `tests/test_daemon_mailbox.py`

Cases:

- `test_message_available_event_is_reference_only`
  - Build event with `message_id`, `from_actor_address`, `to_actor_address`.
  - Assert forbidden fields are absent.
- `test_event_deliver_rejects_message_body_fields`
  - Send event containing `content`, `message`, `from_buddy`, or `to_buddy`.
  - Expect rejection before mailbox delivery.
- `test_event_deliver_writes_to_mailbox_socket`
  - Start a mailbox server in a thread.
  - Register target endpoint kind `daemon_mailbox_socket`.
  - Deliver event through central daemon service.
  - Assert mailbox handler received exactly that event.
  - Close server and assert thread exits.
- `test_event_deliver_reports_delivery_failed_for_unreachable_mailbox`
  - Register endpoint pointing to missing socket.
  - Assert `delivery_status: delivery_failed` and registry row remains online until heartbeat changes it.

### T5: Instance Daemon Integration

File: `tests/test_daemon_core.py`, `tests/test_instance_daemon_entrypoint.py`

Cases:

- `test_run_daemon_starts_mailbox_before_registering_presence`
  - Patch app-server client and central client.
  - Assert registration endpoint kind is `daemon_mailbox_socket`.
- `test_run_daemon_heartbeats_central_daemon_during_idle`
  - Simulate app-server idle timeout.
  - Assert heartbeat call was made.
- `test_run_daemon_unregisters_and_stops_mailbox_on_exit`
  - Simulate stop exception.
  - Assert unregister called and mailbox server close called.
- `test_instance_daemon_cli_wires_message_available_mailbox_handler`
  - Assert run/start/status use task notification handlers and message mailbox handlers.

### T6: Message Available Consumer

File: `tests/test_message_available_handler.py`

Cases:

- `test_message_available_handler_ignores_non_message_available_events`
- `test_message_available_handler_rejects_event_for_other_actor_address`
- `test_message_available_handler_submits_read_prompt_through_action_gateway`
- `test_message_available_handler_records_failed_submit_turn_as_handler_failure`

Expected prompt shape:

```text
[MESSAGE AVAILABLE]
message_id: msg-...
Use message.list to read the message when ready.
```

The prompt may include actor addresses. It must not include message body text.

### T7: Cleanup of Old Daemon Path

File: `tests/test_daemon_communication_boundary.py`

Cases:

- `test_no_daemon_presence_module_direct_registry_writer`
  - Assert daemon registration uses central daemon client.
  - Assert no source file imports `env.tool_runtime.daemon_presence`.
- `test_no_direct_notification_file_append_endpoint`
  - Search daemon code for `daemon_state_file`, `notifications.jsonl`, and direct event append helpers.
  - These must not be part of delivery path.
- `test_no_to_buddy_or_ambiguous_status_in_daemon_delivery_path`
  - Search daemon-owned files for `to_buddy`, `resolve_notification_target`, and `ambiguous_online_actor`.
  - Allow `to_buddy` only in existing message repository/tool business files that are outside this daemon upgrade.

## Verification Commands

Focused red/green groups:

```bash
python3 -m pytest tests/test_central_daemon_service.py -q
python3 -m pytest tests/test_daemon_mailbox.py -q
python3 -m pytest tests/test_message_available_handler.py -q
python3 -m pytest tests/test_daemon_core.py tests/test_instance_daemon_entrypoint.py -q
python3 -m pytest tests/test_daemon_communication_boundary.py -q
```

Focused daemon regression group:

```bash
python3 -m pytest tests/test_daemon_core.py tests/test_daemon_core_decoupling.py tests/test_daemon_service_contract.py tests/test_task_checkout_handler.py tests/test_instance_daemon_entrypoint.py -q
```

Existing message/runtime smoke:

```bash
python3 -m pytest tests/test_runtime_actor_profile.py tests/test_message_env_tool.py tests/test_runtime_broker.py -q
```

Final gates:

```bash
git diff --check
python3 -m pytest tests -q
pgrep -fl "central_daemon.py|instance_daemon.py" || true
```

The residual process check must show no test-owned daemon process after the suite.

## Review Checklist

- Tests are derived from functional requirements, not from current helper implementation.
- No test assumes registry is a directly writable library file.
- No broad suite is run before focused service lifecycle and cleanup checks pass.
- Event payload tests prove daemon only transports references.
- Boundary search tests prevent the old daemon notification path from remaining as a silent second path.
