# Notification Center Message Inbound Test Plan

Date: 2026-06-09
Source:
- `docs/memo/2026-06-09-notification-center-message-inbound-tasks.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`

## Target

Build Notification Center (NC) as daemon notify infrastructure and connect `message.available` as
the first source-native inbound event. NC must coordinate registration and delivery plumbing while
message keeps event semantics, prompt content, parent/side routing, and disposition behavior.

The target path is:

```text
message.send
  -> durable message row
  -> message.available native event
  -> NC-managed daemon registration and delivery plumbing
  -> MessageAvailableHandler
  -> parent or side message innerTUI
  -> actor uses message tools
```

## Resource Lifecycle Guard

Most planned tests are import, contract, pure dispatcher, and isolated mailbox tests. They must not
start the product daemon, app-server, browser, runtime broker, watcher, or detached worker.

If broader daemon or launcher checks are needed, follow
`docs/bitter/2026-05-26-test-resource-lifecycle-principles.md` first:

- inspect cleanup for every service-starting helper;
- run one focused service-starting test;
- check residual processes and sockets;
- only then scale to broader suites;
- check residuals again after broad verification.

The verification target for any service-starting check is:

```text
behavior passes + host resources return to baseline
```

## Functional Requirements

- NC exists as a small daemon notify infrastructure module.
- NC exposes a source registration contract with `event_type`, `payload_contract`,
  `handler_factory`, and `owner_module`.
- NC validates registration shape, rejects duplicate event types, and builds daemon handlers from
  source-owned handler factories.
- NC can list source-native subscriptions for daemon registration visibility.
- `message.available` is registered through a message-owned inbound module.
- `MessageAvailableHandler` remains source-owned and remains the execution owner for message
  routing and prompt text.
- Existing actor-visible message behavior remains unchanged.
- NC does not inspect message body, conversation state, disposition, or `needs_parent` rules.
- NC does not define actor-facing `notification.*` tools.
- NC does not introduce an `nc.notification` wrapper event.
- NC does not import or mutate message repository internals.
- Future sources can register a source-owned inbound module without adding NC business branches.

## Test Files

Create:

- `tests/test_notification_center.py`

Update:

- `tests/test_instance_daemon_entrypoint.py`
- `tests/test_daemon_core_decoupling.py`
- `tests/test_daemon_communication_boundary.py`

Use existing coverage unchanged where possible:

- `tests/test_message_available_handler.py`
- `tests/test_daemon_trigger_router.py`
- `tests/test_daemon_mailbox.py`
- `tests/test_message_env_tool.py`

## Test Cases

### NC Registration Contract

- Construct an `InboundSourceRegistration` with:

```python
event_type = "example.ready"
payload_contract = {"required_fields": ("example_id",)}
handler_factory = lambda: ExampleHandler()
owner_module = "example.inbound"
```

- Assert `notification_center.handlers_from_registrations(...)` returns one handler from the factory.
- Assert `notification_center.subscriptions_from_registrations(...)` returns `["example.ready"]`.
- Assert `notification_center.registration_records(...)` returns only infrastructure metadata:
  `event_type`, `payload_contract`, `owner_module`, and `handler_name`.
- Assert duplicate `event_type` values raise `ValueError` before any handler factory is called.
- Assert empty event types, non-object payload contracts, non-callable factories, and empty owner
  modules are rejected.

### NC Semantic-Light Boundary

- Assert `tools/launcher/notification_center.py` does not contain:

```text
MessageAvailableHandler
message_id
message body
conversation
disposition
needs_parent
message.mark
message.get
message.send
notification.mark
notification.archive
nc.notification
env.repos.messages
```

- Assert NC imports do not include `message_available_handler`, `env.domain.messages`, or
  `env.repos.messages`.

### Message Source-Native Registration

- Assert `tools/launcher/message_inbound.py` exports one registration for `message.available`.
- Assert the registration `owner_module` is the message inbound module.
- Assert the registration payload contract mentions only shape-level message payload fields, not
  message body, disposition, conversation, or `needs_parent` workflow.
