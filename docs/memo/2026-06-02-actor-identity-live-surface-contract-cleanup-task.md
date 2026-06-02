# Actor Identity Live Surface Contract Cleanup Task

Date: 2026-06-02
Status: execution memo
Supersedes for this cleanup slice: the unexecuted message wording portion of `docs/memo/2026-06-01-actor-identity-final-rebuild-task.md`

## 1. Goal

Clean the remaining live actor/role identity residue in one tested task.

This task must update tests and implementation together so the next execution does not repeat the current failure mode:

```text
runtime behavior is actor-correct
but live catalog / skill / UI guidance still teaches role-as-actor identity
```

The target final state is:

- direct message identity is actor-addressed;
- same `actor_id` is self and cannot be messaged;
- same `role_id` with different `actor_id` is allowed for direct messages;
- message inbox ownership is active actor scoped;
- role remains valid for permissions, capability profiles, request queues, track ownership, artifact template allowlists, and readable target access;
- live runtime catalog, native MCP descriptions, installed skills, README, and web management UI no longer describe direct message identity or private work as role-owned.

This is not a broad actor-identity rebuild. It is a focused live-surface contract cleanup for residue already found after `fea-inst` was advanced to `fea-daemon`.

## 2. Current Confirmed Root Cause

### 2.1 Timeline

- `ab1ef19 feat: repair message product experience`
  - This commit still used the old buddy-era rule.
  - It intentionally taught and tested same-buddy unsendable behavior.
  - This was not a missed actor cleanup at that time.

- `8cac197 Native-first env tool surface cleanup`
  - This task removed CLI-first guidance.
  - It preserved the old same-buddy semantic line in `message-tool`.
  - Identity semantics were not the task scope.

- `c670455 Rebuild actor identity around role and actor`
  - This commit fixed message behavior:
    - same `actor_id` is rejected;
    - same `role_id` with different `actor_id` is allowed;
    - contacts mark only the active actor itself as not sendable.
  - The same commit mechanically changed some old `buddy` wording into `role` wording.
  - That produced wrong live contract text such as:
    - `Role Messages`;
    - `message.direct_role_channel`;
    - `target_actor_address is online and not the active role`;
    - `Active role cannot send to another actor with the same role id`;
    - `active-role inbox`.

- `71cd05c Harden actor identity final rebuild`
  - This commit noticed the residue and wrote the required cleanup into the memo.
  - It did not modify `scripts/env/tools/message/tool.py`.
  - It did not modify `buddyswitch/skills/shared/message-tool/SKILL.md`.
  - It did not encode the live-surface scan into tests.

- `212f1b2 Rebuild daemon message async routing`
  - This task focused on daemon async message routing.
  - It did not reopen actor-vs-role wording.

### 2.2 Why Existing Tests Did Not Catch It

Existing tests cover behavior but not live-surface wording:

- `tests/test_message_env_tool.py` proves same-role different-actor send is allowed.
- `tests/test_message_env_tool.py` proves same actor self-send is rejected.
- `tests/test_env_tool_schema_contract.py` proves message schemas use `target_actor_address`.
- `tests/test_runtime_skills.py` prevents old CLI examples and `to_role` / `from_role`.

Those tests do not currently fail when runtime catalog or skill guidance says:

- `Role Messages`;
- `direct_role_channel`;
- `active-role inbox`;
- `not the active role`;
- `same role id`;
- `direct role inbox`.

The previous memo's suggested scan was also manual only and too narrow. It matched `same role cannot` and `same-role.*cannot`, but did not match:

```text
Active role cannot send to another actor with the same role id.
```

## 3. What Counts As A Live Surface

This task must cover only live surfaces, not historical records.

### 3.1 Live Surfaces In Scope

- `scripts/env/tools/*/tool.py`
  - Source of runtime catalog semantics.
  - Exported by `scripts/env/tool_runtime/registry.py`.
  - Projected to native MCP descriptions by `scripts/env/tool_runtime/native_mcp.py`.

- `scripts/env/domain/messages.py`
  - Source of runtime message rejection and contact guidance text.

- `buddyswitch/skills/**/*.md`
  - Installed into product-mode actor workspaces.
  - Teaches agents how to use runtime tools.

- `README.md`
  - Active repo/workspace guidance.

- `tools/launcher/assets/web-management/*`
  - User-facing management UI.

