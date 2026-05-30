# Message Product Experience No-Residual Repair Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` while implementing behavior changes. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the message product contract so actor-address send, contact discovery, bidirectional conversation reads, shared skills, context cues, daemon status, and product-mode permissions form one verified path with no stale compatibility model.

**Architecture:** Keep the strict actor-address message model already present in `scripts/env/tools/message`. Add a concrete `message.conversation` read action over existing durable message rows instead of changing `message.list`. Keep daemon mailbox observability separate from notification handler observability. Validate product-mode permissions at launcher/app-server boundaries instead of documenting around read-only continuations.

**Tech Stack:** Python stdlib, existing env.tool registry and broker dispatch, existing `RuntimeActorAddress`, pytest/unittest, launcher fake Codex tests.

---

## Current Code Audit

- Already present: `message.contacts`, strict `message.send.target_actor_address`, actor-address durable rows, `message.list` inbox filtering, generic daemon signal delivery.
- Missing/residual:
  - `buddyswitch/skills/shared/message-tool/SKILL.md` still teaches `to_buddy`, `from_buddy`, and old send examples.
  - `normalize_contact_rows()` marks same-buddy online rows `sendable: true`.
  - `message.contacts` response lacks `sendable_count` and precise `target_actor_address` next action.
  - `message.conversation` does not exist.
  - `role_auth.COMMON_ROLE_PERMISSIONS` lacks `message.conversation`.
  - `context._message_cues()` exposes only `source_of_truth: message.list`.
  - `daemon_status()` accepts only notification `handlers`; `instance_daemon status` omits `default_mailbox_handlers()`.
  - Product-mode permission tests already cover many paths; the implementation still needs an explicit audit result for the observed read-only continuation.

## File Structure

- Modify `buddyswitch/skills/shared/message-tool/SKILL.md`
  - Replace stale buddy-level send model with actor-address workflow notes.
- Modify `tests/test_runtime_skills.py`
  - Lock corrected source and materialized runtime skill contract.
- Modify `scripts/env/domain/messages.py`
  - Add `ConversationRequest`, selector validation, bidirectional visible filtering, and contact sendability normalization using active actor.
- Modify `scripts/env/tools/message/tool.py`
  - Add `message.conversation` read action schema and semantics.
- Modify `scripts/env/tools/message/_impl.py`
  - Pass active actor into contact normalization, include `sendable_count`, implement `conversation_messages`, and wire action handler.
- Modify `scripts/env/tool_runtime/role_auth.py`
  - Add `message.conversation` to common permissions.
- Modify `scripts/env/tools/context/_impl.py`
  - Split inbox and conversation source-of-truth cues.
- Modify tests:
  - `tests/test_message_env_tool.py`
  - `tests/test_env_tool_schema_contract.py`
  - `tests/test_env_tool_semantic_contract.py` only if existing semantic coverage needs no new assertion.
  - `tests/test_role_action_auth.py` only if explicit common permission assertion is useful.
  - `tests/test_context_binding_env_tool.py`
  - `tests/test_daemon_core.py`
  - `tests/test_instance_daemon_entrypoint.py`
  - `tests/test_app_server_client.py` / `tests/test_buddyswitch_launcher.py` only if permission audit exposes a missing path.
- Modify `tools/launcher/daemon_core.py`
  - Add mailbox handler status payload while preserving notification handler shape.
- Modify `tools/launcher/instance_daemon.py`
  - Pass `default_mailbox_handlers()` to status.

## Task 1: Lock And Fix Shared Message Skill

- [ ] Add failing assertions to `RuntimeSkillsTests.test_shared_message_skill_prevents_observed_invalid_calls`:
  - source skill has `message contacts --payload`;
  - source skill has `target_actor_address`;
  - source skill has `contact.actor_address`;
  - source skill has `message conversation --payload`;
  - source skill has `context.get.tool_catalog['message']`;
  - source skill does not have `to_buddy` or `from_buddy`;
  - installed PM and market runtime skill copies in a temp workspace match those same constraints.
