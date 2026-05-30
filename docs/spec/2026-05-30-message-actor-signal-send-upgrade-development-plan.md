# Message Actor Signal Send Upgrade Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` while implementing behavior changes. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make `message.send` a true actor-address daemon-network send: durable message creation plus delivered `message.available` signal, with cleanup or indeterminate failure semantics when delivery fails.

**Architecture:** Reuse the existing `RuntimeActorAddress`, `ToolContext.daemon`, central daemon contacts/reachability, and generic signal delivery. Replace the old buddy-level message payload and durable row shape with actor-address rows. Keep daemon presence and endpoint details outside message code.

**Tech Stack:** Python stdlib, existing env.tool runtime context, `RuntimeActorAddress`, central daemon client fakes in tests, pytest/unittest.

---

## File Structure

- Modify `scripts/env/tools/message/tool.py`
  - Add `contacts`.
  - Replace send input `to_buddy` with `target_actor_address`.
  - Keep `list` read shape with optional `buddy`, `q`, and `limit`.
- Modify `scripts/env/domain/messages.py`
  - Validate send payloads against actor-address target.
  - Keep manifest scope for source and target buddies.
  - Validate reply scope by exact actor-address conversation pair.
  - Filter inbox rows by `to_actor_address == context.actor_address`.
- Modify `scripts/env/repos/messages.py`
  - Persist `from_actor_address` and `to_actor_address`.
  - Add `delete_message(message_id)` for failed delivery cleanup.
- Modify `scripts/env/tools/message/_impl.py`
  - Implement contacts.
  - Gate send on reachability before durable write.
  - Deliver `message.available` after durable write.
  - Cleanup on delivery failure and return the correct response contract.
- Modify `scripts/env/tools/context/_impl.py`
  - Build actor-address inbox cues.
  - Include current actor address and pointer to `message.contacts`.
- Modify `scripts/env/tool_runtime/role_auth.py`
  - Permit `message.contacts`.
- Modify `scripts/env/tool_runtime/context.py`
  - Update legacy `RuntimeObjectAccess` message helpers to actor-address shape or remove old assumptions.
- Modify `scripts/env_legacy_store.py`
  - Migrate test helper message validation/creation to actor-address rows while still letting tests pass buddy ids to the helper.
- Modify tests:
  - `tests/test_message_env_tool.py`
  - `tests/test_context_binding_env_tool.py`
  - `tests/test_env_tool_schema_contract.py`
  - `tests/test_env_tool_response_contract.py` if indeterminate rejected writes require explicit allowance.
  - `tests/test_cleanup_system.py` fixture shape if needed.

## Task 1: Write Failing Schema And Contacts Tests

- [x] Update `tests/test_env_tool_schema_contract.py` so `message.send` requires `target_actor_address` and no longer exposes `to_buddy`.
- [x] Add `message.contacts` schema assertions.
- [x] Add contacts behavior tests in `tests/test_message_env_tool.py` with daemon client fakes.
- [x] Run:

```bash
python3 -m pytest tests/test_env_tool_schema_contract.py::EnvToolSchemaContractTests::test_high_risk_schema_shapes_match_domain_contracts tests/test_message_env_tool.py -q
```

Expected: fail because `contacts` and `target_actor_address` send schema are not implemented.

## Task 2: Implement Tool Schema, Auth, And Contacts

- [x] Update `message/tool.py` action definitions.
- [x] Add `message.contacts` permission to `role_auth.COMMON_ROLE_PERMISSIONS`.
- [x] Implement `contacts_message(...)` in `message/_impl.py`.
- [x] Normalize contact rows to:

```python
{
    "buddy_id": actor_address["buddy_id"],
    "actor_address": actor_address,
    "contact_status": row.get("status", "online"),
    "sendable": row.get("status") == "online",
    "last_seen_at": row.get("last_seen_at"),
}
```

- [x] Run:

```bash
python3 -m pytest tests/test_env_tool_schema_contract.py::EnvToolSchemaContractTests::test_high_risk_schema_shapes_match_domain_contracts tests/test_message_env_tool.py::MessageEnvToolTests::test_message_contacts_lists_online_actor_contacts -q
```

Expected: pass after implementation.

## Task 3: Write Failing Actor-Address Message Repo And List Tests

- [x] Update or add tests proving message rows persist `from_actor_address` and `to_actor_address`, not `from_buddy` or `to_buddy`.
- [x] Update list tests to seed actor-address rows and require exact actor-address inbox matching.
- [x] Update context cue test to expect actor-address cues.
- [x] Run:

```bash
python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_list_returns_only_messages_to_current_actor_address tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_includes_compact_active_inbox_message_cues -q
```

Expected: fail against the old buddy-level row shape.

## Task 4: Implement Actor-Address Message Storage And List

