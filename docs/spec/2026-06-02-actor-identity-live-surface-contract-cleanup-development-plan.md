# Actor Identity Live Surface Contract Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean the remaining live actor/role identity residue so direct messaging and private work are taught as actor-owned while role wording remains only for valid role capability and authorization surfaces.

**Architecture:** Add executable live-surface contracts around runtime catalog, skills, repo guidance, Web UI assets, and env profiles. Then replace the stale strings directly in their source files without compatibility aliases, wrappers, or dual terminology.

**Tech Stack:** Python unittest/pytest, Node built-in test runner, JSON profile contracts, HTML/JS static assets, Markdown runtime skills.

---

## File Responsibility Map

- `tests/test_env_tool_semantic_contract.py`: exported runtime catalog and operation semantics language.
- `tests/test_runtime_skills.py`: source and installed runtime skill guidance.
- `tests/test_message_env_tool.py`: actor message behavior guard for contacts and same-role conversation selector.
- `tests/test_repo_consistency.py`: scoped exact-token live-surface residue scan.
- `tests/web_management_ui_state.test.js`: Web UI pure JS state contracts.
- `tests/web_management_ui_contract.test.js`: Web UI asset labels and forbidden residue.
- `tests/test_buddy_env_profiles.py`: role profile matrix and profile enum contract.
- `scripts/env/tools/message/tool.py`: runtime message catalog, schemas, and action semantics.
- `scripts/env/domain/messages.py`: message validation and contact feedback text.
- `scripts/env/tools/comment/tool.py`: comment catalog alternatives to direct messaging.
- `scripts/env/tools/task/tool.py`: task catalog ownership wording.
- `buddyswitch/skills/shared/message-tool/SKILL.md`: installed message skill guidance.
- `buddyswitch/skills/shared/comment-tool/SKILL.md`: installed comment skill guidance.
- `buddyswitch/skills/pm/define-scope/SKILL.md`: PM private task guidance.
- `README.md`: active workspace guidance.
- `tools/launcher/assets/web-management/index.html`: visible Web UI labels.
- `tools/launcher/assets/web-management/app.js`: Web UI internal state and create request payload.
- `framework/contracts/role-env-profile.json`: profile enum contract.
- `buddyswitch/env-profiles/*.json`: live role capability profile values.

## Execution Rules

- Work only in `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`.
- Do not edit `main`.
- Do not edit runtime state under `buddyswitch/objects/**`.
- Start behavior or contract changes with tests, run them, and record the red failure.
- Do not ban all `active role` wording. Only ban exact role-as-actor residue in scoped live surfaces.
- Avoid broad launcher/browser/app-server tests unless a focused failure forces that path.

## Task 1: Add Runtime Catalog Contract Tests

**Files:**

- Modify: `tests/test_env_tool_semantic_contract.py`

- [ ] Step 1: Add `test_message_catalog_uses_actor_address_identity_language`.

Implementation details:

- Read `catalog.env_tools_description()` and `catalog.operation_semantics()`.
- Assert message title is `Direct Actor Messages`.
- Assert `message.send` authority is `message.direct_actor_address_channel`.
- Assert `message.list` authority is `message.active_actor_inbox`.
- Assert list visibility includes `active actor inbox`.
- Serialize message catalog and operation rows with `json.dumps(..., ensure_ascii=True).lower()`.
- Assert absence of the forbidden message tokens from the test plan.

- [ ] Step 2: Add `test_adjacent_catalog_surfaces_do_not_teach_direct_role_inbox_or_role_taskbox`.

Implementation details:

- Serialize `desc["comment"]` and `desc["task"]`.
- Assert absence of direct role inbox/messaging and active-role taskbox tokens.
- Assert the comment catalog still contains `active-role readability` to prove valid role-readable target wording remains allowed.
- Assert the task catalog still contains `env.tool role-action policy allows this action for the active role`.

- [ ] Step 3: Update `test_adjacent_action_boundaries_are_explained`.

Change:

```python
("message", "send", ("inbox", "role", "comment")),
```

to:

```python
("message", "send", ("inbox", "actor address", "comment")),
```