- `framework/contracts/role-env-profile.json`
  - Live env profile contract.

- `buddyswitch/env-profiles/*.json`
  - Live role capability profiles.

- Tests that assert or scan the above surfaces.

### 3.2 Historical Surfaces Out Of Scope

Do not rewrite historical memos and specs solely because they preserve old terms as context:

- `docs/memo/**`
- `docs/spec/**`

Exception: this new memo records the final task and may reference old terms as historical evidence.

## 4. Locked Semantics

### 4.1 Actor

Use Actor for:

- direct message sender;
- direct message recipient;
- online contact address;
- message inbox owner;
- message conversation participant;
- message self-send checks;
- task private owner;
- actor private workspace owner;
- draft artifact owner;
- tool execution provenance.

Canonical direct message participant payload:

```json
{
  "actor_id": "act-pm-example",
  "role_id": "pm"
}
```

### 4.2 Role

Use Role for:

- tool/action permissions;
- role-specific skills;
- env capability profiles;
- request queue recipient via `to_role`;
- track ownership where the product object is role-owned;
- artifact template allowlists;
- readable target access where access is role-based;
- browser/search capability profile.

Do not use Role for:

- direct message identity;
- message inbox ownership;
- self-send checks;
- private task ownership;
- actor private workspace ownership.

### 4.3 Allowed Role Wording

Tests must not forbid all `active role` text. These phrases are legitimate when they describe permission or capability:

- `env.tool role-action policy allows this action for the active role`
- `active role has read access to target`
- `active role is pm`
- request visibility and lifecycle checks involving `to_role`
- track ownership involving `owner_role`
- artifact template allowlists involving active role
- search/context runtime orientation where the surface is role capability, not actor identity

### 4.4 Forbidden Role-As-Actor Wording

The following patterns are forbidden in live surfaces after this task:

- `Role Messages`
- `message.direct_role_channel`
- `message.active_role_inbox`
- `active-role inbox`
- `target_actor_address is online and not the active role`
- `target selector is a declared manifest role outside the active role`
- `Active role cannot send to another actor with the same role id`
- `same role id` in message self-send guidance
- `direct role inbox`
- `direct role messaging`
- `active-role TaskSnapshot`
- `active-role taskbox`
- `current active-role taskbox task`
- `active-role work management`
- `role-locked Codex instances`
- `runtime workspace per role`
- generic UI labels `Buddy` for a role selector or role column
- internal web UI state name `selectedBuddy`
- `active-role-only` profile enum value

Brand strings such as `BuddySwitch` are allowed.

## 5. Confirmed Residue To Fix

### 5.1 Message Runtime Catalog

File: `scripts/env/tools/message/tool.py`

Current residue:

- line 16: `title='Role Messages'`
- line 112: `Target runtime actor actor id.`
- line 133: `authority='message.direct_role_channel'`
- line 157: `target_actor_address is online and not the active role`
- line 181: `List active-role inbox messages.`
- line 193: `active-role inbox message content`
- line 208: `authority='message.active_role_inbox'`
- line 209: `visibility='active-role inbox'`
- line 212: `Lists active-role inbox messages with optional filters.`
- line 215: `active-role inbox messages`
- line 234: `read active-role inbox messages`
- line 268: `Target runtime actor actor id.`
- line 315: `target selector is a declared manifest role outside the active role`

Required replacements:

| Current | Required |
| --- | --- |
| `Role Messages` | `Direct Actor Messages` |
| `message.direct_role_channel` | `message.direct_actor_address_channel` |
| `message.active_role_inbox` | `message.active_actor_inbox` |
| `active-role inbox` | `active actor inbox` |
| `target_actor_address is online and not the active role` | `target actor is online and is not the active actor` |
| `target selector is a declared manifest role outside the active role` | `role selector is a declared manifest role; exact actor selector must not be the active actor` |
| `Target runtime actor actor id.` | `Target runtime actor id.` |

Keep these role concepts because they are valid:

- `role` payload filter;
- `role_id` inside `target_actor_address`;
- manifest role validation;
- role-action permission preconditions.

### 5.2 Message Domain Feedback

File: `scripts/env/domain/messages.py`

Current behavior is correct. Only user-facing feedback may need cleanup:

