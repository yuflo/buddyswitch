# Message Actor Signal Send Upgrade Test Plan

Date: 2026-05-30
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`

## Goal

Upgrade `message.contacts`, `message.send`, and `message.list` so the message tool is the first real business consumer of the daemon actor network:

- targets are explicit `RuntimeActorAddress` payloads;
- send success means durable message creation plus delivered `message.available` signal;
- offline or unreachable targets do not create readable messages;
- delivery failure after creation cleans up the message, or reports an indeterminate write if cleanup fails;
- inbox reads are scoped by actor address, not old buddy-level `to_buddy`.

Authoritative input: `docs/memo/2026-05-30-message-actor-signal-send-upgrade-task.md`.

## Resource Lifecycle Guard

Follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

- Focused message tests must use patched daemon client functions, fake `context.daemon` behavior, or in-process central service objects. They must not start real daemon processes.
- Socket tests remain in the daemon signal suite; this message upgrade should not add broad service-starting tests.
- Run the broad test suite only after focused message/runtime tests pass.
- Final verification includes `pgrep -fl "central_daemon.py|instance_daemon.py" || true`; any test-owned residual daemon process is a failure.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | `message.contacts` exists and returns online contacts from `context.daemon.list_contacts(...)`. |
| FR2 | `message.contacts` accepts an optional `buddy` filter and does not resolve send targets from `to_buddy`. |
| FR3 | `message.send` requires `target_actor_address` and rejects unsupported fields, including `to_buddy`. |
| FR4 | `message.send` validates `target_actor_address` through `RuntimeActorAddress.from_payload()`. |
| FR5 | `message.send` rejects self-send and same-buddy sends before daemon reachability or message creation. |
| FR6 | `message.send` calls `context.daemon.check_reachability(target_actor_address=...)` before creating a message. |
| FR7 | If reachability is `registered_offline`, `never_registered`, or invalid/unavailable, `message.send` returns a rejected response and creates no message. |
| FR8 | Durable message rows use `from_actor_address` and `to_actor_address`; they do not persist `from_buddy` or `to_buddy`. |
| FR9 | `message.send` creates a durable message only after reachability is online. |
| FR10 | After creation, `message.send` calls `context.daemon.deliver_message_available(message_id=..., target_actor_address=...)`. |
| FR11 | Send success requires `delivery_status == "delivered"` and returns `ok: true`, `delivery_status: "delivered"`, `state_changed: true`, and `durability: "durable"`. |
| FR12 | If signal delivery fails after message creation and cleanup succeeds, response is `ok: false`, `state_changed: false`, `durability: "none"`, `delivery_status: "delivery_failed"`, `cleanup_status: "cleaned"`, and the message is no longer readable. |
| FR13 | If signal delivery fails and cleanup fails, response is `ok: false`, `state_changed: true`, `durability: "uncertain"`, includes `message_id`, `cleanup_status: "failed"`, and `retryable: false`. |
| FR14 | `message.list` returns only messages whose `to_actor_address` equals `context.actor_address`. |
| FR15 | `message.list` `buddy` filter matches `from_actor_address.buddy_id`. |
| FR16 | Reply scope uses actor-address conversation pairs, not buddy-only pairs. |
| FR17 | Context message cues use actor-address rows and expose current actor address plus a pointer to `message.contacts`. |
| FR18 | Boundary tests prevent message send from scanning instance JSON, parsing daemon registry files, or using `to_buddy` as the send target. |

## Test Groups

### T1: Message Tool Schema

File: `tests/test_env_tool_schema_contract.py`

Cases:

- `test_high_risk_schema_shapes_match_domain_contracts`
  - Assert `message.send` requires `target_actor_address` and `content`.
  - Assert `target_actor_address` is an object with required `buddy_id` and `instance_id`.
  - Assert `message.send` has no `to_buddy` property.
  - Assert `message.contacts` exists and accepts optional `buddy`.

### T2: Contacts Discovery

File: `tests/test_message_env_tool.py`

Cases:

- `test_message_contacts_lists_online_actor_contacts`
  - Patch `context.daemon.list_contacts` through the daemon client boundary.
  - Dispatch `message.contacts` with `buddy: "dev"`.
  - Assert response contains normalized contacts with `actor_address`, `contact_status: "online"`, `sendable: true`, and `count`.
- `test_message_contacts_rejects_unknown_buddy_filter`
  - Dispatch with `buddy: "ops"`.
  - Assert `E_MESSAGE_PAYLOAD`, `state_changed: false`, and no daemon call.

### T3: Send Validation Before State Change

File: `tests/test_message_env_tool.py`

Cases:

- `test_message_send_rejects_to_buddy_field`
  - Dispatch `message.send` with old `to_buddy`.
  - Assert `E_MESSAGE_PAYLOAD`, `correctable_fields: ["to_buddy"]`, and no message file.
- `test_message_send_rejects_invalid_target_actor_address_without_state_change`
  - Use invalid payload shapes and mismatched buddy/instance ids.
  - Assert no daemon call and no message file.
- `test_message_send_rejects_same_buddy_target_without_state_change`
  - Target actor has same `buddy_id` as source actor.
  - Assert `permission_boundary: "message.self_send"`, no reachability call, and no message file.
- `test_message_send_rejects_blank_content`
  - Keep existing content validation coverage with `target_actor_address`.

### T4: Reachability Gate

File: `tests/test_message_env_tool.py`

Cases:

- `test_message_send_target_not_online_creates_no_message`
  - Patch reachability to return `registered_offline`.
  - Assert `ok: false`, `reachability_status`, `state_changed: false`, `durability: "none"`, and message directory unchanged.
- `test_message_send_never_registered_creates_no_message`
  - Patch reachability to return `never_registered`.
  - Assert response guidance points to `message.contacts`.

### T5: Successful Actor-Address Send

File: `tests/test_message_env_tool.py`

Cases:

- `test_message_send_online_target_creates_actor_address_message_and_delivers_signal`
  - Patch reachability to `online`.
  - Patch signal delivery to return `delivery_status: "delivered"`.
  - Dispatch `message.send` with `target_actor_address`.
  - Assert durable message row has only actor-address fields and content.
  - Assert response has `delivery_status: "delivered"`, `created_ids`, and `state_changes`.
  - Assert the signal payload captured by daemon access is reference-only: `payload.message_id`, no message body, no `from_buddy`, no `to_buddy`.

### T6: Delivery Failure Cleanup

File: `tests/test_message_env_tool.py`

Cases:

- `test_message_send_delivery_failed_cleanup_succeeded_removes_message`
  - Patch reachability online and delivery `delivery_failed`.
  - Assert cleanup deletes the message file.
  - Assert response matches the cleanup-succeeded contract.
- `test_message_send_delivery_failed_cleanup_failed_reports_indeterminate`
  - Patch message repo cleanup to raise after delivery failure.
  - Assert response includes `message_id`, `state_changed: true`, `durability: "uncertain"`, `cleanup_status: "failed"`, `retryable: false`, and duplicate-prevention guidance.

### T7: Actor-Address Inbox Reads

Files: `tests/test_message_env_tool.py`, `tests/test_context_binding_env_tool.py`

Cases:

- `test_message_list_returns_only_messages_to_current_actor_address`
  - Seed actor-address message rows to the active actor, another instance of the same buddy, and a different buddy.
  - Assert only exact `to_actor_address == context.actor_address` rows appear.
- `test_message_list_filters_by_sender_buddy_from_actor_address`
  - Assert `buddy` filter matches `from_actor_address.buddy_id`.
- `test_message_send_reply_to_accepts_same_visible_actor_conversation_pair`
  - Seed an actor-address message visible to the sender and reply to the same target actor.
- `test_message_send_reply_to_requires_same_visible_actor_conversation_pair`
  - Seed a message from a different actor pair and assert rejection.
- `test_context_summarize_includes_actor_address_message_cues`
  - Assert cues include `from_actor_address`, `to_actor_address`, no content body, and the current actor address.

### T8: Boundary Review Tests

Files: `tests/test_message_env_tool.py`, `tests/test_daemon_communication_boundary.py`

Cases:

- Message implementation does not contain `glob("instances")`, direct target instance JSON parsing, daemon registry parsing, or mailbox endpoint inspection.
- `scripts/env/repos/messages.py` persists no `from_buddy` or `to_buddy` fields.
- `scripts/env/tools/message/tool.py` exposes `target_actor_address` and `contacts`, not old `to_buddy` send targeting.

## Verification Commands

Focused red/green commands:

```bash
python3 -m pytest tests/test_message_env_tool.py -q
python3 -m pytest tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_includes_compact_active_inbox_message_cues -q
python3 -m pytest tests/test_env_tool_schema_contract.py::EnvToolSchemaContractTests::test_high_risk_schema_shapes_match_domain_contracts -q
```

Focused runtime/daemon regression:

```bash
python3 -m pytest tests/test_runtime_actor_profile.py tests/test_daemon_mailbox.py tests/test_message_available_handler.py tests/test_central_daemon_service.py -q
```

Message/context regression:

```bash
python3 -m pytest tests/test_message_env_tool.py tests/test_context_binding_env_tool.py tests/test_env_tool_response_contract.py tests/test_env_tool_schema_contract.py -q
```

Final gates:

```bash
git diff --check
python3 -m pytest tests -q
pgrep -fl "central_daemon.py|instance_daemon.py" || true
```

The final residual process check must show no daemon processes started by this test run.

## Review Checklist

- Requirements are derived from the memo, not from the old `to_buddy` implementation.
- Tests assert behavior and state impact, not private helper names except boundary tests.
- No broad service-starting tests are added.
- Failure semantics distinguish rejected non-writes, cleaned failed writes, and indeterminate writes.
- Durable message rows have one actor-address shape.
