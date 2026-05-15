# Buddybox Local Workspace Code Implementation Plan

> **For agentic workers:** Implement this plan in `/Users/chen/Dev/buddyswitch/.worktrees/dev2258` on branch `dev2258`. Do not implement from `main`, do not revert unrelated existing dirty changes, and use the shortest verified loop for each phase.

**Goal:** Make `buddybox` the active buddy's private local working directory, backed by `buddyswitch/local/buddybox/<active_buddy>/`, with runtime-visible semantics that prevent cross-buddy read assumptions and expose artifact promotion as the BuddySwitch path when the host decides content must become product-readable.

**Architecture:** `buddybox.desc` is the safe orientation surface for context. `buddybox.list/read/write/delete` are the active-buddy-only data plane. Context, workspace projection, handoff, launcher projection, profiles, console, and guidance stop treating buddybox as shared product content.

**Tech Stack:** Python env tool services and tests, broker-routed `env.tool`, JSON/TOML contracts, shell launcher workspace setup, Codex config generation, JavaScript console normalization.

---

## 1. 任务目标

完成后，BuddySwitch 的 buddybox 表示“当前 active buddy 的私有本地工作目录”：当前 buddy 可以通过 env tool 写入草稿、生成文件、截图、二进制输出、报告或笔记，其他 buddy 不能通过 buddybox list/read/write/delete 看到或操作这些文件。当前核心瓶颈是现有实现把 buddybox 放在 `buddyswitch/content/buddybox` 并投影成 context/workspace/product 数据，导致 host 会把私有文件误当跨 buddy 可读的协作内容；这是最重要的问题，因为它直接影响 artifact、handoff、context 的正确使用边界。

## 2. 需求提取

- `REQ-001`：buddybox 必须被定义为 active buddy 的 private local working directory，不是共享产品对象、协作区、handoff transport、global context section 或权限特例系统。
- `REQ-002`：active storage root 必须切换到 `buddyswitch/local/buddybox/<active_buddy>/`。
- `REQ-003`：active runtime 不再从 `buddyswitch/content/buddybox/<buddy>/` 读取、写入、投影或清理 buddybox 文件。
- `REQ-004`：不迁移、不兼容读取、不自动清理旧 `buddyswitch/content/buddybox/**` 文件；旧文件作为旧 runtime state unmanaged。
- `REQ-005`：新增 `buddybox.desc`，read-only，返回 active buddy 本地 workspace 的语义说明和 compact state summary。
- `REQ-006`：`buddybox.desc` 不返回文件内容，不默认返回完整文件列表。
- `REQ-007`：`buddybox.desc` response 必须包含 active buddy id、logical local root、privacy boundary、available operations、file count、total bytes、latest update timestamp、next-action affordances。
- `REQ-008`：`buddybox.desc` 必须包含语义消息：`This is the active buddy's private local working directory. Other buddies cannot list, read, write, or delete these files. Use artifact when content must become product-readable.` 该消息表达的是边界和可选升级路径，不把 artifact 创建变成每次 buddybox 操作后的唯一后续动作。
- `REQ-009`：`buddybox.list` 只列出 active buddy 私有本地 workspace 中的 file summaries，不返回内容。
- `REQ-010`：`buddybox.list` 的 path filter 缺省表示 active buddy root；给定 filter 时必须留在 active buddy root 内；foreign buddy prefix 必须清晰拒绝。
- `REQ-011`：`buddybox.read` 只能读取 active buddy root 内的单个文件；删除 PM foreign read 特例；返回 UTF-8 text 或 base64 content。
- `REQ-012`：`buddybox.write` 只能创建或替换 active buddy root 内文件；支持 `content` 和 `content_base64`；创建父目录；响应明确 created 或 overwritten。
- `REQ-013`：`buddybox.delete` 只能删除 active buddy root 内单个文件；不做 bulk cleanup、retention、garbage collection；重复删除保持显式幂等并说明是否实际删除。
- `REQ-014`：buddybox success response 必须说明实际 state impact，并明确没有创建或更新 artifact、handoff、task、track、context、evidence 等产品/协作对象。
- `REQ-015`：buddybox rejection response 必须用普通语言解释 private-local boundary，保留 `state_changed`、`durability`、`permission_boundary`、`retryable`、`retry_guidance`、`allowed_next_actions` 或 structured next-action affordances。
- `REQ-016`：runtime-visible buddybox semantics 必须覆盖 what/when/inputs/reads/mutates/success/rejection/privacy/next action。
- `REQ-017`：buddybox semantic metadata 必须出现：`active buddy`、`private`、`local workspace` 或 `local working directory`、`not collaborative`、`not visible to other buddies`、`not product object`、`use artifact for product-readable deliverables`。
- `REQ-018`：semantic wording 不得使用保留旧歧义的表达：只说 `durable output`、只说 `buddy-owned`、泛泛的 `readable scope`、或暗示 read authority 的 `source_ref` wording。
- 语义约束边界：hard rejection 只用于 active-buddy privacy、path safety、无效 payload、以及把 buddybox path/source_ref 当作跨 buddy 可读授权的情况；`use_when`、`do_not_use_when`、`allowed_next_actions` 是 host 决策输入，不是单一路径策略。
- `REQ-019`：`context.get` 和 `context.summarize` 用 `buddybox_desc` 替换 `buddybox_files`。
- `REQ-020`：context 不返回 buddybox file content，不作为 buddybox file browser。
- `REQ-021`：`context.list_sources` 将 buddybox 描述为 active-buddy local workspace 和 tool-backed data plane，source of truth 指向 `buddyswitch/local/buddybox/<active_buddy>/**`。
- `REQ-022`：`decision_surface.context_readiness` 使用 desc-oriented signal，例如 `has_buddybox_workspace`，不再使用 `has_buddybox_files`。
- `REQ-023`：workspace projection、workspace contract、workspace data facade、console normalization 不再包含 top-level `buddybox_files`，不全局扫描所有 buddybox roots。
- `REQ-024`：launcher 不再把整个 buddybox root 作为跨 instance 共享 projection；每个 instance workspace 只暴露 active buddy 的 local buddybox root。
- `REQ-025`：Codex profile sandbox 只把 active buddy buddybox local root 加入 writable paths；其他 buddy 的 buddybox path 不出现在该 workspace 的 writable roots。
- `REQ-026`：env profiles、runtime AGENTS templates、framework contracts、shared skills、active docs 统一描述 buddybox 为 active-buddy private local workspace。
- `REQ-027`：direct filesystem edits to broker-managed state remain prohibited；guidance 禁止绕过 env tool 直接编辑 `buddyswitch/objects/**` 或 `buddyswitch/local/buddybox/**`。
- `REQ-028`：handoff active contract 不再接受、保存、返回或投影 `buddybox_paths`。
- `REQ-029`：buddybox 文件不能作为 target buddy 可消费 payload；当 host 判断内容需要跨 buddy 阅读时，可读内容必须来自 artifact 内容或明确可读的产品/外部引用，buddybox path 本身不授予读取权。
- `REQ-030`：`source_refs.type="buddybox"` 只可作为 owning buddy 的 private provenance，不能作为 cross-buddy read hint。
- `REQ-031`：handoff validate/create 必须拒绝 buddybox source_ref，并提示 buddybox source_ref 是 private provenance、不是读取授权；当 handoff 需要可读内容时，由 host 选择 artifact 内容或其他明确可读的产品/外部引用承载内容。
- `REQ-032`：artifact 中保留 buddybox provenance 时，source_ref 必须有 `private_to_buddy=<active_buddy>` 和 `read_grant=false`；artifact 自身携带 product-readable content。
- `REQ-033`：manifest 中所有 buddy 的 buddybox permission surface 保持一致的 `buddybox.read/write/delete`；没有 PM 或 buddy-type 特例权限。
- `REQ-034`：不改 track/task/artifact/evidence/search 的业务语义；只更新这些路径中的 buddybox 边界 wording、source_refs validation 或 tests。
- `REQ-035`：实施必须在 `.worktrees/dev2258` 内完成，不污染 main worktree。
- `REQ-036`：当前 worktree 已有 memory-removal 相关 dirty changes；实施时不得回滚这些非本任务变更。