- [ ] Run:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_message_skill_prevents_observed_invalid_calls -q
```

Expected: fail on stale skill.

- [ ] Replace `buddyswitch/skills/shared/message-tool/SKILL.md` with concise workflow notes:

```bash
python3 scripts/env/client.py message contacts --payload '{"buddy":"market"}'
python3 scripts/env/client.py message send --payload '{"target_actor_address":{"buddy_id":"market","instance_id":"inst-market-ae219d1e9e24"},"content":"Please review track-alpha."}'
python3 scripts/env/client.py message list --payload '{}'
python3 scripts/env/client.py message conversation --payload '{"buddy":"market","limit":20}'
```

- [ ] State these rules in the skill:
  - `message.contacts` returns `contact.actor_address`.
  - `message.send` copies `contact.actor_address` into `target_actor_address`.
  - `message.list` reads active actor inbox only and does not accept `box`.
  - `message.conversation` reads active actor visible bidirectional conversation.
  - Runtime catalog and status are the schema source of truth.
- [ ] Re-run the focused skill test and keep it green.

## Task 2: Fix Contacts Sendability

- [ ] Add `MessageEnvToolTests.test_message_contacts_marks_active_buddy_rows_not_sendable`.
- [ ] Run:

```bash
python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_contacts_marks_active_buddy_rows_not_sendable -q
```

Expected: fail because same-buddy online rows are currently sendable.

- [ ] Change `normalize_contact_rows(rows)` to `normalize_contact_rows(rows, active_actor_address=...)`.
- [ ] For each valid contact:
  - compute `contact_status`;
  - `sendable = contact_status == "online" and actor_address["buddy_id"] != active_actor_address.buddy_id`;
  - include `why_not_sendable` for same-buddy rows and non-online rows;
  - keep same-buddy rows visible instead of filtering them out.
- [ ] Update `contacts_message()`:
  - pass `context.actor_address`;
  - include `sendable_count`;
  - change next action to `Use message.send with contact.actor_address copied into target_actor_address.`
- [ ] Run:

```bash
python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_contacts_marks_active_buddy_rows_not_sendable -q
python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_rejects_same_buddy_target_without_state_change -q
```

Expected: pass.

## Task 3: Add Conversation Schema And Permission

- [ ] Extend `EnvToolSchemaContractTests.test_high_risk_schema_shapes_match_domain_contracts` to assert `message.conversation`.
- [ ] Add an explicit common-permission assertion for `message.conversation` in `RoleActionAuthPolicyTests.test_common_permissions_allow_every_manifest_role`.
- [ ] Run:

```bash
python3 -m pytest tests/test_env_tool_schema_contract.py::EnvToolSchemaContractTests::test_high_risk_schema_shapes_match_domain_contracts -q
python3 -m pytest tests/test_role_action_auth.py::RoleActionAuthPolicyTests::test_common_permissions_allow_every_manifest_role -q
```

Expected: fail because the action and permission do not exist.

- [ ] Add `message.conversation` `ActionDefinition` to `scripts/env/tools/message/tool.py`:
  - kind `read`;
  - mutates `none`;
  - permission `message.conversation`;
  - fields `target_actor_address`, `buddy`, `q`, `limit`;
  - no `box`, `to_buddy`, or `from_buddy`.
- [ ] Add `message.conversation` to `COMMON_ROLE_PERMISSIONS`.
- [ ] Run the two focused tests plus:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_registry_semantics_cover_every_registered_tool_and_action -q
```

Expected: pass after definition and auth are consistent.

## Task 4: Implement Conversation Domain Rules

- [ ] Add failing conversation tests in `tests/test_message_env_tool.py`:
  - exact actor selector returns only visible bidirectional exact actor-pair rows;
  - buddy selector returns visible bidirectional rows for any actor of that buddy;
  - selector must be exactly one of `target_actor_address` or `buddy`;
  - old fields `box`, `to_buddy`, `from_buddy` are rejected;
  - limit selects newest N then returns chronological old-to-new.
