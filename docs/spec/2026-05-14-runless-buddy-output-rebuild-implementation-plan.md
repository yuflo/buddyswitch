# Runless Buddy Output Rebuild Code Implementation Plan

## 1. 任务目标

完成后，BuddySwitch 不再把 host execution run 当作 durable product state；系统只提供 active buddy、broker、权限、锁和原子写能力，持久状态由 track、task、artifact、handoff、memory、buddybox 显式承载。当前核心瓶颈是运行事务、当前实例绑定和 source run 校验正在决定产品写入归属，导致 sub-agent、多 track、多任务输出互相抢同一个隐式 run/task 上下文，这是阻塞 BuddySwitch 协作能力继续前进的最高优先级问题。

## 2. 需求提取

- `REQ-001`：BuddySwitch 的 durable state 只管理 buddy output、collaboration objects 和 reusable knowledge，不管理 execution history。
- `REQ-002`：system layer 只保留 execution infrastructure：`instance_id`、active buddy、workspace/session metadata、broker/tool routing、manifest permission enforcement、runtime lock coordination、必要的 transient request/operation id。
- `REQ-003`：`instance.json` 必须缩小为 execution-container identity，允许字段为 `instance_id`、`buddy`、`status`、`workspace_dir`、`browser_port`、`updated_at`；不得包含 current task/track 字段。
- `REQ-004`：product collaboration layer 通过显式 tools 管理 `track`、`task`、`artifact`、`handoff`、`memory`、`buddybox`。
- `REQ-005`：track 保留 `id`、`title`、`summary`、`status`、`current_buddy`、`next_buddy`、`task_ids`、`updated_at`；PM lifecycle authority 保持具体规则，不引入 workflow engine 或 broad ACL system。
- `REQ-006`：task 保留 `id`、`buddy`、`title`、`summary`、`status`、`track_id`、`artifact_ids`、`artifact_slots`、`created_at`、`updated_at`；移除 `run_ids` 和 `latest_run_id`。
- `REQ-007`：artifact 保留 formal deliverable 语义和 revision/currentness 字段；移除 required `source_run_id`，新增 `created_by` 和 optional structured `source_refs`。
- `REQ-008`：artifact write authority 为 active buddy 可以写自己拥有的 task，且 artifact kind 必须在 manifest artifact kinds 中允许；不得需要 run reservation。
- `REQ-009`：`artifact.create_revision` 必须显式要求 `task_id`，不得回退到 `instance.current_task_id`。
- `REQ-010`：handoff 保持 durable collaboration object，引用 product objects：source/target buddy、track id、source task id、artifact ids、memory ids、buddybox paths、reason、context、status；移除 run-based source fields。
- `REQ-011`：memory 是 durable reusable buddy knowledge，不是 transcript sink；必须由 buddy 显式写入。
- `REQ-012`：memory records 使用 `buddyswitch/objects/memories/<memory_id>.json`，字段为 `id`、`buddy`、`kind`、`title`、`summary`、`content`、`source_refs`、`status`、`created_at`、`updated_at`。
- `REQ-013`：memory kind 初始只允许 `decision`、`fact`、`preference`、`constraint`、`lesson`、`context-summary`；status 初始只允许 `active`、`archived`。
- `REQ-014`：memory actions 为 `memory.list`、`memory.get`、`memory.write`、`memory.update`、`memory.archive`，并执行 owner-scope write、PM useful summary read、full read scope 限制。
- `REQ-015`：buddybox 是 intentional durable buddy-owned file domain，根路径为 `buddyswitch/content/buddybox/<buddy>/`，不是 `runs/raw` 的重命名。
- `REQ-016`：buddybox actions 为 `buddybox.list`、`buddybox.read`、`buddybox.write`、`buddybox.delete`，必须执行 relative path、no `..`、no absolute path、active-buddy write/delete root、binary base64、atomic write 规则。
- `REQ-017`：host turn 默认 disposable；没有最终 `persist` step。若 execution summary 要持久，buddy 必须显式写 artifact、memory、handoff 或 buddybox。
- `REQ-018`：sub-agent 不接收 run context，只接收 active buddy identity、explicit target ids、同 active buddy permissions、可选 buddybox path 或 memory purpose。
- `REQ-019`：tool surface 保留并简化 `track.*`、`task.*`、`artifact.*`、`handoff.*`、`context.*`，新增 `memory.*` 和 `buddybox.*`。
- `REQ-020`：canonical tool surface 移除 `run.commit`、`run.validate_result`、`run.get_receipt`、`run.get_raw`、`binding.get`、`binding.set_task`、`binding.set_track`、`binding.clear`。
- `REQ-021`：`prepare` 不创建 durable reservation，不返回 run id、run envelope、run-tied context revision、persist hint、current task/track、task-bound reservation；context discovery 通过 `context.get`、`context.summarize`、`context.list_sources` 完成。
- `REQ-022`：runtime broker 删除 `prepare` 和 `persist` 作为 lifecycle methods，保留 `env.tool`、`ping`、`status`。
- `REQ-023`：删除 `scripts/runtime_kernel/persist.py`、`scripts/env/services/runs.py`、`scripts/env/services/bindings.py`、`buddyswitch/skills/shared/run-tool/SKILL.md`、`framework/contracts/persist-buddy-run.json`。
- `REQ-024`：移除 canonical run storage：`buddyswitch/content/runs/*.json`、`buddyswitch/content/runs/reserved/*.json`、`runs/raw/*`。
- `REQ-025`：移除所有创建、扫描、清理、投影、展示 run content/run raw/run audit/current binding 的代码路径。
- `REQ-026`：`task.create` 可以显式接收 `track_id`；`track.join` 可以创建或复用 active-buddy task 并 attach 到 track，但不得写 instance binding。
- `REQ-027`：`artifact.update_metadata` 只按 `artifact_id` 和 active-buddy ownership 修改 title/summary/source_refs，不要求 provenance field。
- `REQ-028`：browser evidence 不再 run-token based；保留时必须绑定到 target artifact 或 memory，不能要求 prepared run。
- `REQ-029`：env profiles 和 launcher sandbox 把 durable writable file root 从 `runs/raw/<buddy>` 改为 `buddyswitch/content/buddybox/<buddy>`；project workspace write rule 保持独立。
- `REQ-030`：引入 shared `source_refs` schema，允许类型 `artifact`、`memory`、`buddybox`、`track`、`task`、`handoff`、`external`、`note`，并验证 type、required keys、id/path shape。
- `REQ-031`：`source_refs` 是 provenance/context，不是 authorization；权限仍由 service、broker、launcher、manifest/env-profile enforcement 决定。
- `REQ-032`：new/changed env tool metadata 遵守 env tool semantic contract：capability 暴露 `title`、`plain_description`、`use_when`、`do_not_use_when`、`capability_boundary`；action 暴露 `title`、`plain_description`、`inputs_explained`、`side_effects`、`risk_hints`、`success_means`、`common_failures`。
- `REQ-033`：每个 payload field 都有 plain-language explanation；success response 返回 `state_changed`、`durability`、`created_ids`、`updated_ids`、`read_scope` 等机器可读状态信号；rejection 返回 `permission_boundary`、`why_blocked`、`impact`、`retryable`、`retry_guidance`、`allowed_next_actions`。
- `REQ-034`：permission rules 不能只存在于 AGENTS、skills、docs 或 prompts；memory/buddybox owner scope、cross-buddy read/write、path validation、archive/delete authority 必须在 code 中执行。
- `REQ-035`：local file implementation only；不得引入 database、vector store、background indexer、search service、sync service、plugin system、rule engine、event bus、generic DSL、generic permission language。
- `REQ-036`：context discovery 是 read-only orientation payload，包含 active buddy、tool catalog、relevant tracks/tasks/artifacts/handoffs/memory/buddybox summaries；不得包含 run envelope、current binding、persist hints、run audit summaries、source run fields。
- `REQ-037`：workspace projection 和 console UI 展示 durable output objects：tracks、tasks、artifacts、handoffs、memory summaries、buddybox file summaries；不得展示 latest run、run audit detail、source run labels。
- `REQ-038`：cleanup 和 workspace/git policy 覆盖 tracks、tasks、artifacts、handoffs、memories、buddybox；移除 run raw、run content、run ids、reserved runs。
- `REQ-039`：README、root AGENTS、buddy AGENTS、shared skills、buddy-specific skills、framework docs、contracts、runtime agents validation、skill importer generated guidance 必须教授 explicit durable output model，不再教授 prepare/persist/current binding/run receipt/run raw/buddy-run commit。
- `REQ-040`：旧 tests 和 active docs 不能作为兼容压力；断言 old run/binding/source-run behavior 的测试必须改为新模型。
- `REQ-041`：新增 regression tests，确保 canonical code/active guidance 不再返回或教授 `run_envelope`、run-tied `context_revision`、`persist_command_hint`、`source_run_id`、`current_task_id`、`current_track_id`、`run_ids`、`latest_run_id`、`run` tool、`binding` tool。
- `REQ-042`：历史 run raw 不自动迁移；如果旧 run 有产品价值，只能人工提取为 memory、artifact、handoff 或 buddybox。
- `REQ-043`：review gate searches 在 `scripts`、`buddyswitch`、`tools`、`framework`、`README.md`、`AGENTS.md` 下不得出现 old canonical hits，历史 memo 和 explicitly historical changelog 除外。
- `REQ-044`：implementation 必须在 `.worktrees/dev2258` 完成，不污染 main worktree。