## 3. 现状探索摘要

### 关键路径

- `AGENTS.md`：SHARP、testing-bound、direct replacement、no verification no done。
- `README.md`：当前 runtime state 仍提到 `buddyswitch/content/buddybox/<buddy>/**`。
- `docs/memo/2026-05-15-buddybox-local-workspace-semantic-task-memo.md`：本任务需求源。
- `scripts/env_store.py`：当前有 `CONTENT_ROOT`、`BUDDYBOX_CONTENT_DIR = CONTENT_ROOT / "buddybox"`；`ensure_runtime_dirs()` 创建旧 content root；handoff schema 和 source_refs normalization 支持 buddybox paths。
- `scripts/env/services/buddybox.py`：当前 root 指向 `BUDDYBOX_CONTENT_DIR`；write/delete 强制 active prefix，但 read 对 PM 有 foreign exception；list foreign filter 会静默空结果；responses 仍是旧 file-state wording。
- `scripts/env/tools/contracts.py`：buddybox 只有 `list/read/write/delete`；scope 是 `buddy-owned durable output files`；context returns 仍含 `buddybox_files`；handoff payload_fields 仍含 `buddybox_paths`。
- `scripts/env/tools/semantics.py`：buddybox semantics 仍使用 durable/buddy-owned/readable-scope 旧词；side_effects 指向 `buddyswitch/content/buddybox/<buddy>/**`。
- `scripts/env/tools/dispatch.py`：缺少 `buddybox.desc` handler。
- `scripts/env/client.py`：缺少 `buddybox desc` subcommand。
- `scripts/env/services/context.py`：`_buddybox_files()` 扫描旧 content root；context payload 有 `buddybox_files`、`has_buddybox_files`、`buddybox_files` count。
- `scripts/runtime_store/projections.py`：全局扫描旧 buddybox root，返回 top-level `content_root` 和 `buddybox_files`。
- `scripts/workspace_data.py`：暴露 `scan_buddybox_files()` facade。
- `framework/contracts/workspace-projection.json`：包含 `buddybox_files` data source/view shape，handoff shape 包含 `buddybox_paths`。
- `framework/console/app.js`：`emptyWorkspace` 和 `normalizeWorkspaceData()` 包含 `buddybox_files`。
- `scripts/env/services/handoffs.py`：validate/create/list/create row 接受并返回 `buddybox_paths`，success guidance 提示 target buddy consume artifacts/buddybox files。
- `scripts/env/services/source_refs.py`：允许 buddybox source_ref，但没有 private provenance marker 或 handoff-specific rejection。
- `buddyswitch/env-profiles/*.json` 和 `scripts/env_profiles.py`：profile root 指向并校验旧 content path。
- `scripts/runtime_agents.py` 和 `tools/launcher/assets/buddies/*/AGENTS.md`：模板校验和 guidance 仍要求旧 root wording。
- `tools/launcher/workspace.sh`：runtime output paths、projected state paths、local excludes、state skeleton 都使用 `buddyswitch/content/buddybox`。
- `tools/launcher/codex_config.py`：sandbox writable path 来自 profile root，因此当前授予旧 content path。
- `scripts/env_cleanup.py`：`buddybox_files` cleanup category 扫描、删除、重建旧 content buddybox。