- [ ] Run:

```bash
python3 -m pytest tests/test_message_env_tool.py -k "conversation" -q
```

Expected: fail before implementation.

- [ ] In `scripts/env/domain/messages.py`, add:
  - `ConversationRequest`;
  - `prepare_conversation_request(args, source_actor_address, manifest_buddy_ids, allowed_fields)`;
  - `filter_conversation_messages(messages, active_actor_address, target_actor_address=None, target_buddy=None, q=None, limit=20)`.
- [ ] Validation details:
  - unknown fields use existing `_reject_unknown_fields`;
  - exactly one selector required;
  - `target_actor_address` must be valid and manifest-declared;
  - target buddy must differ from active buddy;
  - `buddy` must be manifest-declared and differ from active buddy;
  - `limit` is a positive integer;
  - `q` is optional lowercase content filter.
- [ ] Filtering details:
  - active actor must equal `from_actor_address` or `to_actor_address`;
  - exact actor selector matches the other participant exactly;
  - buddy selector matches the other participant `buddy_id`;
  - sort newest first for limiting, take `limit`, then return old-to-new.
- [ ] In `scripts/env/tools/message/_impl.py`, add `conversation_messages()` and wire `_ACTION_HANDLERS["conversation"]`.
- [ ] Response shape:

```json
{
  "ok": true,
  "state_changed": false,
  "durability": "none",
  "read_scope": "active actor visible direct conversation messages",
  "messages": [],
  "count": 0,
  "selector": {}
}
```

- [ ] Run:

```bash
python3 -m pytest tests/test_message_env_tool.py -k "conversation" -q
python3 -m pytest tests/test_message_env_tool.py -q
```

Expected: pass.

## Task 5: Update Context Message Cues

- [ ] Update `ContextBindingEnvToolTests.test_context_summarize_includes_compact_active_inbox_message_cues` to expect:
  - `inbox_source_of_truth`;
  - `conversation_source_of_truth`;
  - `latest_inbox`;
  - no full message `content`;
  - message context source text mentions both `message.list` and `message.conversation`.
- [ ] Run:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_includes_compact_active_inbox_message_cues -q
```

Expected: fail before implementation.

- [ ] Change `_message_cues()` to return:

```python
{
    "count": len(inbox),
    "latest_inbox": latest,
    "inbox_source_of_truth": "message.list",
    "conversation_source_of_truth": "message.conversation",
    "target_discovery": "Use message.contacts to discover online target actor addresses.",
}
```

- [ ] Update context sources message description/source accordingly.
- [ ] Run focused context test.

## Task 6: Add Mailbox Handler Status Observability

- [ ] Update daemon status tests to pass and assert `mailbox_handlers`.
- [ ] Update instance daemon status test to record both handler lists.
- [ ] Run:

```bash
python3 -m pytest tests/test_daemon_core.py::DaemonCoreTest::test_daemon_status_reports_registered_handler_observability -q
python3 -m pytest tests/test_daemon_core.py::DaemonCoreTest::test_daemon_status_includes_persisted_unregistered_handler_state -q
python3 -m pytest tests/test_instance_daemon_entrypoint.py::InstanceDaemonEntrypointTest::test_status_prints_json_from_daemon_core -q
```

Expected: fail before implementation.

- [ ] Extend `daemon_core.daemon_status(instance_json, *, handlers=None, mailbox_handlers=None)`.
- [ ] Return both:

```json
{
  "handlers": {"registered": [], "items": {}},
  "mailbox_handlers": {"registered": [], "items": {}}
}
```

- [ ] Reuse `_handler_status_payload()` unless persisted state separation is needed; current `DaemonState` stores handler results by handler name, so source separation happens at status grouping.
- [ ] Pass both handler groups in `instance_daemon status`.
- [ ] Run the focused daemon status tests.

## Task 7: Product-Mode Permission Audit And Fix

- [ ] Inspect and document whether the observed read-only goal continuation was BuddySwitch-owned or external/manual.
- [ ] Run existing focused permission tests first:

```bash
python3 -m pytest tests/test_app_server_client.py -k "permissions or resume or side or goal" -q
```

- [ ] Then run launcher permission subset only after confirming service helper cleanup:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "permissions or resume or side or goal or daemon" -q
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex" || true
```