- current self-send message: `cannot send a message to the same actor` is acceptable;
- current same conversation message: `cannot read a message conversation with the same actor` is acceptable;
- current contact row explanation uses `same actor_id`.

Required adjustment:

- Replace `message.send rejects targets with the same actor_id as the active actor` with a human-readable actor rule such as:

```text
message.send rejects the active actor itself as a target
```

This keeps the actor-correct meaning without making tests depend on awkward field-name prose.

### 5.3 Message Skill

File: `buddyswitch/skills/shared/message-tool/SKILL.md`

Current residue:

- `Active role cannot send to another actor with the same role id.`

Required replacement:

```text
- Active actor cannot send to itself; same role with a different actor is allowed.
```

Do not add payload examples or CLI examples.

### 5.4 Comment Catalog And Skill

Files:

- `scripts/env/tools/comment/tool.py`
- `buddyswitch/skills/shared/comment-tool/SKILL.md`

Current residue:

- `direct role inbox messages`
- `direct role inbox communication`
- `direct role inbox history`
- `direct role messaging`

Required replacement:

- `direct actor-address inbox messages`
- `direct actor-address inbox communication`
- `direct actor-address inbox history`
- `direct actor-address messaging`

Keep role-based readable target access wording where it describes target authorization:

- `Comment scope requires active-role readability on the target object.`
- `active role has read access to target`
- `active role is pm`

Those are not direct message identity claims.

### 5.5 Task Catalog And PM Skill

Files:

- `scripts/env/tools/task/tool.py`
- `buddyswitch/skills/pm/define-scope/SKILL.md`

Current residue:

- `active-role TaskSnapshot`
- `active-role taskbox`
- `current active-role taskbox task`
- `active-role work management`

Required replacement:

- `active actor TaskSnapshot`
- `active actor taskbox`
- `current active actor taskbox task`
- `active actor private work management`

Keep role-action permission preconditions.

Do not rename `authority="task.role_scope"` in this task unless focused tests prove it misleads runtime catalog consumers. The immediate residue is prose around task ownership, not permission authorization.

### 5.6 README

File: `README.md`

Current residue:

- `role-locked Codex instances`
- `runtime workspace per role`

Required replacement:

- `role-configured actor instances`
- `runtime workspace per actor`

Keep the role in the product-mode command example:

```bash
./buddyswitch-codex instance start --role pm
```

That command selects role capability for a newly created actor instance.

### 5.7 Web Management UI

Files:

- `tools/launcher/assets/web-management/index.html`
- `tools/launcher/assets/web-management/app.js`
- `tests/web_management_ui_state.test.js`
- `tests/web_management_ui_contract.test.js` if affected by label or state changes

Current residue:

- visible role selector label: `Buddy`
- visible role column header: `Buddy`
- subtitle: `Stored local role instances`
- JS state name: `selectedBuddy`
- tests pass `selectedBuddy`

Required replacement:

- selector label: `Role`
- column header: `Role`
- subtitle: `Stored local actor instances`
- JS state name: `selectedRole`
- tests pass `selectedRole`

Keep `BuddySwitch` brand strings.

### 5.8 Env Profile Skill Projection Enum

Files:

- `framework/contracts/role-env-profile.json`
- `buddyswitch/env-profiles/design.json`
- `buddyswitch/env-profiles/dev.json`
- `buddyswitch/env-profiles/market.json`
- `buddyswitch/env-profiles/pm.json`
- `buddyswitch/env-profiles/test.json`
- `tests/test_buddy_env_profiles.py`

Current residue:

- `context_projection.skills = "active-role-only"`

This enum describes skill projection by role capability. That role-based meaning is valid, but the value name still uses `active-role` phrasing that reads like actor identity.

Required replacement:

```text
role-profile-only
```

The new value means:

```text
install skills declared by the active actor's role profile
```

Required test additions:

- assert every profile has `context_projection.skills == "role-profile-only"`;
- assert `"active-role-only"` is absent from `framework/contracts/role-env-profile.json` and `buddyswitch/env-profiles/*.json`;
- run `python3 scripts/env_profiles.py validate-all`.

### 5.9 Deliberately Not Fixed In This Task

Do not change these unless a focused behavior test proves they are wrong:

- `request.to_role`
- request visibility by active role
- `track.owner_role`
- track PM-only create/archive
- artifact template permissions by active role
- comment target readability by active role
- search/context role capability profile wording
- broker permission boundary string `active-role`
- auth denial copy such as `active role is not allowed`

