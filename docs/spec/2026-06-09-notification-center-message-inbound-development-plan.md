# Notification Center Message Inbound Development Plan

Date: 2026-06-09
Source:
- `docs/spec/2026-06-09-notification-center-message-inbound-test-plan.md`
- `docs/memo/2026-06-09-notification-center-message-inbound-tasks.md`

## Goal

Create NC as daemon notify infrastructure and connect `message.available` through a message-owned
source-native inbound registration without changing actor-visible message behavior.

## Non-Negotiables

- Work only in `/Users/chen/Dev/buddyswitch/.worktrees/nc`; do not touch main.
- Follow sharp-forward: add one clear NC registration path, not a compatibility layer.
- Use tests first and verify the new tests fail before production code exists.
- Do not add actor-facing `notification.*` tools.
- Do not add an `nc.notification` wrapper event.
- Do not move message prompt text, parent/side routing, message body semantics, disposition, or
  `needs_parent` rules into NC.
- Do not redesign Track, Comment, Artifact, or future source integrations in this change.
- Keep verification focused and avoid broad service-starting suites unless lifecycle cleanup is
  proven per `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

## File Responsibilities

- `tools/launcher/notification_center.py`: NC infrastructure contract. Owns registration validation,
  source subscription listing, handler construction, and registration metadata reporting. Must not
  import message implementation or message repos.
- `tools/launcher/message_inbound.py`: message-owned source-native inbound registration for
  `message.available`. Owns the message payload contract metadata and handler factory.
- `tools/launcher/instance_daemon.py`: daemon entrypoint wiring. Builds task handler directly and
  message inbound handler through NC registrations.
- `tools/launcher/daemon_core.py`: carries notify subscription metadata into daemon registration and
  status. Does not inspect source-specific payloads.
- `tests/test_notification_center.py`: NC contract and boundary tests.
- `tests/test_instance_daemon_entrypoint.py`: entrypoint wiring and subscription propagation tests.
- `tests/test_daemon_core_decoupling.py`: architecture boundary tests for NC and message ownership.
- `tests/test_daemon_communication_boundary.py`: negative checks against actor-facing notification
  lifecycle and wrapper events.

## Implementation Sequence

### Task 1: Add Failing NC Contract Tests

Create `tests/test_notification_center.py`.

Add tests that:

- load `tools/launcher/notification_center.py` and fail because it does not exist yet;
- assert valid registration records build handlers and subscriptions;
- assert duplicate event types are rejected before handler factories are called;
- assert invalid registration fields are rejected;
- assert NC source has no message-specific semantics, no actor notification lifecycle, and no message
  repo/domain imports;
- assert `tools/launcher/message_inbound.py` registers `message.available` and creates
  `MessageAvailableHandler`.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_notification_center -v
```

Expected before implementation: fail because `notification_center.py` and `message_inbound.py` are
missing.

### Task 2: Add Failing Entrypoint And Daemon Core Tests

Modify:

- `tests/test_instance_daemon_entrypoint.py`
- `tests/test_daemon_core_decoupling.py`
- `tests/test_daemon_communication_boundary.py`

Add tests that:

- assert `instance_daemon.py` imports `notification_center` and `message_inbound`, not
  `message_available_handler`;
- assert default notify subscriptions equal `["message.available"]`;
- assert `run`, `start`, and `status` pass notify subscriptions into daemon core;
- assert `daemon_core.register_daemon_actor` includes subscriptions in the mailbox endpoint;
- assert `daemon_status` exposes notify subscriptions;
- assert no production source contains actor-facing `notification.*` lifecycle tools or
  `nc.notification`.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_instance_daemon_entrypoint \
  tests.test_daemon_core_decoupling \
  tests.test_daemon_communication_boundary \
  -v
```

Expected before implementation: fail because entrypoint and daemon core do not expose NC
registrations or notify subscriptions yet.

### Task 3: Implement NC Registration Module

Create `tools/launcher/notification_center.py`.

Implement:

- immutable `InboundSourceRegistration`;
- `normalized_registrations(registrations)`;
- `handlers_from_registrations(registrations)`;
- `subscriptions_from_registrations(registrations)`;
- `registration_records(registrations)`.

Rules:

- validate non-empty `event_type`;
- validate `payload_contract` is a mapping and copy it without inspecting message-specific keys;
- validate `handler_factory` is callable;
- validate non-empty `owner_module`;
- reject duplicate event types before calling any factory;
- validate produced handlers have callable `handles` and `handle`;
- do not import any source-specific handler or repo.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_notification_center -v
```

