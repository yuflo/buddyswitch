# Message Tool Skill Clean Removal Plan

Date: 2026-07-07

## Task Goal

彻底清除 `buddyswitch/skills/shared/message-tool/` 这个 shared skill 以及由该 skill 产生的 manifest、runtime skill materialization、测试断言和活跃引用残留。

本任务只删除 `message-tool` skill 这个非权威指导层，不改基础 IM product tool 本身。

目标完成后的清晰结构是：

```text
actor
  -> native message product tool: message.contacts/send/get/mark/list/conversation
  -> tool schema / role permission / runtime implementation
  -> Central IM service and repos
```

不再存在：

```text
actor
  -> shared message-tool skill prose guidance
  -> native message product tool
```

## Boundary

### In Scope

- 删除 `buddyswitch/skills/shared/message-tool/`。
- 从 `buddyswitch/manifest.toml` 删除 `[[skills]] id = "message-tool"`。
- 从所有 role `skills` 列表删除 `"message-tool"`。
- 更新 runtime skill 安装、manifest、repo consistency 相关测试。
- 增加或调整 residue 测试，确保 `message-tool` 不再回到 live surfaces。
- 保留并验证基础 message product tool 行为和权限仍然正常。

### Out Of Scope

- 不修改 `scripts/env/tools/message/` 的 action schema、实现、语义。
- 不修改 `scripts/env/tool_runtime/im_client.py`。
- 不修改 `scripts/env/services/messages.py`。
- 不修改 `tools/launcher/task_sys_runtime.py` 的 side/parent frame message 能力。
- 不修改 `buddyswitch/skills/shared/task-management/`，除非测试暴露它直接引用了 `message-tool` skill id。
- 不重命名 `message.*` product tool。
- 不清理历史 memo、历史 spec、commit history。历史文档是证据，不是 live residue。

## Bitter Lessons Applied

- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`: skill 应该承载重复业务 workflow，不应该复制 tool schema 或弥补 tool contract。`message-tool` 当前只是 message product tool 的软提示，权威信息已经在 tool catalog、schema、role auth、runtime response。
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`: 删除语义层时必须同时清掉 live surfaces，并用 scoped scan 验收。行为测试和 surface scan 不能互相替代。
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`: IM 是 built-in product capability，product tool 是 projection；不能让一个 shared skill prose layer 成为 IM 语义入口。
- `docs/bitter/2026-07-07-guarded-residue-boundary-principles.md`: 不保留 retired structure guard 或兼容双轨。删除 `message-tool` 后不新增 replacement wrapper skill。
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`: 这是一个 shared skill surface 的清理任务，不和基础 message product tool 行为改动混在同一 changeset。

## Current Code Findings

### Direct `message-tool` live references

- `buddyswitch/skills/shared/message-tool/SKILL.md`
- `buddyswitch/manifest.toml`
  - skill row: `id = "message-tool"`
  - role skills: `market`, `pm`, `design`, `dev`, `test`
- `tests/test_runtime_skills.py`
  - `SHARED_TOOL_SKILLS["message"]`
  - `SHARED_RUNTIME_TOOL_SKILLS`
  - role shared-skill assertions
  - message skill content assertions
  - shared skill no-schema/no-action-catalog assertions
- `tests/test_env_manifest_v2.py`
  - `test_all_roles_have_message_and_track_tools`
- `tests/test_repo_consistency.py`
  - live surface scan includes `buddyswitch/skills/shared/message-tool/SKILL.md`
  - communication identity scan includes `buddyswitch/skills/shared/message-tool`
- `tests/test_buddyswitch_launcher.py`
  - no direct `message-tool` literal, but runtime skill materialization follows manifest role skill lists and must be rerun after the manifest removal.

### Not `message-tool` skill dependencies

These mention "message tool(s)" as the product tool concept, not the deleted skill id:

- `tools/launcher/task_sys_runtime.py`
- `buddyswitch/skills/shared/task-management/SKILL.md`
- `scripts/env/tools/message/_impl.py`
- `tests/test_message_tool_im_client.py`

Do not delete or rewrite these solely because they contain the words "message tool".

## Implementation Path

### Phase 1: Lock The Removal Contract

Modify tests first so the desired state is explicit.

1. In `tests/test_runtime_skills.py`, add a focused assertion that `message-tool` is retired:
   - no manifest skill row with `id == "message-tool"`;
   - `buddyswitch/skills/shared/message-tool` does not exist;
   - no role includes `"message-tool"`;
   - runtime skill installation for each role does not install `message-tool`.
2. In `tests/test_env_manifest_v2.py`, replace the current "message and track tools as skills" expectation:
   - keep `track-tool` as a shared skill expectation;
   - remove `message-tool` from skill expectations because message is now a product tool, not a skill.
3. In `tests/test_role_action_auth.py`, strengthen the existing message permission coverage if needed:
   - every manifest role can use `message.contacts`, `message.send`, `message.get`, `message.mark`, `message.list`, and `message.conversation` through role-action policy.
   - This proves direct actor message capability did not depend on the removed skill.

Expected red state before implementation: tests fail because manifest and skill directory still contain `message-tool`.

### Phase 2: Delete The Skill Surface

1. Delete `buddyswitch/skills/shared/message-tool/`.
2. Remove the `message-tool` skill row from `buddyswitch/manifest.toml`.
3. Remove `"message-tool"` from every role skill list in `buddyswitch/manifest.toml`.
4. Do not add a replacement shared skill.
5. Do not add compatibility aliases such as `"im-tool"`, `"central-im-tool"`, or `"message-product-tool"`.