## 3. 现状探索摘要

### 关键目录、文件、测试、运行命令

- `AGENTS.md`：SHARP、testing-bound、direct replacement、no verification no done；当前 runtime state 列表仍包含 `buddyswitch/content/runs/*.json` 和 `runs/raw/`，需要改为新 durable object set。
- `README.md`：当前 product runtime loop 仍是 `prepare-turn-context -> persist-buddy-run`，需要替换为 context discovery + explicit product tool writes。
- `docs/memo/2026-05-14-runless-buddy-output-rebuild-memo.md`：本计划源需求。
- `docs/memo/2026-05-14-env-tool-semantic-contract-memo.md`：memory、buddybox 和 source_refs 的 runtime-visible semantics 必须满足该 contract。
- `scripts/turn_runtime.py`：当前包含 run id、context revision、reservation、prepare payload、persist CLI、run audit commit helpers；必须压缩为 runtime support 或替换为 context discovery helper。
- `scripts/runtime_kernel/dispatcher.py`、`scripts/runtime_kernel/coordinator.py`、`scripts/runtime_kernel/client.py`、`scripts/runtime_kernel/protocol.py`、`scripts/runtime_kernel/resolve.py`、`scripts/runtime_kernel/persist.py`：当前 broker 支持 `prepare`、`persist` 和 persist idempotency；必须变成 `env.tool`/`ping`/`status` gateway。
- `scripts/env_store.py`：当前 defines `RUN_CONTENT_DIR`、`run_content_path()`、`save_run_content()`，task validation requires `run_ids/latest_run_id`，artifact validation requires `source_run_id`，handoff validation requires `source_run_id`。
- `scripts/env/services/{runs.py,bindings.py}`：whole-service delete。
- `scripts/env/services/{tasks.py,tracks.py,artifacts.py,handoffs.py,context.py,evidence.py,track_relations.py}`：remove run/current-binding coupling; add source_refs/memory/buddybox awareness.
- `scripts/env/tools/{contracts.py,semantics.py,dispatch.py,responses.py,router.py}`：registry currently exposes `run` and `binding`; must remove them and add memory/buddybox.
- `scripts/env/client.py`：CLI currently exposes `task get-current/set-current`、`track get-current`、`binding`、`run`；must remove those and add memory/buddybox commands.
- `scripts/runtime_store/projections.py`、`scripts/workspace_data.py`、`framework/console/app.js`、`framework/contracts/workspace-projection.json`：currently project `run_audits` and run fields; must project memories and buddybox instead.
- `scripts/env_cleanup.py`、`tools/launcher/workspace.sh`、`tools/launcher/env.sh`、`tools/launcher/instance.sh`、`tools/launcher/codex_config.py`：currently create/project/allow/list current binding and run raw/content paths; must switch to instance identity and buddybox.
- `scripts/env_profiles.py`、`buddyswitch/env-profiles/*.json`、`framework/contracts/buddy-env-profile.json`：currently require `scratch.root = runs/raw/<buddy>`; must replace with buddybox root.
- `scripts/runtime_agents.py`、`scripts/skill_creator_importer.py`、`buddyswitch/manifest.toml`、`buddyswitch/skills/**/SKILL.md`、`tools/launcher/assets/buddies/*/AGENTS.md`、`framework/docs/*.md`、`framework/contracts/*.md`：currently contain prepare/persist/run guidance; must teach explicit durable writes.
- Existing tests to rewrite or extend: `tests/test_turn_runtime.py`、`tests/test_runtime_broker.py`、`tests/test_prepare_runtime_context.py`、`tests/test_run_env_tool.py`、`tests/test_run_env_services.py`、`tests/test_context_binding_env_tool.py`、`tests/test_artifact_env_tool.py`、`tests/test_task_env_tool.py`、`tests/test_track_env_tool.py`、`tests/test_evidence_env_tool.py`、`tests/test_market_browser_evidence.py`、`tests/test_buddy_env_profiles.py`、`tests/test_buddy_env_sandbox.py`、`tests/test_cleanup_system.py`、`tests/test_console_app_contract.py`、`tests/test_parallel_contracts.py`、`tests/test_output_schema_boundaries.py`、`tests/test_repo_consistency.py`、`tests/test_runtime_agents.py`、`tests/test_runtime_skills.py`、`tests/test_env_layer_end_to_end.py`。
- New tests to create: `tests/test_memory_env_tool.py`、`tests/test_buddybox_env_tool.py`、`tests/test_runless_runtime_contract.py`。

Exploration and verification commands:

```bash
pwd
git status --short --branch
rg --files -g 'AGENTS.md' -g 'CLAUDE.md' -g 'README.md' -g 'pyproject.toml' -g 'package.json' -g 'pytest.ini' -g 'Makefile'
rg -n "run\\.commit|run\\.validate_result|run\\.get_receipt|run\\.get_raw|binding\\.|current_task_id|current_track_id|source_run_id|run_ids|latest_run_id|prepare-context|persist_command_hint|buddyswitch/content/runs|runs/raw" scripts buddyswitch tools framework README.md AGENTS.md tests
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py -q
```

### 保留、替换、删除、迁移

- 保留：runtime broker framing、Unix socket gateway、active buddy identity、manifest permission checks、runtime locks、generic env.tool dispatch、structured response helper、search execution-support boundary。
- 保留：track/task/artifact/handoff product object concept 和 existing relation-aware artifact read rules，去掉 run/current-binding coupling。
- 保留：PM-only track lifecycle authority；不引入 generic workflow engine。
- 替换：`prepare/persist` run lifecycle 替换为 `context.get/summarize/list_sources` + explicit product write tools。
- 替换：task/artifact/handoff provenance 从 run ids 替换为 structured `source_refs`。
- 替换：runtime scratch/output policy 从 `runs/raw/<buddy>` 替换为 intentional durable `buddyswitch/content/buddybox/<buddy>/`。
- 替换：console and workspace projection 从 run audit timeline 替换为 durable output inventory。
- 删除：run service、binding service、run-tool skill、persist contract、run content/reservation storage、run raw canonical policy。
- 删除：task `run_ids/latest_run_id`、artifact `source_run_id`、handoff `source_run_id`、instance `current_task_id/current_track_id`。
- 不迁移：historical run raw/run audits；implementation 可删除 generated/canonical development state under run paths，产品知识只通过人工转写保留。

## 4. 最终目标架构

### 文件结构与职责

- Modify `scripts/env_store.py`
  - Define `MEMORY_OBJECTS_DIR = OBJECTS_ROOT / "memories"` and `BUDDYBOX_CONTENT_DIR = CONTENT_ROOT / "buddybox"`.
  - Remove `RUN_CONTENT_DIR`、`run_content_path()`、`save_run_content()`、`add_run_to_task()`、`initial_run_id` support。
  - `validate_task()` rejects any input containing `run_ids` or `latest_run_id` with stable errors.
  - `validate_artifact()` normalizes `created_by` and `source_refs`; rejects `source_run_id`.
  - `validate_handoff_record()` normalizes object-based fields and rejects `source_run_id`.
  - Add `memory_file()`、`validate_memory()`、`list_memories()`、`get_memory()`、`save_memory()`、`create_memory()`、`update_memory()`。
- Create `scripts/env/services/source_refs.py`
  - Own shared `source_refs` normalization for artifacts, memories, and handoffs.
  - Functions: `normalize_source_refs(raw_refs, *, active_buddy, read_claim=None) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]`、`source_ref_summary(refs) -> list[dict[str, Any]]`、`validate_buddybox_ref_path(path) -> str`。
  - It validates shape only and performs targeted read-scope checks when a caller claims to summarize internal full content.
