# Memory Removal Code Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan phase-by-phase. This plan is scoped to `/Users/chen/Dev/buddyswitch/.worktrees/dev2258` on branch `dev2258`.

**Goal:** Remove BuddySwitch `memory` completely from the active runtime, tool contract, launcher projection, buddy-facing guidance, docs, and tests for this iteration.

**Architecture:** The final runtime keeps one runless product-state path: `task`, `track`, `artifact`, `handoff`, `buddybox`, `context`, `evidence`, and `search`. Old `buddyswitch/objects/memories/*.json` files are not migrated, deleted, projected, read, validated, or used.

**Tech Stack:** Python runtime services and tests, TOML manifest, shell launcher scripts, JSON framework contracts, JavaScript console normalization.

---

## 1. 任务目标

完成后，BuddySwitch 不再把 `memory` 暴露为 env tool、权限、source ref、handoff ref、evidence target、context section、workspace projection 或 buddy-facing 能力。当前核心瓶颈是本地 buddy-level memory 模型尚未设计，但现有运行时已经把 memory 当作 durable product state 扩散到多层 contract；继续保留会让 buddies 和 tests 依赖一个产品语义未成立的状态模型，阻塞清晰的 runless 主路径。

## 2. 需求提取

- `REQ-001`：从 BuddySwitch 当前迭代中完整移除 `memory` 产品能力；这不是本地 memory redesign。
- `REQ-002`：删除 `memory` env tool 和全部 memory actions：`memory.list`、`memory.get`、`memory.write`、`memory.update`、`memory.archive`。
- `REQ-003`：`scripts/env/tools/contracts.py::TOOL_REGISTRY`、`supported_tools()`、`env_tools_description()`、`operation_semantics()` 不包含 `memory`。
- `REQ-004`：`scripts/env/tools/router.py` 和 `scripts/env/tools/dispatch.py` 不把 `memory` 作为 supported tool；`env.tool` payload `{"tool": "memory", ...}` 返回 unsupported tool feedback 且不写状态。
- `REQ-005`：`python3 scripts/turn_runtime.py status` 输出的 `env_tools` 不包含 `memory`。
- `REQ-006`：`python3 scripts/env/client.py --help` 不列出 `memory` resource；`python3 scripts/env/client.py memory ...` 由 argparse 作为 invalid choice 拒绝，不调用 broker，不写状态。
- `REQ-007`：`buddyswitch/manifest.toml` 和 profile-facing capability surface 不包含 `memory.read`、`memory.write`、`memory.update`、`memory.archive`。
- `REQ-008`：所有 buddy runtime `AGENTS.md` tool list 包含 `task`、`track`、`artifact`、`handoff`、`buddybox`、`context`、`evidence`、`search`，不包含 `memory`。
- `REQ-009`：Market buddy guidance 中 evidence target 只允许 artifact，不再写 artifact-or-memory；final output guidance 不再要求 summarize memories。
- `REQ-010`：`context.get` 和 `context.summarize` 不接受 `memory_kind`。
- `REQ-011`：context responses 不包含 `memory_summaries`、`has_memories`、`memories` count。
- `REQ-012`：`context.list_sources` 不包含 `memories` source descriptor。
- `REQ-013`：workspace projection 不包含 top-level `memories`，不包含 memory view shape，不读取 `env_store.list_memories()`。
- `REQ-014`：console app 不 normalize、render 或 depend on `memories`。
- `REQ-015`：runtime directory setup 不创建 `buddyswitch/objects/memories`。
- `REQ-016`：launcher workspace projection、state skeleton、local excludes 不创建、不 symlink、不 exclude `buddyswitch/objects/memories`。
- `REQ-017`：现有旧 `buddyswitch/objects/memories/*.json` 文件被 active runtime 忽略；本任务不新增 cleanup、migration、archive 或 delete process。
- `REQ-018`：`source_refs` 不接受 `{"type": "memory", ...}`；store-level normalizer 和 service-level normalizer 都拒绝该 type。
- `REQ-019`：full-summary read claim checks 不读取 memory，不对 memory 执行 scope validation。
- `REQ-020`：Evidence targets are artifacts only；`target_type="memory"` 返回 structured rejection，不创建 evidence token。
- `REQ-021`：`scripts/browser_evidence.py` 只接受 `--target-type artifact`。
- `REQ-022`：handoff validate/create payload 不接受 `memory_ids`。
- `REQ-023`：新创建和新保存的 handoff record 不包含 `memory_ids` 字段。
- `REQ-024`：旧 handoff JSON 中若存在 `memory_ids`，active read path 不验证、不返回、不投影该字段；该字段被当作 retired field 忽略。
- `REQ-025`：删除 `scripts/env/services/memories.py` 及 memory-specific service tests。
- `REQ-026`：删除 store-level memory constants、validators、file helpers、list/get/save/create/update functions。
- `REQ-027`：删除 env semantic metadata 中的 memory capability/action rows，并更新 artifact/handoff/buddybox/context/evidence 文案中对 memory 的引用。
- `REQ-028`：active docs/contracts 更新为 memory removed；historical `docs/memo/**` 和旧 `docs/spec/2026-05-14-*` 可作为历史记录保留。
- `REQ-029`：Buddybox remains in scope；不改变 buddybox local-vs-shared semantics，只删除提到 memory 的引用。
- `REQ-030`：不重构 task、track、artifact、handoff、buddybox 行为；只移除这些路径中对 memory 的引用和字段。
- `REQ-031`：cleanup system 不再发现、计划、删除或重建 memory object paths；old memory files 保持 unmanaged。
- `REQ-032`：tests 不再期待 memory lifecycle、memory projection、memory evidence、memory handoff refs 或 memory context summaries。
- `REQ-033`：最终 grep gate 对 active code/tests/docs 不再命中 `memory` runtime surface；历史 memo/spec 可排除。
- `REQ-034`：实施必须在 `.worktrees/dev2258` 内完成，不能污染 main worktree。

## 3. 现状探索摘要

### 关键目录、文件、测试、运行命令