Those describe role authorization or product object ownership, not direct actor identity.

## 6. Test Strategy

This task must start with tests. The tests are not "word proves behavior" tests. They are live-surface contract tests for strings that are exported to agents and users.

Behavior tests continue to prove behavior. Catalog/guidance tests prove that the behavior is not contradicted by the live contract surface.

### 6.1 Add Failing Runtime Catalog Contract Tests

File: `tests/test_env_tool_semantic_contract.py`

Add a test named:

```python
def test_message_catalog_uses_actor_address_identity_language(self) -> None:
```

Required assertions:

- `catalog.env_tools_description()["message"]["title"] == "Direct Actor Messages"`;
- `catalog.operation_semantics()["message.send"]["authority"] == "message.direct_actor_address_channel"`;
- `catalog.operation_semantics()["message.list"]["authority"] == "message.active_actor_inbox"`;
- message list visibility contains `active actor inbox`;
- message send preconditions mention active actor, not active role;
- message conversation preconditions do not forbid selecting the active role;
- serialized message catalog and message operation semantics do not contain:
  - `role messages`;
  - `direct_role_channel`;
  - `active_role_inbox`;
  - `active-role inbox`;
  - `not the active role`;
  - `outside the active role`;
  - `same role id`;
  - `active role cannot`;
  - `target runtime actor actor id`.

Expected before implementation:

```text
FAIL because scripts/env/tools/message/tool.py still exports role-as-actor wording.
```

Add a second test named:

```python
def test_adjacent_catalog_surfaces_do_not_teach_direct_role_inbox_or_role_taskbox(self) -> None:
```

Required assertions:

- serialized `comment` catalog does not contain:
  - `direct role inbox`;
  - `direct role messaging`;
- serialized `task` catalog does not contain:
  - `active-role taskbox`;
  - `active-role tasksnapshot`;
  - `current active-role taskbox task`;
- serialized `comment` catalog still may contain active role readable target access;
- serialized `task` catalog still may contain role-action permission preconditions.

Expected before implementation:

```text
FAIL because comment and task catalog prose still contains those exact strings.
```

Also update the existing snippet checks:

- `message.send` should require snippets such as `inbox`, `actor address`, `comment`;
- do not require `role` as a positive message.send semantic snippet merely to keep a role word present.

### 6.2 Add Failing Runtime Skill Tests

File: `tests/test_runtime_skills.py`

Extend `test_shared_message_skill_prevents_observed_invalid_calls`.

For both source skill text and installed skill text, assert absence of:

- `active role cannot`;
- `same role id`;
- `same role cannot`;
- `same-role cannot`;
- `same buddy`;
- `buddybox`;
- `role messages`;
- `direct_role_channel`;
- `active-role inbox`;
- `not the active role`.

Assert presence of:

```text
active actor cannot send to itself
same role with a different actor is allowed
```

Expected before implementation:

```text
FAIL because message-tool still says active role cannot send to another actor with the same role id.
```

Update `test_pm_define_scope_teaches_track_boundary_heuristics_without_routing_rules`.

Required change:

- replace expected `use private tasks for active-role work management` with `use private tasks for active actor private work management`.

Expected before implementation:

```text
FAIL because PM define-scope still says active-role work management.
```

### 6.3 Add Failing Message Behavior Guard For Active Role Selector

File: `tests/test_message_env_tool.py`

Add or extend the conversation role-selector test to prove same-role role selection is allowed.

Required scenario:

- active actor: `{"role_id": "dev", "actor_id": "act-dev-conversation-role"}`
- other actor with same role: `{"role_id": "dev", "actor_id": "act-dev-conversation-peer"}`
- create messages between active dev and other dev;
- call `message.conversation` with `args={"role": "dev"}`;
- assert the active-dev to other-dev messages are returned;
- assert unrelated dev-dev messages that do not include the active actor are not returned;
- assert no rejection reason says active role is forbidden.

Expected before implementation:

```text
Likely PASS because runtime behavior is already actor-correct.
```

This test is still required because it protects the exact behavior the cleaned catalog will describe.

Update `test_message_contacts_marks_only_active_actor_row_not_sendable` after message domain text is changed:

- replace exact assertion on `same actor_id` with assertion on the actor self-target meaning;
- assert the explanation does not contain `same role` or `same role id`.

### 6.4 Add Failing Live Guidance / UI / Profile Residue Tests

Use the smallest number of tests that cover the live surfaces without banning legitimate role capability language.

Recommended file: `tests/test_repo_consistency.py`

Add a test named:

```python
def test_actor_identity_live_surfaces_do_not_reintroduce_role_as_actor_residue(self) -> None:
```

Scan only these paths:

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
- `buddyswitch/env-profiles`

Forbid these exact lower-case tokens or case-sensitive UI fragments:

- `role messages`;
- `direct_role_channel`;
- `active_role_inbox`;
- `active-role inbox`;
- `not the active role`;
- `outside the active role`;
- `active role cannot`;
- `same role id`;
- `direct role inbox`;
- `direct role messaging`;
- `active-role tasksnapshot`;
- `active-role taskbox`;
- `current active-role taskbox task`;
- `active-role work management`;
- `role-locked codex instances`;
- `runtime workspace per role`;
- `selectedBuddy`;
- `>Buddy<`;
- `Stored local role instances`;
- `active-role-only`.

Do not scan all of `scripts`, `tests`, or `docs` with these tokens. That would flag valid role authorization and historical context.

Expected before implementation:

```text
FAIL because multiple live surfaces still contain these exact tokens.
```

Update web UI tests:

- `tests/web_management_ui_state.test.js`
  - pass `selectedRole` to `computeCreateEnabled`;
  - no longer use `selectedBuddy`;
- `tests/web_management_ui_contract.test.js`
  - if it checks visible labels, expect `Role`, not `Buddy`;
  - keep `BuddySwitch` brand assertions.

Update env profile tests:

- `tests/test_buddy_env_profiles.py`
  - assert `profile["context_projection"]["skills"] == "role-profile-only"` for every role;
  - assert `active-role-only` does not appear in contract/profile serialized text.

Expected before implementation:

```text
FAIL because profiles and the contract still use active-role-only.
```

## 7. Implementation Phases

### Phase 1: Add Tests First

Modify:

- `tests/test_env_tool_semantic_contract.py`
- `tests/test_runtime_skills.py`
- `tests/test_message_env_tool.py`
- `tests/test_repo_consistency.py`
- `tests/web_management_ui_state.test.js`
- `tests/web_management_ui_contract.test.js` if needed
- `tests/test_buddy_env_profiles.py`

Run focused tests and confirm the new contract tests fail for the expected reason:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
python3 -m pytest tests/test_runtime_skills.py -q
python3 -m pytest tests/test_message_env_tool.py -q
python3 -m pytest tests/test_repo_consistency.py -q
node --test tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
python3 -m pytest tests/test_buddy_env_profiles.py -q
```

Expected result before fixes:

- semantic contract tests fail on message/comment/task catalog residue;
- runtime skill tests fail on message-tool and PM define-scope residue;
- repo consistency test fails on live-surface residue;
- web UI tests fail if they already expect `selectedRole`;
- env profile test fails on `active-role-only`;
- message behavior test for same-role conversation selector should pass or reveal a behavior bug that must be fixed before continuing.

Do not skip the red test check. The value of this task is to convert the previous manual scan into executable constraints.

### Phase 2: Fix Runtime Catalog And Domain Feedback

Modify:

- `scripts/env/tools/message/tool.py`
- `scripts/env/domain/messages.py`
- `scripts/env/tools/comment/tool.py`
- `scripts/env/tools/task/tool.py`

Required message catalog final strings:

- tool title: `Direct Actor Messages`;
- send authority: `message.direct_actor_address_channel`;
- list authority: `message.active_actor_inbox`;
- list description: `List active actor inbox messages.`;
- list visibility: `active actor inbox`;
- list reads: `active actor inbox messages`;
- conversation precondition must not forbid the active role;
- actor id schema descriptions must say `Target runtime actor id.`;
- message send preconditions must distinguish:
  - manifest role validation for `target_actor_address.role_id`;
  - online target actor;
  - target actor differs from active actor.

Required message domain feedback:

- contact row unsendable explanation describes active actor self-target, not same role and not awkward field prose.

Required comment catalog final strings:

- use `direct actor-address inbox` wording for message alternatives.

Required task catalog final strings:

- use `active actor TaskSnapshot`;
- use `active actor taskbox`;
- use `current active actor taskbox task`.

Run:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_message_env_tool.py -q
```