- Modify `scripts/env/services/artifacts.py`
  - `_CREATE_FIELDS = {"artifact_id", "task_id", "kind", "title", "summary", "content", "source_refs"}`.
  - Delete `_validate_source_run()` and `_source_run_error()`.
  - `_normalized_create_payload()` requires explicit `task_id`; rejects missing `task_id`; validates owned task and kind; normalizes optional `source_refs`.
  - `create_artifact_revision()` calls `env_store.create_artifact(..., created_by=context["active_buddy"], source_refs=normalized_refs)`.
  - `update_artifact_metadata()` accepts optional `source_refs` with title/summary changes and never requires provenance.
  - `get_artifact_for_active_buddy()` returns `created_by` and `source_refs`, no source run fields.
- Modify `scripts/env/services/tasks.py`
  - Delete `get_current_task()` and `set_current_task()`.
  - `create_task_for_active_buddy()` accepts optional `task_id` and `track_id`; validates track exists; writes task object and track membership.
  - `list_tasks_for_active_buddy()` and `get_task_for_active_buddy()` return artifact summaries without run fields or current binding.
- Modify `scripts/env/services/tracks.py`
  - Delete `get_current_track()`.
  - `join_track_for_active_buddy()` creates/reuses/attaches active-buddy task and returns `task_id`; it does not call binding service and does not mutate instance payload.
  - Track summaries and current artifact rows omit source run fields.
- Modify `scripts/env/services/handoffs.py`
  - `_VALIDATE_FIELDS` becomes `track_id`、`source_task_id`、`target_buddy`、`artifact_ids`、`memory_ids`、`buddybox_paths`、`source_refs`、`reason`、`context`、`status`.
  - `_validate_handoff_payload()` validates explicit product refs and rejects hidden lifecycle fields and `source_run_id`.
  - `list_handoffs_for_active_buddy()` reads explicit handoff records only, not run audits.
  - `create_handoff_for_active_buddy()` writes object-based handoff record.
- Delete `scripts/env/services/runs.py`
- Delete `scripts/env/services/bindings.py`
- Create `scripts/env/services/memories.py`
  - Functions: `list_memories_for_active_buddy()`、`get_memory_for_active_buddy()`、`write_memory_for_active_buddy()`、`update_memory_for_active_buddy()`、`archive_memory_for_active_buddy()`。
  - Enforces allowed kind/status, owner write scope, owner full read, PM cross-buddy summary list, stable rejection fields.
- Create `scripts/env/services/buddybox.py`
  - Functions: `normalize_buddybox_path()`、`buddybox_root_for_buddy()`、`list_buddybox_for_active_buddy()`、`read_buddybox_for_active_buddy()`、`write_buddybox_for_active_buddy()`、`delete_buddybox_for_active_buddy()`。
  - Atomic writes use temp file in same parent plus `os.replace`.
  - `read` returns UTF-8 `content` for text and `content_base64` for binary.
- Modify `scripts/env/services/context.py`
  - Remove import and calls to bindings.
  - `current_context_sections()` builds read-only sections from active buddy, tool catalog, relevant tracks/tasks/artifacts/handoffs/memories/buddybox summaries.
  - Delete `_validate_context_payload()` prepared-run validation.
  - `context_sources_desc()` names object directories for tracks/tasks/artifacts/handoffs/memories/buddybox and omits run content source-of-truth.
- Modify `scripts/env/services/evidence.py` and `scripts/browser_evidence.py`
  - Replace prepared-run validation with target validation: `target_type` in `artifact|memory`, `target_id`, optional `reason`.
  - Evidence token or record is stored under target metadata or target-scoped evidence directory that is not referenced by task/run state; if target metadata storage is selected, artifact/memory `source_refs` includes a `note` or `external` ref rather than a run token.
- Modify `scripts/env/tools/contracts.py`
  - Remove tool rows `run` and `binding`.
  - Remove task/track current actions and run-based artifact fields.
  - Add `memory` and `buddybox` tool rows with all actions, payload fields, mutability, returns, authority, preconditions.
  - Update `artifact.create_revision`、`artifact.validate_payload`、`artifact.update_metadata` payloads to `source_refs`.
- Modify `scripts/env/tools/semantics.py`
  - Remove `run` and `binding` capability/action semantics.
  - Add `memory` and `buddybox` capability/action semantics.
  - Update context/artifact/handoff/task/track/evidence text to explain explicit product object writes and no run authority.
- Modify `scripts/env/tools/dispatch.py`
  - Remove imports and handlers for `runs` and `bindings`.
  - Add imports and handlers for `memories` and `buddybox`.
  - Runtime feedback wrappers stop special-casing run/persist.
- Modify `scripts/env/client.py`
  - Remove `binding` resource, `run` resource, `task get-current`, `task set-current`, `track get-current`.
  - Add `memory list|get|write|update|archive`.
  - Add `buddybox list|read|write|delete`.
  - Artifact create/update payload examples use `source_refs`.
- Modify `scripts/runtime_kernel/dispatcher.py`
  - Remove imports from `runtime_kernel.persist` and `runtime_kernel.resolve`.
  - Delete `_prepare_dispatch()` and `_persist_dispatch()`.
  - `dispatch_runtime_request()` supports only `env.tool`、`ping`、`status`.
  - Unsupported methods error lists only `env.tool, ping, status`.
- Delete `scripts/runtime_kernel/persist.py`
- Delete `scripts/runtime_kernel/resolve.py`
  - Delete if no code path imports it; otherwise replace with a context discovery helper that calls env tool context service without run envelope.
- Modify `scripts/runtime_kernel/coordinator.py`
  - Remove special `prepare/persist` lock mode. `env.tool` read/write mode remains registry-driven.
- Modify `scripts/runtime_kernel/client.py`
  - Delete `_extract_run_id()` and `make_persist_idempotency_key()`.
  - Retry policy treats `env.tool` reads as retryable and mutating env tools as non-retryable unless a future operation id is explicitly supplied.
- Modify `scripts/runtime_kernel/protocol.py`
  - Remove `persist` idempotency requirement from `validate_request()`.
- Modify `scripts/turn_runtime.py`
  - Remove run id generation, run envelope, context revision from run id, reservation helpers, persist payload hint, `_cmd_persist`, `persist_buddy_run`, and prepare payload fields that imply a run transaction.
  - Keep only runtime lock/session/error helpers that remain used by broker and services, or move them into `scripts/runtime_kernel/runtime_support.py` in the same phase with imports updated.
- Modify `tools/launcher/env.sh`
  - New instance records omit `current_task_id` and `current_track_id`.
- Modify `tools/launcher/instance.sh`
  - `instance list` columns remove current task/track.
  - Field readers and validation no longer expect current binding fields.
- Modify `tools/launcher/workspace.sh`
  - Projected state paths include tracks/tasks/artifacts/handoffs/memories and `buddyswitch/content/buddybox`.
  - Remove `buddyswitch/content/runs` and `runs/raw` from skeleton, projections, excludes, restore logic.
- Modify `tools/launcher/codex_config.py`
  - Writable root uses `workspace_dir / profile["buddybox"]["root"]`.
  - `state_root` remains blocked as a broad writable root; only active buddybox projected root is writable when profile allows it.
- Modify `buddyswitch/env-profiles/*.json` and `framework/contracts/buddy-env-profile.json`
  - Replace top-level `scratch` with `buddybox` containing `root = "buddyswitch/content/buddybox/<buddy>"`.
  - Validator enforces active buddy root and cross-buddy write denial.
- Modify `scripts/env_profiles.py`
  - Remove `scratch.root` validation.
  - Validate `buddybox.root`, expected writable labels, and no `runs/raw`.
- Modify `scripts/runtime_store/projections.py`
  - Add `build_memory_view()` and `scan_buddybox_files()`.
  - `build_workspace_projection()` returns `memories` and `buddybox_files`; no `run_audits`.
- Modify `scripts/workspace_data.py`
  - Remove `scan_run_audits()` facade; add memory/buddybox facades only if console imports them.
- Modify `framework/console/app.js`、`framework/console/index.html`、`framework/console/styles.css`
  - Remove run audit state, counts, lists, latest run helpers.
  - Render memory summaries and buddybox files with source refs, task/artifact links, and updated_at sorting.
- Modify `scripts/env_cleanup.py`
  - Categories become `artifact_objects`、`task_objects`、`track_objects`、`handoff_objects`、`memory_objects`、`buddybox_files`.
  - Remove discovery and deletion of run content/run raw/run ids.