- `AGENTS.md`：SHARP、testing-bound、direct replacement over wrappers、no verification no done。
- `README.md`：当前 product runtime loop 仍列出 `memory_id`、`memory.*`、`buddyswitch/objects/memories/*.json`。
- `docs/memo/2026-05-15-memory-removal-task-memo.md`：本任务源需求。
- `scripts/env_store.py`：定义 `MEMORY_OBJECTS_DIR`、`VALID_MEMORY_STATUS`、`VALID_MEMORY_KINDS`、`memory_file()`、`validate_memory()`、`list_memories()`、`get_memory()`、`save_memory()`、`create_memory()`、`update_memory()`；handoff validation/create 包含 `memory_ids`；internal `_normalize_source_refs()` 接受 `memory`。
- `scripts/env/services/memories.py`：完整 memory env tool service，需要删除。
- `scripts/env/tools/contracts.py`：`TOOL_REGISTRY` 包含 `memory` tool row；handoff payload fields 包含 `memory_ids`；context payload/returns 包含 `memory_kind`、`memory_summaries`；evidence preconditions 包含 artifact or memory。
- `scripts/env/tools/semantics.py`：包含 memory capability/action semantics；artifact、handoff、buddybox、context、evidence 文案引用 memory。
- `scripts/env/tools/dispatch.py`：imports `env.services.memories as memory_service`，`HANDLERS_BY_TOOL["memory"]` 注册 memory actions。
- `scripts/env/tools/router.py`：registry-backed supported tools 会随 `contracts.py` 改动。
- `scripts/env/client.py`：argparse 注册 `memory` resource；`context get` 支持 `--memory-kind`；`_dispatch_memory()` 和 main branch 调用 broker。
- `scripts/env/services/context.py`：`_GET_FIELDS` 包含 `memory_kind`；`_memory_summary()`、`env_store.list_memories()`、`visible_memories`、`memory_summaries`、`has_memories`、`memories` count、`context_sources_desc()["memories"]`。
- `scripts/env/services/handoffs.py`：`_VALIDATE_FIELDS`、`_CREATE_FIELDS`、`_validate_payload()`、`_handoff_row()`、`create_handoff_for_active_buddy()` 包含 `memory_ids` 和 `env_store.get_memory()`。
- `scripts/env/services/source_refs.py`：`_ALLOWED_TYPES` 包含 `memory`；`normalize_source_refs()` full-summary read claim 读取 `env_store.get_memory()`。
- `scripts/env/services/evidence.py`：`_resolve_target()` 支持 `target_type == "memory"`；rejection/follow-up 文案写 artifact or memory。
- `scripts/browser_evidence.py`：CLI choices 为 `["artifact", "memory"]`。
- `scripts/runtime_store/projections.py`：`_workspace_uses_projected_state()` 检查 memory symlink；`memory_object_path()`、`build_memory_view()`、`env_store.list_memories()`、payload top-level `memories`；handoff view 包含 `memory_ids`。
- `scripts/workspace_data.py`：compat facade 暴露 `build_memory_view()`。
- `framework/contracts/workspace-projection.json`：top-level `memories`、memory data source、handoff `memory_ids`、`view_shapes.memory`。
- `framework/console/app.js`：`emptyWorkspace.memories` 和 `normalizeWorkspaceData().memories`。
- `scripts/env_manifest.py`：permission object allow-list 包含 `memory`；authority note 写 `track/task/artifact/handoff/memory/buddybox`。
- `buddyswitch/manifest.toml`：每个 buddy permissions 包含 `memory.*`。
- `buddyswitch/env-profiles/*.json`：当前未直接包含 memory permission drift，但实施时需要运行 grep 确认。
- `tools/launcher/assets/buddies/*/AGENTS.md`：tool list 包含 `memory`；Market evidence/final output 文案包含 memory。
- `tools/launcher/workspace.sh`：runtime output paths、projected state paths、git excludes、state skeleton 包含 `buddyswitch/objects/memories`。
- `scripts/env_cleanup.py`：`memory_objects` category、`discover_memory_objects()`、`add_indexed_memory()`、plan fields、skeleton dirs、all-data delete logic。
- `tests/test_memory_env_tool.py`：memory lifecycle integration tests，需要删除。
- `tests/runtime_root_test_helper.py`：patches `env_store.MEMORY_OBJECTS_DIR`。
- Memory-dependent tests to update: `tests/test_env_tool_response_contract.py`、`tests/test_repo_consistency.py`、`tests/test_evidence_env_tool.py`、`tests/test_handoff_env_tool.py`、`tests/test_run_env_tool.py`、`tests/test_cleanup_system.py`、`tests/test_env_layer_end_to_end.py`、`tests/test_parallel_contracts.py`、`tests/test_host_decision_surface_product_mode.py`、`tests/test_runtime_tool_feedback.py`、`tests/test_runless_runtime_contract.py`、`tests/test_prepare_runtime_context.py`、`tests/test_context_binding_env_tool.py`、`tests/test_env_tool_semantic_contract.py`、`tests/test_buddyswitch_launcher.py`、`tests/test_env_manifest_v2.py`、`tests/test_env_tool_identity.py`、`tests/test_market_browser_evidence.py`。

Exploration commands already used and useful during implementation:

```bash
pwd
git branch --show-current
git status --short
rg -n "memory|memories|memory_ids|memory_kind|MEMORY_|create_memory|get_memory|list_memories|update_memory|memory\\." scripts framework buddyswitch tools tests README.md projects/app/README.md docs -g '!docs/memo/2026-05-15-memory-removal-task-memo.md'
rg -n "def |class |MEMORY|memory|memories|source_refs|memory_ids|target_type" scripts/env_store.py scripts/env/services scripts/env/tools scripts/runtime_store/projections.py scripts/workspace_data.py scripts/env_manifest.py scripts/turn_runtime.py tools/launcher/workspace.sh tools/launcher/codex_config.py framework/console/app.js buddyswitch/manifest.toml
```

### 保留、替换、删除、迁移

- 保留：runless broker method `env.tool`、`ping`、`status`。
- 保留：active tool families `task`、`track`、`artifact`、`handoff`、`buddybox`、`context`、`evidence`、`search`。
- 保留：existing response helpers `scripts/env/tools/responses.py` 和 structured success/rejection shape。
- 保留：artifact、task、track、handoff、buddybox ownership enforcement，只移除 memory-specific references。
- 保留：buddybox path validation and source_refs support for `buddybox`、`artifact`、`track`、`task`、`handoff`、`external`、`note`。
- 替换：evidence target model 从 `artifact|memory` 改为 artifact-only。
- 替换：handoff object shape 从 `artifact_ids + memory_ids + buddybox_paths + source_refs` 改为 `artifact_ids + buddybox_paths + source_refs`。
- 替换：workspace projection top-level key order 和 contract 从 including `memories` 改为 excluding `memories`。
- 删除：`scripts/env/services/memories.py`。
- 删除：memory tool registry、handler map、CLI parser/dispatch branch、semantic metadata。
- 删除：store-level memory directory constant, validators, readers, writers。
- 删除：cleanup memory discovery/delete/skeleton behavior。
- 不迁移：old `buddyswitch/objects/memories/*.json` data。
- 不保留双路径：no `legacy_memory_*`, no compatibility memory tool, no hidden memory source ref support。

## 4. 最终目标架构

### 最终文件结构和职责

- Modify `scripts/env/tools/contracts.py`
  - `TOOL_REGISTRY` contains exactly `task`, `track`, `artifact`, `handoff`, `buddybox`, `context`, `evidence`, `search`.
  - Handoff action `payload_fields` remove `memory_ids`.
  - Context `get.payload_fields` remove `memory_kind`.
  - Context `summarize.returns` remove `memory_summaries`.
  - Evidence preconditions and inputs describe artifact targets only.

- Modify `scripts/env/tools/semantics.py`
  - Remove `_CAPABILITIES["memory"]`.
  - Remove memory rows from `_action_rows()`.
  - Update task/artifact/handoff/buddybox/context/evidence descriptions so no active semantic row recommends memory.
  - Keep `semantic_coverage_errors()` strict for every remaining registered action.

- Modify `scripts/env/tools/dispatch.py`
  - Remove `from env.services import memories as memory_service`.
  - Remove `HANDLERS_BY_TOOL["memory"]`.
  - `dispatch_handler_actions()` remains registry-comparable for remaining tools.

- Modify `scripts/env/client.py`
  - Remove `memory = sub.add_parser("memory", ...)` block.
  - Remove `context_get.add_argument("--memory-kind")`.
  - Remove `memory_kind` from `_context_args_from_cli()`.
  - Delete `_dispatch_memory()`.
  - Remove `elif args.resource == "memory"` branch in `main()`.