This is a clean removal, not a rename.

### Phase 3: Clean Test Expectations

Update tests that previously treated `message-tool` as a required runtime skill.

1. `tests/test_runtime_skills.py`
   - Remove `"message"` from `SHARED_TOOL_SKILLS`.
   - Remove `"message-tool"` from `SHARED_RUNTIME_TOOL_SKILLS`.
   - Update `test_each_role_keeps_shared_runtime_tools_without_handoff` required set to `track-tool`, `artifact-tool`, `task-management`.
   - Remove `test_shared_message_skill_prevents_observed_invalid_calls`; its valid contract checks already belong to message tool schema/semantic tests.
   - Update `test_shared_tool_skills_do_not_embed_payload_or_return_schema_blocks` to check only remaining relevant shared tool skill files.
   - Update `test_message_track_shared_tool_skills_stay_atomic`; either rename to track/shared skill only or remove the message half.
   - Update `test_shared_tool_skills_do_not_duplicate_runtime_action_catalogs` to remove the message entry.
2. `tests/test_repo_consistency.py`
   - Remove `buddyswitch/skills/shared/message-tool/SKILL.md` from actor identity live surface scans.
   - Remove `buddyswitch/skills/shared/message-tool` from communication identity high-signal scan paths.
   - Add or keep a targeted no-residue assertion for the retired skill id/path.
   - If a test must name the retired id/path, construct it from split string fragments so the exact residue scan below still has no direct `message-tool` or `buddyswitch/skills/shared/message-tool` hits in live surfaces.
3. `tests/test_env_manifest_v2.py`
   - Rename the old test so it no longer claims message is a skill.
   - Assert only actual skill requirements in manifest.

Do not weaken tests that protect the actual message product tool.

### Phase 4: Verify Message Product Tool Is Unchanged

Run focused product-tool tests after deletion:

```bash
python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_message_tool_im_client.py -q
```

These prove:

- `message.send` still exposes target identity and reply wrapper semantics;
- `message.contacts/get/mark/list/conversation` still have schema and semantic coverage;
- actor tool projection still delegates to the IM client path;
- direct send and reply send behavior still use the IM product implementation.

Run permission and context tests:

```bash
python3 -m pytest tests/test_role_action_auth.py tests/test_context_binding_env_tool.py -q
```

These prove:

- message actions are still available through role-action policy;
- context summary still points actors to `message.list` and `message.conversation` as source of truth.

### Phase 5: Verify Runtime Skill Materialization

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py tests/test_env_manifest_v2.py -q
```

Run launcher skill materialization coverage:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_role -q
```

These prove:

- runtime workspaces no longer install `message-tool`;
- all role skill directories still materialize from manifest correctly;
- remaining shared skills still install.

### Phase 6: Residue Scan

Run a scoped live-surface scan:

```bash
rg -n "message-tool|buddyswitch/skills/shared/message-tool" \
  buddyswitch tools scripts tests framework README.md
```

Expected: no output.

Do not fail the task on generic phrases like "message tool", "message tools", or `message__send`; those refer to the live IM product tool and remain valid.

If a negative test intentionally checks the retired id/path, it must avoid embedding the exact retired literal so this scan remains a clean no-hit proof.

## Critical Questions And Decisions

### Should Task Sys message rules change?

No. Task Sys renders its own side/parent message capabilities in `tools/launcher/task_sys_runtime.py`, and `task-management` independently documents Task Sys frame handling. Neither depends on the deleted `message-tool` skill id/path.

### Should actor get a replacement shared IM skill?

No. That would create a new guidance layer with the same drift risk. The direct source of truth is the native message product tool catalog and runtime feedback.

### Should role AGENTS get new message prose?

No for this task. Current AGENTS already tells actors to prefer native BuddySwitch env MCP tools and inspect `context.get.tool_catalog` when exact schema is needed. Adding new message-specific prose would recreate the removed layer in another file.

### Should historical docs be edited?

No. Historical memo/spec content is not a live surface. Residue cleanup should target current runtime-visible surfaces and tests.

### Should generic "message tool" wording be removed?

No. The target is the retired skill id/path `message-tool`, not the live product concept "message tool".

## Definition Of Done

- `buddyswitch/skills/shared/message-tool/` no longer exists.
- `buddyswitch/manifest.toml` has no `message-tool` skill row and no role includes it.
- Runtime skill materialization does not install `message-tool` for any role.
- Tests no longer require or read `message-tool/SKILL.md`.
- A scoped live-surface scan finds no `message-tool` or `buddyswitch/skills/shared/message-tool` references.
- Message product tool tests still pass.
- Role auth still exposes message actions directly through runtime permissions.
- No replacement skill, alias, compatibility wrapper, or dual-track guidance is introduced.

## Recommended Verification Command Set

```bash
python3 -m pytest \
  tests/test_runtime_skills.py \
  tests/test_env_manifest_v2.py \
  tests/test_repo_consistency.py \
  tests/test_role_action_auth.py \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_message_tool_im_client.py \
  tests/test_context_binding_env_tool.py \
  -q
```

```bash
python3 -m pytest \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_role \
  -q
```

```bash
rg -n "message-tool|buddyswitch/skills/shared/message-tool" \
  buddyswitch tools scripts tests framework README.md
```