- Delete `buddyswitch/skills/shared/run-tool/SKILL.md`
- Modify `buddyswitch/manifest.toml`
  - Remove `run-tool` skill from global skills and every buddy.
  - Add explicit permissions `memory.read`、`memory.write`、`memory.update`、`memory.archive`、`buddybox.read`、`buddybox.write`、`buddybox.delete` if permission strings remain.
- Modify `buddyswitch/skills/shared/{artifact-tool,task-tool,track-tool,handoff-tool}/SKILL.md`
  - Explicit ids and direct product writes only; no current binding, source run, run commit, or persist wording.
- Modify buddy-specific skills under `buddyswitch/skills/{pm,design,dev,market,test}/**/SKILL.md`
  - Replace “contribute to one buddy-run commit” and “before persist” with “write artifact/memory/handoff/buddybox explicitly”.
- Modify `tools/launcher/assets/buddies/{pm,design,dev,market,test}/AGENTS.md`
  - Remove mandatory prepare/persist and receipt/run-id language.
  - Explain AGENTS/skills are guidance, not permission source.
  - Replace `runs/raw/<buddy>` with buddybox only for intentional durable file outputs.
- Modify docs/contracts: `README.md`、`AGENTS.md`、`framework/docs/architecture-overview.md`、`framework/docs/turn-runtime-spec.md`、`framework/docs/skill-runtime-shared-rules.md`、`framework/docs/skill-architecture-best-practices.md`、`framework/docs/track-registry.md`、`framework/docs/interface-spec.md`、`framework/docs/browser-cockpit.md`、`framework/docs/runtime-broker-v2-runbook.md`、`framework/docs/artifacts-runs-git-policy.md`、`framework/agent-registry.md`、`framework/contracts/prepare-turn-context.json`、`framework/contracts/workspace-projection.json`、`framework/contracts/{pm,design,dev,market,test}.md`。
  - Remove run lifecycle contract; document explicit durable output objects and context discovery.
- Modify `scripts/runtime_agents.py`
  - Validate AGENTS templates for context discovery and explicit durable writes, not prepare/persist.
- Modify `scripts/skill_creator_importer.py`
  - Generated BuddySwitch rules say imported skills write durable outputs explicitly; no current buddy run commit language.

### 核心数据模型

Task:

```json
{
  "id": "task-pm-fireflies",
  "buddy": "pm",
  "title": "Fireflies positioning lock",
  "summary": "Lock landing page gaps.",
  "status": "active",
  "track_id": "track-fireflies",
  "artifact_ids": ["art-task-pm-fireflies-prd-r1"],
  "artifact_slots": {
    "prd": {
      "current_artifact_id": "art-task-pm-fireflies-prd-r1",
      "revision_count": 1
    }
  },
  "created_at": "2026-05-14T00:00:00+08:00",
  "updated_at": "2026-05-14T00:00:00+08:00"
}
```

Artifact:

```json
{
  "id": "art-task-pm-fireflies-prd-r1",
  "task_id": "task-pm-fireflies",
  "buddy": "pm",
  "kind": "prd",
  "title": "Fireflies PRD",
  "summary": "Landing page lock requirements.",
  "content": {"body": "..." },
  "revision": 1,
  "supersedes_artifact_id": null,
  "is_current": true,
  "created_by": "pm",
  "source_refs": [
    {"type": "memory", "id": "mem-pm-fireflies-locks-001"},
    {"type": "buddybox", "path": "pm/prototypes/fireflies.html"}
  ],
  "created_at": "2026-05-14T00:00:00+08:00",
  "updated_at": "2026-05-14T00:00:00+08:00"
}
```

Handoff:

```json
{
  "id": "handoff-pm-design-fireflies-001",
  "source_buddy": "pm",
  "target_buddy": "design",
  "track_id": "track-fireflies",
  "source_task_id": "task-pm-fireflies",
  "artifact_ids": ["art-task-pm-fireflies-prd-r1"],
  "memory_ids": ["mem-pm-fireflies-locks-001"],
  "buddybox_paths": ["pm/prototypes/fireflies.html"],
  "source_refs": [{"type": "artifact", "id": "art-task-pm-fireflies-prd-r1"}],
  "reason": "Design needs locked PM inputs.",
  "context": "Use the PRD and prototype file as source material.",
  "status": "active",
  "created_at": "2026-05-14T00:00:00+08:00",
  "updated_at": "2026-05-14T00:00:00+08:00"
}
```

Memory:

```json
{
  "id": "mem-pm-fireflies-locks-001",
  "buddy": "pm",
  "kind": "decision",
  "title": "Fireflies landing page lock gaps",
  "summary": "CTA, proof, pricing, hero visual, and security claims must be locked.",
  "content": {"body": "..." },
  "source_refs": [{"type": "artifact", "id": "art-task-pm-fireflies-prd-r1"}],
  "status": "active",
  "created_at": "2026-05-14T00:00:00+08:00",
  "updated_at": "2026-05-14T00:00:00+08:00"
}
```

Buddybox file summary:

```json
{
  "buddy": "pm",
  "path": "pm/prototypes/fireflies.html",
  "size_bytes": 18420,
  "updated_at": "2026-05-14T00:00:00+08:00",
  "content_type": "text/html",
  "source_ref": {"type": "buddybox", "path": "pm/prototypes/fireflies.html"}
}
```

### 调用流

1. Host starts in locked buddy instance and calls `python3 scripts/env/client.py context summarize` or broker `env.tool` with `context.summarize`.
2. Context response returns active buddy, tool catalog, and readable product-state summaries, but no run envelope or current binding.
3. Host chooses explicit target ids and calls product tools:
   - `task.create --payload {"track_id": "...", ...}`
   - `artifact.create-revision --payload {"task_id": "...", "source_refs": [...], ...}`
   - `memory.write --payload {...}`
   - `buddybox.write --path pm/prototypes/foo.html --content ...`
   - `handoff.create --payload {...}`
4. Each service validates manifest permission, active buddy ownership, path/id shape, and object relation before writing.
5. Each write uses atomic file persistence and returns `ok=true` with `state_changed=true` and durable object/file ids.
6. Host final response summarizes objects written. Nothing is persisted automatically for the turn.

## 5. 分阶段实施计划

### 阶段一：锁定 runless 契约的失败测试

目标：先把旧架构回归点变成 failing tests，防止实现过程中保留兼容路径。

具体文件变更：

- Create `tests/test_runless_runtime_contract.py`
- Modify `tests/test_env_tool_router.py`
- Modify `tests/test_env_tool_semantic_contract.py`
- Modify `tests/test_env_tool_response_contract.py`
- Modify `tests/test_prepare_runtime_context.py`
- Modify `tests/test_repo_consistency.py`

详细步骤：

1. 在 `tests/test_runless_runtime_contract.py` 新建 `RunlessRuntimeContractTests`，使用 `RuntimeWorkspaceTestMixin`。
2. 添加 `test_instance_record_contains_execution_identity_only`：创建 active instance JSON 后断言没有 `current_task_id`、`current_track_id`，并且只包含 accepted identity/status/workspace/browser/timestamp fields。
3. 添加 `test_context_discovery_writes_no_run_reservation_or_run_content`：调用 broker `env.tool context.summarize`，断言 `buddyswitch/content/runs`、`buddyswitch/content/runs/reserved`、`runs/raw` 不存在或为空，response 没有 `run_envelope`、`context_revision`、`persist_command_hint`。
4. 添加 `test_tool_registry_exposes_memory_and_buddybox_and_excludes_run_and_binding`：断言 `supported_tools()` 包含 `memory`、`buddybox`，不包含 `run`、`binding`。
5. 添加 `test_task_artifact_records_reject_run_fields`：通过 env_store validation fixtures 断言 task with `run_ids/latest_run_id` rejected，artifact with `source_run_id` rejected，handoff with `source_run_id` rejected。
6. 添加 `test_artifact_create_revision_requires_explicit_task_id_without_source_run`：broker dispatch `artifact.create_revision` without `task_id` returns `E_ARTIFACT_PAYLOAD` and with valid `task_id`/no `source_run_id` writes artifact.
7. 在 `tests/test_env_tool_router.py::EnvToolRouterTests::test_router_supported_tools_and_actions_match_registry` 改期望，移除 run/binding handler coverage，新增 memory/buddybox handler coverage。
8. 在 `tests/test_env_tool_semantic_contract.py` 改 coverage matrix，新增 memory/buddybox actions，移除 run/binding/current task/current track actions。
9. 在 `tests/test_repo_consistency.py` 新增 `test_runless_architecture_residue_scan`，执行 memo 中三条 `rg` pattern 并过滤 `docs/memo/` 和测试中明确的 absence assertions。

预期行为变化：

