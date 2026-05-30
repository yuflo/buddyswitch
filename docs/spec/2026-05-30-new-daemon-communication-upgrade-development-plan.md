# New Daemon Communication Upgrade Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace the temporary daemon presence helper with a real shared-root central daemon process plus instance daemon mailbox delivery.

**Architecture:** `actor_profile` remains the only owner of runtime actor address. A new central daemon process owns presence registry, contacts, reachability, and event delivery. Each instance daemon registers through the central daemon, exposes a mailbox socket, consumes `message.available`, and triggers the local ActionGateway.

**Tech Stack:** Python stdlib Unix sockets, existing `runtime_kernel.protocol` framing, launcher daemon core, actor_profile `RuntimeActorAddress`, pytest/unittest.

---

## File Structure

- Create `tools/launcher/central_daemon.py`
  - CLI: `serve`, `start`, `status`, `stop`, `stop-if-idle`, `request`.
  - Owns independent process lifecycle.
- Create `tools/launcher/central_daemon_core.py`
  - Central daemon paths, registry state, request dispatch, Unix socket server.
  - Single writer of registry.
- Create `scripts/env/tool_runtime/daemon_client.py`
  - Small client used by tools and launcher code to talk to central daemon.
  - Contains request helpers: register, unregister, heartbeat, contacts, reachability, deliver.
- Create `tools/launcher/daemon_mailbox.py`
  - Instance mailbox Unix socket server.
  - Validates target actor address and dispatches local mailbox handlers.
- Create `tools/launcher/message_available_handler.py`
  - Handles `message.available` events and submits a read prompt through ActionGateway.
- Modify `tools/launcher/daemon_core.py`
  - Replace `daemon_presence` direct writes with central daemon client calls.
  - Start/stop mailbox lifecycle inside instance daemon run loop.
  - Register endpoint kind `daemon_mailbox_socket`.
  - Heartbeat during idle.
- Modify `tools/launcher/instance_daemon.py`
  - Wire default mailbox handlers separately from app-server notification handlers.
- Modify `tools/launcher/daemon.sh`
  - Ensure central daemon before starting instance daemon.
  - Call stop-if-idle after instance daemon stop.
- Modify `scripts/env/tool_runtime/context.py`
  - Replace `daemon_presence` access with explicit central daemon client access.
- Delete or fully stop using `scripts/env/tool_runtime/daemon_presence.py`
  - No library-level registry writes remain.
- Add tests:
  - `tests/test_central_daemon_service.py`
  - `tests/test_daemon_mailbox.py`
  - `tests/test_message_available_handler.py`
  - `tests/test_daemon_communication_boundary.py`
  - update existing daemon and instance daemon tests.

## Task 1: Central Daemon Lifecycle and Registry Tests

- [x] Add `tests/test_central_daemon_service.py` with lifecycle path, fake process start/stop, ping socket, registration, unregister, heartbeat, contacts, and reachability tests from the test plan.
- [x] Run:

```bash
python3 -m pytest tests/test_central_daemon_service.py -q
```

Expected: fail because central daemon modules do not exist.

## Task 2: Implement Central Daemon Service

- [x] Create `tools/launcher/central_daemon_core.py`.
  - Define `CentralDaemonPaths(shared_root)`.
  - Store pid/socket/log under `<shared-root>/run/central-daemon/`.
  - Store registry under `<shared-root>/state/runtime/central-daemon/registry.json`.
  - Implement `CentralDaemonService.dispatch(request)`.
  - Implement methods:
    - `daemon.ping`
    - `daemon.register`
    - `daemon.unregister`
    - `daemon.heartbeat`
    - `daemon.registry`
    - `contacts.list`
    - `actor.check_reachability`
    - `event.deliver`
  - Use `RuntimeActorAddress.from_payload()` for every identity payload.
  - Keep endpoint/heartbeat/status outside `actor_address`.
  - Mark unregister as `registered_offline`, do not delete row.