### 关键测试

- `tests/test_buddybox_env_tool.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_runtime_tool_feedback.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_handoff_env_tool.py`
- `tests/test_env_store_v2.py`
- `tests/test_artifact_env_tool.py`
- `tests/test_env_layer_end_to_end.py`
- `tests/test_parallel_contracts.py`
- `tests/test_console_app_contract.py`
- `tests/test_buddy_env_profiles.py`
- `tests/test_runtime_agents.py`
- `tests/test_buddy_env_sandbox.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_cleanup_system.py`
- `tests/test_repo_consistency.py`
- `tests/runtime_root_test_helper.py`

### 保留、替换、删除、迁移

- 保留：runless broker method `env.tool`、`ping`、`status`。
- 保留：buddybox `list/read/write/delete` core capability，但统一 active-buddy-only。
- 保留：text and binary base64 support。
- 保留：all buddies have same `buddybox.read/write/delete` permission names.
- 替换：`BUDDYBOX_CONTENT_DIR` active root with `BUDDYBOX_LOCAL_DIR = STATE_ROOT / "buddyswitch" / "local" / "buddybox"`。
- 替换：context `buddybox_files` with `buddybox_desc`。
- 替换：workspace projection global buddybox scan with no buddybox projection.
- 删除：PM foreign read exception。
- 删除：handoff active `buddybox_paths` payload/persist/return/projection。
- 删除：cleanup management of old `buddyswitch/content/buddybox/**`。
- 不迁移：old `buddyswitch/content/buddybox/**` files.
- 不保留双路径：no fallback from local root to old content root.

## 4. 最终目标架构

### 文件结构与职责

- Modify `scripts/env_store.py`
  - Add `LOCAL_ROOT = STATE_ROOT / "buddyswitch" / "local"`.
  - Add `BUDDYBOX_LOCAL_DIR = LOCAL_ROOT / "buddybox"`.
  - Remove active use of `BUDDYBOX_CONTENT_DIR`.
  - `ensure_runtime_dirs()` creates object dirs only; buddybox service creates active local root lazily.
  - `_normalize_source_refs(..., active_buddy=None, allow_buddybox=True)` normalizes buddybox refs as private provenance only when active buddy is known.
  - `validate_handoff_record()` ignores retired `buddybox_paths` in legacy JSON and omits it from normalized output.
  - `create_handoff()` signature removes `buddybox_paths`.

- Modify `scripts/env/services/buddybox.py`
  - Add `BUDDYBOX_PRIVACY_MESSAGE` equal to `REQ-008`.
  - Add `_DESC_FIELDS: set[str] = set()`.
  - Add `buddybox_root_for_buddy(buddy: str) -> Path` returning `env_store.BUDDYBOX_LOCAL_DIR / buddy`.
  - Add `normalize_active_buddybox_path(path, active_buddy)` requiring first segment equal active buddy.
  - Add `normalize_buddybox_prefix(path, active_buddy)` for list filters.
  - Add `_buddybox_state_summary(root)` returning `file_count`, `total_bytes`, `latest_update_at`.
  - Add `build_buddybox_desc(active_buddy)` returning the context-safe description.
  - Add `describe_buddybox_for_active_buddy(args, context)` for `buddybox.desc`.
  - Update `_file_summary()` to include `private_to_buddy` and omit `source_ref`.
  - Update list/read/write/delete to use local root, reject foreign paths, and produce high-signal impact text.
  - For every success response, set `effect_summary` to an action-specific sentence that states whether local buddybox state changed and whether product/collaboration objects changed.
  - For every rejection response, set `why_blocked`, `impact`, `permission_boundary`, `retryable`, `retry_guidance`, and `allowed_next_actions` to explain the private-local boundary and unchanged state. `allowed_next_actions` lists safe affordances the host may choose from; it is not exhaustive and does not require artifact creation unless the rejected operation tried to use buddybox as cross-buddy-readable content.

- Modify `scripts/env/tools/contracts.py`
  - Buddybox scope becomes `active-buddy private local workspace files`.
  - Add `buddybox.desc` action: no payload fields, read-only, `required_permission="buddybox.read"`, returns `["buddybox_desc"]`.
  - Update buddybox preconditions and returns for active-buddy local root.
  - Context `summarize.returns` replaces `buddybox_files` with `buddybox_desc`.
  - Handoff validate/create payload_fields remove `buddybox_paths`.