- [x] Update `scripts/env/repos/messages.py` normalization and creation APIs.
- [x] Add `delete_message(message_id)`.
- [x] Update `scripts/env_legacy_store.py` test helpers to write actor-address rows from buddy ids using stable helper instance ids.
- [x] Update `scripts/env/domain/messages.py` list filtering by `RuntimeActorAddress`.
- [x] Update `scripts/env/tools/context/_impl.py` cues.
- [x] Run:

```bash
python3 -m pytest tests/test_message_env_tool.py tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_includes_compact_active_inbox_message_cues -q
```

Expected: list and context message cue tests pass or expose send tests still needing migration.

## Task 5: Write Failing Send Validation And Reachability Tests

- [x] Add send validation tests for unsupported `to_buddy`, invalid `target_actor_address`, same-buddy send, blank content, and unsupported broadcast/recipients/status fields.
- [x] Add reachability rejection tests for `registered_offline` and `never_registered`.
- [x] Run:

```bash
python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_rejects_to_buddy_field tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_target_not_online_creates_no_message -q
```

Expected: fail until send validation and reachability gate are replaced.

## Task 6: Implement Send Validation And Reachability Gate

- [x] Replace `prepare_send_request(...)` with `target_actor_address` validation through `RuntimeActorAddress.from_payload`.
- [x] Reject target buddies outside manifest scope.
- [x] Reject same-buddy sends through `MessageScopeError(permission_boundary="message.self_send")`.
- [x] In `send_message(...)`, call `context.daemon.check_reachability(...)` before `create_message(...)`.
- [x] Return rejected non-write responses for invalid/unavailable/non-online reachability.
- [x] Run:

```bash
python3 -m pytest tests/test_message_env_tool.py -q
```

Expected: validation and reachability tests pass; delivery tests still fail until implemented.

## Task 7: Write Failing Delivery Success And Failure Tests

- [x] Add success test capturing daemon `deliver_message_available` signal input.
- [x] Add delivery-failed cleanup-succeeded test.
- [x] Add delivery-failed cleanup-failed indeterminate test.
- [x] Add actor-address reply scope tests.
- [x] Run:

```bash
python3 -m pytest tests/test_message_env_tool.py -q
```

Expected: fail until send delivery and cleanup semantics are implemented.

## Task 8: Implement Delivery And Cleanup Semantics

- [x] After durable message creation, call `context.daemon.deliver_message_available(message_id=..., target_actor_address=...)`.
- [x] Treat only `delivery_status == "delivered"` as success.
- [x] On any other delivery status, call `context.repos.message.delete_message(message_id)`.
- [x] If cleanup succeeds, return `E_MESSAGE_DELIVERY_FAILED` with `state_changed: false`, `durability: "none"`, `cleanup_status: "cleaned"`, and retry guidance.
- [x] If cleanup fails, return `E_MESSAGE_SEND_INDETERMINATE` with `state_changed: true`, `durability: "uncertain"`, `message_id`, `cleanup_status: "failed"`, and `retryable: false`.
- [x] Run:

```bash
python3 -m pytest tests/test_message_env_tool.py -q
```

Expected: pass.

## Task 9: Boundary Cleanup And Focused Regression

- [x] Remove old message send target assumptions from implementation and tests.
- [x] Run boundary searches:

```bash
rg -n "to_buddy|from_buddy" scripts/env/tools/message scripts/env/domain/messages.py scripts/env/repos/messages.py
rg -n "glob\\(.*instances|instance_json|registry_path|daemon_mailbox_socket|socket_path" scripts/env/tools/message scripts/env/domain/messages.py scripts/env/repos/messages.py
```

Expected: no old send target or daemon endpoint parsing in message code.

- [x] Run focused regression:

```bash
python3 -m pytest tests/test_message_env_tool.py tests/test_context_binding_env_tool.py tests/test_env_tool_response_contract.py tests/test_env_tool_schema_contract.py -q
python3 -m pytest tests/test_runtime_actor_profile.py tests/test_daemon_mailbox.py tests/test_message_available_handler.py tests/test_central_daemon_service.py -q
```

Expected: pass.

## Task 10: Final Verification And Review

- [x] Run:

```bash
git diff --check
python3 -m pytest tests -q
pgrep -fl "central_daemon.py|instance_daemon.py" || true
```

- [x] Review against the memo:
  - `message.send` has no old `to_buddy` main path;
  - durable message rows have actor addresses only;
  - offline targets create no message;
  - delivery failure cleanup semantics match the response contract;
  - context cues and message list are actor-address scoped;
  - no daemon endpoint or registry parsing leaked into message code.

## Self Review

- The plan covers the full memo scope: contacts, send, list, durable rows, delivery cleanup, response contracts, context cues, and boundary checks.
- The plan replaces old message routing instead of layering compatibility into the main path.
- Tests avoid real daemon process startup and use the existing daemon client boundary.
- The final gate includes full tests and residual daemon process inspection.
