# Message Async Processing Stage 3 Test Plan

Date: 2026-06-03
Source memo: `docs/memo/2026-06-03-message-async-processing-stage3-task.md`

## Goal

Prove direct messages are processed through disposition-driven parent/side async routing:

```text
message.available
  -> message handler checks parent activity
  -> parent idle: parent handles exact message
  -> parent running: side triages exact message
  -> side either handles independently or marks parent required
  -> message module interrupts/submits parent when parent is required
```

This is a direct replacement. Tests must prove the final message Stage 3 behavior, not preserve old inbox-list prompt handling, `message.conversation(role=...)`, or daemon mailbox `message.parent_required`.

## Resource Safety

Most tests below are in-process or run through the runless runtime broker. Follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`:

1. Run focused message/schema/handler tests first.
2. Do not run broad launcher tests until focused behavior is green.
3. For any test that starts persistent services, check residual daemon/app-server/browser/broker processes before claiming completion.
4. Treat resource leakage as a verification failure even when assertions pass.

## Functional Test Matrix

### Tool Schema And Registry

Files:

- `tests/test_env_tool_schema_contract.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_black_box_tool_runtime.py`
- `tests/test_env_native_mcp_server.py`
- `tests/test_runtime_skills.py`
- `tests/test_role_action_auth.py`

Required coverage:

- `message.get` exists in the message tool registry and native MCP projection as `message__get`.
- `message.mark` exists in the message tool registry and native MCP projection as `message__mark`.
- `message.conversation` has only `target_actor_address`, `q`, and `limit` inputs.
- `message.conversation` requires `target_actor_address`.
- `message.conversation(role=...)` is rejected as an unsupported payload field.
- Role-action policy authorizes `message.get` and `message.mark` for normal manifest roles.
- Shared message skill mentions `message__get` and `message__mark`, and no longer teaches a role selector for `message__conversation`.

### Message Repository Rows

Files:

- `scripts/env/repos/messages.py`
- `scripts/env_legacy_store.py`
- `tests/test_message_env_tool.py`

Required coverage:

- Newly created messages persist these minimal disposition fields:
  - `disposition`
  - `disposition_reason`
  - `disposition_updated_at`
  - `processed_by_actor_address`
- Existing or manually saved rows without disposition data normalize as `unseen`.
- Forbidden message fields remain forbidden: no `status`, read receipt, product binding, broadcast, or recipient-list fields.
- `message.list` and `message.conversation` return rows with disposition metadata.

### Message Domain Rules

Files:

- `scripts/env/domain/messages.py`
- `tests/test_message_env_tool.py`

Required coverage:

- Durable dispositions are exactly `unseen`, `absorbed`, `replied`, and `needs_parent`.
- Valid transitions:
  - `unseen -> absorbed`
  - `unseen -> replied`
  - `unseen -> needs_parent`
  - `needs_parent -> absorbed`
  - `needs_parent -> replied`
- Invalid transitions are rejected by message business logic:
  - `absorbed -> absorbed`
  - `absorbed -> replied`
  - `replied -> absorbed`
  - `replied -> replied`
  - `replied -> needs_parent`
  - `needs_parent -> needs_parent`
- Processable inbound messages must be addressed to the active actor and currently be `unseen` or `needs_parent`.
- Unknown, invisible, already absorbed, and already replied messages are rejected for exact processing.

### Message Get

Files:

- `scripts/env/tools/message/tool.py`
- `scripts/env/tools/message/_impl.py`
- `tests/test_message_env_tool.py`

Required coverage:

- `message.get(message_id)` returns exactly one processable message visible to the active actor.
- The result includes message content, sender actor address, target actor address, reply metadata, disposition, disposition reason, disposition updated time, and processed actor address.
- Unknown message ids are rejected.
- Messages not addressed to the active actor are rejected.
- Completed messages (`absorbed` or `replied`) are rejected to prevent duplicate processing.

### Message Mark

Files:

- `scripts/env/tools/message/tool.py`
- `scripts/env/tools/message/_impl.py`
- `scripts/env/tool_runtime/context.py`
- `tests/test_message_env_tool.py`

Required coverage:

- `message.mark(message_id, disposition="absorbed")` transitions `unseen -> absorbed`.
- `message.mark(message_id, disposition="absorbed")` transitions `needs_parent -> absorbed`.
- `message.mark(message_id, disposition="needs_parent", reason="...")` transitions `unseen -> needs_parent`, stores the reason, records `processed_by_actor_address`, and calls the internal parent-required runtime hook.
- `message.mark(..., disposition="needs_parent")` requires a non-empty reason.
- `message.mark` rejects invalid dispositions and invalid transitions.
- Duplicate side/parent processing is rejected after `absorbed` or `replied`.

### Message Send Reply-To Transitions

Files:

- `scripts/env/tools/message/_impl.py`
- `scripts/env/domain/messages.py`
- `tests/test_message_env_tool.py`

Required coverage:

- `message.send(..., reply_to=<processable inbound message>)` transitions `unseen -> replied` after successful delivery.
- `message.send(..., reply_to=<needs_parent inbound message>)` transitions `needs_parent -> replied` after successful delivery.
- The original inbound message stores `processed_by_actor_address` and `disposition_updated_at`.
- Delivery failures do not mark the original message replied.
- Duplicate reply processing is rejected once the original message is `replied` or `absorbed`.

### Conversation Cleanup

Files:

- `scripts/env/tools/message/tool.py`
- `scripts/env/domain/messages.py`
- `scripts/env/tools/message/_impl.py`
- `tests/test_message_env_tool.py`
- `tests/test_env_tool_schema_contract.py`

Required coverage:

- `message.conversation(target_actor_address={role_id, actor_id}, q?, limit?)` still returns bidirectional visible messages for that exact actor-address pair.
- `message.conversation(role=...)` tests are removed or rewritten to expect rejection.
- `prepare_conversation_request(...)` has no role branch.
- `filter_conversation_messages(...)` has no `target_role` support.

### Message-Owned Prompts And Handler Routing

Files:

- `scripts/env/domain/messages.py`
- `tools/launcher/message_available_handler.py`
- `tests/test_message_available_handler.py`

Required coverage:

- `render_parent_message_prompt(...)` emits the memo's `[MESSAGE AVAILABLE]` prompt.
- `render_side_triage_prompt(...)` emits the memo's `[MESSAGE TRIAGE]` prompt.
- `render_parent_required_prompt(...)` emits the memo's `[MESSAGE NEEDS PARENT]` prompt.
- Prompts instruct `message__get`, exact `message_id`, `message__conversation` with sender actor address, `message__send(reply_to=...)`, and `message__mark`.
- Prompts do not instruct `message__list` as the primary exact-message path.
- Prompts do not mention daemon mailbox, launcher APIs, local triggers, parent thread ids, side thread ids, or `message.parent_required`.
- Idle parent submits `render_parent_message_prompt(...)` through `runtime.submit_parent_prompt(..., interrupt_policy="none")`.
- Running parent submits `render_side_triage_prompt(...)` through `runtime.submit_side_triage_prompt(...)`.
- Parent-required handling is not a daemon trigger contract.

### Parent-Required Runtime Entry

Files:

- `scripts/env/tools/message/_impl.py`
- `scripts/env/tool_runtime/context.py`
- `tests/test_message_env_tool.py`

Required coverage:

- When `message.mark(..., disposition="needs_parent")` succeeds, the message tool renders `render_parent_required_prompt(...)`.
- The message tool calls an internal daemon/runtime access method that submits parent prompt with `interrupt_policy="before_submit"`.
- This is not exposed as a model-facing env tool action or mailbox trigger.
- If the parent-required runtime submit fails, `message.mark` reports a rejected/failed result without hiding the runtime error.

## Verification Commands

Run focused tests first:

```bash
python3 -m pytest tests/test_env_tool_schema_contract.py -q
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
python3 -m pytest tests/test_black_box_tool_runtime.py tests/test_env_native_mcp_server.py tests/test_role_action_auth.py tests/test_runtime_skills.py -q
python3 -m pytest tests/test_message_available_handler.py -q
python3 -m pytest tests/test_message_env_tool.py -q
```

Run source audits:

```bash
rg -n 'message\\.parent_required|mailbox\\.local_trigger|parent_thread_id|side_thread_id|message__list' tools/launcher/message_available_handler.py tests/test_message_available_handler.py
rg -n 'target_role|\"role\".*conversation|conversation.*role selector|message_conversation_role_selector' scripts/env/domain/messages.py scripts/env/tools/message tests/test_message_env_tool.py tests/test_env_tool_schema_contract.py buddyswitch/skills/shared/message-tool/SKILL.md
rg -n 'message\\.get|message\\.mark|message__get|message__mark' scripts/env tools tests buddyswitch/skills/shared/message-tool/SKILL.md
```

The first two audits should return no old-path residues except test names explicitly proving rejection. The third audit should show the new registered surfaces and tests.

Run broader validation only after focused tests and audits pass:

```bash
python3 -m pytest tests/test_runtime_actor_profile.py tests/test_context_binding_env_tool.py tests/test_env_native_mcp_projection.py -q
python3 -m pytest --collect-only -q tests
git diff --check
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

If broad validation starts persistent services, record process state before and after and confirm no owned residual services remain.

## Review Checklist

- The message module owns message state, prompt rendering, message tool behavior, and parent-required handoff.
- The daemon handler only routes `message.available` based on parent activity and submits message-owned prompt text.
- No compatibility alias, old/new dual path, or `seen` disposition exists.
- `message.conversation(role=...)` is removed from schema, domain, implementation, tests, and skill guidance.
- Duplicate processing is prevented by disposition transitions, not by prompt wording alone.
