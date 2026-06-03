# Message Async Processing Stage 3 Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Use TDD for behavior changes: write or rewrite the focused test first, run it and confirm it fails for the expected contract gap, then implement the smallest direct change.

**Goal:** Rebuild direct message processing around exact-message get/mark tools, durable dispositions, message-owned prompts, and parent/side async routing.

**Architecture:** Keep the daemon as a runtime coordinator for `message.available`; move message prompt text, disposition rules, processability validation, and parent-required handoff into the message module. The message repository stores minimal disposition metadata, the message domain enforces transitions, and the message tool calls an internal runtime access hook when side triage marks a message `needs_parent`.

**Tech Stack:** Python runtime env tools, Python daemon launcher modules, runtime object JSON rows, and pytest/unittest tests.

---

## Task 1: Replace Wrong Phase Artifacts

**Files:**

- Create: `docs/spec/2026-06-03-message-async-processing-stage3-test-plan.md`
- Create: `docs/spec/2026-06-03-message-async-processing-stage3-development-plan.md`
- Create: `docs/spec/2026-06-03-message-async-processing-stage3-phase2-prompt.md`

Steps:

- [ ] Save the Stage 3 message test plan that maps every memo requirement to tests.
- [ ] Save this development plan.
- [ ] Save the Phase 2 execution prompt.
- [ ] Review the three docs against `docs/memo/2026-06-03-message-async-processing-stage3-task.md` and fix gaps before implementation.

## Task 2: Add Schema And Registry Failing Tests

**Files:**