- Modify `scripts/env/tools/semantics.py`
  - Rewrite buddybox capability/action semantics with required vocabulary in `REQ-017`.
  - Add action row for `desc`.
  - For every buddybox action, fill `plain_description`, `use_when`, `do_not_use_when`, `inputs_explained`, `side_effects`, `risk_hints`, `success_means`, and `common_failures` with action-specific text.
  - Keep semantics descriptive instead of prescriptive: `use_when` and `do_not_use_when` explain fit, `risk_hints` explain boundaries, and next-action text leaves host free to continue local work, inspect files, delete local files, create artifact content, or use another explicitly readable product/external reference according to the task.
  - `inputs_explained` states exact payload meaning:
    - `desc`: no payload fields.
    - `list.path`: optional active buddy local path prefix under `<active_buddy>/`.
    - `list.recursive`: whether to include nested files under the active buddy local root.
    - `list.limit`: positive maximum number of summaries.
    - `read.path`: required active buddy private local file path.
    - `read.encoding`: `auto`, `utf-8`, or `base64`.
    - `write.path`: required active buddy private local write path.
    - `write.content`: UTF-8 text body.
    - `write.content_base64`: base64 binary body.
    - `write.content_type`: optional MIME hint.
    - `delete.path`: required active buddy private local file path.
  - `success_means` states actual product meaning per action:
    - `desc`: returned semantic description and compact local summary only.
    - `list`: returned summaries only; no file content read and no product state changed.
    - `read`: returned one active buddy private local file and no product/collaboration object changed.
    - `write`: created or overwrote one active buddy private local file and did not create artifact/handoff/task/track/context/evidence state.
    - `delete`: deleted one active buddy private local file or confirmed it was absent; no product/collaboration object changed.
  - `common_failures` includes unsupported payload fields, path traversal, absolute path, foreign buddy prefix, missing file, invalid encoding, invalid base64, directory delete, and attempts to treat a buddybox path as cross-buddy readable content.
  - `risk_hints` marks desc/list/read as read-only, write as private-local state mutation, and delete as destructive; no buddybox action is open-world or grants cross-buddy read access.
  - For write/delete, `side_effects.writes=["buddyswitch/local/buddybox/<active_buddy>/**"]`.
  - For desc/list/read, `side_effects.writes=[]`.
  - `does_not_write` includes product objects and cross-buddy collaboration state.
  - Context semantics mention `buddybox_desc`, not file rows.
  - Handoff semantics explain that buddybox paths are not readable payloads; when host decides a handoff needs file content, the readable payload must come from artifact content or another explicit product/external reference.

- Modify `scripts/env/tools/dispatch.py`
  - Add `HANDLERS_BY_TOOL["buddybox"]["desc"] = buddybox_service.describe_buddybox_for_active_buddy`.

- Modify `scripts/env/client.py`
  - Add `buddybox desc` subcommand.
  - `_dispatch_buddybox()` routes desc to `_dispatch_env_tool("buddybox", "desc", {})`.

- Modify `scripts/env/services/context.py`
  - Delete `_buddybox_files()`.
  - Use `buddybox_service.build_buddybox_desc(active_buddy)`.
  - Return `buddybox_desc` in `context.get` and `context.summarize`.
  - Replace `has_buddybox_files` with `has_buddybox_workspace`.
  - `context_sources_desc()["buddybox"]` describes active-buddy private local workspace with source `buddyswitch/local/buddybox/<active_buddy>/**`.

- Modify `scripts/runtime_store/projections.py`
  - Remove buddybox path from `_workspace_uses_projected_state()`.
  - Delete `scan_buddybox_files()`.
  - Remove `buddybox_files` and `content_root` from `build_workspace_projection()`.
  - Remove `buddybox_paths` from `build_handoff_view()`.

- Modify `scripts/workspace_data.py`
  - Delete `scan_buddybox_files()` facade.

- Modify `framework/contracts/workspace-projection.json`
  - Remove `content_root` and `buddybox_files` from top-level key order and field constraints.
  - Remove `buddyswitch/content/buddybox/**/*` from data_sources.
  - Remove `buddybox_paths` from handoff view shape.
  - Delete `buddybox_file` view shape.

- Modify `framework/console/app.js`
  - Remove `content_root` and `buddybox_files` from `emptyWorkspace`.
  - Remove buddybox normalization and any render dependency.

- Modify `scripts/env/services/handoffs.py`
  - Remove `buddybox_paths` from `_VALIDATE_FIELDS` and `_CREATE_FIELDS`.
  - Delete `_normalize_paths()`.
  - Reject `buddybox_paths` as unsupported payload field.
  - Reject handoff `source_refs.type="buddybox"` with `E_SOURCE_REFS`.
  - Remove `buddybox_paths` from normalized payload, `_handoff_row()`, and env_store create call.

- Modify `scripts/env/services/source_refs.py`
  - Add `allow_buddybox` parameter.
  - Enforce active buddy prefix for buddybox provenance.
  - Normalize artifact buddybox provenance to `{"type":"buddybox","path":..., "private_to_buddy": active_buddy, "read_grant": false}`.
  - Preserve `private_to_buddy` and `read_grant` in summaries.

- Modify `scripts/env/services/artifacts.py`
  - Pass active buddy and `allow_buddybox=True` when normalizing source_refs.
  - Keep full-content read claim checks artifact-only.

- Modify `buddyswitch/env-profiles/{market,pm,design,dev,test}.json`
  - Set `buddybox.root` to `buddyswitch/local/buddybox/<buddy>`.

- Modify `scripts/env_profiles.py`
  - Expected root becomes `buddyswitch/local/buddybox/{buddy_id}`.

- Modify `scripts/runtime_agents.py`
  - Require private-local wording, artifact promotion wording, active root wording, and direct-edit prohibition for local buddybox root.

- Modify `tools/launcher/workspace.sh`
  - Remove `buddyswitch/content/buddybox` from runtime output paths, projected state paths, local excludes, skeleton.
  - Add helper `buddyswitch_workspace_install_active_buddybox_root()` creating only `${BUDDYSWITCH_WORKSPACE_DIR}/buddyswitch/local/buddybox/${BUDDYSWITCH_ACTIVE_BUDDY}` linked to shared state active buddy local root.

- Modify `tools/launcher/codex_config.py`
  - Writable root follows profile local root; protected shared roots remain forbidden.