- Delete `scripts/env/services/memories.py`
  - No replacement service.

- Modify `scripts/env_store.py`
  - Remove `MEMORY_OBJECTS_DIR`, `VALID_MEMORY_STATUS`, `VALID_MEMORY_KINDS`, `memory_file()`, `validate_memory()`, `list_memories()`, `get_memory()`, `save_memory()`, `create_memory()`, `update_memory()`.
  - `ensure_runtime_dirs()` creates tracks/tasks/artifacts/handoffs and buddybox only.
  - `_normalize_source_refs()` accepts only `artifact`, `track`, `task`, `handoff`, `buddybox`, `external`, `note`.
  - `validate_handoff_record()` reads `artifact_ids`, `buddybox_paths`, `source_refs`, and no `memory_ids`; existing extra `memory_ids` fields in old JSON are ignored by omission from normalized output.
  - `create_handoff()` signature removes `memory_ids` and saved payload omits `memory_ids`.

- Modify `scripts/env/services/source_refs.py`
  - `_ALLOWED_TYPES` removes `memory`.
  - `normalize_source_refs()` validates id refs only for `artifact`, `track`, `task`, `handoff`.
  - `read_claim == "summarized-full-content"` checks only artifact full-summary ownership.

- Modify `scripts/env/services/handoffs.py`
  - `_VALIDATE_FIELDS` and `_CREATE_FIELDS` remove `memory_ids`.
  - `_validate_payload()` rejects `memory_ids` as unsupported payload field through `_require_allowed_fields()`.
  - Remove `env_store.get_memory()` ownership loop.
  - `_handoff_row()` omits `memory_ids`.
  - `create_handoff_for_active_buddy()` calls `env_store.create_handoff()` without `memory_ids`.
  - Allowed next actions mention task/artifact/buddybox/source_refs, not memory.

- Modify `scripts/env/services/context.py`
  - `_GET_FIELDS = {"track_id", "task_id", "limit"}`.
  - Delete `_memory_summary()`.
  - `_current_context_sections()` does not call `env_store.list_memories()`, does not build `visible_memories`, and omits `memory_summaries`.
  - `decision_surface.context_readiness` omits `has_memories`.
  - `current_context_summary` omits `memories`.
  - `context_sources_desc()` omits `memories`.
  - Success guidance lists `task/track/artifact/handoff/buddybox`.

- Modify `scripts/env/services/evidence.py`
  - `_resolve_target()` accepts only `target_type == "artifact"`.
  - `target_type == "memory"` returns `E_EVIDENCE_TARGET_TYPE`, `permission_boundary="evidence.target_type"`, `state_changed=false`, `impact` states no evidence token changed.
  - `_reject_scope()` guidance says readable owner-scoped artifact target.
  - Success guidance says attach evidence metadata to artifact provenance.

- Modify `scripts/browser_evidence.py`
  - `issue.add_argument("--target-type", choices=["artifact"])`.
  - `downgrade.add_argument("--target-type", choices=["artifact"])`.

- Modify `scripts/runtime_store/projections.py`
  - `_workspace_uses_projected_state()` removes `objects/memories` symlink check.
  - Delete `memory_object_path()` and `build_memory_view()`.
  - `build_handoff_view()` omits `memory_ids`.
  - `build_workspace_projection()` does not call `env_store.list_memories()` and does not include `memories`.

- Modify `scripts/workspace_data.py`
  - Remove `build_memory_view()` facade.

- Modify `framework/contracts/workspace-projection.json`
  - `top_level_key_order` removes `memories`.
  - `data_sources` removes `buddyswitch/objects/memories/*.json`.
  - `view_shapes.handoff.key_order` and `field_types` remove `memory_ids`.
  - Delete `view_shapes.memory`.

- Modify `framework/console/app.js`
  - Remove `memories` from `emptyWorkspace`.
  - Remove `memories` normalization in `normalizeWorkspaceData()`.
  - If later render code is found for memory, delete it rather than hiding it.

- Modify `scripts/env_manifest.py`
  - `_validate_permission()` supported object set removes `memory`.
  - `buddy_authority_profile()` runtime note lists `track/task/artifact/handoff/buddybox`.

- Modify `buddyswitch/manifest.toml`
  - Remove every `memory.*` permission from all buddies.

- Modify `tools/launcher/assets/buddies/{design,dev,market,pm,test}/AGENTS.md`
  - Tool list removes `memory`.
  - Market evidence sentence says target-scoped `artifact`.
  - Output rules remove written memories.

- Modify `tools/launcher/workspace.sh`
  - `buddyswitch_workspace_runtime_output_paths()` removes `buddyswitch/objects/memories`.
  - `buddyswitch_workspace_projected_state_paths()` removes `buddyswitch/objects/memories`.
  - `buddyswitch_workspace_neutralize_project_codex_config()` removes `buddyswitch/objects/memories/**`.
  - `buddyswitch_workspace_ensure_state_skeleton()` removes `buddyswitch/objects/memories`.

- Modify `scripts/env_cleanup.py`
  - Remove `memory_objects` category.
  - Delete `discover_memory_objects()` and `add_indexed_memory()`.
  - Remove `memory_object_ids` and `memory_records` from plan shape and JSON output.
  - Remove all-data and buddy cleanup logic that reads or deletes `buddyswitch/objects/memories`.
  - Remove skeleton recreation of `buddyswitch/objects/memories`.

- Modify active docs and skills:
  - `README.md`
  - `framework/docs/turn-runtime-spec.md`
  - `framework/docs/browser-cockpit.md`
  - `framework/docs/skill-runtime-shared-rules.md`
  - `framework/docs/artifacts-runs-git-policy.md`
  - `framework/docs/architecture-overview.md`
  - `framework/docs/interface-spec.md`
  - `framework/agent-registry.md`
  - `framework/contracts/{pm,market,dev,design,test}.md`
  - `buddyswitch/skills/shared/handoff-tool/SKILL.md`
  - `buddyswitch/skills/shared/task-tool/SKILL.md`
  - Any other active file found by the final grep gate.

- Delete `tests/test_memory_env_tool.py`.

- Add `tests/test_memory_removal_contract.py`
  - Focused regression contract for memory absence across registry, router, CLI, context, source_refs, evidence, handoff, projection, launcher, cleanup, and old-file-ignore behavior.

- Modify existing tests listed in section 3 so they assert memory absence and use artifacts/buddybox/source_refs/note instead of memory.

### 核心数据模型

Remaining `source_refs` schema:

```python
[
    {"type": "artifact", "id": "<artifact-id>"},
    {"type": "track", "id": "<track-id>"},
    {"type": "task", "id": "<task-id>"},
    {"type": "handoff", "id": "<handoff-id>"},
    {"type": "buddybox", "path": "<buddy>/<relative-path>"},
    {"type": "external", "label": "<label>", "url": "<optional-url>"},
    {"type": "note", "label": "<label>"}
]
```

Remaining handoff record shape:

```python
{
    "id": str,
    "track_id": str,
    "source_buddy": str,
    "target_buddy": str,
    "source_task_id": str | None,
    "artifact_ids": list[str],
    "buddybox_paths": list[str],
    "source_refs": list[dict] | None,
    "reason": str,
    "context": str,
    "status": "active" | "superseded" | "archived",
    "created_at": str,
    "updated_at": str,
}
```

Remaining workspace projection top-level order:

```json
[
  "generated_at",
  "manifest_path",
  "objects_root",
  "content_root",
  "buddies",
  "tracks",
  "standalone_tasks",
  "tasks",
  "artifacts",
  "handoffs",
  "buddybox_files"
]
```

### 接口、函数边界、调用流

- `env.tool` call flow remains `runtime_kernel.broker.dispatch_runtime_request()` -> `env.tools.router.dispatch_env_tool_request()` -> `env.tools.dispatch.dispatch_registered_env_tool()` -> service handler.
- Unsupported memory tool flow: router computes supported tools from `contracts.supported_tools()`, rejects `tool="memory"` before dispatch, returns structured rejection, and no service module import is possible.
- CLI flow for memory: `scripts/env/client.py` argparse rejects resource `memory` before broker request construction.
- Context flow: `context.get`/`context.summarize` build orientation from tracks/tasks/artifacts/handoffs/buddybox only.
- Evidence flow: `evidence.issue_browser` and `evidence.approve_downgrade` resolve artifact target through `env_store.get_artifact()` only.
- Handoff flow: service validates artifact ids and buddybox paths only; created object excludes `memory_ids`; old extra `memory_ids` in loaded JSON is omitted from normalized output.
- Projection flow: `workspace_data.build_workspace_data()` -> `runtime_store.projections.build_workspace_projection()` reads tracks/tasks/artifacts/handoffs/buddybox only.

### 需要删除的旧路径和旧逻辑

- File delete: `scripts/env/services/memories.py`.
- File delete: `tests/test_memory_env_tool.py`.
- Delete all references to `MEMORY_OBJECTS_DIR`, `VALID_MEMORY_STATUS`, `VALID_MEMORY_KINDS`, `memory_file`, `validate_memory`, `list_memories`, `get_memory`, `save_memory`, `create_memory`, `update_memory`.
- Delete all active references to `memory_ids`, except historical docs/spec/memo kept outside active grep gate.
- Delete all active references to `memory_kind`, `memory_summaries`, `has_memories`, top-level `memories`.
- Delete all active references to `memory.read`, `memory.write`, `memory.update`, `memory.archive`.
- Delete launcher creation/projection/exclude of `buddyswitch/objects/memories`.

## 5. 分阶段实施计划

### 阶段 1：写出 memory removal regression contract

**目标**

先让完整移除目标变成 failing tests，覆盖 tool registry、router、status、CLI、manifest、context、source_refs、evidence、handoff、projection、launcher、cleanup 和 old-file-ignore 行为。

**具体文件变更**

- Create: `tests/test_memory_removal_contract.py`
- Modify: `tests/test_env_tool_router.py`
- Modify: `tests/test_turn_runtime.py`
- Modify: `tests/test_prepare_runtime_context.py`
- Modify: `tests/test_runless_runtime_contract.py`
- Modify: `tests/test_env_manifest_v2.py`
- Modify: `tests/test_repo_consistency.py`

**详细步骤**

1. In `tests/test_memory_removal_contract.py`, create `MemoryRemovalContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase)` with helper `_instance_json(buddy: str, instance_id: str) -> Path` and `_dispatch(tool: str, action: str, args: dict[str, object]) -> dict[str, object>` using `runtime_kernel.broker.dispatch_runtime_request()`.
2. Add `test_tool_registry_status_and_help_exclude_memory`:
   - Assert `"memory" not in contracts.supported_tools()`.
   - Assert no key in `contracts.operation_semantics()` starts with `"memory."`.
   - Run `python3 scripts/turn_runtime.py status`, parse JSON, assert `env_tools` excludes `memory`.
   - Run `python3 scripts/env/client.py --help`, assert stdout excludes `memory`.
3. Add `test_env_tool_memory_request_is_rejected_without_state_mutation`:
   - Create runtime workspace with one task file through `env_store.create_task()`.
   - Snapshot `buddyswitch/objects` tree file list and JSON contents.
   - Dispatch `tool="memory", action="write", args={"kind": "decision", ...}`.
   - Assert `ok=false`, error code `E_ENV_TOOL`, `permission_boundary="env.tool"`, `state_changed=false`.
   - Assert snapshot unchanged and no `buddyswitch/objects/memories` directory exists.
4. Add `test_context_rejects_memory_kind_and_omits_memory_sections`:
   - Write an old memory JSON file directly at `buddyswitch/objects/memories/mem-old.json` using test helper, not `env_store`.
   - Dispatch `context.get` with `{"memory_kind": "decision"}` and assert `E_CONTEXT_PAYLOAD`.
   - Dispatch `context.summarize` and assert no keys `memory_summaries`, no `has_memories`, no `memories` count.
   - Dispatch `context.list_sources` and assert `sources` lacks `memories`.
5. Add `test_source_refs_reject_memory_type`:
   - Call `source_refs.normalize_source_refs([{"type": "memory", "id": "mem-old"}], active_buddy="pm")`.
   - Assert `ValueError` message contains `unsupported source_ref type: memory`.
   - Call `env_store.validate_artifact()` with `source_refs=[{"type": "memory", "id": "mem-old"}]` and assert `ValueError`.
6. Add `test_evidence_rejects_memory_target_and_accepts_artifact_target`:
   - Seed PM task and artifact.
   - Dispatch `evidence.issue_browser` with artifact target and assert success target_type artifact.
   - Dispatch `evidence.issue_browser` with `target_type="memory"` and assert `E_EVIDENCE_TARGET_TYPE`, `state_changed=false`, no `tool_evidence`.
7. Add `test_handoff_rejects_memory_ids_and_created_record_omits_memory_ids`:
   - Seed track, task, artifact, buddybox path.
   - Dispatch `handoff.validate` with `memory_ids=["mem-old"]`; assert `E_HANDOFF_PAYLOAD` and unsupported field message.
   - Dispatch valid `handoff.create` without `memory_ids`; assert returned `handoff` lacks `memory_ids` and saved JSON lacks `memory_ids`.
8. Add `test_workspace_projection_launcher_and_cleanup_ignore_old_memory_files`:
   - Write old memory JSON directly under runtime root.
   - Build `workspace_data.build_workspace_data()` and assert payload lacks `memories`.
   - Load `framework/contracts/workspace-projection.json` and assert top-level order lacks `memories` and data sources lack `objects/memories`.
   - Call `env_cleanup.build_cleanup_plan(scope="all-data", ...)` and assert JSON plan lacks `memory_object_ids`, delete paths do not include `objects/memories`.
9. Update `tests/test_env_tool_router.py::EnvToolRouterTests::test_router_supported_tools_and_actions_match_registry` to assert `memory` absent and remaining tools present.
10. Update `tests/test_turn_runtime.py::TurnRuntimeRunlessTests::test_status_lists_only_runless_tool_surfaces` and `tests/test_prepare_runtime_context.py::PrepareRuntimeContextRunlessTests::test_status_payload_has_runless_context_only` to assert `memory` absent.
11. Update `tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_tool_registry_exposes_memory_and_buddybox_and_excludes_run_and_binding` by renaming to `test_tool_registry_exposes_runless_tools_and_excludes_memory_run_and_binding`; assert `buddybox` present, `memory` absent.
12. Update `tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_env_client_help_exposes_runless_resources` to assert help excludes `memory`.
13. Update `tests/test_env_manifest_v2.py` memory permission assertions to assert no permission starts with `"memory."`.
14. Update `tests/test_repo_consistency.py` expected tool set to `{"task", "track", "artifact", "handoff", "buddybox", "context", "evidence", "search"}` and workspace projection checks to exclude `memories`.