- 测试在旧代码上失败，失败点集中在 run/binding/source-run/current-binding residues。

对应需求编号：

- `REQ-001`、`REQ-003`、`REQ-020`、`REQ-021`、`REQ-023`、`REQ-024`、`REQ-040`、`REQ-041`、`REQ-043`

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runless_runtime_contract.py tests/test_env_tool_router.py::EnvToolRouterTests::test_router_supported_tools_and_actions_match_registry tests/test_env_tool_semantic_contract.py tests/test_repo_consistency.py::RepoConsistencyTests::test_runless_architecture_residue_scan -q
```

阶段完成标准：

- 新 tests 因现存旧路径失败，failure messages 指向具体 old fields/tools/paths，不出现 broad snapshot mismatch。

### 阶段二：收缩 instance 与 context discovery

目标：把当前 work selection 从 instance/runtime context 中移除，context 成为 read-only product-state discovery helper。

具体文件变更：

- Modify `tools/launcher/env.sh`
- Modify `tools/launcher/instance.sh`
- Modify `scripts/env/services/context.py`
- Modify `scripts/env/services/tasks.py`
- Modify `scripts/env/services/tracks.py`
- Modify `scripts/env/client.py`
- Modify `tests/test_buddyswitch_launcher.py`
- Modify `tests/test_context_binding_env_tool.py`
- Modify `tests/test_prepare_runtime_context.py`

详细步骤：

1. 在 `tools/launcher/env.sh` 的 instance record writer 中删除 `current_task_id` 和 `current_track_id` 字段。
2. 在 `tools/launcher/instance.sh` 中把 list output columns 改为 `instance_id buddy status browser_port updated_at workspace_dir`。
3. 删除 `scripts/env/services/context.py` 对 `bindings` 的 import；`current_context_sections()` 改为直接从 `env_store.list_tracks()`、`list_tasks()`、`list_artifacts()`、`list_handoffs()`、`list_memories()` 和 buddybox summary builder 生成 read-only sections。
4. 删除 `_validate_context_payload()` 中对 prepared run context 的校验；`context.get` 只允许 optional filters such as `track_id`、`task_id`、`memory_kind`，非法 filter 返回 `permission_boundary="context.filter"`。
5. 删除 `tasks.py::get_current_task`、`tasks.py::set_current_task`、`tracks.py::get_current_track` 的 public handler usage；service 中如有 helper 仅保留 local read utilities。
6. 在 `scripts/env/client.py` 删除 `task get-current`、`task set-current`、`track get-current` parser/dispatch/args branches。
7. 更新 `tests/test_buddyswitch_launcher.py::test_start_with_buddy_wires_instance_env_and_lifecycle`，断言 instance JSON no current fields。
8. 把 `tests/test_context_binding_env_tool.py` 中 binding/current-context tests 改名为 context discovery tests：`test_context_tools_return_product_state_without_current_binding_or_runs`、`test_context_filters_reject_invalid_payload_without_state_change`。

预期行为变化：

- Instance records 不再表达 current work。
- Context responses 不再输出 `current_binding`、`current_task_id`、`current_track_id`、run-derived stale binding warnings。
- Existing callers 必须使用 explicit ids。

对应需求编号：

- `REQ-002`、`REQ-003`、`REQ-017`、`REQ-018`、`REQ-021`、`REQ-026`、`REQ-036`

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_instance_record_contains_execution_identity_only tests/test_context_binding_env_tool.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_wires_instance_env_and_lifecycle -q
```

阶段完成标准：

- Focused tests pass.
- `rg -n "current_task_id|current_track_id" scripts/env tools/launcher tests/test_context_binding_env_tool.py tests/test_buddyswitch_launcher.py` only returns tests asserting absence or historical fixture strings explicitly scoped to legacy input rejection.

### 阶段三：删除 run lifecycle 服务和 broker lifecycle methods

目标：切断 durable run reservation、run commit、run receipt、persist idempotency 作为 canonical runtime path。

具体文件变更：

- Delete `scripts/env/services/runs.py`
- Delete `scripts/runtime_kernel/persist.py`
- Delete `scripts/runtime_kernel/resolve.py`
- Modify `scripts/runtime_kernel/__init__.py`
- Modify `scripts/runtime_kernel/dispatcher.py`
- Modify `scripts/runtime_kernel/coordinator.py`
- Modify `scripts/runtime_kernel/client.py`
- Modify `scripts/runtime_kernel/protocol.py`
- Modify `scripts/turn_runtime.py`
- Modify `tests/test_runtime_broker.py`
- Modify `tests/test_turn_runtime.py`
- Modify `tests/test_run_env_tool.py`
- Modify `tests/test_run_env_services.py`
- Modify `tests/test_parallel_contracts.py`

详细步骤：

1. 删除 `scripts/env/services/runs.py` 并从 `scripts/env/services/__init__.py` 中移除任何 import/export。
2. 在 `scripts/env/tools/dispatch.py` 删除 `run_service` import 和 `HANDLERS_BY_TOOL["run"]`。
3. 删除 `scripts/runtime_kernel/persist.py`，从 `scripts/runtime_kernel/__init__.py` 删除 `persist_buddy_run_request`。
4. 若 `scripts/runtime_kernel/resolve.py` 只包装 old prepare，则删除文件并移除 `prepare_turn_context_request` export；若保留，则改名为 context discovery helper 并不产生 run output。
5. 在 `scripts/runtime_kernel/dispatcher.py` 删除 `prepare`、`persist` dispatch branches、idempotency hydration、`_validate_product_persist_context_binding()` 调用。
6. 在 `scripts/runtime_kernel/coordinator.py::lock_mode_for_request()` 删除 `method in {"prepare", "persist"}` special case；unknown non-env methods default write lock only until dispatcher rejects.
7. 在 `scripts/runtime_kernel/client.py` 删除 `_extract_run_id()`、`make_persist_idempotency_key()`、persist retry branch；`request_runtime_broker()` 保持 generic request helper。
8. 在 `scripts/runtime_kernel/protocol.py::validate_request()` 删除 `method.strip() == "persist"` idempotency check。
9. 在 `scripts/turn_runtime.py` 删除 `_context_save_path()`、`_persist_command_hint_for_context()`、`_validate_prepared_run_context()`、run reservation helpers、`persist_buddy_run()`、`prepare_turn_context()`、CLI `prepare`/`persist` parser branches；保留 `_hold_product_runtime_lock()`、`RuntimeFeedbackError` 和 product session helpers until moved.
10. Replace tests:
    - `tests/test_runtime_broker.py::RuntimeBrokerTests::test_env_tool_supports_active_instance_and_identity_checks` remains.
    - Add `test_prepare_and_persist_methods_are_rejected` expecting supported methods list `env.tool, ping, status`.
    - Delete run idempotency tests and replace with `test_mutating_env_tool_is_not_retried_without_operation_id`.
    - `tests/test_parallel_contracts.py` removes persist-buddy-run contract assertions and asserts no persist contract file exists.

预期行为变化：

- Broker no longer accepts `prepare` or `persist`.
- No code creates, loads, clears, scans, or commits run reservations/audits.
- Product writes happen when product tools are called.

对应需求编号：