- Modify `tests/runtime_root_test_helper.py`
  - Patch `env_store.LOCAL_ROOT` and `env_store.BUDDYBOX_LOCAL_DIR`.

- Modify `scripts/env_cleanup.py`
  - Remove `buddybox_files` category.
  - Do not scan, delete, or recreate old `buddyswitch/content/buddybox`.
  - Do not add cleanup for `buddyswitch/local/buddybox/**` in this task.

- Modify active docs/guidance:
  - `README.md`
  - `framework/docs/turn-runtime-spec.md`
  - `framework/docs/artifacts-runs-git-policy.md`
  - `framework/docs/browser-cockpit.md`
  - `framework/docs/skill-runtime-shared-rules.md`
  - `framework/docs/interface-spec.md`
  - `framework/docs/architecture-overview.md`
  - `framework/agent-registry.md`
  - `framework/contracts/{market,pm,design,dev,test}.md`
  - `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md`
  - `buddyswitch/skills/dev/implement-task/SKILL.md`
  - `buddyswitch/skills/test/smoke-test/SKILL.md`
  - `buddyswitch/skills/shared/handoff-tool/SKILL.md`

### 核心数据模型

`BuddyboxDesc`:

```json
{
  "active_buddy": "dev",
  "logical_root": "buddyswitch/local/buddybox/dev",
  "privacy_boundary": "active-buddy-private-local-workspace",
  "message": "This is the active buddy's private local working directory. Other buddies cannot list, read, write, or delete these files. Use artifact when content must become product-readable.",
  "available_operations": ["buddybox.desc", "buddybox.list", "buddybox.read", "buddybox.write", "buddybox.delete"],
  "state_summary": {
    "file_count": 0,
    "total_bytes": 0,
    "latest_update_at": null
  },
  "allowed_next_actions": [
    "Use buddybox.list to inspect active buddy private file summaries.",
    "Use buddybox.write for private local drafts or generated files.",
    "When the host decides another buddy must read this content, create an artifact revision or another explicit readable reference that carries the content."
  ]
}
```

`BuddyboxFileSummary`:

```json
{
  "buddy": "dev",
  "path": "dev/reports/notes.md",
  "size_bytes": 42,
  "updated_at": "2026-05-15T12:00:00+08:00",
  "content_type": "text/markdown",
  "private_to_buddy": "dev"
}
```

`BuddyboxSourceRef` for artifact provenance only:

```json
{
  "type": "buddybox",
  "path": "dev/reports/notes.md",
  "private_to_buddy": "dev",
  "read_grant": false
}
```

### 调用流

- `context.get/summarize` -> `context._current_context_sections()` -> `buddybox_service.build_buddybox_desc(active_buddy)` -> no file rows/content.
- `env.tool buddybox.desc` -> router -> dispatch -> `describe_buddybox_for_active_buddy()` -> `BuddyboxDesc`.
- `env.tool buddybox.list` -> active path validation -> local root walk -> summaries only.
- `env.tool buddybox.read` -> active path validation -> local file read -> UTF-8/base64 content -> no product mutation.
- `env.tool buddybox.write` -> active path validation -> atomic local write -> created/overwritten response.
- `env.tool buddybox.delete` -> active path validation -> unlink one file if present -> deleted true/false.
- `artifact.create_revision` with buddybox source_ref -> private provenance marker saved; artifact content remains product-readable payload.
- `handoff.validate/create` with `buddybox_paths` or buddybox source_ref -> structured rejection.

## 5. 分阶段实施计划

### 阶段 1：写出需求边界测试

**目标**

先把 private/local/non-collaborative semantics、active-only access、context desc、projection removal、handoff retirement 固化为 failing tests。

**具体文件变更**

- Modify `tests/test_buddybox_env_tool.py`
- Modify `tests/test_env_tool_semantic_contract.py`
- Modify `tests/test_context_binding_env_tool.py`
- Modify `tests/test_runtime_tool_feedback.py`
- Modify `tests/test_env_tool_response_contract.py`
- Modify `tests/test_parallel_contracts.py`
- Modify `tests/test_handoff_env_tool.py`
- Modify `tests/test_env_store_v2.py`
- Modify `tests/test_artifact_env_tool.py`
- Modify `tests/test_env_layer_end_to_end.py`
- Modify `tests/test_buddy_env_profiles.py`
- Modify `tests/test_runtime_agents.py`
- Modify `tests/test_buddy_env_sandbox.py`
- Modify `tests/test_buddyswitch_launcher.py`
- Modify `tests/test_cleanup_system.py`
- Modify `tests/test_repo_consistency.py`

**详细步骤**