Expected after this task: NC generic tests pass; message inbound tests still fail until Task 4.

### Task 4: Implement Message Inbound Registration

Create `tools/launcher/message_inbound.py`.

Implement:

- `MESSAGE_AVAILABLE_EVENT_TYPE = "message.available"`;
- `MESSAGE_AVAILABLE_PAYLOAD_CONTRACT = {"required_fields": ("message_id",)}`;
- `message_available_registration()`;
- `inbound_registrations()`.

The module may import `message_available_handler.MessageAvailableHandler`; NC must not.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_notification_center -v
```

Expected after this task: all `tests.test_notification_center` tests pass.

### Task 5: Wire Instance Daemon Through NC

Modify `tools/launcher/instance_daemon.py`.

Steps:

- replace direct `message_available_handler` import with `notification_center` and `message_inbound`;
- add `default_notification_registrations()`;
- add `default_notify_subscriptions()`;
- make `default_daemon_handlers()` return `TaskCheckoutHandler()` plus NC-built handlers;
- pass `notify_subscriptions=default_notify_subscriptions()` to daemon core for `run`, `start`, and
  `status`.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_instance_daemon_entrypoint -v
```

Expected after this task: entrypoint tests pass.

### Task 6: Add Notify Subscription Visibility To Daemon Core

Modify `tools/launcher/daemon_core.py`.

Steps:

- add a small `_notify_subscriptions_payload(...)` normalizer;
- extend `register_daemon_actor(...)` with `notify_subscriptions`;
- include normalized subscriptions in the mailbox endpoint when non-empty;
- extend `daemon_status(...)`, `start_daemon(...)`, and `run_daemon(...)` with
  `notify_subscriptions`;
- make `daemon_status` report `{"notify": {"subscriptions": [...]}}`;
- pass subscriptions from `run_daemon` to `register_daemon_actor`.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_instance_daemon_entrypoint \
  tests.test_daemon_core_decoupling \
  -v
```

Expected after this task: daemon subscription and decoupling tests pass.

### Task 7: Preserve Existing Message And Delivery Behavior

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_message_available_handler \
  tests.test_daemon_trigger_router \
  tests.test_daemon_mailbox \
  -v
```

Expected: all pass. If any fail, fix root cause without moving message semantics into NC.

### Task 8: Run Focused Boundary And Tool-Surface Verification

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_notification_center \
  tests.test_instance_daemon_entrypoint \
  tests.test_daemon_core_decoupling \
  tests.test_daemon_communication_boundary \
  tests.test_env_tool_schema_contract \
  tests.test_env_native_mcp_projection \
  tests.test_message_env_tool \
  -v
```

Expected: all pass. These checks are focused and do not require persistent daemon/app-server/browser
processes.

### Task 9: Compile And Scan

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile \
  tools/launcher/notification_center.py \
  tools/launcher/message_inbound.py \
  tools/launcher/instance_daemon.py \
  tools/launcher/daemon_core.py
```

Run:

```bash
rg -n "notification\\.mark|notification\\.archive|notification\\.needs_parent|notification__mark|notification__archive|notification__needs_parent|nc\\.notification" \
  tools scripts tests buddyswitch docs/spec/2026-06-09-notification-center-message-inbound-*.md
```

Expected: compile succeeds. Residue scan has no production hits; hits in this plan/test-plan negative
assertions are acceptable.

### Task 10: Final Review

Review the diff and verify:

- NC is infrastructure-only and semantic-light.
- Message owns its inbound handler and all message behavior.
- Existing message behavior tests pass.
- Daemon registration exposes `message.available` as a subscription.
- No actor-facing notification lifecycle or wrapper event was introduced.
- No service-starting broad suite was run without lifecycle proof.

If all checks pass, report changed files, verification output, and any residual risk.

## Self-Review

- Scope covers both memo tasks: NC core and message source-native inbound hookup.
- Tests are driven from requirements and boundaries, not implementation convenience.
- The plan keeps Track, Comment, and Artifact out of scope.
- The plan uses focused tests first and avoids broad service-starting verification.
- No compatibility path, wrapper event, or actor notification lifecycle is planned.