- [ ] If a BuddySwitch-owned thread/turn path lacks `permissions: "buddyswitch-runtime"`, add the smallest regression test around that RPC params object and fix the launcher/app-server call.
- [ ] If no BuddySwitch-owned path lacks permissions, record the conclusion in this plan's execution notes and do not add compatibility code. The product route is: env-tool collaboration must happen in instance main/daemon/side/input paths that already carry `buddyswitch-runtime`; external/manual read-only continuations are not a supported env-tool execution surface.

## Task 8: Focused Regression

## Execution Notes

- 2026-05-30 permission audit: `tests/test_app_server_client.py -k "permissions or resume or side or goal" -q` passed with `4 passed, 15 deselected`.
- 2026-05-30 launcher permission/lifecycle subset: `tests/test_buddyswitch_launcher.py -k "permissions or resume or side or goal or daemon" -q` passed with `46 passed, 147 deselected, 4 subtests passed`.
- Residual process check after the launcher subset returned no matching `instance_daemon.py`, `central_daemon.py`, `runtime_broker`, `app_server.py`, or `fake_codex` processes.
- Conclusion: the observed read-only goal continuation is not reproduced on BuddySwitch-owned product-mode start, daemon resume, instance resume, attach, input, side, or goal launcher paths covered by these tests. Product env-tool collaboration remains routed through managed instance main/daemon/input/side paths carrying `buddyswitch-runtime`; no runtime-object fallback or compatibility path is added for external/manual read-only continuations.

- [ ] Run pure contract group:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_message_skill_prevents_observed_invalid_calls -q
python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_role_action_auth.py -q
python3 -m pytest tests/test_message_env_tool.py -q
python3 -m pytest tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_includes_compact_active_inbox_message_cues -q
```

- [ ] Run daemon observability group:

```bash
python3 -m pytest tests/test_daemon_core.py tests/test_instance_daemon_entrypoint.py -q
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex" || true
```

- [ ] Fix only failures in this task's scope.

## Task 9: Full Verification And Real Path

- [ ] Run:

```bash
git diff --check
python3 -m pytest tests -q
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex" || true
```

- [ ] If full suite passes and residuals are clean, run the PM/market main path from the test plan.
- [ ] Stop/delete test instances unless intentionally retained, and record the decision.

## Review Checklist

- [ ] No `to_buddy` or `from_buddy` in the shared message skill.
- [ ] No `to_buddy`, `from_buddy`, or `box` accepted by `message.conversation`.
- [ ] No alias path added to `message.send`.
- [ ] `message.list` remains inbox-only.
- [ ] Conversation reads are active-actor-visible only.
- [ ] Context cues distinguish inbox and conversation source of truth.
- [ ] Daemon status has separate notification and mailbox handler groups.
- [ ] Product-mode permission conclusion is backed by tests or a targeted fix.
- [ ] Automated focused tests pass before broad tests.
- [ ] Residual process checks are clean after service-starting tests.

## Self Review

- Spec coverage: the plan covers every in-scope item from `docs/memo/2026-05-30-message-product-experience-no-residual-repair-task.md`, including skill, contacts, read model, context, auth, daemon status, permission boundary, materialization, and real PM/market verification.
- Placeholder scan: no task contains TBD/TODO placeholders; each task names exact files, expected red state, implementation point, and verification command.
- Type consistency: the plan uses `target_actor_address`, `RuntimeActorAddress`, `message.conversation`, `latest_inbox`, `inbox_source_of_truth`, and `conversation_source_of_truth` consistently.
- Scope check: no request/track/artifact/comment model changes, no offline queue, no old payload compatibility aliases, and no overloaded `message.list`.