Expected result:

```text
PASS for message behavior and catalog actor-identity contract.
```

### Phase 3: Fix Live Skills, README, Web UI, And Env Profiles

Modify:

- `buddyswitch/skills/shared/message-tool/SKILL.md`
- `buddyswitch/skills/shared/comment-tool/SKILL.md`
- `buddyswitch/skills/pm/define-scope/SKILL.md`
- `README.md`
- `tools/launcher/assets/web-management/index.html`
- `tools/launcher/assets/web-management/app.js`
- `framework/contracts/role-env-profile.json`
- `buddyswitch/env-profiles/design.json`
- `buddyswitch/env-profiles/dev.json`
- `buddyswitch/env-profiles/market.json`
- `buddyswitch/env-profiles/pm.json`
- `buddyswitch/env-profiles/test.json`

Required skill/doc replacements:

- message skill says active actor cannot send to itself and same role with different actor is allowed;
- comment skill says direct actor-address messaging;
- PM define-scope says active actor private work management;
- README says role-configured actor instances and runtime workspace per actor.

Required web UI replacements:

- visible `Buddy` selector label becomes `Role`;
- visible `Buddy` table column becomes `Role`;
- subtitle becomes `Stored local actor instances`;
- JS state name `selectedBuddy` becomes `selectedRole`;
- function contracts and tests use `selectedRole`.

Required profile replacements:

- contract enum value becomes `role-profile-only`;
- all five env profile JSON files use `role-profile-only`;
- tests prove `active-role-only` is absent from live profile files.

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py tests/test_buddy_env_profiles.py -q
node --test tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
python3 scripts/env_profiles.py validate-all
```

Expected result:

```text
PASS for skills, repo consistency, env profiles, and web UI state/contract tests.
```

### Phase 4: Run Explicit Live-Surface Scans

After tests pass, run exact scans against live surfaces.

Scan message and adjacent tool catalogs:

```bash
rg -n -i "role messages|direct_role_channel|active_role_inbox|active-role inbox|not the active role|outside the active role|active role cannot|same role id|direct role inbox|direct role messaging|active-role tasksnapshot|active-role taskbox|current active-role taskbox task" \
  scripts/env/tools/message/tool.py \
  scripts/env/tools/comment/tool.py \
  scripts/env/tools/task/tool.py
```

Expected:

```text
no output
```

Scan live skills and README:

```bash
rg -n -i "active role cannot|same role id|direct role messaging|active-role work management|role-locked codex instances|runtime workspace per role" \
  buddyswitch/skills/shared/message-tool/SKILL.md \
  buddyswitch/skills/shared/comment-tool/SKILL.md \
  buddyswitch/skills/pm/define-scope/SKILL.md \
  README.md
```

Expected:

```text
no output
```

Scan web UI role labels and internal state:

```bash
rg -n "selectedBuddy|>Buddy<|Stored local role instances" \
  tools/launcher/assets/web-management \
  tests/web_management_ui_state.test.js \
  tests/web_management_ui_contract.test.js
```

Expected:

```text
no output
```

Scan env profile enum:

```bash
rg -n "active-role-only" \
  framework/contracts/role-env-profile.json \
  buddyswitch/env-profiles
```

Expected:

```text
no output
```

Run a broad informational scan for remaining active-role wording:

```bash
rg -n "active-role|active role|direct role|same role|role-locked|workspace per role" \
  scripts/env/tools \
  buddyswitch/skills \
  README.md \
  tools/launcher/assets \
  framework/contracts \
  buddyswitch/env-profiles
