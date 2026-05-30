# Message Product Experience No-Residual Repair Test Plan

Date: 2026-05-30
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`

## Goal

Prove the message product path no longer requires hosts to guess payload fields, direction, entrypoint permissions, or daemon handler state:

```text
message.contacts -> copy contact.actor_address into message.send.target_actor_address
-> delivered message.available signal -> target reads inbox with message.list
-> either side reads bidirectional context with message.conversation
-> daemon status shows notification handlers and mailbox handlers truthfully
```

## Resource Lifecycle Guard

Follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

- Pure message/domain/schema/skill/context tests must not start daemon, broker, app-server, browser, or fake Codex processes.
- Before any launcher or daemon group is broadened, run one focused service-starting check and then inspect residuals.
- After every daemon/launcher group and after real PM/market verification, run:

```bash
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex" || true
```

- Unexpected test-owned residual processes or sockets are test failures, even if assertions passed.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | `buddyswitch/skills/shared/message-tool/SKILL.md` teaches the current actor-address workflow and contains no stale `to_buddy` / `from_buddy` message-send model. |
| FR2 | `message.contacts` marks online same-buddy / active-buddy contacts as `sendable: false`, preserves them with a reason, and reports `sendable_count`. |
| FR3 | `message.contacts` next action explicitly says to copy `contact.actor_address` into `target_actor_address`. |
| FR4 | `message.send` remains strict: accepts `target_actor_address + content`, rejects old aliases, and does not add compatibility fields. |
| FR5 | `message.list` remains active actor inbox-only and does not accept `box`. |
| FR6 | `message.conversation` exists as a read action with permission `message.conversation`. |
| FR7 | `message.conversation` requires exactly one selector: `target_actor_address` or `buddy`. |
| FR8 | `message.conversation` returns only active-actor-visible direct messages between the active actor and the selected target actor/buddy. |
| FR9 | `message.conversation` orders returned rows chronologically old-to-new after applying a latest-N limit. |
| FR10 | `message.conversation` rejects unsupported fields including `box`, `to_buddy`, and `from_buddy`. |
| FR11 | Role-action auth allows `message.conversation` for every manifest role. |
| FR12 | Context message cues distinguish `message.list` inbox source, `message.conversation` bidirectional source, and `message.contacts` discovery source. |
| FR13 | Daemon status reports mailbox handlers separately from notification handlers, including registered `message_available`. |
| FR14 | Persisted mailbox handler state is not falsely reported as unregistered when the mailbox handler is wired. |
| FR15 | Product-mode launcher-created main, daemon, side, input, attach, resume, and goal continuation paths use `buddyswitch-runtime` permissions, or non-product external continuation paths are clearly not instructed to call env tools. |
| FR16 | Fresh runtime skill materialization uses the corrected source skill; stale instance skill copies are not used as proof. |
| FR17 | Real PM/market path works first try with contacts -> send -> daemon wake -> list -> reply -> conversation -> status. |

## Test Groups

### T1: Shared Message Skill Contract

File: `tests/test_runtime_skills.py`

Extend `RuntimeSkillsTests.test_shared_message_skill_prevents_observed_invalid_calls`.

Assertions:

- Contains `message contacts --payload`.
- Contains `target_actor_address`.
- Contains `contact.actor_address`.
- Contains `message send --payload '{"target_actor_address"`.
- Contains `message conversation --payload`.
- Contains `message list --payload '{}'`.
- Contains `does not accept \`box\``.
- Contains `context.get.tool_catalog['message']`.
- Does not contain `to_buddy`.
- Does not contain `from_buddy`.
- Does not contain old `actor_address` / `message` send-payload examples.