- Modify: `tests/test_env_tool_schema_contract.py`
- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_black_box_tool_runtime.py`
- Modify: `tests/test_env_native_mcp_server.py`
- Modify: `tests/test_role_action_auth.py`
- Modify: `tests/test_runtime_skills.py`

Steps:

- [ ] Update expected message actions to include `get` and `mark`.
- [ ] Assert `message.get` schema requires `message_id`.
- [ ] Assert `message.mark` schema requires `message_id` and `disposition`, with disposition enum `absorbed` and `needs_parent`.
- [ ] Assert `message.conversation` properties are exactly `target_actor_address`, `q`, and `limit`.
- [ ] Assert `message.conversation` requires `target_actor_address`.
- [ ] Assert native MCP exposes `message__get` and `message__mark`.
- [ ] Assert shared message skill includes `message__get` and `message__mark`, and does not teach a conversation role selector.
- [ ] Run `python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_black_box_tool_runtime.py tests/test_env_native_mcp_server.py tests/test_role_action_auth.py tests/test_runtime_skills.py -q` and confirm the failures are the expected missing new surfaces and old conversation role surface.

## Task 3: Implement Tool Definition And Permission Surfaces

**Files:**

- Modify: `scripts/env/tools/message/tool.py`
- Modify: `scripts/env/tool_runtime/role_auth.py`
- Modify: `buddyswitch/skills/shared/message-tool/SKILL.md`

Steps:

- [ ] Add `message.get` action definition with `message_id` required.
- [ ] Add `message.mark` action definition with `message_id`, `disposition`, and optional `reason`.
- [ ] Remove `role` from `message.conversation` schema, description, preconditions, use text, and return text.
- [ ] Add `message.get` and `message.mark` permissions to `COMMON_ROLE_PERMISSIONS`.
- [ ] Update shared message-tool skill to describe exact-message processing and target-actor conversation context only.
- [ ] Run the Task 2 command until the schema/registry portions fail only on missing implementation behavior.

## Task 4: Add Repository And Domain Failing Tests

**Files:**

- Modify: `tests/test_message_env_tool.py`

Steps:

- [ ] Add a test that newly created messages persist default disposition metadata as `unseen`.
- [ ] Add a test that `message.get` returns one exact processable inbound message with disposition metadata.
- [ ] Add rejection tests for unknown, invisible, absorbed, and replied message ids.
- [ ] Add mark transition tests for `unseen -> absorbed`, `unseen -> needs_parent`, and `needs_parent -> absorbed`.
- [ ] Add invalid transition tests for completed and duplicate states.
- [ ] Add send reply transition tests for `unseen -> replied` and `needs_parent -> replied`.
- [ ] Rewrite role-selector conversation tests to assert `role` is rejected and target actor address is required.
- [ ] Run `python3 -m pytest tests/test_message_env_tool.py -q` and confirm the failures are the expected missing repository/domain/tool behavior.

## Task 5: Implement Disposition Storage And Domain Rules

**Files:**

- Modify: `scripts/env/repos/messages.py`
- Modify: `scripts/env_legacy_store.py`
- Modify: `scripts/env/domain/messages.py`

Steps:

- [ ] Normalize stored rows with disposition fields, defaulting missing rows to `unseen`, `None`, `None`, and `None`.
- [ ] Add valid disposition and transition constants.
- [ ] Add request parsing for `message.get` and `message.mark`.
- [ ] Remove `role` from `ConversationRequest`, `prepare_conversation_request`, and `filter_conversation_messages`.
- [ ] Add processable inbound validation for exact get/mark/reply transitions.
- [ ] Add transition helper that returns an updated message row with disposition metadata.
- [ ] Run `python3 -m pytest tests/test_message_env_tool.py -q` and confirm remaining failures are in tool implementation wiring.

## Task 6: Implement Get/Mark And Reply Transitions

**Files:**

- Modify: `scripts/env/tools/message/_impl.py`
- Modify: `scripts/env/tool_runtime/context.py`

Steps:

- [ ] Add `get_message(...)` implementation that validates and returns exactly one processable inbound message.
- [ ] Add `mark_message(...)` implementation that validates and persists `absorbed` or `needs_parent`.
- [ ] Add internal `DaemonAccess.request_parent_message_handling(...)`.
- [ ] In production, have that helper load the daemon context/state and call `DaemonRuntime.submit_parent_prompt(..., interrupt_policy="before_submit")`.
- [ ] In tests, patch that helper to verify `needs_parent` calls it with rendered parent-required prompt text.
- [ ] Update `send_message(...)` so successful `reply_to` on a processable inbound message transitions the original to `replied`.
- [ ] Ensure delivery failure paths do not transition the original message.
- [ ] Run `python3 -m pytest tests/test_message_env_tool.py -q` until green.

## Task 7: Add Message-Owned Prompt Tests

**Files:**

- Modify: `tests/test_message_available_handler.py`

Steps:

- [ ] Add tests for idle parent prompt text from `render_parent_message_prompt(...)`.
- [ ] Add tests for running parent side triage prompt text from `render_side_triage_prompt(...)`.
- [ ] Add tests for `render_parent_required_prompt(...)` either directly or through `message.mark(needs_parent)`.
- [ ] Assert prompts include exact `message_id`, `From`, `To`, `message__get`, `message__conversation` with sender actor address, `message__send(reply_to=...)`, and `message__mark`.
- [ ] Assert prompts do not include `message__list`, daemon mailbox, launcher APIs, parent thread id, side thread id, or `message.parent_required`.
- [ ] Run `python3 -m pytest tests/test_message_available_handler.py -q` and confirm failures point to old handler prompt ownership/text.

## Task 8: Implement Message-Owned Prompts And Handler Wiring

**Files:**

- Modify: `scripts/env/domain/messages.py`
- Modify: `tools/launcher/message_available_handler.py`

Steps:

- [ ] Add `render_parent_message_prompt(...)`, `render_side_triage_prompt(...)`, and `render_parent_required_prompt(...)` in the message domain module.
- [ ] Update handler to extract source actor address from `trigger.source_context["source_actor_address"]`.
- [ ] Update handler to call message-owned prompt renderers.
- [ ] Keep handler routing limited to `message.available`.
- [ ] Run `python3 -m pytest tests/test_message_available_handler.py -q` until green.

## Task 9: Focused Verification And Source Audits

**Files:**

- Verify: focused message/schema/handler tests
- Verify: message source and prompt source

Steps:

- [ ] Run `python3 -m pytest tests/test_env_tool_schema_contract.py -q`.
- [ ] Run `python3 -m pytest tests/test_env_tool_semantic_contract.py -q`.
- [ ] Run `python3 -m pytest tests/test_black_box_tool_runtime.py tests/test_env_native_mcp_server.py tests/test_role_action_auth.py tests/test_runtime_skills.py -q`.
- [ ] Run `python3 -m pytest tests/test_message_available_handler.py -q`.
- [ ] Run `python3 -m pytest tests/test_message_env_tool.py -q`.
- [ ] Run source audits from the test plan and inspect every match.
- [ ] Fix any old path residue before broad verification.

## Task 10: Broad Verification And Review

**Files:**

- Verify: runtime actor/context/native projection tests
- Verify: collection, diff, and launcher regression

Steps:

- [ ] Run `python3 -m pytest tests/test_runtime_actor_profile.py tests/test_context_binding_env_tool.py tests/test_env_native_mcp_projection.py -q`.
- [ ] Run `python3 -m pytest --collect-only -q tests`.
- [ ] Run `git diff --check`.
- [ ] Run `python3 -m pytest tests/test_buddyswitch_launcher.py -q` only after focused tests pass.
- [ ] If the launcher test starts persistent services, inspect residual processes before final completion.
- [ ] Re-read the memo and this plan; check each explicit requirement against code, tests, and command output.
- [ ] Perform final review for no compatibility aliases, no `seen`, no role selector, no `message.parent_required`, no hidden dual path, and no unverified behavior.

## Self-Review

- Spec coverage: every section of the Stage 3 memo maps to a concrete test and implementation task.
- Placeholder scan: no task depends on placeholder tokens or unspecified "add tests" work.
- Type consistency: final names are `message.get`, `message.mark`, `message__get`, `message__mark`, `disposition`, `disposition_reason`, `disposition_updated_at`, `processed_by_actor_address`, `unseen`, `absorbed`, `replied`, and `needs_parent`.
- Scope guard: no `seen`, no role-selector conversation, no model-facing parent handoff tool, no daemon mailbox `message.parent_required`, no plugin/workflow/event framework.