1. Add `BuddyboxEnvToolTests.test_buddybox_desc_returns_private_local_workspace_summary` asserting desc shape, exact privacy message, local root, compact summary, and no content/list rows.
2. Add `BuddyboxEnvToolTests.test_pm_cannot_read_list_write_or_delete_foreign_buddybox_paths` seeding `dev/report.md` under local root and asserting PM gets structured rejections.
3. Add `BuddyboxEnvToolTests.test_old_content_buddybox_root_is_not_active_storage` seeding only old content root and asserting list/read ignore it.
4. Update lifecycle test paths to assert files land under `buddyswitch/local/buddybox/<buddy>` and old content root is untouched.
5. Add list-summary test asserting list rows include no `content`, `content_base64`, or read-grant source_ref.
6. Extend negative path tests for blank, absolute, traversal, foreign prefix, missing content, conflicting content/content_base64, and invalid encoding.
7. Add `EnvToolSemanticContractTests.test_buddybox_semantics_explain_private_local_workspace_boundary`.
8. Add `EnvToolSemanticContractTests.test_buddybox_semantics_reject_old_ambiguous_wording`.
9. Add `ContextBindingEnvToolTests.test_context_uses_buddybox_desc_not_file_projection`.
10. Add `ContextBindingEnvToolTests.test_context_list_sources_describes_buddybox_private_local_workspace`.
11. Update workspace projection contract test to assert exact payload keys without `content_root` and `buddybox_files`.
12. Add console contract assertion that `framework/console/app.js` has no `buddybox_files`.
13. Replace handoff positive buddybox path cases with positives that use artifact content or another explicit readable reference, plus negative `buddybox_paths` / buddybox source_ref cases.
14. Add source_refs tests for active-buddy prefix and private provenance marker.
15. Update profile/sandbox/launcher tests to expect local root.
16. Update cleanup tests to assert old content buddybox is unmanaged.
17. Add repo consistency grep gate for old root, `buddybox_files`, `buddybox_paths`, and vague semantic tokens.

**预期行为变化**

Before implementation, tests fail for missing desc, old storage root, PM read exception, context/projection file rows, handoff buddybox payloads, and vague semantics.

**对应需求编号**

`REQ-001` through `REQ-036`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddybox_env_tool.py tests/test_env_tool_semantic_contract.py tests/test_context_binding_env_tool.py tests/test_handoff_env_tool.py tests/test_parallel_contracts.py tests/test_buddy_env_profiles.py tests/test_cleanup_system.py -q
```

**阶段完成标准**

Failures are limited to the new buddybox contract assertions; no syntax/import errors.

### 阶段 2：替换 storage root 并实现 buddybox.desc 与 active-only data plane

**目标**

把 buddybox data plane 从旧 content root 直接替换为 active buddy local root。

**具体文件变更**

- Modify `scripts/env_store.py`
- Modify `scripts/env/services/buddybox.py`
- Modify `scripts/env/tools/contracts.py`
- Modify `scripts/env/tools/dispatch.py`
- Modify `scripts/env/client.py`
- Modify `tests/runtime_root_test_helper.py`
- Modify `tests/test_buddybox_env_tool.py`
- Modify `tests/test_runtime_tool_feedback.py`
- Modify `tests/test_env_tool_response_contract.py`

**详细步骤**

1. Add `LOCAL_ROOT` and `BUDDYBOX_LOCAL_DIR` in `env_store.py`.
2. Remove buddybox local directory creation from `ensure_runtime_dirs()`.
3. Patch `LOCAL_ROOT` and `BUDDYBOX_LOCAL_DIR` in `RuntimeWorkspaceSandbox`.
4. Replace buddybox service path resolution with `BUDDYBOX_LOCAL_DIR`.
5. Implement `normalize_active_buddybox_path()` and `normalize_buddybox_prefix()`.
6. Implement `_buddybox_state_summary()` and `build_buddybox_desc()`.
7. Implement `describe_buddybox_for_active_buddy()`.
8. Add `desc` to contracts, dispatch, and CLI.
9. Update list/read/write/delete to active-only local root validation.
10. Delete PM read exception.
11. Update success/rejection text and structured state changes.

**预期行为变化**

`buddybox.desc` is callable; writes land under local root; PM cannot access foreign buddybox; old content root is ignored.

**对应需求编号**

`REQ-002` through `REQ-015`, `REQ-033`, `REQ-035`, `REQ-036`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddybox_env_tool.py tests/test_runtime_tool_feedback.py tests/test_env_tool_response_contract.py -q
python3 scripts/env/client.py buddybox desc --help
```

**阶段完成标准**

Focused buddybox tests pass; CLI help exposes `buddybox desc`; `rg -n "BUDDYBOX_CONTENT_DIR|buddyswitch/content/buddybox" scripts/env_store.py scripts/env/services/buddybox.py tests/runtime_root_test_helper.py tests/test_buddybox_env_tool.py` has no active hits.

### 阶段 3：重写 semantics 和 context desc surface

**目标**

让 runtime-visible contracts 和 context payload 告诉 host buddybox 的私有本地边界，并把 artifact/readable reference 呈现为需要跨 buddy 可读时的安全选项。

**具体文件变更**

- Modify `scripts/env/tools/semantics.py`
- Modify `scripts/env/services/context.py`
- Modify `scripts/env/tools/contracts.py`
- Modify `tests/test_env_tool_semantic_contract.py`
- Modify `tests/test_context_binding_env_tool.py`
- Modify `tests/test_env_tool_identity.py`
- Modify `tests/test_run_env_tool.py`
- Modify `tests/test_prepare_runtime_context.py`
- Modify `tests/test_runless_runtime_contract.py`

**详细步骤**

1. Rewrite buddybox capability text with private local workspace semantics.
2. Add buddybox action semantics for `desc`.
3. Ensure every buddybox action row contains required vocabulary from `REQ-017`.
4. Add host decision-space wording: safe next actions are affordances, not exhaustive policy; artifact/readable-reference guidance is conditional on the host needing cross-buddy or product-readable content.
5. Set write/delete side effects to local root only.
6. Set desc/list/read side effects to no writes.
7. Update context semantics to mention `buddybox_desc`.
8. Delete `context._buddybox_files()`.
9. Return `buddybox_desc` in context sections and summary.
10. Replace readiness key with `has_buddybox_workspace`.
10. Update context sources descriptor to local private workspace wording.
11. Update tests expecting `buddybox_files`.

