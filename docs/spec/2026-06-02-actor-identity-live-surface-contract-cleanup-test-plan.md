# Actor Identity Live Surface Contract Cleanup Test Plan

Date: 2026-06-02
Worktree: `fea-daemon`
Source memo: `docs/memo/2026-06-02-actor-identity-live-surface-contract-cleanup-task.md`

## Goal

Prove that live runtime surfaces describe direct message and private work identity as actor-owned while preserving role wording only for permissions, capability profiles, request queues, track ownership, artifact allowlists, and readable target access.

The current bottleneck is not core message behavior. The behavior already rejects same `actor_id` self-send and allows same `role_id` with a different `actor_id`. The bottleneck is that live catalog, skill, README, Web UI, and env-profile surfaces still teach role-as-actor wording.

## Requirements Under Test

1. Direct message sender, recipient, inbox owner, conversation participant, and self-send checks are Actor concepts.
2. Same `actor_id` targets are not sendable and cannot be messaged.
3. Same `role_id` with different `actor_id` is sendable and can be selected in `message.conversation`.
4. Message inbox ownership is active actor scoped.
5. Runtime message catalog uses actor-address wording and no role-as-actor authorities.
6. Comment and task catalogs do not describe direct inbox messaging or taskbox ownership as active-role concepts.
7. Runtime skills installed into actor workspaces do not teach role-as-actor direct message rules.
8. README and Web UI describe role-configured actor instances, not role-locked instances or role-owned runtime workspaces.
9. Web UI visible labels and JS state use `Role` / `selectedRole`, while keeping `BuddySwitch` as a brand string.
10. Env profile contract and all role profiles use `role-profile-only`, not `active-role-only`.
11. Remaining role wording is valid only when it describes authorization, capability, request queues, track ownership, artifact template allowlists, or readable target access.

## Resource-Safe Rule

Follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

This cleanup should use pure unit, catalog, repo consistency, Web UI asset, and `RuntimeWorkspaceTestMixin` tests. Do not run broad launcher tests before focused verification. If any command starts daemon, app-server, browser, broker, watcher, or fake Codex processes, run one focused test first and inspect residual processes before scaling.

Residual process inspection command after any service-sensitive check:

```bash
ps -axo pid,ppid,command | rg 'buddyswitch|runtime_broker|app_server|central_daemon|chrome|fake_codex' || true
```

Expected service-sensitive state for this task: no new residual process inspection is needed unless a launcher or browser test is introduced. The planned commands below avoid those broad service-starting paths.

## Test Group 1: Runtime Catalog Actor Identity

File: `tests/test_env_tool_semantic_contract.py`

Add `test_message_catalog_uses_actor_address_identity_language`.

Assertions:

- `catalog.env_tools_description()["message"]["title"] == "Direct Actor Messages"`.
- `catalog.operation_semantics()["message.send"]["authority"] == "message.direct_actor_address_channel"`.
- `catalog.operation_semantics()["message.list"]["authority"] == "message.active_actor_inbox"`.
- `message.list` visibility contains `active actor inbox`.
- message send preconditions mention active actor, not active role.
- message conversation preconditions do not forbid the active role.
- serialized message catalog and operation semantics do not contain:
  - `role messages`
  - `direct_role_channel`
  - `active_role_inbox`
  - `active-role inbox`
  - `not the active role`
  - `outside the active role`
  - `same role id`
  - `active role cannot`
  - `target runtime actor actor id`

Add `test_adjacent_catalog_surfaces_do_not_teach_direct_role_inbox_or_role_taskbox`.

Assertions:

- serialized `comment` catalog does not contain `direct role inbox` or `direct role messaging`.
- serialized `task` catalog does not contain `active-role taskbox`, `active-role tasksnapshot`, or `current active-role taskbox task`.
- serialized `comment` catalog may still contain active-role readable target access.
- serialized `task` catalog may still contain role-action permission preconditions.

Update `test_adjacent_action_boundaries_are_explained` so `message.send` requires `inbox`, `actor address`, and `comment`, not `role` as a positive participant snippet.