**预期行为变化**

Before implementation these tests fail because memory is still registered, accepted, projected, documented, and cleaned. The failures locate every active surface that must be removed.

**对应需求编号**

`REQ-001` through `REQ-034`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_memory_removal_contract.py tests/test_env_tool_router.py tests/test_turn_runtime.py tests/test_prepare_runtime_context.py tests/test_runless_runtime_contract.py tests/test_env_manifest_v2.py tests/test_repo_consistency.py -q
```

Expected at this phase before code removal: failures mention active memory surfaces. Expected after later phases: pass.

**阶段完成标准**

The new tests fail for concrete memory-removal reasons, not import errors unrelated to memory removal. Existing modified tests express absence expectations and still import successfully.

### 阶段 2：移除 env tool registry、dispatch、CLI、semantics surface

**目标**

Make `memory` unavailable through registry, router, `turn_runtime.py status`, and `scripts/env/client.py`.

**具体文件变更**

- Modify: `scripts/env/tools/contracts.py`
- Modify: `scripts/env/tools/semantics.py`
- Modify: `scripts/env/tools/dispatch.py`
- Modify: `scripts/env/client.py`
- Delete: `scripts/env/services/memories.py`
- Modify tests from phase 1 as needed after exact response fields are confirmed.

**详细步骤**

1. In `scripts/env/tools/contracts.py`, delete the entire `{"tool": "memory", ...}` registry row.
2. In `scripts/env/tools/contracts.py`, remove `"memory_ids"` from handoff `validate.payload_fields` and `create.payload_fields`.
3. In `scripts/env/tools/contracts.py`, remove `"memory_kind"` from context `get.payload_fields`.
4. In `scripts/env/tools/contracts.py`, change context `summarize.returns` from `["summary", "candidate_tracks", "memory_summaries", "buddybox_files"]` to `["summary", "candidate_tracks", "buddybox_files"]`.
5. In `scripts/env/tools/contracts.py`, change evidence action preconditions from `"target_type is artifact or memory"` to `"target_type is artifact"`.
6. In `scripts/env/tools/semantics.py`, delete `_CAPABILITIES["memory"]`.
7. In `scripts/env/tools/semantics.py`, delete the `# memory actions` block and `memory_rows`.
8. In `scripts/env/tools/semantics.py`, update text values:
   - Task `use_when`: "attach artifacts, handoffs, or memories" -> "attach artifacts or handoffs".
   - Artifact `do_not_use_when`: remove "use memory actions"; recommend `buddybox` for durable files or `artifact` for deliverables only.
   - Handoff `use_when`: "artifact/memory/buddybox refs" -> "artifact/buddybox/source_refs".
   - Handoff fields remove `memory_ids`.
   - Context `use_when`: remove memories from snapshot wording.
   - Evidence title/description/use_when/input explanations mention artifact targets only.
9. In `scripts/env/tools/dispatch.py`, remove `from env.services import memories as memory_service`.
10. In `scripts/env/tools/dispatch.py`, remove `HANDLERS_BY_TOOL["memory"]`.
11. In `scripts/env/client.py`, remove the memory argparse block, `_dispatch_memory()`, and the `elif args.resource == "memory"` branch.
12. In `scripts/env/client.py`, remove `context_get.add_argument("--memory-kind")` and remove `memory_kind` from `_context_args_from_cli()` field loop.
13. Delete `scripts/env/services/memories.py`.
14. Run the focused command and confirm registry/status/help removal tests now fail only on downstream storage/context/projection references if those remain.

**预期行为变化**

- `contracts.supported_tools()` excludes `memory`.
- Router rejects `tool="memory"` before dispatch.
- `turn_runtime.py status` excludes memory automatically through `env_tools_description()`.
- `scripts/env/client.py memory ...` is invalid CLI usage.
- No import path can load `env.services.memories`.

**对应需求编号**

`REQ-002`, `REQ-003`, `REQ-004`, `REQ-005`, `REQ-006`, `REQ-022`, `REQ-027`, `REQ-034`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_tool_registry_status_and_help_exclude_memory tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_env_tool_memory_request_is_rejected_without_state_mutation tests/test_env_tool_router.py tests/test_turn_runtime.py tests/test_prepare_runtime_context.py tests/test_runless_runtime_contract.py -q
```

**阶段完成标准**

The command shows registry/router/status/help checks pass; any remaining failures point to context, storage, handoff, evidence, projection, manifest, docs, cleanup, or old tests.

### 阶段 3：移除 store-level memory、source_refs memory、handoff memory_ids

**目标**

Remove memory object store support and eliminate memory as a valid source/handoff reference without adding migration or cleanup.

**具体文件变更**

- Modify: `scripts/env_store.py`
- Modify: `scripts/env/services/source_refs.py`
- Modify: `scripts/env/services/handoffs.py`
- Modify: `tests/runtime_root_test_helper.py`
- Modify: `tests/test_handoff_env_tool.py`
- Modify: `tests/test_env_layer_end_to_end.py`
- Modify: `tests/test_env_tool_response_contract.py`
- Modify: `tests/test_runtime_tool_feedback.py`
- Delete: `tests/test_memory_env_tool.py`

**详细步骤**

1. In `scripts/env_store.py`, remove `MEMORY_OBJECTS_DIR`, `VALID_MEMORY_STATUS`, and `VALID_MEMORY_KINDS`.
2. In `scripts/env_store.py::ensure_runtime_dirs()`, delete `MEMORY_OBJECTS_DIR.mkdir(...)`.
3. In `scripts/env_store.py`, delete `memory_file()`.
4. In `scripts/env_store.py::_normalize_source_refs()`, change `if ref_type in {"artifact", "memory", "track", "task", "handoff"}` to `{"artifact", "track", "task", "handoff"}`.
5. In `scripts/env_store.py`, delete `validate_memory()`.
6. In `scripts/env_store.py`, delete `list_memories()`, `get_memory()`, `save_memory()`, `create_memory()`, `update_memory()`.
7. In `scripts/env_store.py::validate_handoff_record()`, remove `memory_ids = record.get("memory_ids", [])`, its list validation loop, and `"memory_ids"` from returned dict.
8. In `scripts/env_store.py::create_handoff()`, remove parameter `memory_ids: list[str]` and omit `"memory_ids"` from payload.
9. In `scripts/env/services/source_refs.py`, remove `"memory"` from `_ALLOWED_TYPES`.
10. In `scripts/env/services/source_refs.py::normalize_source_refs()`, change id-ref branch to `{"artifact", "track", "task", "handoff"}`.
11. In `scripts/env/services/source_refs.py::normalize_source_refs()`, in `read_claim == "summarized-full-content"` branch, check only `ref_type == "artifact"` and delete `env_store.get_memory()` branch.
12. In `scripts/env/services/handoffs.py`, remove `"memory_ids"` from `_VALIDATE_FIELDS`.
13. In `scripts/env/services/handoffs.py::_reject_scope()`, replace `"Use task.list/artifact.list/memory.list..."` with `"Use task.list/artifact.list/context.summarize..."`.
14. In `scripts/env/services/handoffs.py::_validate_payload()`, delete `memory_ids` normalization and ownership validation.
15. In `scripts/env/services/handoffs.py::_validate_payload()`, remove `"memory_ids"` from `normalized`.
16. In `scripts/env/services/handoffs.py::_handoff_row()`, remove `"memory_ids"`.
17. In `scripts/env/services/handoffs.py::create_handoff_for_active_buddy()`, remove `memory_ids=normalized["memory_ids"]` from `env_store.create_handoff()` call.
18. In `scripts/env/services/handoffs.py::create_handoff_for_active_buddy()`, replace allowed next action text `"artifacts/memories/buddybox files"` with `"artifacts/buddybox files"`.
19. In `tests/runtime_root_test_helper.py`, remove patch object for `env_store.MEMORY_OBJECTS_DIR`.
20. Delete `tests/test_memory_env_tool.py`.
21. In `tests/test_handoff_env_tool.py`, remove `env_store.create_memory()` seeding and all `memory_ids` payload assertions; add assertion that payload containing `memory_ids` is rejected.
22. In `tests/test_env_layer_end_to_end.py`, replace memory write and `get_memory()` assertions with artifact or buddybox state assertions matching the workflow purpose.
23. In `tests/test_env_tool_response_contract.py`, replace memory write/source_ref setup with a second artifact or a `note` source_ref; add explicit `source_refs` memory rejection assertion in the new removal test.
24. In `tests/test_runtime_tool_feedback.py`, replace memory owner-scope rejection test with a remaining scoped rejection such as foreign artifact update or buddybox owner-scope rejection.

**预期行为变化**

- New runtime writes never create memory object files.
- Source ref validation rejects `memory`.
- Handoff create/validate rejects `memory_ids` and new handoff JSON omits it.
- Old handoff records containing `memory_ids` can still be read as handoff records, but the field is ignored and not returned.

**对应需求编号**

`REQ-017`, `REQ-018`, `REQ-019`, `REQ-022`, `REQ-023`, `REQ-024`, `REQ-025`, `REQ-026`, `REQ-030`, `REQ-032`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_source_refs_reject_memory_type tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_handoff_rejects_memory_ids_and_created_record_omits_memory_ids tests/test_handoff_env_tool.py tests/test_env_layer_end_to_end.py tests/test_env_tool_response_contract.py tests/test_runtime_tool_feedback.py -q
```