- `REQ-001`、`REQ-017`、`REQ-020`、`REQ-021`、`REQ-022`、`REQ-023`、`REQ-024`、`REQ-042`

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py tests/test_turn_runtime.py tests/test_parallel_contracts.py tests/test_runless_runtime_contract.py -q
```

阶段完成标准：

- `python3 scripts/env/client.py --help` 不显示 `run` resource。
- `rg -n "def persist_buddy_run|run_envelope|persist_command_hint|prepare-context|run reservation|run audit" scripts/runtime_kernel scripts/turn_runtime.py scripts/env/services` has no hits except tests asserting absence if command includes tests.

### 阶段四：替换 product object schema 与 artifact/task/handoff 写入路径

目标：移除 task/artifact/handoff 中的 run fields，用 explicit task target 和 source_refs 完成产品写入。

具体文件变更：

- Modify `scripts/env_store.py`
- Create `scripts/env/services/source_refs.py`
- Modify `scripts/env/services/artifacts.py`
- Modify `scripts/env/services/tasks.py`
- Modify `scripts/env/services/tracks.py`
- Modify `scripts/env/services/handoffs.py`
- Modify `scripts/env/services/track_relations.py`
- Modify `tests/test_env_store_v2.py`
- Modify `tests/test_artifact_env_tool.py`
- Modify `tests/test_task_env_tool.py`
- Modify `tests/test_track_env_tool.py`
- Modify `tests/test_context_binding_env_tool.py`

详细步骤：

1. In `env_store.validate_task()`, if input contains `run_ids` or `latest_run_id`, raise `ValueError("task.run_ids/latest_run_id are retired; use artifact_ids and artifact_slots")`; normalized output omits both fields.
2. In `env_store.create_task()`, remove `initial_run_id`; payload writes task without run fields.
3. In `env_store.update_task()`, remove `run_ids` and `latest_run_id` from allowed patch set.
4. Delete `env_store.add_run_to_task()`.
5. Create `source_refs.py` with allowed type validators:
   - `artifact|memory|track|task|handoff` require `id`.
   - `buddybox` requires `path`.
   - `external` requires `label` and optional `url`.
   - `note` requires `label`.
   - Unknown type returns rejection with `permission_boundary="source_refs.type"`.
6. In `env_store.validate_artifact()`, reject `source_run_id`, require `created_by`, normalize `source_refs` through source_refs helper, and return output with `created_by`/`source_refs`.
7. In `env_store.create_artifact()`, replace required `source_run_id` parameter with `created_by` and `source_refs=None`.
8. In `env_store.update_artifact()`, remove `source_run_id` from allowed patch and allow `source_refs`.
9. In `artifacts.py`, remove `_validate_source_run()` and all reservation file reads.
10. In `artifacts.py::_normalized_create_payload()`, reject missing `task_id` with `E_ARTIFACT_PAYLOAD`, normalize optional `source_refs`, and return no source run value.
11. In `tasks.py::create_task_for_active_buddy()`, accept optional `track_id`; if provided, require existing track and call `env_store.create_task(..., track_id=track_id)`.
12. In `tracks.py::join_track_for_active_buddy()`, remove binding write; return `relation="participant"` and `state_changes` for task creation/attachment only.
13. In `handoffs.py`, remove `source_run_id` from payload and record; validate `artifact_ids` belong to active-buddy source task, `memory_ids` readable within rules, `buddybox_paths` valid path refs.
14. In `track_relations.py::artifact_summary_row()` and context summaries, replace `source_run_id/source_run` with `created_by` and `source_refs`.

预期行为变化：

- Artifact revision write works with explicit `task_id` and no run reservation.
- Existing task/artifact/handoff records with run fields are rejected by validation instead of normalized forward.
- Track join no longer changes instance JSON.

对应需求编号：

- `REQ-006`、`REQ-007`、`REQ-008`、`REQ-009`、`REQ-010`、`REQ-026`、`REQ-027`、`REQ-030`、`REQ-031`

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_store_v2.py tests/test_artifact_env_tool.py tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_handoff_create_validates_owned_sources_and_does_not_mutate_track_lifecycle -q
```

阶段完成标准：

- Focused tests pass.
- `rg -n "source_run_id|run_ids|latest_run_id|current_binding" scripts/env_store.py scripts/env/services tests/test_artifact_env_tool.py tests/test_task_env_tool.py tests/test_track_env_tool.py` returns only explicit old-field rejection tests.

### 阶段五：新增 memory 对象和 tool surface

目标：把 durable reusable knowledge 作为一等 product object，使用本地 JSON 文件和 owner-scope permissions。

具体文件变更：

- Modify `scripts/env_store.py`
- Create `scripts/env/services/memories.py`
- Modify `scripts/env/tools/contracts.py`
- Modify `scripts/env/tools/semantics.py`
- Modify `scripts/env/tools/dispatch.py`
- Modify `scripts/env/client.py`
- Modify `buddyswitch/manifest.toml`
- Create `tests/test_memory_env_tool.py`
- Modify `tests/test_env_tool_router.py`
- Modify `tests/test_env_tool_semantic_contract.py`
- Modify `tests/test_env_tool_response_contract.py`

详细步骤：

1. Add `MEMORY_OBJECTS_DIR` and include it in `ensure_runtime_dirs()`.
2. Implement `env_store.memory_file(memory_id)`, `validate_memory()`, `list_memories()`, `get_memory()`, `save_memory()`, `create_memory()`, `update_memory()`.
3. Memory id generation in service uses `mem-<buddy>-<slug>-<shortid>` with `env_store.slugify(title)` and `uuid.uuid4().hex[:8]`.
4. `memories.py::write_memory_for_active_buddy()` requires `kind`、`title`、`summary`、`content`, optional `source_refs`; validates `kind` and content dict/string as the chosen contract specifies. To keep content general and deterministic, accept JSON object only; callers can put markdown under `{"body": "..."}`.
5. `memories.py::list_memories_for_active_buddy()` supports filters `buddy`、`kind`、`status`、`source_ref`、`limit`; PM may list cross-buddy summaries, non-PM may list own summaries plus readable refs only.
6. `memories.py::get_memory_for_active_buddy()` returns full content for owner and PM only when PM read rule is explicitly allowed; otherwise returns structured rejection `permission_boundary="memory.read_scope"`.
7. `update_memory_for_active_buddy()` allows owner to update `kind/title/summary/content/source_refs/status`, rejects invalid status, returns changed field names.
8. `archive_memory_for_active_buddy()` sets `status="archived"` and is idempotent if already archived.
9. Add registry row and semantics for memory actions; action payload explanations include source_refs meaning.
10. Add CLI commands:
    - `python3 scripts/env/client.py memory list [--buddy <buddy>] [--kind <kind>] [--status <status>] [--limit <n>]`
    - `memory get --memory-id <id>`
    - `memory write --payload <json>`
    - `memory update --payload <json>`
    - `memory archive --memory-id <id>`
11. Add manifest permissions for every buddy according to owner-scope behavior; PM receives cross-summary read if permission strings express it.
12. Add `tests/test_memory_env_tool.py` tests named `test_memory_write_get_list_update_archive_for_owner`、`test_memory_rejects_invalid_kind_status_and_missing_fields_without_write`、`test_memory_cross_buddy_full_read_denial_returns_structured_recovery`、`test_memory_semantics_and_cli_routing_are_runtime_visible`。

预期行为变化：

- Durable decisions/facts/preferences/constraints/lessons/context summaries can be written and later discovered without execution runs.

对应需求编号：