- [x] Create `tools/launcher/central_daemon.py`.
  - Add CLI lifecycle and JSON output.
  - Start with `subprocess.Popen(..., start_new_session=True)`.
  - Stop by pid and cleanup socket/pid marker.
- [x] Run:

```bash
python3 -m pytest tests/test_central_daemon_service.py -q
```

Expected: pass.

## Task 3: Central Daemon Client and Boundary Replacement Tests

- [x] Add `tests/test_daemon_communication_boundary.py`.
  - Assert daemon code imports `daemon_client`, not `daemon_presence`.
  - Assert daemon-owned files do not contain direct file append delivery.
  - Assert daemon-owned delivery path does not expose fuzzy `to_buddy` resolution or `ambiguous_online_actor`.
- [x] Run:

```bash
python3 -m pytest tests/test_daemon_communication_boundary.py -q
```

Expected: fail against current `daemon_presence` path.

- [x] Create `scripts/env/tool_runtime/daemon_client.py`.
  - Implement socket request helper using `runtime_kernel.protocol`.
  - Resolve socket from `BUDDYSWITCH_CENTRAL_DAEMON_SOCKET` or `<shared-root>/run/central-daemon/central-daemon.sock`.
  - Provide explicit methods: `register_actor`, `unregister_actor`, `heartbeat_actor`, `list_contacts`, `check_reachability`, `deliver_event`.
- [x] Modify `tools/launcher/daemon_core.py` to use `daemon_client`.
- [x] Remove imports and use of `env.tool_runtime.daemon_presence`.
- [x] Delete `scripts/env/tool_runtime/daemon_presence.py` after all references are gone.
- [x] Run:

```bash
python3 -m pytest tests/test_daemon_communication_boundary.py tests/test_daemon_core.py -q
```

Expected: pass after daemon tests are updated for central client calls.

## Task 4: Instance Mailbox and Delivery Tests

- [x] Add `tests/test_daemon_mailbox.py`.
  - Verify mailbox socket receives event.
  - Verify target actor mismatch is rejected.
  - Verify malformed event is rejected.
  - Verify server closes and thread exits.
- [x] Run:

```bash
python3 -m pytest tests/test_daemon_mailbox.py -q
```

Expected: fail because mailbox module does not exist.

- [x] Create `tools/launcher/daemon_mailbox.py`.
  - `message_available_event(...)` validates reference-only event payload.
  - `DaemonMailboxServer` listens on a Unix socket and handles `mailbox.deliver`.
  - Server validates `event.to_actor_address == local_actor_address`.
  - Server dispatches each accepted event to mailbox handlers.
  - `close()` removes socket.
- [x] Wire `central_daemon_core.event.deliver` to connect to endpoint kind `daemon_mailbox_socket`.
- [x] Run:

```bash
python3 -m pytest tests/test_daemon_mailbox.py tests/test_central_daemon_service.py -q
```

Expected: pass.

## Task 5: Message Available Handler

- [x] Add `tests/test_message_available_handler.py`.
  - Ignore non-message events.
  - Reject wrong target actor.
  - Submit reference-only read prompt through ActionGateway.
  - Record submit failure as handler failure.
- [x] Run:

```bash
python3 -m pytest tests/test_message_available_handler.py -q
```

Expected: fail because handler does not exist.

- [x] Create `tools/launcher/message_available_handler.py`.
  - Handler name: `message_available`.
  - For valid `message.available`, submit:

```text
[MESSAGE AVAILABLE]
message_id: <id>
Use message.list to read the message when ready.
```

  - Do not include message body.
- [x] Run:

```bash
python3 -m pytest tests/test_message_available_handler.py -q
```

Expected: pass.

## Task 6: Instance Daemon Run Loop Integration