- [ ] Step 4: Run red check.

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
```

Expected: FAIL on current role-as-actor catalog wording.

## Task 2: Add Skill, Message Behavior, Repo, UI, And Profile Tests

**Files:**

- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_message_env_tool.py`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tests/web_management_ui_contract.test.js`
- Modify: `tests/test_buddy_env_profiles.py`

- [ ] Step 1: Extend message skill tests.

Implementation details:

- In `test_shared_message_skill_prevents_observed_invalid_calls`, check source text and installed skill text.
- For both, assert required positive guidance:
  - `active actor cannot send to itself`
  - `same role with a different actor is allowed`
- For both, assert forbidden message skill tokens from the test plan are absent.

- [ ] Step 2: Update PM define-scope expected text.

Change expected token:

```python
"use private tasks for active-role work management",
```

to:

```python
"use private tasks for active actor private work management",
```

- [ ] Step 3: Strengthen message contacts and conversation tests.

Implementation details:

- In `test_message_contacts_marks_only_active_actor_row_not_sendable`, expect the self row reason to contain `active actor itself` and not contain `same role`.
- Replace the role-selector conversation scenario with same-role active `dev` and peer `dev` messages plus unrelated `dev` messages that must not be returned.

- [ ] Step 4: Add scoped repo consistency scan.

Implementation details:

- Add a test that reads the exact live files/directories from the test plan.
- Compare lower-cased text for lower-case forbidden tokens and raw text for `selectedBuddy`, `>Buddy<`, and `Stored local role instances`.
- Fail with `relative/path: token` rows.

- [ ] Step 5: Update Web UI tests.

Implementation details:

- Change `selectedBuddy` test inputs to `selectedRole`.
- Add asset contract assertions for `Role`, `Stored local actor instances`, no `selectedBuddy`, no `>Buddy<`, and no `Stored local role instances`.

- [ ] Step 6: Update env profile tests.

Implementation details:

- In the profile matrix loop, assert `profile["context_projection"]["skills"] == "role-profile-only"`.
- Add a contract/profile file scan that asserts `active-role-only` is absent.

- [ ] Step 7: Run red checks.

```bash
python3 -m pytest tests/test_runtime_skills.py -q
python3 -m pytest tests/test_message_env_tool.py -q
python3 -m pytest tests/test_repo_consistency.py -q
node --test tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
python3 -m pytest tests/test_buddy_env_profiles.py -q
```

Expected: FAIL on stale live-surface strings except the same-role conversation behavior guard may already pass.

## Task 3: Fix Runtime Catalog And Message Domain Feedback

**Files:**

- Modify: `scripts/env/tools/message/tool.py`
- Modify: `scripts/env/domain/messages.py`
- Modify: `scripts/env/tools/comment/tool.py`
- Modify: `scripts/env/tools/task/tool.py`

- [ ] Step 1: Replace message catalog strings.

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

- [ ] Step 2: Replace message contact feedback.

Required text:

```text
message.send rejects the active actor itself as a target
```

- [ ] Step 3: Replace comment direct role wording.

Required replacements:

| Current | Required |
| --- | --- |
| `direct role inbox messages` | `direct actor-address inbox messages` |
| `direct role inbox communication` | `direct actor-address inbox communication` |
| `direct role inbox history` | `direct actor-address inbox history` |
| `direct role messaging` | `direct actor-address messaging` |

- [ ] Step 4: Replace task taskbox ownership wording.

Required replacements:

| Current | Required |
| --- | --- |
| `active-role TaskSnapshot` | `active actor TaskSnapshot` |
| `active-role taskbox` | `active actor taskbox` |
| `current active-role taskbox task` | `current active actor taskbox task` |

- [ ] Step 5: Run focused catalog/message verification.

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_message_env_tool.py -q
```

Expected: PASS.

## Task 4: Fix Live Skills, README, Web UI, And Env Profiles

**Files:**

- Modify: `buddyswitch/skills/shared/message-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/comment-tool/SKILL.md`
- Modify: `buddyswitch/skills/pm/define-scope/SKILL.md`
- Modify: `README.md`
- Modify: `tools/launcher/assets/web-management/index.html`
- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `framework/contracts/role-env-profile.json`
- Modify: `buddyswitch/env-profiles/design.json`
- Modify: `buddyswitch/env-profiles/dev.json`
- Modify: `buddyswitch/env-profiles/market.json`
- Modify: `buddyswitch/env-profiles/pm.json`
- Modify: `buddyswitch/env-profiles/test.json`

- [ ] Step 1: Replace skill and README strings.

Required replacements:

| File | Current | Required |
| --- | --- | --- |
| `message-tool/SKILL.md` | `Active role cannot send to another actor with the same role id.` | `Active actor cannot send to itself; same role with a different actor is allowed.` |
| `comment-tool/SKILL.md` | `direct role messaging` | `direct actor-address messaging` |
| `define-scope/SKILL.md` | `active-role work management` | `active actor private work management` |
| `README.md` | `role-locked Codex instances` | `role-configured actor instances` |
| `README.md` | `runtime workspace per role` | `runtime workspace per actor` |

- [ ] Step 2: Rename Web UI state and labels.

Required replacements:

| Current | Required |
| --- | --- |
| visible `Buddy` selector label | visible `Role` selector label |
| visible `Buddy` table header | visible `Role` table header |
| `Stored local role instances` | `Stored local actor instances` |
| JS state `selectedBuddy` | JS state `selectedRole` |

Keep `BuddySwitch` brand strings and `role-select` DOM id.

- [ ] Step 3: Replace env profile enum.

Required replacements:

| Current | Required |
| --- | --- |
| `active-role-only` | `role-profile-only` |

Update both `framework/contracts/role-env-profile.json` and all five profile JSON files.

- [ ] Step 4: Run focused guidance/UI/profile verification.

```bash
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py tests/test_buddy_env_profiles.py -q
node --test tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
python3 scripts/env_profiles.py validate-all
```

Expected: PASS.

## Task 5: Run Final Scans And Broader Verification

**Files:**

- No edits expected unless verification reveals a missed live-surface residue.

- [ ] Step 1: Run exact live-surface scans.

```bash
rg -n -i "role messages|direct_role_channel|active_role_inbox|active-role inbox|not the active role|outside the active role|active role cannot|same role id|direct role inbox|direct role messaging|active-role tasksnapshot|active-role taskbox|current active-role taskbox task" \
  scripts/env/tools/message/tool.py \
  scripts/env/tools/comment/tool.py \
  scripts/env/tools/task/tool.py

rg -n -i "active role cannot|same role id|direct role messaging|active-role work management|role-locked codex instances|runtime workspace per role" \
  buddyswitch/skills/shared/message-tool/SKILL.md \
  buddyswitch/skills/shared/comment-tool/SKILL.md \
  buddyswitch/skills/pm/define-scope/SKILL.md \
  README.md

rg -n "selectedBuddy|>Buddy<|Stored local role instances" \
  tools/launcher/assets/web-management \
  tests/web_management_ui_state.test.js \
  tests/web_management_ui_contract.test.js

rg -n "active-role-only" \
  framework/contracts/role-env-profile.json \
  buddyswitch/env-profiles
```

Expected: every exact scan exits with code 1 and no output.

- [ ] Step 2: Run broad informational scan and classify hits.

```bash
rg -n "active-role|active role|direct role|same role|role-locked|workspace per role" \
  scripts/env/tools \
  buddyswitch/skills \
  README.md \
  tools/launcher/assets \
  framework/contracts \
  buddyswitch/env-profiles
```

Expected: remaining hits, if any, are valid role authorization/capability wording, request queue wording, track ownership, artifact template allowlist, readable target access, or brand text.

- [ ] Step 3: Run final focused verification.

```bash
python3 -m pytest \
  tests/test_env_tool_semantic_contract.py \
  tests/test_runtime_skills.py \
  tests/test_message_env_tool.py \
  tests/test_repo_consistency.py \
  tests/test_buddy_env_profiles.py \
  -q

node --test tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js

python3 scripts/env_profiles.py validate-all
```

Expected: PASS.

- [ ] Step 4: Run broader non-launcher verification.

```bash
python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_context_binding_env_tool.py tests/test_task_env_tool.py tests/test_comment_env_tool.py -q
```

Expected: PASS, or fail only on stale wording expectations that are updated to actor-correct requirements within this task scope.

## Self-Review

- Spec coverage: all source memo live surfaces have a test or exact scan.
- Placeholder scan: no forbidden placeholder wording or deferred-action steps are present.
- Type/string consistency: `selectedRole`, `role-profile-only`, `Direct Actor Messages`, `message.direct_actor_address_channel`, and `message.active_actor_inbox` are used consistently across tests and implementation steps.
- Scope control: no broad actor identity rebuild, launcher rewrite, or compatibility layer is part of this plan.