Red command:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
```

Expected before implementation: FAIL on current `Role Messages`, `message.direct_role_channel`, `message.active_role_inbox`, `active-role inbox`, comment direct role inbox text, or task active-role taskbox text.

## Test Group 2: Runtime Skills

File: `tests/test_runtime_skills.py`

Extend `test_shared_message_skill_prevents_observed_invalid_calls`.

For source skill text and installed skill text, assert absence of:

- `active role cannot`
- `same role id`
- `same role cannot`
- `same-role cannot`
- `same buddy`
- `buddybox`
- `role messages`
- `direct_role_channel`
- `active-role inbox`
- `not the active role`

Assert presence of:

- `active actor cannot send to itself`
- `same role with a different actor is allowed`

Update `test_pm_define_scope_teaches_track_boundary_heuristics_without_routing_rules` to require:

- `use private tasks for active actor private work management`

Red command:

```bash
python3 -m pytest tests/test_runtime_skills.py -q
```

Expected before implementation: FAIL because `message-tool` still says active role cannot message another actor with the same role id and PM define-scope still says active-role work management.

## Test Group 3: Message Behavior Guard

File: `tests/test_message_env_tool.py`

Extend `test_message_conversation_role_selector_returns_visible_bidirectional_role_messages` so role selector `role="dev"` works when the active actor is also `dev`.

Scenario:

- active actor: `{"role_id": "dev", "actor_id": "act-dev-conversation-role"}`
- peer actor: `{"role_id": "dev", "actor_id": "act-dev-conversation-peer"}`
- unrelated dev actors not involving the active actor
- messages active-to-peer and peer-to-active are returned by `message.conversation` with `args={"role": "dev"}`
- unrelated dev-dev messages are not returned
- response is successful and no rejection says active role is forbidden

Update `test_message_contacts_marks_only_active_actor_row_not_sendable`:

- self row reason contains active actor self-target meaning.
- self row reason does not contain `same role` or `same role id`.
- same-role different actor remains sendable.

Focused command:

```bash
python3 -m pytest tests/test_message_env_tool.py -q
```

Expected before implementation: contact wording assertion should FAIL after the test is updated; same-role conversation behavior may already PASS and is required as a guard.

## Test Group 4: Scoped Live-Surface Residue Scan

File: `tests/test_repo_consistency.py`

Add `test_actor_identity_live_surfaces_do_not_reintroduce_role_as_actor_residue`.

Scan only:

- `scripts/env/tools/message/tool.py`
- `scripts/env/tools/comment/tool.py`
- `scripts/env/tools/task/tool.py`
- `buddyswitch/skills/shared/message-tool/SKILL.md`
- `buddyswitch/skills/shared/comment-tool/SKILL.md`
- `buddyswitch/skills/pm/define-scope/SKILL.md`
- `README.md`
- `tools/launcher/assets/web-management/index.html`
- `tools/launcher/assets/web-management/app.js`
- `framework/contracts/role-env-profile.json`
- `buddyswitch/env-profiles/*.json`

Forbid exact lower-case tokens or case-sensitive fragments:

- `role messages`
- `direct_role_channel`
- `active_role_inbox`
- `active-role inbox`
- `not the active role`
- `outside the active role`
- `active role cannot`
- `same role id`
- `direct role inbox`
- `direct role messaging`
- `active-role tasksnapshot`
- `active-role taskbox`
- `current active-role taskbox task`
- `active-role work management`
- `role-locked codex instances`
- `runtime workspace per role`
- `selectedBuddy`
- `>Buddy<`
- `Stored local role instances`
- `active-role-only`

Do not scan all tests, all scripts, or `docs/**` with this list; that would catch legitimate role authorization and historical context.

Red command:

```bash
python3 -m pytest tests/test_repo_consistency.py -q
```

Expected before implementation: FAIL with one or more scoped live-surface hits.

## Test Group 5: Web UI State And Contract

Files:

- `tests/web_management_ui_state.test.js`
- `tests/web_management_ui_contract.test.js`

State test updates:

- `computeCreateEnabled({ selectedRole: '', isCreating: false })` returns `false`.
- `computeCreateEnabled({ selectedRole: 'pm', isCreating: true })` returns `false`.
- `computeCreateEnabled({ selectedRole: 'pm', isCreating: false })` returns `true`.
- test text and fixtures no longer use `selectedBuddy`.

Contract test updates:

- `index.html` includes visible `Role` selector and table header.
- assets exclude `>Buddy<`, `selectedBuddy`, and `Stored local role instances`.
- assets keep `BuddySwitch` brand strings.

Red command:

```bash
node --test tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
```

Expected before implementation: FAIL because app assets and tests still use `selectedBuddy` / visible `Buddy`.

## Test Group 6: Env Profile Projection Enum

File: `tests/test_buddy_env_profiles.py`

Add assertions:

- every validated profile has `profile["context_projection"]["skills"] == "role-profile-only"`.
- serialized `framework/contracts/role-env-profile.json` and every `buddyswitch/env-profiles/*.json` file do not contain `active-role-only`.

Commands:

```bash
python3 -m pytest tests/test_buddy_env_profiles.py -q
python3 scripts/env_profiles.py validate-all
```

Expected before implementation: pytest FAILS on profile enum, and validate-all may fail after the contract is changed until every JSON profile is updated.

## Exact Completion Scans

Run after focused tests pass.

```bash
rg -n -i "role messages|direct_role_channel|active_role_inbox|active-role inbox|not the active role|outside the active role|active role cannot|same role id|direct role inbox|direct role messaging|active-role tasksnapshot|active-role taskbox|current active-role taskbox task" \
  scripts/env/tools/message/tool.py \
  scripts/env/tools/comment/tool.py \
  scripts/env/tools/task/tool.py
```

Expected: no output.

```bash
rg -n -i "active role cannot|same role id|direct role messaging|active-role work management|role-locked codex instances|runtime workspace per role" \
  buddyswitch/skills/shared/message-tool/SKILL.md \
  buddyswitch/skills/shared/comment-tool/SKILL.md \
  buddyswitch/skills/pm/define-scope/SKILL.md \
  README.md
```

Expected: no output.

```bash
rg -n "selectedBuddy|>Buddy<|Stored local role instances" \
  tools/launcher/assets/web-management \
  tests/web_management_ui_state.test.js \
  tests/web_management_ui_contract.test.js
```

Expected: no output.

```bash
rg -n "active-role-only" \
  framework/contracts/role-env-profile.json \
  buddyswitch/env-profiles
```

Expected: no output.

Run a broad informational scan:

```bash
rg -n "active-role|active role|direct role|same role|role-locked|workspace per role" \
  scripts/env/tools \
  buddyswitch/skills \
  README.md \
  tools/launcher/assets \
  framework/contracts \
  buddyswitch/env-profiles
```

Expected: remaining hits, if any, are valid role authorization, role capability, request queue, track ownership, artifact template allowlist, readable target access, or brand text.

## Final Verification

Focused Python verification:

```bash
python3 -m pytest \
  tests/test_env_tool_semantic_contract.py \
  tests/test_runtime_skills.py \
  tests/test_message_env_tool.py \
  tests/test_repo_consistency.py \
  tests/test_buddy_env_profiles.py \
  -q
```

Web UI verification:

```bash
node --test tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
```

Profile CLI verification:

```bash
python3 scripts/env_profiles.py validate-all
```

Broader non-launcher verification:

```bash
python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_context_binding_env_tool.py tests/test_task_env_tool.py tests/test_comment_env_tool.py -q
```

## Review Check

- Requirement coverage: all memo live surfaces are covered by at least one behavior, catalog, skill, repo scan, UI, or profile test above.
- Historical scope: `docs/**` is excluded from residue scans except this plan and the source memo can mention old terms as context.
- False-positive control: exact role authorization strings such as active-role readable target access and permission boundaries are not globally banned.
- Resource safety: planned verification avoids broad launcher/browser/app-server suites.