- Assert the handler factory creates `MessageAvailableHandler`.
- Assert the created handler handles a native `message.available` `DaemonTrigger`; no
  `nc.notification` wrapper is involved.

### Instance Daemon Wiring

- Assert `instance_daemon.default_daemon_handlers()` returns:

```text
TaskCheckoutHandler
MessageAvailableHandler
```

- Assert the message handler is obtained through NC source registrations, not direct
  `message_available_handler` construction inside `instance_daemon.py`.
- Assert `instance_daemon.default_notify_subscriptions()` returns `["message.available"]`.
- Assert `run`, `start`, and `status` pass the default notify subscriptions into `daemon_core`
  where applicable.

### Daemon Registration Visibility

- Assert `daemon_core.register_daemon_actor(..., notify_subscriptions=["message.available"])`
  registers a mailbox endpoint with:

```python
{
    "kind": "daemon_mailbox_socket",
    "socket_path": "/tmp/buddyswitch-test/runtime/daemon/mailbox.sock",
    "subscriptions": ["message.available"],
}
```

- Assert `daemon_core.daemon_status(..., notify_subscriptions=["message.available"])` reports the
  same subscriptions under a notify/NC status section.
- Assert empty or duplicate subscriptions normalize to a stable unique list.

### Existing Message Behavior

Run the existing message handler tests to prove actor behavior stays unchanged:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_message_available_handler -v
```

Required behavior:

- idle parent receives the message-owned parent prompt;
- running parent receives the message-owned side triage prompt;
- wrong target actor and invalid payload fail before runtime calls;
- parent-required prompt remains message-owned;
- no parent/side routing moves into NC.

### Mailbox And Trigger Delivery

Run existing delivery plumbing tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_daemon_trigger_router \
  tests.test_daemon_mailbox \
  -v
```

Required behavior:

- `message.available` remains a native daemon trigger type;
- cross-actor signal payload stays transparent;
- mailbox dispatch reports handled, ignored, and failed handler outcomes;
- no legacy message event shape or `nc.notification` wrapper appears.

### Actor-Facing Tool Boundary

- Assert env tool package discovery contains no `notification` tool package.
- Assert native MCP projection has no `notification__mark`, `notification__archive`, or
  `notification__needs_parent`.
- Assert message tools remain `message.send`, `message.get`, and `message.mark`; no actor-facing
  notification lifecycle is introduced.

### Residue Scan

Run:

```bash
rg -n "notification\\.mark|notification\\.archive|notification\\.needs_parent|notification__mark|notification__archive|notification__needs_parent|nc\\.notification" \
  tools scripts tests buddyswitch docs/spec/2026-06-09-notification-center-message-inbound-*.md
```

Expected:

- no hits in production source or tests except this test plan and explicit negative assertions.

## Focused Verification Set

Run after implementation:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_notification_center \
  tests.test_instance_daemon_entrypoint \
  tests.test_daemon_core_decoupling \
  tests.test_daemon_communication_boundary \
  tests.test_message_available_handler \
  tests.test_daemon_trigger_router \
  tests.test_daemon_mailbox \
  -v
```

Run schema and message env-tool checks:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_env_tool_schema_contract \
  tests.test_env_native_mcp_projection \
  tests.test_message_env_tool \
  -v
```

Compile changed runtime modules:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile \
  tools/launcher/notification_center.py \
  tools/launcher/message_inbound.py \
  tools/launcher/instance_daemon.py \
  tools/launcher/daemon_core.py
```

## Review Checklist

- NC is infrastructure-only: registration, subscription visibility, and handler construction.
- Message owns `message.available`, `message_id`, handler behavior, prompt text, parent/side routing,
  and message tool lifecycle.
- No actor-facing `notification.*` tool exists.
- No `nc.notification` wrapper exists.
- NC imports no message repository/domain internals.
- Existing message handler and daemon mailbox behavior still passes.
- Verification did not run broad service-starting suites without lifecycle proof.