Focused command:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_message_skill_prevents_observed_invalid_calls -q
```

Expected red before implementation: fails on the stale shared skill.

### T2: Contacts Sendability Truth

File: `tests/test_message_env_tool.py`

Add `MessageEnvToolTests.test_message_contacts_marks_active_buddy_rows_not_sendable`.

Scenario:

- Active actor: `pm / inst-pm-contacts-self`.
- Daemon returns contacts:
  - `pm / inst-pm-contacts-self`
  - `pm / inst-pm-other`
  - `market / inst-market-contacts`
- Assert PM rows remain visible but `sendable is False`.
- Assert PM rows include `why_not_sendable`.
- Assert market row is `sendable is True`.
- Assert response `sendable_count == 1`.
- Assert `allowed_next_actions` mentions `target_actor_address`.

Focused command:

```bash
python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_contacts_marks_active_buddy_rows_not_sendable -q
```

Expected red before implementation: current `normalize_contact_rows()` marks same-buddy online contacts sendable.

### T3: Message Conversation Schema And Policy

Files:

- `tests/test_env_tool_schema_contract.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_role_action_auth.py`

Extend `EnvToolSchemaContractTests.test_high_risk_schema_shapes_match_domain_contracts`.

Assertions:

- `message.conversation` action exists.
- `message.conversation` schema has optional fields: `target_actor_address`, `buddy`, `q`, `limit`.
- `target_actor_address` has required `buddy_id` and `instance_id`.
- Schema does not include `box`, `to_buddy`, or `from_buddy`.
- Action kind is `read`, mutates `none`, durability `none`, required permission `message.conversation`.

Existing semantic and role-auth tests must pass without special-casing:

```bash
python3 -m pytest tests/test_env_tool_schema_contract.py::EnvToolSchemaContractTests::test_high_risk_schema_shapes_match_domain_contracts -q
python3 -m pytest tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_registry_semantics_cover_every_registered_tool_and_action -q
python3 -m pytest tests/test_role_action_auth.py -q
```

Expected red before implementation: `conversation` does not exist and role policy lacks `message.conversation`.

### T4: Message Conversation Behavior

File: `tests/test_message_env_tool.py`

Add cases:

- `test_message_conversation_returns_visible_bidirectional_actor_messages`
  - Seed active dev, PM, design, and another dev actor.
  - Include dev -> PM, PM -> dev, PM -> other-dev, design -> PM, and market/noise rows.
  - Dispatch `message.conversation` with exact PM `target_actor_address`.
  - Assert only dev/PM exact actor pair rows return.
  - Assert inbox and outbox both appear.
  - Assert chronological old-to-new order.
- `test_message_conversation_buddy_selector_returns_visible_bidirectional_buddy_messages`
  - Seed active dev with two PM actors plus unrelated design rows.
  - Dispatch with `{"buddy":"pm"}`.
  - Assert rows include all visible dev <-> any PM actor rows and exclude active-actor-unrelated rows.
- `test_message_conversation_requires_exactly_one_selector`
  - Dispatch with no selector and both selectors.
  - Assert `E_MESSAGE_PAYLOAD`, `state_changed: false`, and `correctable_fields` point at selector fields.
- `test_message_conversation_rejects_old_direction_fields`
  - Dispatch with `box`, `to_buddy`, and `from_buddy`.
  - Assert `E_MESSAGE_PAYLOAD`.
- `test_message_conversation_applies_latest_limit_then_returns_chronological`
  - Seed more than limit with sortable `created_at`.
  - Assert latest N messages are returned old-to-new.

Focused command:

```bash
python3 -m pytest tests/test_message_env_tool.py -k "conversation" -q
```

Expected red before implementation: unsupported action.

### T5: Context Message Cues

File: `tests/test_context_binding_env_tool.py`

Update `ContextBindingEnvToolTests.test_context_summarize_includes_compact_active_inbox_message_cues`.

Assertions:

- `message_cues.inbox_source_of_truth == "message.list"`.
- `message_cues.conversation_source_of_truth == "message.conversation"`.
- `message_cues.target_discovery` mentions `message.contacts`.
- `message_cues.latest_inbox` contains active actor inbox cue rows.
- Cue rows omit message `content`.
- Context sources for messages describe both inbox and conversation reads.

Focused command:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_includes_compact_active_inbox_message_cues -q
```

Expected red before implementation: cues only expose `source_of_truth: message.list`.

### T6: Daemon Status Mailbox Handler Observability

Files:

- `tests/test_daemon_core.py`
- `tests/test_instance_daemon_entrypoint.py`

Updates:

- `DaemonCoreTest.test_daemon_status_reports_registered_handler_observability`
  - Pass `handlers=[FakeTaskHandler()]` and `mailbox_handlers=[FakeMailboxHandler()]`.
  - Assert payload has `handlers.registered == ["task_checkout"]`.
  - Assert payload has `mailbox_handlers.registered == ["message_available"]`.
  - Assert both item entries are registered/enabled/active.
- `DaemonCoreTest.test_daemon_status_includes_persisted_unregistered_handler_state`
  - Persist state for one unregistered notification handler and one wired mailbox handler.
  - Assert wired mailbox handler is registered, not falsely unregistered.
- `InstanceDaemonEntrypointTest.test_status_prints_json_from_daemon_core`
  - Assert `instance_daemon status` passes both `default_handlers()` and `default_mailbox_handlers()`.

Focused commands:

```bash
python3 -m pytest tests/test_daemon_core.py::DaemonCoreTest::test_daemon_status_reports_registered_handler_observability -q
python3 -m pytest tests/test_daemon_core.py::DaemonCoreTest::test_daemon_status_includes_persisted_unregistered_handler_state -q
python3 -m pytest tests/test_instance_daemon_entrypoint.py::InstanceDaemonEntrypointTest::test_status_prints_json_from_daemon_core -q
```

Expected red before implementation: `daemon_status()` has no `mailbox_handlers` parameter and status entrypoint omits mailbox handlers.