**预期行为变化**

Context exposes buddybox awareness through desc/summary only and never returns file rows or content.

**对应需求编号**

`REQ-001`, `REQ-005` through `REQ-008`, `REQ-016` through `REQ-022`, `REQ-034`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_semantic_contract.py tests/test_context_binding_env_tool.py tests/test_env_tool_identity.py tests/test_run_env_tool.py tests/test_prepare_runtime_context.py tests/test_runless_runtime_contract.py -q
```

**阶段完成标准**

`contracts.semantic_contract_errors()` returns `[]`; context responses include `buddybox_desc` and exclude `buddybox_files`.

### 阶段 4：移除 workspace/product projection 中的 buddybox file rows

**目标**

删除 `/api/workspace` 和 console 中的 global buddybox file projection。

**具体文件变更**

- Modify `scripts/runtime_store/projections.py`
- Modify `scripts/workspace_data.py`
- Modify `framework/contracts/workspace-projection.json`
- Modify `framework/console/app.js`
- Modify `tests/test_parallel_contracts.py`
- Modify `tests/test_console_app_contract.py`
- Modify `tests/test_repo_consistency.py`

**详细步骤**

1. Remove buddybox path from `_workspace_uses_projected_state()`.
2. Delete `scan_buddybox_files()`.
3. Remove buddybox scan from `build_workspace_projection()`.
4. Remove `buddybox_files` and `content_root` from projection payload.
5. Remove `buddybox_paths` from handoff projection row.
6. Delete `workspace_data.scan_buddybox_files()`.
7. Update workspace projection JSON key order, data sources, field constraints, handoff shape, and view shapes.
8. Remove `buddybox_files` from console default data and normalization.
9. Update projection and console tests.

**预期行为变化**

Workspace projection exposes manifest, tracks, tasks, artifacts, handoffs, but no buddybox file rows.

**对应需求编号**

`REQ-023`, `REQ-028`, `REQ-034`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_parallel_contracts.py tests/test_console_app_contract.py tests/test_repo_consistency.py -q
```

**阶段完成标准**

Projection payload key order matches contract; active code has no `buddybox_files`, `scan_buddybox_files`, or `buddybox_file`.

### 阶段 5：修正 handoff 与 source_refs 边界

**目标**

让 handoff 不再把 buddybox 当 cross-buddy payload，同时保留 artifact private provenance。

**具体文件变更**

- Modify `scripts/env/services/handoffs.py`
- Modify `scripts/env/services/source_refs.py`
- Modify `scripts/env/services/artifacts.py`
- Modify `scripts/env_store.py`
- Modify `scripts/env/tools/contracts.py`
- Modify `scripts/env/tools/semantics.py`
- Modify `framework/contracts/workspace-projection.json`
- Modify `tests/test_handoff_env_tool.py`
- Modify `tests/test_env_store_v2.py`
- Modify `tests/test_artifact_env_tool.py`
- Modify `tests/test_env_layer_end_to_end.py`
- Modify `tests/test_memory_removal_contract.py` cases that seed old buddybox handoff paths.

**详细步骤**

1. Remove `buddybox_paths` from handoff validate/create allowed fields.
2. Delete handoff buddybox path normalization.
3. Reject payloads containing `buddybox_paths` with `E_HANDOFF_PAYLOAD`.
4. Reject handoff source_refs of type buddybox with `E_SOURCE_REFS`.
5. Remove `buddybox_paths` from handoff normalized dict and list rows.
6. Remove `buddybox_paths` from `env_store.create_handoff()`.
7. Make legacy handoff records with `buddybox_paths` read without returning that field.
8. Add `allow_buddybox` to source_refs normalizer.
9. Artifact source_refs allow buddybox private provenance with active buddy prefix.
10. Handoff source_refs call normalizer with `allow_buddybox=False`.
11. Update contracts/semantics/tests so handoff rejects buddybox as readable payload while allowing normal artifact/product-reference choices.
12. Update E2E: buddybox private note plus artifact product-readable content plus handoff that carries no buddybox path.

**预期行为变化**

New handoff payloads with buddybox paths or buddybox source_refs are rejected. Artifact source_refs can record private buddybox provenance with `read_grant=false`.

**对应需求编号**

`REQ-028` through `REQ-032`, `REQ-034` through `REQ-036`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_handoff_env_tool.py tests/test_env_store_v2.py tests/test_artifact_env_tool.py tests/test_env_layer_end_to_end.py tests/test_parallel_contracts.py -q
```

**阶段完成标准**

Artifact-only handoffs pass; buddybox handoff payloads fail; artifact buddybox provenance includes `private_to_buddy` and `read_grant=false`.

### 阶段 6：更新 launcher、profiles、sandbox 和 buddy-facing guidance

**目标**

让 product-mode instance 的 filesystem、profile、sandbox 和 guidance 只暴露 active buddy local root。

**具体文件变更**

- Modify `buddyswitch/env-profiles/{market,pm,design,dev,test}.json`
- Modify `scripts/env_profiles.py`
- Modify `scripts/runtime_agents.py`
- Modify `tools/launcher/workspace.sh`
- Modify `tools/launcher/codex_config.py`
- Modify `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md`
- Modify `framework/contracts/{market,pm,design,dev,test}.md`
- Modify active framework docs and skills listed in Section 4
- Modify `tests/test_buddy_env_profiles.py`
- Modify `tests/test_runtime_agents.py`
- Modify `tests/test_buddy_env_sandbox.py`
- Modify `tests/test_buddyswitch_launcher.py`
- Modify `tests/test_repo_consistency.py`

**详细步骤**

1. Update all profile JSON roots to `buddyswitch/local/buddybox/<buddy>`.
2. Update `env_profiles.py` validation.
3. Update `runtime_agents.py` validation for private-local wording.
4. Remove old content buddybox paths from `workspace.sh`.
5. Add active buddy local root install helper in `workspace.sh`.
6. Ensure only active buddy local root is linked in instance workspace.
7. Ensure `codex_config.py` grants write to profile local root only.
8. Update AGENTS templates with private local workspace wording and conditional artifact/readable-reference guidance.
9. Update framework contracts, docs, and listed skills.
10. Run profile and runtime agent validators.

**预期行为变化**

Launcher-managed workspaces expose only active buddy local buddybox root; guidance no longer teaches shared content semantics.

**对应需求编号**

`REQ-001` through `REQ-004`, `REQ-024` through `REQ-027`, `REQ-033`, `REQ-035`, `REQ-036`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddy_env_profiles.py tests/test_runtime_agents.py tests/test_buddy_env_sandbox.py tests/test_buddyswitch_launcher.py tests/test_repo_consistency.py -q
python3 scripts/env_profiles.py validate-all
python3 scripts/runtime_agents.py validate-all
```