**阶段完成标准**

The command passes; importing `env_store` exposes no memory helper names; `rg -n "create_memory|get_memory|list_memories|update_memory|validate_memory|MEMORY_OBJECTS_DIR" scripts tests` returns no active hits.

### 阶段 4：移除 context、workspace projection、console、cleanup、launcher memory paths

**目标**

Stop reading, projecting, cleaning, or presenting memory anywhere in runtime context, workspace data, console data shape, cleanup plan, or launcher state projection.

**具体文件变更**

- Modify: `scripts/env/services/context.py`
- Modify: `scripts/runtime_store/projections.py`
- Modify: `scripts/workspace_data.py`
- Modify: `framework/contracts/workspace-projection.json`
- Modify: `framework/console/app.js`
- Modify: `scripts/env_cleanup.py`
- Modify: `tools/launcher/workspace.sh`
- Modify: `tests/test_context_binding_env_tool.py`
- Modify: `tests/test_parallel_contracts.py`
- Modify: `tests/test_console_app_contract.py`
- Modify: `tests/test_cleanup_system.py`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_env_tool_identity.py`

**详细步骤**

1. In `scripts/env/services/context.py`, set `_GET_FIELDS = {"track_id", "task_id", "limit"}`.
2. Delete `_memory_summary()`.
3. In `_current_context_sections()`, remove `memories = env_store.list_memories()`.
4. In `_current_context_sections()`, delete `memory_kind` filter logic.
5. In `_current_context_sections()`, delete `visible_memories`.
6. In returned sections, remove `"memory_summaries"`, `decision_surface.context_readiness["has_memories"]`, and `current_context_summary["memories"]`.
7. In `context_sources_desc()`, remove `"memories"` entry.
8. In `get_context()` allowed next actions, replace `task/track/artifact/handoff/memory/buddybox` with `task/track/artifact/handoff/buddybox`.
9. In `summarize_context()`, remove `"memory_summaries": sections["memory_summaries"]`.
10. In `scripts/runtime_store/projections.py`, remove memory path from `_workspace_uses_projected_state()`.
11. Delete `memory_object_path()` and `build_memory_view()`.
12. In `build_handoff_view()`, remove `"memory_ids"`.
13. In `build_workspace_projection()`, remove `memories = ...` line and remove `"memories": memories` from payload.
14. In `scripts/workspace_data.py`, remove `build_memory_view()`.
15. In `framework/contracts/workspace-projection.json`, remove `memories` from top-level key order, data sources, and view shapes; remove `memory_ids` from handoff key order and field types.
16. In `framework/console/app.js`, remove `memories` from `emptyWorkspace` and `normalizeWorkspaceData()`.
17. Search `framework/console` for `memories` and delete any remaining memory render/filter functions if present.
18. In `scripts/env_cleanup.py`, remove `memory_objects` from category lists and any plan fields named `memory_object_ids` or `memory_records`.
19. In `scripts/env_cleanup.py`, delete `discover_memory_objects()` and `add_indexed_memory()`.
20. In `scripts/env_cleanup.py::build_cleanup_plan()`, remove discovery, warnings, buddy-scope memory selection, all-data memory selection, and output fields for memories.
21. In cleanup skeleton recreation, remove `buddyswitch/objects/memories`.
22. In `tools/launcher/workspace.sh`, remove `buddyswitch/objects/memories` from `buddyswitch_workspace_runtime_output_paths()`.
23. In `tools/launcher/workspace.sh`, remove `buddyswitch/objects/memories` from `buddyswitch_workspace_projected_state_paths()`.
24. In `tools/launcher/workspace.sh`, remove `buddyswitch/objects/memories/**` from runtime-only excludes.
25. In `tools/launcher/workspace.sh`, remove `buddyswitch/objects/memories` from state skeleton creation.
26. In `tests/test_context_binding_env_tool.py`, remove memory seeding from `_seed_context_state()` and rename `test_context_list_sources_includes_memory_and_buddybox` to assert `memories` absent and `buddybox` present.
27. In `tests/test_parallel_contracts.py`, remove `create_memory` import and memory creation; create handoff without memory ids; assert projection lacks `memories` and handoff shape lacks `memory_ids`.
28. In `tests/test_cleanup_system.py`, remove memory fixture file and expectations; assert cleanup plan lacks memory fields and does not delete old `buddyswitch/objects/memories/mem-pm.json` if such a file is created directly for ignore behavior.
29. In `tests/test_buddyswitch_launcher.py`, remove `scripts/env/services/memories.py` from copied runtime surface expectations and remove `buddyswitch/objects/memories` from projection pairs.
30. In `tests/test_env_tool_identity.py`, assert context sources exclude `memories`.

**预期行为变化**

- Context and projection are artifact/handoff/buddybox oriented with no memory summaries.
- Launcher no longer creates memory directories or symlinks.
- Cleanup leaves old memory files unmanaged and does not recreate memory skeletons.
- Console accepts workspace payloads without memory top-level data.

**对应需求编号**

`REQ-010`, `REQ-011`, `REQ-012`, `REQ-013`, `REQ-014`, `REQ-015`, `REQ-016`, `REQ-017`, `REQ-031`, `REQ-032`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_context_rejects_memory_kind_and_omits_memory_sections tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_workspace_projection_launcher_and_cleanup_ignore_old_memory_files tests/test_context_binding_env_tool.py tests/test_parallel_contracts.py tests/test_console_app_contract.py tests/test_cleanup_system.py tests/test_buddyswitch_launcher.py tests/test_env_tool_identity.py -q
```

**阶段完成标准**

The command passes; `rg -n "memory_summaries|has_memories|memory_kind|\"memories\"|build_memory_view|memory_object_ids" scripts framework tests tools` returns no active code/test hits except historical docs excluded by final grep rules.

### 阶段 5：移除 evidence memory target 和 browser evidence memory target

**目标**

Make evidence artifact-only in service code, CLI wrapper, docs, tests, and Market guidance.

**具体文件变更**

- Modify: `scripts/env/services/evidence.py`
- Modify: `scripts/browser_evidence.py`
- Modify: `tests/test_evidence_env_tool.py`
- Modify: `tests/test_market_browser_evidence.py`
- Modify: `tests/test_env_tool_response_contract.py`
- Modify: `tools/launcher/assets/buddies/market/AGENTS.md`
- Modify: `framework/docs/browser-cockpit.md`
- Modify: `framework/contracts/market.md`

**详细步骤**

1. In `scripts/env/services/evidence.py::_reject_scope()`, change retry guidance to `"Use readable owner-scoped artifact targets."`.
2. In `_resolve_target()`, keep artifact branch unchanged.
3. In `_resolve_target()`, delete memory branch using `env_store.get_memory()`.
4. In `_resolve_target()` final rejection, change message to `"target_type must be: artifact"`.
5. In `issue_browser_for_active_instance()`, success `allowed_next_actions` says `"Attach evidence token metadata via artifact source_refs when persisting outputs."`.
6. In `approve_downgrade_for_active_instance()`, success `allowed_next_actions` says `"Persist downgrade reason in artifact source_refs when writing outputs."`.
7. In `scripts/browser_evidence.py`, change argparse choices for both target type args to `["artifact"]`.
8. In `tests/test_evidence_env_tool.py`, remove memory target from `_seed_market_targets()` and return only `artifact_id`.
9. Replace `test_approve_downgrade_requires_reason_and_owns_target` with artifact target setup; keep missing reason assertion and successful artifact approval assertion.
10. Add assertion that `target_type="memory"` returns `E_EVIDENCE_TARGET_TYPE` and no token.
11. In `tests/test_market_browser_evidence.py`, rename tests and assertions from artifact-or-memory to artifact-only.
12. In `tools/launcher/assets/buddies/market/AGENTS.md`, change evidence sentence to `Market evidence is target-scoped to artifacts and must not be fabricated.`
13. In `framework/docs/browser-cockpit.md` and `framework/contracts/market.md`, replace artifact-or-memory with artifact-only.

**预期行为变化**

- Evidence token issuance never validates or references memory objects.
- CLI wrapper rejects `--target-type memory` before broker request.
- Market docs and runtime guidance no longer imply memory evidence targets.

**对应需求编号**

`REQ-009`, `REQ-020`, `REQ-021`, `REQ-027`, `REQ-028`, `REQ-032`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_memory_removal_contract.py::MemoryRemovalContractTests::test_evidence_rejects_memory_target_and_accepts_artifact_target tests/test_evidence_env_tool.py tests/test_market_browser_evidence.py tests/test_env_tool_response_contract.py -q
python3 scripts/browser_evidence.py issue --help
```

Expected CLI help contains `artifact` and not `memory`.

**阶段完成标准**

Evidence tests pass and `rg -n "artifact or memory|artifact/memory|target_type.*memory|choices=\\[\"artifact\", \"memory\"\\]" scripts tests framework tools` returns no active hits.

### 阶段 6：移除 manifest permissions、buddy guidance、active docs、skills references

**目标**

Remove memory from buddy-facing capability surfaces and active documentation so users and agents do not discover or request removed behavior.

**具体文件变更**

- Modify: `buddyswitch/manifest.toml`
- Modify: `scripts/env_manifest.py`
- Modify: `tools/launcher/assets/buddies/{design,dev,market,pm,test}/AGENTS.md`
- Modify: `README.md`
- Modify: `framework/docs/turn-runtime-spec.md`
- Modify: `framework/docs/skill-runtime-shared-rules.md`
- Modify: `framework/docs/artifacts-runs-git-policy.md`
- Modify: `framework/docs/architecture-overview.md`
- Modify: `framework/docs/interface-spec.md`
- Modify: `framework/agent-registry.md`
- Modify: `framework/contracts/{pm,market,dev,design,test}.md`
- Modify: `buddyswitch/skills/shared/handoff-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/task-tool/SKILL.md`
- Modify additional active files found by grep under `scripts framework buddyswitch tools tests README.md projects/app/README.md`.

**详细步骤**

1. In `buddyswitch/manifest.toml`, remove `memory.read`, `memory.write`, `memory.update`, `memory.archive` from every buddy permissions list.
2. In `scripts/env_manifest.py::_validate_permission()`, remove `"memory"` from `supported_objects`.
3. In `scripts/env_manifest.py::buddy_authority_profile()`, replace `track/task/artifact/handoff/memory/buddybox` with `track/task/artifact/handoff/buddybox`.
4. In every `tools/launcher/assets/buddies/*/AGENTS.md`, change tool list to ``(`task`, `track`, `artifact`, `handoff`, `buddybox`, `context`, `evidence`, `search`)``.
5. In `tools/launcher/assets/buddies/market/AGENTS.md`, remove memories from final output rule.
6. In `README.md`, remove `memory_id`, `memory.*`, and `buddyswitch/objects/memories/*.json`; product runtime loop lists explicit target ids as `track_id`, `task_id`, `artifact_id`, buddybox path.
7. In `framework/docs/turn-runtime-spec.md`, durable state paths exclude memories; persistence sentence says write artifact/handoff/buddybox objects directly.
8. In `framework/docs/skill-runtime-shared-rules.md`, remove memory durable target and permission check references.
9. In `framework/docs/artifacts-runs-git-policy.md`, remove memory objects and update "write artifact/memory/handoff" sentence to "write artifact/handoff".
10. In `framework/docs/architecture-overview.md` and `framework/docs/interface-spec.md`, remove memories from product state lists.
11. In `framework/agent-registry.md`, remove memory object persistence sentence.
12. In `framework/contracts/pm.md` and `framework/contracts/dev.md`, replace `memory.write` guidance with `artifact.create_revision` for formal records or `buddybox.write` for durable files.
13. In `framework/contracts/market.md`, evidence target remains artifact-only and output targets exclude memory.
14. In `framework/contracts/design.md` and `framework/contracts/test.md`, ensure durable output targets exclude memory if present.
15. In `buddyswitch/skills/shared/handoff-tool/SKILL.md`, remove `memory_ids` from provenance guidance.
16. In `buddyswitch/skills/shared/task-tool/SKILL.md`, remove "memories" from task ids guidance.

**预期行为变化**

- Buddies cannot discover memory permissions or memory tool usage from manifest, generated authority profile, launcher AGENTS files, or active docs.
- `env_manifest.load_manifest()` rejects any future `memory.*` permission.

**对应需求编号**

`REQ-007`, `REQ-008`, `REQ-009`, `REQ-028`, `REQ-029`, `REQ-032`, `REQ-033`, `REQ-034`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_manifest_v2.py tests/test_repo_consistency.py tests/test_runtime_agents.py tests/test_runtime_skills.py -q
rg -n "memory\\.read|memory\\.write|memory\\.update|memory\\.archive|memory_id|memory_ids|memory_kind|memory_summaries|has_memories|artifact or memory|artifact/memory|objects/memories" README.md scripts framework buddyswitch tools projects/app/README.md -g '!docs/memo/**' -g '!docs/spec/2026-05-14-*' -g '!docs/spec/2026-05-15-memory-removal-*'
```

Expected grep result after this phase is empty except any match in implementation/test plan files is excluded by the command.

**阶段完成标准**

Manifest, generated profile tests, runtime agent tests, and repo consistency tests pass; active buddy/docs grep shows no memory capability text.

### 阶段 7：rewrite remaining tests and run full verification

**目标**

Remove or rewrite all memory-dependent tests so the suite proves memory absence and preserves non-memory product behavior.

**具体文件变更**

- Modify every memory-dependent test still reported by `rg`.
- Delete memory lifecycle assertions that no longer represent product behavior.
- Keep or add absence assertions in `tests/test_memory_removal_contract.py`, `tests/test_repo_consistency.py`, and focused affected test files.

**详细步骤**

1. Run `rg -n "memory|memories|memory_ids|memory_kind|MEMORY_|create_memory|get_memory|list_memories|update_memory|memory\\." scripts framework buddyswitch tools README.md projects/app/README.md -g '!docs/memo/**' -g '!docs/spec/2026-05-14-*' -g '!docs/spec/2026-05-15-memory-removal-*'`.
2. For each remaining test hit:
   - If it validates old memory lifecycle, delete the test or the file.
   - If it uses memory as seed data for another behavior, replace with artifact, buddybox file, external source_ref, or note source_ref according to the behavior being tested.
   - If it validates active product surfaces, invert assertion to memory absence.
3. Update `tests/test_env_tool_semantic_contract.py`:
   - `test_registry_semantics_cover_every_registered_tool_and_action` asserts memory absent.
   - `test_risk_hints_match_mutation_and_open_world_behavior` removes `memory.write` assertion.
4. Update `tests/test_run_env_tool.py` if still present as runless status/context coverage:
   - Assert status tool list excludes memory.
   - Replace seeded memory context expectation with artifact/handoff/buddybox expectation.
5. Update `tests/test_host_decision_surface_product_mode.py`:
   - Remove `env_store.create_memory()`.
   - Assert `context.summarize` decision surface excludes `has_memories` and still returns candidate tracks.
6. Update `tests/test_parallel_contracts.py`:
   - Remove memory view shape assertion.
   - Assert `payload` lacks `memories`.
7. Update `tests/test_buddyswitch_launcher.py`:
   - Runtime copied service files exclude `scripts/env/services/memories.py`.
   - Projection pairs exclude memory dir.
8. Run focused groups from prior phases and fix direct fallout.
9. Run broader env/runtime verification.
10. Run final grep gate.

**预期行为变化**

The suite no longer uses memory to prove runless behavior. It proves memory is absent and non-memory workflows remain intact.

**对应需求编号**

`REQ-001` through `REQ-034`.

**验证命令**

Focused:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_memory_removal_contract.py tests/test_env_tool_router.py tests/test_turn_runtime.py tests/test_prepare_runtime_context.py tests/test_runless_runtime_contract.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py -q
```

Runtime services:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_handoff_env_tool.py tests/test_buddybox_env_tool.py tests/test_context_binding_env_tool.py tests/test_evidence_env_tool.py tests/test_search_env_tool.py -q
```

Launcher/projection/docs:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py tests/test_parallel_contracts.py tests/test_console_app_contract.py tests/test_cleanup_system.py tests/test_env_manifest_v2.py tests/test_repo_consistency.py tests/test_runtime_agents.py tests/test_runtime_skills.py -q
```

Broader:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py tests/test_env_layer_end_to_end.py tests/test_host_decision_surface_product_mode.py tests/test_market_browser_evidence.py tests/test_output_schema_boundaries.py tests/test_buddy_env_profiles.py tests/test_buddy_env_sandbox.py -q
```

Final grep gate:

```bash
rg -n "memory|memories|memory_ids|memory_kind|MEMORY_|create_memory|get_memory|list_memories|update_memory|memory\\." README.md scripts framework buddyswitch tools projects/app/README.md -g '!docs/memo/**' -g '!docs/spec/2026-05-14-*' -g '!docs/spec/2026-05-15-memory-removal-*'
```

**阶段完成标准**

All verification commands pass. Final grep gate returns no active hits. Old memory files can exist in runtime state but no active command reads, projects, cleans, or mutates them.

## 6. 迁移 / 删除策略

- Delete `scripts/env/services/memories.py` and `tests/test_memory_env_tool.py`.
- Remove memory tool registry and CLI entirely; do not keep hidden aliases, deprecated command handlers, or feature flags.
- Remove store-level memory support entirely; no replacement local memory model is introduced.
- Remove memory from source_refs and handoff payloads. Existing handoff JSON may contain retired `memory_ids`; active validation normalizes records without that field and never validates or returns it.
- Old `buddyswitch/objects/memories/*.json` files are left on disk if present. Runtime ignores them because no active code references the directory or helper functions.
- Cleanup no longer manages memory files. This is intentional because the source memo explicitly excludes migration/cleanup of already-created runtime memory files.
- Historical `docs/memo/**` and old `docs/spec/2026-05-14-*` remain historical records. Active docs, contracts, code, tests, launcher assets, and buddy-facing files must be memory-free.
- Short-term compatibility is limited to ignoring extra `memory_ids` fields in old handoff JSON during normalization. The real reason is to keep old handoff records readable while not exposing memory semantics. Exit condition is not a future compatibility path; the normalized runtime shape already excludes the field, and new writes never produce it.

## 7. 完成定义

The task is complete only when all conditions are true:

- `memory` is not present in env tool registry, router supported tools, dispatch handler map, `turn_runtime.py status`, or env client help.
- `env.tool` requests with `tool="memory"` return unsupported tool feedback and do not mutate runtime state.
- No buddy has `memory.*` permissions in `buddyswitch/manifest.toml`; `env_manifest.load_manifest()` rejects future `memory.*` permissions.
- Buddy runtime `AGENTS.md` files list `task`, `track`, `artifact`, `handoff`, `buddybox`, `context`, `evidence`, `search` only.
- Context outputs and source descriptors contain no memory fields or counts.
- Workspace projection contract, Python projection, console normalization, launcher projection, and cleanup plan contain no memory paths or top-level `memories`.
- `source_refs` rejects `type="memory"`.
- Evidence targets are artifact-only in service code and CLI wrappers.
- Handoff validate/create rejects `memory_ids`; created handoff records do not contain `memory_ids`; old `memory_ids` fields are ignored on read.
- Runtime dir setup and launcher skeleton do not create `buddyswitch/objects/memories`.
- Existing old memory files are left untouched and ignored.
- `tests/test_memory_env_tool.py` is deleted and memory-dependent tests are rewritten to absence tests or non-memory workflows.
- Focused, runtime service, launcher/projection/docs, and broader verification commands from Phase 7 pass.
- Final grep gate over active files returns no memory runtime surface hits, excluding historical memo/spec files and the two new memory-removal planning documents.