```

Expected:

- remaining hits are only valid role authorization, role capability, role readability, request queue, track ownership, or historical brand terms;
- any remaining direct message identity, inbox ownership, task ownership, actor private workspace, or UI role selector hit must be fixed before completion.

### Phase 5: Run Focused And Broader Verification

Focused verification:

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

Broader verification:

```bash
python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_context_binding_env_tool.py tests/test_task_env_tool.py tests/test_comment_env_tool.py -q
```

If the broader tests fail due expected wording changes, update tests only when the new expectation is actor-correct and within this memo's scope.

## 8. Required File Change Summary

### Tests

- Modify: `tests/test_env_tool_semantic_contract.py`
  - Add message catalog actor identity contract.
  - Add adjacent comment/task catalog wording contract.
  - Update message semantic snippets to emphasize actor address rather than role-as-participant.

- Modify: `tests/test_runtime_skills.py`
  - Extend shared message skill negative vocabulary.
  - Assert positive actor/self and same-role-different-actor message guidance.
  - Update PM define-scope expected active actor private wording.

- Modify: `tests/test_message_env_tool.py`
  - Add same-active-role conversation role selector behavior test.
  - Update contact unsendable text assertions to avoid locking awkward `same actor_id` prose.

- Modify: `tests/test_repo_consistency.py`
  - Add a scoped live-surface residue scan.
  - Scan exact live files and exact forbidden tokens only.

- Modify: `tests/web_management_ui_state.test.js`
  - Rename test input key from `selectedBuddy` to `selectedRole`.

- Modify: `tests/web_management_ui_contract.test.js`
  - Update UI label expectations if the test covers visible role labels.

- Modify: `tests/test_buddy_env_profiles.py`
  - Assert `context_projection.skills == "role-profile-only"`.
  - Assert `active-role-only` is gone from live profile contract and profile JSON.

### Runtime Catalog And Domain

- Modify: `scripts/env/tools/message/tool.py`
- Modify: `scripts/env/domain/messages.py`
- Modify: `scripts/env/tools/comment/tool.py`
- Modify: `scripts/env/tools/task/tool.py`

### Live Guidance And UI

- Modify: `buddyswitch/skills/shared/message-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/comment-tool/SKILL.md`
- Modify: `buddyswitch/skills/pm/define-scope/SKILL.md`
- Modify: `README.md`
- Modify: `tools/launcher/assets/web-management/index.html`
- Modify: `tools/launcher/assets/web-management/app.js`

### Env Profile Contract

- Modify: `framework/contracts/role-env-profile.json`
- Modify: `buddyswitch/env-profiles/design.json`
- Modify: `buddyswitch/env-profiles/dev.json`
- Modify: `buddyswitch/env-profiles/market.json`
- Modify: `buddyswitch/env-profiles/pm.json`
- Modify: `buddyswitch/env-profiles/test.json`

## 9. One-Task Execution Order

Execute in this exact order:

1. Add tests in Phase 1.
2. Run focused tests and confirm expected failures.
3. Fix runtime catalog and domain feedback in Phase 2.
4. Run message/catalog focused tests.
5. Fix skills, README, web UI, and env profiles in Phase 3.
6. Run skill/repo/profile/UI focused tests.
7. Run exact scans in Phase 4.
8. Run broader verification in Phase 5.
9. Only then report done.

Do not split this into separate PR-sized cleanups during execution. Splitting is what allowed the previous behavior/guidance divergence to survive.

## 10. Definition Of Done

This task is done only when all of these are true:

1. message behavior still rejects same `actor_id` self-send;
2. message behavior still allows same `role_id` with different `actor_id`;
3. `message.conversation` with `role=<active_role>` returns active actor visible same-role conversation rows and rejects only same actor selection;
4. runtime message catalog uses actor-address identity language;
5. runtime message catalog no longer contains role-as-actor direct message terms;
6. comment catalog no longer describes message alternatives as direct role inbox;
7. task catalog no longer describes private task ownership as active-role taskbox ownership;
8. message skill explicitly says same role with a different actor is allowed;
9. PM define-scope skill says active actor private work management;
10. README describes role-configured actor instances and runtime workspace per actor;
11. web management UI uses Role labels and `selectedRole` internal state;
12. env profiles and contract use `role-profile-only`, not `active-role-only`;
13. focused tests pass;
14. web UI node tests pass;
15. `python3 scripts/env_profiles.py validate-all` passes;
16. exact live-surface scans return no forbidden hits;
17. remaining role wording is manually classified as valid role authorization, capability, request queue, track ownership, artifact template allowlist, readable target access, or brand text.

## 11. Completion Report Requirements

The final execution report must include:

- changed files grouped by test/runtime/guidance/UI/profile;
- the red-test evidence from Phase 1;
- the passing focused test commands;
- the passing scan commands;
- any remaining role-wording hits from the broad informational scan and why each is valid;
- any residual risk.

Do not claim completion from code changes alone.