- `REQ-004`、`REQ-011`、`REQ-012`、`REQ-013`、`REQ-014`、`REQ-030`、`REQ-032`、`REQ-033`、`REQ-034`、`REQ-035`

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_memory_env_tool.py tests/test_env_tool_router.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py -q
```

阶段完成标准：

- Memory service, registry, semantics, CLI, response contract tests pass.
- No test depends on prompt-only memory permissions.

### 阶段六：新增 buddybox 和 sandbox/workspace policy

目标：提供 intentional buddy-owned durable file domain，并把 launcher writable roots 从 `runs/raw` 切换到 buddybox。

具体文件变更：

- Create `scripts/env/services/buddybox.py`
- Modify `scripts/env/tools/contracts.py`
- Modify `scripts/env/tools/semantics.py`
- Modify `scripts/env/tools/dispatch.py`
- Modify `scripts/env/client.py`
- Modify `buddyswitch/env-profiles/*.json`
- Modify `framework/contracts/buddy-env-profile.json`
- Modify `scripts/env_profiles.py`
- Modify `tools/launcher/workspace.sh`
- Modify `tools/launcher/codex_config.py`
- Modify `tests/test_buddybox_env_tool.py`
- Modify `tests/test_buddy_env_profiles.py`
- Modify `tests/test_buddy_env_sandbox.py`
- Modify `tests/test_buddyswitch_launcher.py`

详细步骤：

1. Implement `normalize_buddybox_path(path, *, active_buddy, for_write)`:
   - Require string relative path.
   - Reject empty path, absolute path, `..`, path resolving outside `BUDDYBOX_CONTENT_DIR / active_buddy`.
   - For write/delete, first path part must equal active buddy.
2. Implement `write_buddybox_for_active_buddy()` with one of `content` or `content_base64`; decode base64 with `validate=True`; write bytes atomically.
3. Implement `read_buddybox_for_active_buddy()`; return `encoding="utf-8"` with `content` when decode succeeds, else `encoding="base64"` with `content_base64`.
4. Implement `list_buddybox_for_active_buddy()` with optional `path`、`recursive`、`limit`, returning file summaries sorted by `updated_at desc, path`.
5. Implement `delete_buddybox_for_active_buddy()`; return `deleted=true/false`, reject directories unless path points to a file.
6. Add registry, semantics, dispatch handlers, and CLI commands:
   - `buddybox list [--path <path>] [--recursive] [--limit <n>]`
   - `buddybox read --path <path> [--encoding utf-8|base64|auto]`
   - `buddybox write --payload <json>`
   - `buddybox delete --path <path>`
7. Replace each `buddyswitch/env-profiles/<buddy>.json` top-level `scratch` object with `buddybox`: `{"root": "buddyswitch/content/buddybox/<buddy>"}`.
8. Update `framework/contracts/buddy-env-profile.json` top-level order and required keys from `scratch` to `buddybox`.
9. Update `env_profiles.py::validate_env_profile()` to validate buddybox root and host writable labels.
10. Update `codex_config.py::_build_profile_mode_roots()` to add `workspace_dir / profile["buddybox"]["root"]` as writable root and stop granting `runs/raw`.
11. Update `workspace.sh` projected state paths and skeleton:
    - Add `buddyswitch/objects/memories`
    - Add `buddyswitch/objects/handoffs`
    - Add `buddyswitch/content/buddybox`
    - Remove `buddyswitch/content/runs`
    - Remove `runs/raw`
12. Update launcher tests to assert buddybox symlink/projection and absence of run projections/raw roots.

预期行为变化：

- Buddy can write durable files only under its own buddybox root.
- Cross-buddy buddybox writes/deletes and path traversal return structured rejection.
- Launcher no longer grants canonical run raw write roots.

对应需求编号：

- `REQ-015`、`REQ-016`、`REQ-029`、`REQ-034`、`REQ-035`、`REQ-038`

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddybox_env_tool.py tests/test_buddy_env_profiles.py tests/test_buddy_env_sandbox.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_wires_instance_env_and_lifecycle -q
```

阶段完成标准：

- Buddybox read/write/list/delete pass for text and binary payloads.
- `rg -n "runs/raw|scratch.root|buddyswitch/content/runs" buddyswitch/env-profiles framework/contracts/buddy-env-profile.json scripts/env_profiles.py tools/launcher/codex_config.py tools/launcher/workspace.sh tests/test_buddy_env_profiles.py tests/test_buddy_env_sandbox.py` returns only explicit absence assertions if tests are included.

### 阶段七：重建 context、projection、console、cleanup around durable outputs

目标：所有 read-only discovery/display/cleanup surfaces 都围绕 product objects，不再围绕 execution turns。

具体文件变更：

- Modify `scripts/env/services/context.py`
- Modify `scripts/runtime_store/projections.py`
- Modify `scripts/workspace_data.py`
- Modify `framework/contracts/workspace-projection.json`
- Modify `framework/console/app.js`
- Modify `framework/console/index.html`
- Modify `framework/console/styles.css`
- Modify `scripts/env_cleanup.py`
- Modify `tools/launcher/cleanup.sh`
- Modify `tests/test_console_app_contract.py`
- Modify `tests/test_cleanup_system.py`
- Modify `tests/test_parallel_contracts.py`

详细步骤：

1. In `context.py`, add memory and buddybox summary sections:
   - `memory_summaries`: id, buddy, kind, title, summary, status, source_refs, updated_at.
   - `buddybox_files`: buddy, path, size_bytes, content_type, updated_at, source_ref.
2. `context.list_sources` source descriptors list object directories and buddybox root; no run source-of-truth.
3. In `runtime_store/projections.py`, add `memory_object_path()`, `build_memory_view()`, `scan_buddybox_files()`.
4. `build_workspace_projection()` top-level keys become `generated_at`, `manifest_path`, `objects_root`, `content_root`, `buddies`, `tracks`, `standalone_tasks`, `tasks`, `artifacts`, `handoffs`, `memories`, `buddybox_files`.
5. Remove `scan_run_audits()` from `workspace_data.py`; add facade functions only for active projection builders.
6. Rewrite `workspace-projection.json` data sources and view shapes for handoff, memory, buddybox; remove `run_audit`, task `run_ids/latest_run_id`, artifact `source_run_id`.
7. In console app:
   - `emptyWorkspace` removes `run_audits`; adds `handoffs`, `memories`, `buddybox_files`.
   - Remove `runMap()`、`getTaskRuns()`、`getTrackRuns()`、`latestRunForTask()`、`latestRunForTrack()`.
   - Add `memoryMap()` and `buddyboxByBuddy()` helpers.
   - Track/task detail panels render current artifacts, handoffs, memories, buddybox references.
8. In `env_cleanup.py`, replace category order with product object/file categories and remove run discovery functions.
9. Cleanup all-data deletes tracks/tasks/artifacts/handoffs/memories/buddybox files and preserves shared root/project workspace/instance roots.
10. Cleanup buddy-scope deletes only active buddy tasks/artifacts/memories and `buddyswitch/content/buddybox/<buddy>`; it does not delete foreign buddybox roots.

预期行为变化：

- Context panel answers “what outputs/collaboration state exist” rather than “what execution turns happened”.
- Cleanup no longer reports or deletes run content/raw state.

对应需求编号：

- `REQ-024`、`REQ-025`、`REQ-036`、`REQ-037`、`REQ-038`

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_console_app_contract.py tests/test_cleanup_system.py tests/test_parallel_contracts.py tests/test_context_binding_env_tool.py -q
```

阶段完成标准：

- Workspace projection contract matches runtime projection.
- Console tests assert no run audit DOM/state helpers remain.
- Cleanup tests cover buddybox and memory deletion with symlink guards.

### 阶段八：重建 docs、skills、AGENTS、contracts、generated guidance

目标：active guidance 全部教授 explicit durable output model，且明确 prompts/docs 不是权限来源。

具体文件变更：

- Modify `README.md`
- Modify `AGENTS.md`
- Modify `tools/launcher/assets/buddies/{pm,design,dev,market,test}/AGENTS.md`
- Delete `buddyswitch/skills/shared/run-tool/SKILL.md`
- Modify `buddyswitch/skills/shared/{artifact-tool,task-tool,track-tool,handoff-tool}/SKILL.md`
- Modify `buddyswitch/skills/{pm,design,dev,market,test}/**/SKILL.md`
- Modify `buddyswitch/manifest.toml`
- Modify `framework/docs/architecture-overview.md`
- Modify `framework/docs/turn-runtime-spec.md`
- Modify `framework/docs/skill-runtime-shared-rules.md`
- Modify `framework/docs/skill-architecture-best-practices.md`
- Modify `framework/docs/track-registry.md`
- Modify `framework/docs/interface-spec.md`
- Modify `framework/docs/browser-cockpit.md`
- Modify `framework/docs/runtime-broker-v2-runbook.md`
- Delete `framework/docs/artifacts-runs-git-policy.md`
- Create `framework/docs/product-output-storage-policy.md`
- Modify `framework/agent-registry.md`
- Modify `framework/contracts/prepare-turn-context.json`
- Delete `framework/contracts/persist-buddy-run.json`
- Modify `framework/contracts/{pm,design,dev,market,test}.md`
- Modify `scripts/runtime_agents.py`
- Modify `scripts/skill_creator_importer.py`
- Modify `tests/test_repo_consistency.py`
- Modify `tests/test_runtime_agents.py`
- Modify `tests/test_runtime_skills.py`
- Modify `tests/test_skill_creator_importer.py`

详细步骤：

1. README product runtime loop becomes:
   - Start locked buddy instance.
   - Use context env tools for orientation.
   - Write durable outputs explicitly through task/artifact/handoff/memory/buddybox tools.
   - Final host response summarizes written object ids.
2. Root AGENTS state list becomes `buddyswitch/objects/{tracks,tasks,artifacts,handoffs,memories}/*.json` and `buddyswitch/content/buddybox/<buddy>/`.
3. Buddy AGENTS templates remove prepare/persist command references, receipt sections, run id language, and run raw guidance; add direct product tools and buddybox durability boundary.
4. Delete run-tool skill and remove `run-tool` from manifest skills and each buddy skill list.
5. Shared artifact skill shows payload with explicit `task_id` and optional `source_refs`.
6. Shared task skill removes current binding workflow and documents optional `track_id` on create.
7. Shared track skill explains `track.join` creates/reuses task relation but does not select instance binding.
8. Shared handoff skill documents object-based refs and no source_run_id.
9. Buddy-specific skills replace “before persist” with concrete durable write instructions. Example wording: “When this work matters later, call artifact.create_revision or memory.write before final response.”
10. Runtime AGENTS validator requires new wording:
    - `context.get` or `context.summarize`
    - `artifact.create_revision`
    - `memory.write`
    - `buddybox.write`
    - “AGENTS.md is not the permission source”
    - no prepare/persist command strings.
11. Skill importer generated rules append explicit durable output rules and no buddy-run commit language.
12. Framework contracts:
    - `prepare-turn-context.json` becomes `context-discovery.json` if a separate contract file is clearer; otherwise contract id stays only if content no longer says prepare/run.
    - `persist-buddy-run.json` deleted.
    - Buddy contracts replace `runs/raw/<buddy>` with buddybox for durable files only.
13. Repo consistency tests enforce no active docs/skills teach old model.

预期行为变化：

- New runtime sessions and installed skills no longer instruct agents to prepare/persist or write run raw.
- Manifest exposes memory/buddybox capability and no run-tool.

对应需求编号：

- `REQ-019`、`REQ-020`、`REQ-032`、`REQ-033`、`REQ-034`、`REQ-039`、`REQ-043`

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py tests/test_runtime_agents.py tests/test_runtime_skills.py tests/test_skill_creator_importer.py -q
```

阶段完成标准：

- Runtime skill materialization installs track/artifact/task/handoff plus memory/buddybox guidance and never installs run-tool.
- Active docs residue tests pass.

### 阶段九：证据、market gate、端到端主路径

目标：保留必要 market/browser quality gate 时不再使用 run tokens，并证明多 buddy、多 task、多 artifact 工作流没有 run/current-binding coupling。

具体文件变更：

- Modify `scripts/env/services/evidence.py`
- Modify `scripts/browser_evidence.py`
- Modify `tests/test_evidence_env_tool.py`
- Modify `tests/test_market_browser_evidence.py`
- Modify `tests/test_env_layer_end_to_end.py`
- Modify `tests/test_host_decision_surface_product_mode.py`
- Modify `tests/test_runtime_tool_feedback.py`

详细步骤：

1. Change evidence payloads:
   - `evidence.issue_browser`: required `target_type`, `target_id`; optional `mode`.
   - `evidence.approve_downgrade`: required `target_type`, `target_id`, `reason`.
2. Evidence service validates target exists and is writable/readable by active buddy:
   - `target_type="artifact"` requires owned artifact or an artifact being created through immediate write flow.
   - `target_type="memory"` requires owned memory.
3. Evidence response returns `tool_evidence` with `target_type`, `target_id`, `issued_at`, `evidence_kind`, no `run_id`.
4. Market artifact/memory write paths accept evidence reference through `source_refs` or explicit `evidence` field if contract chooses a separate field; the field must be validated before write and returned in success response.
5. Rewrite `tests/test_market_browser_evidence.py`:
   - `test_market_evidence_requires_target_artifact_or_memory`
   - `test_market_artifact_write_with_browser_evidence_succeeds_without_run_audit`
   - `test_market_evidence_token_for_other_target_rejects_before_write`
   - `test_approved_downgrade_records_reason_on_target_refs`
6. Rewrite `tests/test_env_layer_end_to_end.py::test_full_buddy_loop_uses_env_tool_and_persists_state` into `test_full_buddy_loop_writes_product_objects_without_run_state`.
7. Add E2E scenarios:
   - PM creates three track notes for three tasks without run reservations.
   - PM simulates multiple sub-agents writing artifacts to different PM tasks without switching instance binding.
   - Design reads PM artifact and writes design handoff artifact.
   - Dev reads PM/design artifacts and writes implementation report.
   - Test reads implementation report and writes test report.
   - Buddy writes HTML prototype to buddybox and references it from artifact.
   - Buddy writes reusable decision memory and later sees it in context.

预期行为变化：

- Browser/market evidence cannot recreate a hidden run lifecycle.
- Full collaboration loop produces only product object files and buddybox files.

对应需求编号：

- `REQ-017`、`REQ-018`、`REQ-028`、`REQ-036`、`REQ-041`

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_evidence_env_tool.py tests/test_market_browser_evidence.py tests/test_env_layer_end_to_end.py tests/test_host_decision_surface_product_mode.py tests/test_runtime_tool_feedback.py -q
```

阶段完成标准：

- E2E assertions show no files under `buddyswitch/content/runs` or `runs/raw`.
- Artifact/memory/buddybox/handoff ids created in E2E are discoverable through context/projection.

### 阶段十：全仓 residue gate 和最终验证

目标：确保实现完成的是完整 rebuild，而不是并存旧路径。

具体文件变更：

- Modify tests only if a residue assertion reveals an active false positive with a precise historical marker.
- No production code changes in this phase unless a failing gate exposes remaining old canonical behavior.

详细步骤：

1. Run full focused runless suite.
2. Run residue scans:

```bash
rg -n "run\\.commit|run\\.validate_result|run\\.get_receipt|run\\.get_raw|binding\\." scripts buddyswitch tools framework README.md AGENTS.md
rg -n "source_run_id|run_ids|latest_run_id|current_task_id|current_track_id" scripts buddyswitch tools framework README.md AGENTS.md
rg -n "run_envelope|persist_command_hint|prepare-context|buddyswitch/content/runs|runs/raw" scripts buddyswitch tools framework README.md AGENTS.md
```

3. Inspect any hits:
   - Historical memo hits under `docs/memo/` are allowed only outside these command scopes.
   - Tests asserting absence are allowed only under `tests/`, not active runtime/guidance files.
   - Any active source/guidance hit is fixed by deleting or rewriting the old path.
4. Run final broad suite.
5. Run `git status --short` and confirm changes are contained in `dev2258`.

预期行为变化：

- No active canonical run/binding/source-run/current-binding residues remain.

对应需求编号：

- `REQ-040`、`REQ-041`、`REQ-043`、`REQ-044`

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runless_runtime_contract.py tests/test_memory_env_tool.py tests/test_buddybox_env_tool.py tests/test_env_tool_router.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py tests/test_artifact_env_tool.py tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_context_binding_env_tool.py tests/test_runtime_broker.py tests/test_buddy_env_profiles.py tests/test_buddy_env_sandbox.py tests/test_cleanup_system.py tests/test_console_app_contract.py tests/test_runtime_skills.py tests/test_runtime_agents.py tests/test_repo_consistency.py tests/test_env_layer_end_to_end.py tests/test_evidence_env_tool.py tests/test_market_browser_evidence.py tests/test_host_decision_surface_product_mode.py tests/test_output_schema_boundaries.py tests/test_parallel_contracts.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests -q
```

阶段完成标准：

- Focused and broad verification pass.
- Residue scans have zero active source/guidance hits.
- Final git status shows no changes outside the intended worktree and no accidental runtime state files committed.

## 6. 迁移 / 删除策略

- Delete whole services/files:
  - `scripts/runtime_kernel/persist.py`
  - `scripts/env/services/runs.py`
  - `scripts/env/services/bindings.py`
  - `buddyswitch/skills/shared/run-tool/SKILL.md`
  - `framework/contracts/persist-buddy-run.json`
- Remove generated/canonical runtime state paths from workspace creation and cleanup:
  - `buddyswitch/content/runs/*.json`
  - `buddyswitch/content/runs/reserved/*.json`
  - `runs/raw/*`
- Remove product-object fields:
  - `task.run_ids`
  - `task.latest_run_id`
  - `artifact.source_run_id`
  - `handoff.source_run_id`
  - `instance.current_task_id`
  - `instance.current_track_id`
- No automated migration for historical run raw or run audits. Development state can be discarded or manually converted into artifact/memory/handoff/buddybox before landing.
- No long-lived dual path. The only short-lived compatibility during a single implementation phase is test fixture acceptance while a phase is partially executed; by phase completion the old field/tool/path is rejected or removed.
- If a real production data constraint appears, the implementation pauses before building migration because the source memo explicitly says current scope is not production-sensitive migration.

## 7. 完成定义

The task is complete only when all conditions are true:

- Durable BuddySwitch state consists of tracks, tasks, artifacts, handoffs, memories, and buddybox files.
- Runtime no longer writes canonical run raw, run reservations, or run audit files.
- `instance.json` contains no current task or current track fields.
- Artifact writes require explicit `task_id`, do not accept or require `source_run_id`, and return created artifact ids plus normalized `source_refs`.
- Task records contain no run bookkeeping.
- Handoff provenance is object-based and can reference artifacts, memories, buddybox paths, tasks, tracks, handoffs, external refs, and notes.
- Memory and buddybox tools are wired through service, registry, semantics, dispatch, CLI, manifest/profile permissions, response contracts, context projection, and tests.
- Sub-agent-style independent writes to different tasks under one buddy work without switching instance binding.
- Context/console/projections show durable output objects, not execution history.
- Active docs, skills, AGENTS, contracts, runtime agents validation, and skill importer guidance teach explicit durable output writes and do not teach prepare/persist/run raw/current binding.
- Focused and broad verification commands in phase ten pass.
- Residue scans have no active source/guidance hits for retired run/binding/source-run/current-binding paths.