**阶段完成标准**

Generated launcher config grants write access to `buddyswitch/local/buddybox/<active_buddy>` only; active docs no longer contain old content buddybox path.

### 阶段 7：清理旧 residues 并跑完整验证

**目标**

确认 old buddybox-as-product-content surface 从 active code/tests/docs 消失，remaining runless product paths 不回归。

**具体文件变更**

- Modify `scripts/env_cleanup.py`
- Modify `tests/test_cleanup_system.py`
- Modify `tests/test_repo_consistency.py`
- Modify any active file named by the final grep gate.

**详细步骤**

1. Remove `buddybox_files` from cleanup categories.
2. Remove cleanup plan additions for old content buddybox dirs.
3. Remove skeleton recreation of old content buddybox.
4. Do not add cleanup for local buddybox.
5. Update cleanup tests.
6. Run focused suites from prior phases.
7. Run final grep gate.
8. Run full tests.

**预期行为变化**

Cleanup no longer manages old buddybox content. No active code/docs/tests mention retired buddybox projection tokens.

**对应需求编号**

`REQ-003`, `REQ-004`, `REQ-023`, `REQ-028`, `REQ-035`, `REQ-036`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py tests/test_repo_consistency.py -q
rg -n "BUDDYBOX_CONTENT_DIR|buddyswitch/content/buddybox|buddybox_files|buddybox_paths|durable buddy-owned|readable buddybox scope" README.md AGENTS.md scripts framework buddyswitch tools tests -g '!docs/memo/**' -g '!docs/spec/**'
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests -q
```

**阶段完成标准**

Focused and full tests pass; grep gate has no active hits.

## 6. 迁移 / 删除策略

- Remove active runtime use of `buddyswitch/content/buddybox/**`.
- Do not migrate, copy, archive, delete, index, or clean old `buddyswitch/content/buddybox/**` files.
- Remove active `BUDDYBOX_CONTENT_DIR`; use `BUDDYBOX_LOCAL_DIR`.
- Remove global `buddybox_files` projection and console normalization.
- Remove `buddybox_paths` from handoff active payloads and new persisted handoff shape.
- Legacy handoff JSON with `buddybox_paths` is read by omitting that retired field so old records do not crash context/projection reads.
- Keep buddybox source_refs only as artifact private provenance with `private_to_buddy` and `read_grant=false`.
- Do not add PM override, buddy-type-specific permission branches, old-root compatibility, or shared buddybox projection.

## 7. 完成定义

The task is complete only when:

- `buddybox.desc` exists in registry, dispatch and CLI.
- `buddybox.desc` returns the exact privacy message, active buddy id, local root, operations, state summary and next actions.
- `buddybox.list/read/write/delete` operate only under `buddyswitch/local/buddybox/<active_buddy>/`.
- PM and every other buddy are rejected when addressing another buddy's buddybox path.
- Old `buddyswitch/content/buddybox/**` is not read, written, projected or cleaned.
- `context.get` and `context.summarize` expose `buddybox_desc`, not `buddybox_files`.
- Workspace projection and console do not include buddybox file rows.
- Handoff validate/create rejects `buddybox_paths` and buddybox source_refs; handoff rows/projection omit `buddybox_paths`.
- Artifact buddybox source_refs are private provenance with `private_to_buddy` and `read_grant=false`.
- Profiles, launcher sandbox, AGENTS templates, framework docs and active skills describe buddybox as private local workspace.
- The final verification commands pass:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddybox_env_tool.py tests/test_env_tool_semantic_contract.py tests/test_context_binding_env_tool.py tests/test_runtime_tool_feedback.py tests/test_handoff_env_tool.py tests/test_parallel_contracts.py tests/test_buddy_env_profiles.py tests/test_runtime_agents.py tests/test_buddy_env_sandbox.py tests/test_buddyswitch_launcher.py tests/test_cleanup_system.py tests/test_repo_consistency.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests -q
python3 scripts/env_profiles.py validate-all
python3 scripts/runtime_agents.py validate-all
rg -n "BUDDYBOX_CONTENT_DIR|buddyswitch/content/buddybox|buddybox_files|buddybox_paths|durable buddy-owned|readable buddybox scope" README.md AGENTS.md scripts framework buddyswitch tools tests -g '!docs/memo/**' -g '!docs/spec/**'
```