### T7: Product-Mode Permission Entrypoints

Files:

- `tests/test_app_server_client.py`
- `tests/test_buddyswitch_launcher.py`

Audit and test exact BuddySwitch-owned entrypoints:

- `thread/start` on instance start includes `permissions: "buddyswitch-runtime"`.
- daemon `thread/resume` includes `permissions: "buddyswitch-runtime"`.
- `turn/start` from instance input includes `permissions: "buddyswitch-runtime"`.
- side fork and side turn include `permissions: "buddyswitch-runtime"`.
- attach preflight `thread/resume` includes `permissions: "buddyswitch-runtime"`.
- instance resume `thread/resume` includes `permissions: "buddyswitch-runtime"`.
- `goal get/set/clear` do not create a new execution thread and therefore are not env-tool continuations.

Focused commands:

```bash
python3 -m pytest tests/test_app_server_client.py -k "permissions or resume or side or goal" -q
python3 -m pytest tests/test_buddyswitch_launcher.py -k "permissions or resume or side or goal or daemon" -q
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex" || true
```

Expected: pass after audit or fail with the precise missing product-mode permission path to fix.

### T8: Runtime Skill Materialization

File: `tests/test_runtime_skills.py`

Extend the shared skill test to install runtime skills into a temporary workspace for at least PM and market and assert installed copies match the corrected source contract:

- No `to_buddy`.
- No `from_buddy`.
- Includes `target_actor_address`.
- Includes `message.conversation`.

Focused command:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_message_skill_prevents_observed_invalid_calls -q
```

### T9: Regression And Boundary Checks

Focused pure contract group:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_message_skill_prevents_observed_invalid_calls -q
python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_role_action_auth.py -q
python3 -m pytest tests/test_message_env_tool.py -q
python3 -m pytest tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_includes_compact_active_inbox_message_cues -q
```

Daemon observability group:

```bash
python3 -m pytest tests/test_daemon_core.py tests/test_instance_daemon_entrypoint.py -q
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex" || true
```

Launcher permission group:

```bash
python3 -m pytest tests/test_app_server_client.py -k "permissions or resume or side or goal" -q
python3 -m pytest tests/test_buddyswitch_launcher.py -k "permissions or resume or side or goal or daemon" -q
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex" || true
```

Final code gates:

```bash
git diff --check
python3 -m pytest tests -q
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex" || true
```

### T10: Real PM/Market Main Path

Run only after automated focused groups pass.

Start fresh instances:

```bash
./buddyswitch-codex instance start --buddy pm
./buddyswitch-codex instance start --buddy market
```

Verify from PM runtime:

```bash
python3 scripts/env/client.py message contacts --payload '{"buddy":"market"}'
python3 scripts/env/client.py message send --payload '{"target_actor_address":{"buddy_id":"market","instance_id":"<market-instance>"},"content":"请先从目标用户和替代方案聊起。"}'
python3 scripts/env/client.py message conversation --payload '{"buddy":"market","limit":20}'
```

Verify from market runtime after daemon wake:

```bash
python3 scripts/env/client.py message list --payload '{"buddy":"pm","limit":20}'
python3 scripts/env/client.py message send --payload '{"target_actor_address":{"buddy_id":"pm","instance_id":"<pm-instance>"},"content":"先看项目制/客户制人群。"}'
```

Verify from PM:

```bash
python3 scripts/env/client.py message list --payload '{"buddy":"market","limit":20}'
python3 scripts/env/client.py message conversation --payload '{"buddy":"market","limit":20}'
./buddyswitch-codex instance status <pm-instance> --json
./buddyswitch-codex instance status <market-instance> --json
```

Expected:

- Contacts returns market `sendable: true`.
- Contacts does not mark PM/self buddy rows sendable.
- PM send succeeds with `delivery_status: delivered`.
- Market list shows PM inbox message.
- Market reply succeeds.
- PM list shows market reply.
- PM conversation shows PM outbound and market inbound rows.
- Status reports `handlers.task_checkout` and `mailbox_handlers.message_available` as registered when wired.

Cleanup:

```bash
./buddyswitch-codex instance stop <pm-instance>
./buddyswitch-codex instance stop <market-instance>
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex" || true
```

If instances are intentionally retained for inspection, record that in the final report.

## Self Review

- Coverage: FR1-FR17 map to T1-T10; the plan covers skill, contacts, send strictness, list boundary, conversation read model, context cues, auth, daemon status, runtime permissions, materialization, automated tests, real path, and residual resource checks.
- Anti-cheat check: tests assert product behavior and externally visible contracts; implementation details are only inspected for boundary invariants already used by the repo.
- Resource check: service-starting tests are separated from pure tests and have residual process checks before broad runs.
- Forward principle: no legacy payload aliases, no overloaded `message.list`, and no runtime-object hand edits are accepted.