- [x] Update `tests/test_daemon_core.py`.
  - Replace direct registry tests with central client registration tests.
  - Add mailbox start before registration.
  - Add heartbeat during idle.
  - Add unregister and mailbox close on exit.
- [x] Update `tests/test_instance_daemon_entrypoint.py`.
  - Assert default app-server notification handlers remain `TaskCheckoutHandler`.
  - Assert mailbox handlers include `MessageAvailableHandler`.
- [x] Run:

```bash
python3 -m pytest tests/test_daemon_core.py tests/test_instance_daemon_entrypoint.py -q
```

Expected: fail before integration.

- [x] Modify `daemon_core.run_daemon()`.
  - Resolve `actor_address_for_context(context)` once.
  - Start mailbox server with local actor address and mailbox handlers.
  - Register actor with central daemon endpoint `daemon_mailbox_socket`.
  - On `AppServerTimeoutError`, heartbeat central daemon and continue.
  - In `finally`, unregister and close mailbox server.
- [x] Modify `instance_daemon.py` default handler wiring.
- [x] Run:

```bash
python3 -m pytest tests/test_daemon_core.py tests/test_instance_daemon_entrypoint.py -q
```

Expected: pass.

## Task 7: Launcher Shell Integration

- [x] Add or update launcher tests that inspect shell wiring.
  - `daemon.sh` ensures central daemon before instance daemon start.
  - `daemon.sh` stop calls central stop-if-idle after instance stop.
- [x] Update `tools/launcher/daemon.sh`.
- [x] Run:

```bash
python3 -m pytest tests/test_instance_daemon_entrypoint.py tests/test_buddyswitch_launcher.py -q
```

Expected: pass. If `test_buddyswitch_launcher.py` is too broad for a focused loop, first run only affected test names, then run the full file once focused checks pass.

## Task 8: Message Tool Smoke Adjustment

- [x] Update `scripts/env/tool_runtime/context.py` so daemon access exposes explicit central daemon client capabilities and no longer calls `notify_message_available(to_buddy=...)`.
- [x] Keep the existing message tool durable behavior unless the separate message upgrade is in scope.
- [x] Update message tests that depended on the deleted direct file append notification path.
- [x] Run:

```bash
python3 -m pytest tests/test_message_env_tool.py tests/test_runtime_actor_profile.py -q
```

Expected: pass.

## Task 9: Final Verification and Review

- [x] Run focused daemon group:

```bash
python3 -m pytest tests/test_central_daemon_service.py tests/test_daemon_mailbox.py tests/test_message_available_handler.py tests/test_daemon_communication_boundary.py -q
```

- [x] Run daemon regression group:

```bash
python3 -m pytest tests/test_daemon_core.py tests/test_daemon_core_decoupling.py tests/test_daemon_service_contract.py tests/test_task_checkout_handler.py tests/test_instance_daemon_entrypoint.py -q
```

- [x] Run smoke group:

```bash
python3 -m pytest tests/test_runtime_actor_profile.py tests/test_message_env_tool.py tests/test_runtime_broker.py -q
```

- [x] Run formatting and full suite:

```bash
git diff --check
python3 -m pytest tests -q
pgrep -fl "central_daemon.py|instance_daemon.py" || true
```

- [x] Review:
  - central daemon is an independent process;
  - registry writes are single-writer through central daemon;
  - mailbox endpoint is socket based;
  - event payload is reference-only;
  - old daemon presence helper is gone or unused;
  - no broad service-starting tests leak resources.

## Self Review

- Spec coverage: all P1-P5 daemon responsibilities in the HTML memo are covered by Tasks 1-7; message business rewrite is explicitly out of this daemon plan and Task 8 only removes old daemon coupling.
- Red-flag scan: this plan avoids empty filler text and gives exact files, commands, expected failures, and implementation responsibilities.
- Type consistency: all daemon identity payloads are named `actor_address`; delivery target is explicit `target_actor_address` / event `to_actor_address`, not fuzzy `to_buddy`.
