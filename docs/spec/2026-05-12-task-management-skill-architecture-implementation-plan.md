# Task Management Skill Architecture Implementation Plan

## 1. 任务目标

完成后，BuddySwitch 的系统运行时只负责锁定实例、准备运行上下文、校验运行边界、保存 run audit；任务生命周期由 buddy 通过 `task-tool` 和 broker-routed env tool 显式完成。当前核心瓶颈是 `prepare` 和 `persist` 仍在隐藏创建、绑定、更新任务，导致 buddy 明确创建 3 个任务时系统额外生成第 4 个任务，破坏 skill 架构的单一权限路径。

`docs/plans/` 在本次规划中创建，用来保存这份实施计划和对应测试计划。

## 2. 需求提取

- `REQ-001`：系统只拥有 run 边界、身份校验、权限校验、reservation、run audit 持久化；buddy 拥有任务生命周期决策。
- `REQ-002`：普通用户输入不能自动创建任务。
- `REQ-003`：`prepare` 不得创建、修复、绑定、更新、归档任务或 track。
- `REQ-004`：无当前任务绑定时，`prepare` 返回 `current_task_id: null`、`task_context: null`、`binding_state: unbound`。
- `REQ-005`：绑定任务或 track 缺失时，`prepare` 返回 stale binding 反馈或 stale context，不创建替代对象。
- `REQ-006`：`context_revision` 来自 reserved run envelope，不再来自 task object 或 task run count。
- `REQ-007`：run reservation 支持 `task_id: null`，保留 `run_id`、`instance_id`、`active_buddy`、`context_revision` 校验；仅在显式绑定 task 时保留 task-level 并发检查。
- `REQ-008`：`persist` 只提交 run audit 和 receipt，不创建、修复、绑定、更新、归档、链接任务。
- `REQ-009`：`persist` 不再接受或执行 `state_effects.task`；反馈必须指向 `task.update`。
- `REQ-010`：`persist` 不再接受或执行 `state_effects.track`；反馈必须指向 `track.create|update|advance|archive|attach_task|detach_task`。
- `REQ-011`：`persist` 不创建 artifact content；artifact revision 由 `artifact-tool` 的 `artifact.create_revision` 显式写入。
- `REQ-012`：artifact 继续保持 task-owned；创建 artifact revision 必须有 active-buddy task id 和 reserved `source_run_id`，但 reservation 的 `task_id` 可以为 `null`。
- `REQ-013`：task 关联是可选 metadata，不是 run envelope 的必填容器。
- `REQ-014`：`framework/contracts/persist-buddy-run.json` 的 receipt 必填字段移除 `task_id` 和 `task_title`，并把 task association 标为 optional metadata。
- `REQ-015`：task create/list/get/get-current/set-current/update/archive 只能通过 `task-tool` 或 broker-routed `task` env tool 完成。
- `REQ-016`：instance task binding 只能通过 `task.set_current`、`binding.set_task`、`binding.clear` 显式改变。
- `REQ-017`：post-prepare 和 post-persist 不得从 prepare payload、receipt、refreshed context 推导并写回 instance binding。
- `REQ-018`：track-task 关系保留在 `track-tool` 的 `attach_task` / `detach_task` 中，因为这是显式 env tool 行为；`persist` 不得隐式 register task to track。
- `REQ-019`：taskless run 是合法结果，可保存 run audit 并返回 receipt。
- `REQ-020`：显式创建 3 个 task 的请求最终只能产生 3 个 task object，不能产生隐藏的 prepared task。
- `REQ-021`：runtime context、persist hints、AGENTS、skills、framework docs 不再指导 buddy 使用 `state_effects.task` 或 `state_effects.track` 完成生命周期写入。
- `REQ-022`：runtime feedback 必须把缺失 task、stale binding、非法 state effects、artifact task requirement 指向相应 env tool 命令。
- `REQ-023`：static scans 必须防止 `prepare`、`persist`、run commit 路径重新调用 task mutation、track linkage、artifact creation API。
- `REQ-024`：现有显式 env tool 权限、active buddy scope、broker identity checks、Market evidence policy 继续有效。
- `REQ-025`：不引入 workflow engine、event bus、rule engine、plugin system、DSL、长期双路径或兼容 wrapper。
- `REQ-026`：不迁移历史 task/artifact/track 数据 shape；旧对象继续可读，新写入走显式 env tool。

## 3. 现状探索摘要

### 关键路径

- `docs/memo/2026-05-12-task-management-skill-architecture-handoff-memo.md`：本任务的架构决策来源。
- `scripts/turn_runtime.py`：当前 `_build_prepare_turn_context` 会调用 `create_task`、`create_track`、`register_task_to_track`，并在 `_cmd_prepare` 中通过 `binding_service.write_product_session_binding` 写 binding。
- `scripts/env/services/runs.py`：当前 `commit_buddy_run` 会调用 `_apply_track_effect`、`env_store.register_task_to_track`、`env_store.update_task`、`env_store.create_artifact`、`env_store.add_run_to_task`，并在 `commit_for_active_instance` 后写 binding。
- `scripts/env/services/bindings.py`：当前 `resolve_binding_from_payload` 和 `persist_binding_from_payload` 支持从 prepare payload 或 receipt 推导 binding。
- `scripts/env/services/context.py`：当前 `_validate_context_payload` 要求 prepared context 有 `current_task_id`，context revision 仍按 task run count 推导。
- `scripts/env/services/evidence.py`：当前 evidence issuance 要求 `context.current_task_id`，token scope 也要求 task id。
- `scripts/env/services/artifacts.py`：当前 `_validate_source_run` 要求 reservation 的 `task_id` 等于 artifact task id。
- `scripts/env/services/tasks.py`：已经是正确的 task lifecycle 显式 env tool 服务，应保留。
- `scripts/env/services/tracks.py`：`attach_task_to_track` 和 `detach_task_from_track` 是显式 env tool task-track linkage，应保留并在文档中声明边界。
- `scripts/env/tools/dispatch.py`、`scripts/env/tools/router.py`、`scripts/env/tools/contracts.py`：已经提供正向 env tool loop，应保留。
- `framework/contracts/persist-buddy-run.json`：当前 receipt 仍要求 `task_id`、`task_title`。
- `framework/contracts/prepare-turn-context.json`：当前 response shape 没有 `binding_snapshot`，且 `task_context` 隐含为对象。
- `framework/docs/turn-runtime-spec.md`、`framework/docs/skill-runtime-shared-rules.md`、`framework/docs/track-registry.md`、`framework/docs/architecture-overview.md`：仍有“每个 run 属于 task”和 `state_effects.task|track` 指导。
- `buddyswitch/skills/shared/task-tool/SKILL.md`：正向 task lifecycle skill，需要强化为唯一 task lifecycle path。
- `buddyswitch/skills/shared/artifact-tool/SKILL.md`：正向 artifact revision skill，需要声明 persist 不写 artifact content。
- `buddyswitch/skills/shared/track-tool/SKILL.md`：正向 track tool，需要声明 attach/detach 是显式 task-track linkage path。
- `tools/launcher/assets/buddies/*/AGENTS.md`：receipt 当前要求 task，PM AGENTS 仍提到 `state_effects.track`。
- `tests/test_turn_runtime.py`、`tests/test_prepare_runtime_context.py`、`tests/test_turn_integration.py`、`tests/test_env_layer_end_to_end.py`、`tests/test_host_decision_surface_product_mode.py`：当前多处依赖 prepare auto-task 和 persist side effects。
- `tests/test_task_env_tool.py`、`tests/test_track_env_tool.py`、`tests/test_artifact_env_tool.py`、`tests/test_context_binding_env_tool.py`：显式 env tool 行为测试，应保留并用于防回归。

### 运行命令

- 聚焦 runtime：`python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py tests/test_prepare_runtime_context.py tests/test_run_env_services.py -q`
- 聚焦 env tool：`python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_context_binding_env_tool.py -q`
- 聚焦 broker/集成：`python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py tests/test_env_layer_end_to_end.py tests/test_host_decision_surface_product_mode.py -q`
- 全量验证：`python3 -m pytest -p no:cacheprovider tests -q`

### 保留、替换、删除、迁移

- 保留：`scripts/env/services/tasks.py` 的 task CRUD 与 binding 行为。
- 保留：`scripts/env/services/tracks.py` 的 PM lifecycle 和 active-buddy `attach_task` / `detach_task`。
- 保留：`scripts/env/services/artifacts.py` 的 artifact revision 写入路径，但调整 reservation-task 校验以支持 taskless prepare 后显式选择 task。
- 保留：runtime broker active instance、active buddy、status、protocol、env.tool envelope 校验。
- 替换：`turn_runtime._build_prepare_turn_context` 中的 task/track auto-create 分支，改成只读取 binding snapshot 和上下文。
- 替换：`scripts/env/services/runs.py` 的 write-heavy commit，改成 audit-only commit。
- 替换：persist result contract，从 `artifacts` 和 `state_effects` 写入请求改成 `task_id`、`track_id`、`artifact_ids` association metadata。
- 删除：`turn_runtime._derive_task_id` 在 prepare 中的使用。
- 删除：`turn_runtime._derive_task_title` 在 prepare 中的使用。
- 删除：`turn_runtime._validate_context_revision` 对 task object 的依赖，替换为 run-envelope revision validation。
- 删除：`turn_runtime._cmd_prepare` 中 post-prepare binding update。
- 删除：`turn_runtime._cmd_persist`、`runtime_kernel.broker._persist_dispatch`、`run_service.commit_for_active_instance` 中 post-persist binding update。
- 删除：`binding_service.resolve_binding_from_payload`、`binding_service.persist_binding_from_payload`、`binding_service.write_product_session_binding`，除非实施时发现还有非 runtime 的真实调用；当前 `rg` 结果显示只有 prepare/persist bypass 使用它们。
- 不迁移：历史 `buddyswitch/objects/tasks/*.json`、`tracks/*.json`、`artifacts/*.json` schema，不做数据 shape 变更。

## 4. 最终目标架构

### 文件结构

- 修改 `scripts/turn_runtime.py`：prepare 只构造 run envelope、binding snapshot、context projection、hints；persist CLI 只调用 run service。
- 修改 `scripts/env/services/runs.py`：run reservation 支持 optional task association；commit 只验证 result metadata、保存 run audit、清 reservation、返回 receipt。
- 修改 `scripts/env/services/bindings.py`：保留 `current_binding`、`write_instance_binding`、`get_binding`、`set_task_binding`、`set_track_binding`、`clear_binding`；删除 prepare/persist 推导 binding 的 helper。
- 修改 `scripts/env/services/context.py`：context projection 支持 `task_context: null`，prepared context validation 支持 taskless run envelope。
- 修改 `scripts/env/services/evidence.py`：evidence token 绑定 run、instance、buddy、context_revision；`task_id` 变为可选 token metadata。
- 修改 `scripts/env/services/artifacts.py`：artifact creation 仍要求 task id；reservation 如果有 task id 必须匹配 artifact task id，如果 reservation task id 为 `null` 则只校验 run、instance、buddy。
- 修改 `scripts/runtime_kernel/broker.py`：`_persist_dispatch` 不再从 receipt/refreshed context 写 binding。
- 修改 `framework/contracts/prepare-turn-context.json`：加入 `binding_snapshot`，允许 `task_context` 为 `null`。
- 修改 `framework/contracts/persist-buddy-run.json`：request boundary 改为 `active_buddy + reserved run envelope + optional binding snapshot + optional association metadata`；receipt 必填移除 task fields。
- 修改 `framework/docs/turn-runtime-spec.md`、`framework/docs/skill-runtime-shared-rules.md`、`framework/docs/track-registry.md`、`framework/docs/architecture-overview.md`：描述 taskless run 和显式 env tool lifecycle。
- 修改 `buddyswitch/skills/shared/task-tool/SKILL.md`、`artifact-tool/SKILL.md`、`track-tool/SKILL.md`：写清 task、artifact、track linkage 的唯一写入路径。
- 修改 `tools/launcher/assets/buddies/market/AGENTS.md`、`pm/AGENTS.md`、`design/AGENTS.md`、`dev/AGENTS.md`、`test/AGENTS.md`：Receipt 的 task 变成 optional，移除 `state_effects` lifecycle 指导。
- 新增 `tests/test_task_management_skill_architecture.py`：集中覆盖 handoff memo 的新边界和 static scans。
- 修改现有 runtime、integration、env tool tests：把 old auto-task 预期改为 explicit task-tool workflow。

### 核心数据模型

Prepared context:

```json
{
  "ok": true,
  "context_revision": "ctx-run-<run-id>",
  "instance_id": "<launcher-instance-id>",
  "active_buddy": "<buddy-id>",
  "binding_snapshot": {
    "instance_id": "<launcher-instance-id>",
    "current_task_id": "<task-id-or-null>",
    "current_track_id": "<track-id-or-null>",
    "binding_state": "unbound|bound_task_only|bound_track_only|bound_task_and_track|stale"
  },
  "current_task_id": "<task-id-or-null>",
  "current_track_id": "<track-id-or-null>",
  "task_context": null,
  "track_context": null,
  "run_envelope": {
    "run_id": "run-<hex>",
    "status": "reserved",
    "sequence": 1,
    "turn_identity": {
      "instance_id": "<launcher-instance-id>",
      "active_buddy": "<buddy-id>",
      "request_text": "<input>",
      "task_id": "<task-id-or-null>",
      "track_id": "<track-id-or-null>",
      "context_revision": "ctx-run-<run-id>",
      "sequence": 1,
      "run_id": "run-<hex>"
    }
  }
}
```

Persist result:

```json
{
  "execution_summary": "non-empty summary",
  "working_notes": ["optional notes"],
  "task_id": "optional explicit task association",
  "track_id": "optional explicit track association",
  "artifact_ids": ["optional explicit artifact ids already written by artifact-tool"],
  "handoff": {
    "next_buddy": "optional manifest buddy id",
    "reason": "non-empty",
    "context": "non-empty"
  },
  "contributors": {
    "skills": ["skill ids"],
    "agents": ["agent ids"]
  },
  "tool_evidence": {
    "browser_cockpit_token": "optional market token",
    "approved_downgrade_token": "optional market token"
  }
}
```

Receipt:

```json
{
  "ok": true,
  "buddy_id": "<active-buddy>",
  "run_id": "<run-id>",
  "artifact_ids": [],
  "next_state": {
    "task_id": null,
    "track_id": null,
    "current_buddy": "<active-buddy>",
    "next_buddy": null,
    "mode": "taskless_audit|task_associated|handoff|track_associated"
  },
  "receipt_paths": {
    "run": "buddyswitch/content/runs/<run-id>.json"
  },
  "related_run_ids": []
}
```

When `task_id`, `track_id`, or `artifact_ids` are supplied and validated, receipt includes their paths as references in `receipt_paths`; `writes` in run audit still contains only the run audit path.

### 接口、函数、调用流

Prepare call flow:

```text
runtime broker prepare or turn_runtime CLI
  -> turn_runtime.prepare_turn_context
  -> _build_prepare_turn_context
  -> _binding_snapshot_from_product_session
  -> context_service.build_task_context(existing_task) only when task exists
  -> context_service.build_track_context(existing_track_id) only when track exists
  -> _derive_run_context_revision(run_id)
  -> run_service.save_run_reservation(task_id=optional)
  -> context_save_path write under runs/raw/<buddy>/
```

Persist call flow:

```text
runtime broker persist, env.tool run.commit, or turn_runtime CLI
  -> run_service.commit_buddy_run
  -> _normalize_audit_commit
  -> _validate_run_envelope
  -> _validate_association_metadata
  -> _validate_handoff
  -> _validate_market_tool_evidence
  -> env_store.save_run_content
  -> run_service.clear_run_reservation
  -> receipt
```

Explicit task lifecycle flow:

```text
host
  -> .agents/skills/task-tool/SKILL.md
  -> python3 scripts/env/client.py task <operation>
  -> runtime broker method env.tool
  -> scripts/env/tools/router.py
  -> scripts/env/tools/dispatch.py
  -> scripts/env/services/tasks.py
  -> buddyswitch/objects/tasks/*.json or instance binding
```

Function boundaries:

- Add `turn_runtime._binding_snapshot_from_product_session(product_session, active_buddy) -> dict[str, Any]`.
- Add `turn_runtime._derive_run_context_revision(run_id: str) -> str`.
- Replace `turn_runtime._validate_context_revision(context)` with `turn_runtime._validate_prepared_run_context(context) -> dict[str, Any]` returning normalized `run_id`, optional `task_id`, optional `track_id`, and `context_revision`.
- Change `turn_runtime._build_turn_identity(..., task_id: str | None, track_id: str | None, ...)`.
- Change `turn_runtime._save_run_reservation(..., task_id: str | None, ...)`.
- Change `run_service.save_run_reservation(task_id: str | None, ...)`.
- Change `run_service.find_active_task_reservation(task_id: str)` to skip task concurrency when `task_id` is `None`.
- Replace `run_service._normalize_commit` with audit-only validation that does not require `stored_task`.
- Add `run_service._validate_association_metadata(result, active_buddy, binding_snapshot) -> dict[str, Any]`.
- Change `run_service._build_next_state(task_id: str | None, track_id: str | None, ...)`.
- Change `run_service._receipt_paths(run_content_path_value, task_id, artifact_ids, track_id)` to include task path only when `task_id` is non-null.
- Change `run_service._build_run_audit` to accept optional task/track/artifact refs and never call mutation APIs.
- Change `artifact_service._validate_source_run` so reservation `task_id: null` does not reject an explicit artifact task selected after prepare.
- Change `evidence_service._context_matches_active_instance` and `_write_evidence_token` so token scope task fields are optional.
- Change `context_service._validate_context_payload` to validate `context_revision == "ctx-" + run_id` and no longer require current task.

## 5. 分阶段实施计划

### 阶段一：用失败测试锁定新边界

**目标**

先让 handoff memo 的核心边界变成可执行测试：unbound prepare 不写 task，显式三次 task create 只写三份 task，persist audit-only，state effects 被拒绝，static scan 禁止 runtime 绕过 task-tool。

**具体文件变更**

- 新增 `tests/test_task_management_skill_architecture.py`
- 修改 `tests/test_turn_runtime.py`
- 修改 `tests/test_prepare_runtime_context.py`
- 修改 `tests/test_run_env_services.py`
- 修改 `tests/test_env_tool_response_contract.py`

**详细步骤**

1. 在 `tests/test_task_management_skill_architecture.py` 新建 `TaskManagementSkillArchitectureTests(RuntimeWorkspaceTestMixin, unittest.TestCase)`。
2. 添加 helper `_instance_json(buddy, instance_id, current_task_id=None, current_track_id=None)`，写入 launcher-style instance JSON。
3. 添加 helper `_dispatch(method, payload, instance_json, instance_id, buddy)`，调用 `runtime_kernel.broker.dispatch_runtime_request`。
4. 添加 helper `_env_tool(...)`，发送 `env.tool` envelope 并断言 `ok=true`。
5. 添加 `test_unbound_prepare_creates_no_task_files`：空 binding instance 调用 broker `prepare` 后，断言 `buddyswitch/objects/tasks` 目录不存在或无 json，payload `current_task_id is None`、`task_context is None`、`runtime_context.decision_surface.binding_state.state == "unbound"`、reservation `task_id is None`。
6. 添加 `test_stale_task_binding_is_reported_without_repair`：instance JSON 写 `current_task_id="task-missing"`，prepare 后断言没有创建 `task-missing.json`，`binding_state.state == "stale"`，warnings 包含 `W_STALE_TASK_BINDING`。
7. 添加 `test_three_explicit_task_creates_produce_exactly_three_task_files`：prepare 一次后通过 `task.create` 创建三个指定 task id，断言 tasks 目录只有这三个文件，且没有从 request text 派生出的 `task-pm-3-task-landing-page-*`。
8. 添加 `test_taskless_persist_writes_run_audit_only`：taskless prepare 后以 `{"execution_summary":"recorded taskless discussion"}` 调用 `run.commit`，断言 receipt 没有 `task_id`，run audit 存在，tasks/tracks/artifacts 目录保持空。
9. 添加 `test_persist_rejects_state_effects_task_with_task_tool_guidance`：taskless prepare 后 result 带 `state_effects.task`，断言 `ok=false`、`permission_boundary=="persist.state_effects"`、`allowed_next_actions` 包含 `task.update`。
10. 添加 `test_persist_rejects_state_effects_track_with_track_tool_guidance`：result 带 `state_effects.track`，断言反馈包含 `track.update` 或 `track.create`。
11. 添加 `test_persist_does_not_mutate_task_object_or_instance_binding`：先通过 `task.create` 和 `task.set_current` 创建并绑定 task，prepare 后保存 task JSON 与 instance JSON 快照，persist result 只带 `execution_summary` 和 `task_id`，断言 task JSON 与 instance JSON 不变，run audit 写入。
12. 添加 `test_prepare_and_persist_paths_do_not_call_task_mutation_apis`：扫描 `scripts/turn_runtime.py`、`scripts/env/services/runs.py`、`scripts/runtime_kernel/broker.py`，禁止出现 `create_task(`、`update_task(`、`add_run_to_task(`、`create_artifact(`、`register_task_to_track(`、`write_product_session_binding(`、`persist_binding_from_payload(`，允许 test file 自身通过字符串拼接表达禁用 tokens。
13. 修改 `tests/test_prepare_runtime_context.py::test_prepare_runtime_context_capability_boundary_matches_manifest_and_profiles`，把 expected `allowed_state_effects.task` 改为空列表或移除该断言，新增断言 persist hint optional 不包含 `state_effects`。
14. 修改 `tests/test_env_tool_response_contract.py::test_each_env_tool_has_success_response_with_canonical_machine_readable_fields`，`run.validate_result` 的 result 改成 audit-only shape，不再使用 embedded artifact creation。
15. 修改 `tests/test_run_env_services.py` 的 delegation result fixture，移除 `state_effects.task`。

**预期行为变化**

这些测试在当前代码上失败，失败点对应 memo 中的泄漏：prepare 自动创建 task、persist 修改 task/artifact/track/binding、state effects 被接受、static scan 命中 bypass API。

**对应需求编号**

`REQ-001` 至 `REQ-023`。

**验证命令**

```bash
python3 -m pytest -p no:cacheprovider tests/test_task_management_skill_architecture.py -q
python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_runtime_context_capability_boundary_matches_manifest_and_profiles tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_each_env_tool_has_success_response_with_canonical_machine_readable_fields tests/test_run_env_services.py -q
```

**阶段完成标准**

新增测试全部以预期边界失败；失败信息能定位到自动 task 创建、persist task mutation、post-persist binding update、state effects 接受或 static scan 命中。

### 阶段二：prepare 与 reservation 解耦

**目标**

让 `prepare` 在空 binding 下只产生 taskless run envelope，不再创建或修复 task/track，不再写 instance binding。

**具体文件变更**

- 修改 `scripts/turn_runtime.py`
- 修改 `scripts/env/services/runs.py`
- 修改 `scripts/env/services/context.py`
- 修改 `framework/contracts/prepare-turn-context.json`
- 修改 `tests/test_turn_runtime.py`
- 修改 `tests/test_prepare_runtime_context.py`

**详细步骤**

1. 在 `turn_runtime.py` 删除 import list 中未用于 prepare/read 的 mutation imports：`create_task`、`create_track`、`register_task_to_track`、`create_artifact`、`add_run_to_task`、`update_track`。
2. 新增 `_derive_run_context_revision(run_id: str) -> str`，返回 `f"ctx-{run_id}"`，并通过 `env_store.require_id` 或当前 run id 格式校验输入非空。
3. 修改 `_build_turn_identity` 参数 `task_id` 为 `str | None`，`track_id` 为 `str | None`，输出保留这两个 key 且允许 null。
4. 新增 `_binding_snapshot_from_product_session(product_session, active_buddy)`：读取 `product_session["payload"]` 的 `current_task_id` 与 `current_track_id`；调用 `get_task` 和 `get_track` 只读查询；输出 `binding_state` 和 warnings。
5. `_binding_snapshot_from_product_session` 对 `current_task_id` 存在但 `get_task` 为 `None` 时，返回 `binding_state="stale"`、`task_context=None`、warning code `W_STALE_TASK_BINDING`，不调用 task create。
6. `_binding_snapshot_from_product_session` 对 `current_track_id` 存在但 `get_track` 为 `None` 时，返回 `binding_state="stale"`、`track_context=None`、warning code `W_STALE_TRACK_BINDING`，不调用 track create。
7. 修改 `_build_prepare_turn_context`：删除 explicit task/track repair 分支和 `_derive_task_id` auto-create 分支；使用 binding snapshot 决定 top-level `current_task_id` 和 `current_track_id`。
8. 修改 `_build_prepare_turn_context`：当 no task binding 时设置 `task_context = None`；当 task exists 时调用 `context_service.build_task_context(existing_task)`。
9. 修改 `_build_prepare_turn_context`：当 no track binding 且 task has track_id 时，可只读读取该 track 作为 derived read context，但 `binding_snapshot.current_track_id` 仍只反映 instance binding；若 task 的 `track_id` 缺失对象，返回 stale warning。
10. 修改 `_build_prepare_turn_context`：先生成 `run_id`，再生成 `context_revision = _derive_run_context_revision(run_id)`，`sequence` 固定为 `1`。
11. 修改 `_save_run_reservation` wrapper 和 `run_service.save_run_reservation` 签名，允许 `task_id: str | None`。
12. 修改 `run_service.save_run_reservation`：仅当 `task_id` 是非空字符串且 `instance_id` 非空时执行 `find_active_task_reservation(task_id)`。
13. 修改 reservation JSON，保留 `"task_id": null`，并保留 `instance_id`、`context_revision`、`turn_identity`。
14. 修改 `_cmd_prepare`：删除 `binding_service.resolve_binding_from_payload` 和 `write_product_session_binding` 调用；prepare 成功后只打印 payload。
15. 修改 `context_service.build_decision_surface`、`summarize_current_context`，参数 `task_context` 允许 `None`，无 task 时 summary task 为 null。
16. 修改 `framework/contracts/prepare-turn-context.json`：`response_key_order` 加入 `binding_snapshot`；说明 `task_context` nullable；`runtime_context_required_sections` 保留 `decision_surface`。
17. 修改 `tests/test_turn_runtime.py` 中依赖 auto-created task 的测试：`test_prepare_accepts_switch_prefixed_text_as_ordinary_request` 断言 `current_task_id is None`、task directory empty、reservation task_id null。
18. 修改 `tests/test_prepare_runtime_context.py` 中 fresh prepare 的 binding state 预期：fresh market/pm/dev/design/test prepare 为 `unbound`。

**预期行为变化**

空绑定实例调用 prepare 后不会产生 `buddyswitch/objects/tasks/*.json`，不会写 `current_task_id` 到 instance JSON，reservation 允许 `task_id: null`。

**对应需求编号**

`REQ-002`、`REQ-003`、`REQ-004`、`REQ-005`、`REQ-006`、`REQ-007`、`REQ-017`、`REQ-019`。

**验证命令**

```bash
python3 -m pytest -p no:cacheprovider tests/test_task_management_skill_architecture.py::TaskManagementSkillArchitectureTests::test_unbound_prepare_creates_no_task_files tests/test_task_management_skill_architecture.py::TaskManagementSkillArchitectureTests::test_stale_task_binding_is_reported_without_repair -q
python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py::TurnRuntimeBuddyRunTests::test_prepare_accepts_switch_prefixed_text_as_ordinary_request tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_returns_runtime_context_for_each_buddy -q
```

**阶段完成标准**

聚焦 prepare tests 通过；`rg -n "create_task\\(|create_track\\(|register_task_to_track\\(" scripts/turn_runtime.py` 没有命中；空 binding prepare 后 tasks/tracks 目录不新增文件。

### 阶段三：persist 改为 audit-only

**目标**

让所有 persist 入口只保存 run audit，不再修改 task、track、artifact、binding，并更新 result/receipt 合同。

**具体文件变更**

- 修改 `scripts/env/services/runs.py`
- 修改 `scripts/turn_runtime.py`
- 修改 `scripts/runtime_kernel/persist.py`
- 修改 `framework/contracts/persist-buddy-run.json`
- 修改 `tests/test_turn_runtime.py`
- 修改 `tests/test_run_env_services.py`

**详细步骤**

1. 在 `runs.py` 删除 `_apply_track_effect`。
2. 在 `runs.py` 删除 commit 中对 `env_store.register_task_to_track`、`env_store.update_task`、`env_store.create_artifact`、`env_store.add_run_to_task` 的调用。
3. 新增 `_validate_prepared_run_context(context, active_buddy, request_text)` 或复用 `turn_runtime._validate_prepared_run_context`，校验 `ok`、`context_revision`、`run_envelope.run_id`、`turn_identity.instance_id`、`turn_identity.active_buddy`、`turn_identity.request_text`、reservation identity。
4. 修改 `_normalize_commit`：不再调用 `rt._validate_context_revision(context)`；不再要求 `current_task_id` 是字符串；不再读取 `stored_task`。
5. 新增 `_reject_retired_persist_fields(result)`：如果 result 含 `state_effects`，抛 `RuntimeFeedbackError`，`permission_boundary="persist.state_effects"`，`allowed_next_actions` 明确包含 `python3 scripts/env/client.py task update --payload <json-file>` 和 `python3 scripts/env/client.py track update --payload <json-file>`；如果 result 含 `artifacts`，反馈指向 `python3 scripts/env/client.py artifact create-revision --payload <json-file>`。
6. 新增 `_validate_association_metadata(result, active_buddy, binding_snapshot)`：校验 optional `task_id` 为现有 active-buddy task；optional `track_id` 为现有 track；optional `artifact_ids` 为现有 artifact id，且每个 artifact 属于 supplied task 或 active-buddy owned task。
7. `_validate_association_metadata` 对 taskless run 返回 `task=None`、`track=None`、`artifact_ids=[]`。
8. 修改 `_validate_handoff` 保持现有 manifest buddy 校验；handoff 不触发 track mutation。
9. 修改 `_validate_market_tool_evidence`，使用 run envelope context revision，不要求 task object。
10. 修改 `_build_next_state` 支持 `task_id: None`；mode 规则为：有 handoff next buddy 时 `"handoff"`，无 task 且无 track 时 `"taskless_audit"`，有 task 时 `"task_associated"`，只有 track 时 `"track_associated"`。
11. 修改 `_receipt_paths`：始终包含 run path；task path、track path、artifact paths 只在对应 metadata validated 后加入。
12. 修改 `_build_run_audit`：字段包含 `run_id`、`timestamp`、`buddy_id`、`instance_id`、`request_text`、`context_revision`、optional `task_id`、optional `track_id`、`artifact_ids`、`execution_summary`、`working_notes`、`handoff`、`contributors`、`tool_evidence`、`next_state`、`receipt_paths`、`related_run_ids`、`writes`；`writes` 只包含 run audit path。
13. 修改 `commit_buddy_run`：保存 audit 后调用 `clear_run_reservation(run_id)`，返回 audit-only receipt。
14. 修改 `validate_run_result`：返回 durable signals 为 `task_association`、`track_association`、`artifact_refs`、`handoff`，不再返回 state effects。
15. 修改 `framework/contracts/persist-buddy-run.json`：`commit_optional_keys` 改为 `working_notes`、`task_id`、`track_id`、`artifact_ids`、`handoff`、`contributors`、`tool_evidence`；`receipt_required_keys` 移除 `task_id`、`task_title`；`receipt_optional_keys` 加入 `task_id`、`task_title`。
16. 修改 `turn_runtime._build_persist_field_desc`、`_build_runtime_context` 的 persist hint：移除 `artifacts` 和 `state_effects`，新增 `task_id`、`track_id`、`artifact_ids` metadata 说明。
17. 保留 `turn_runtime.persist_buddy_run` 对 `run_service.commit_buddy_run` 的 delegation。
18. 修改 `tests/test_turn_runtime.py` 中 artifact/state_effect persist tests：把 artifact creation 测试迁移到 `tests/test_artifact_env_tool.py`；run persist tests 只断言 run audit 和 receipt。

**预期行为变化**

`persist` 成功后只新增 `buddyswitch/content/runs/<run-id>.json`，不改 task JSON，不改 track JSON，不写 artifact JSON，不写 instance JSON。`state_effects` 和 embedded `artifacts` 会得到结构化拒绝。

**对应需求编号**

`REQ-008`、`REQ-009`、`REQ-010`、`REQ-011`、`REQ-013`、`REQ-014`、`REQ-019`、`REQ-021`、`REQ-022`。

**验证命令**

```bash
python3 -m pytest -p no:cacheprovider tests/test_task_management_skill_architecture.py::TaskManagementSkillArchitectureTests::test_taskless_persist_writes_run_audit_only tests/test_task_management_skill_architecture.py::TaskManagementSkillArchitectureTests::test_persist_rejects_state_effects_task_with_task_tool_guidance tests/test_task_management_skill_architecture.py::TaskManagementSkillArchitectureTests::test_persist_rejects_state_effects_track_with_track_tool_guidance tests/test_task_management_skill_architecture.py::TaskManagementSkillArchitectureTests::test_persist_does_not_mutate_task_object_or_instance_binding -q
python3 -m pytest -p no:cacheprovider tests/test_run_env_services.py tests/test_env_tool_response_contract.py -q
```

**阶段完成标准**

Audit-only persist tests 通过；`rg -n "register_task_to_track\\(|update_task\\(|create_artifact\\(|add_run_to_task\\(" scripts/env/services/runs.py` 没有命中；contract test 确认 receipt task fields 可选。

### 阶段四：调整 artifact、evidence、context 对 taskless run 的支持

**目标**

保证 taskless prepare 后，buddy 可以显式创建或绑定 task，再用 artifact-tool 写 artifact，并用同一个 reserved run id 作为 source run；Market evidence 不再因 prepared context taskless 被错误拒绝。

**具体文件变更**

- 修改 `scripts/env/services/artifacts.py`
- 修改 `scripts/env/services/evidence.py`
- 修改 `scripts/env/services/context.py`
- 修改 `tests/test_artifact_env_tool.py`
- 修改 `tests/test_runtime_tool_feedback.py`
- 修改 `tests/test_context_binding_env_tool.py`

**详细步骤**

1. 在 `artifacts.py::_validate_source_run` 中保留 run reservation existence、status、run_id、instance_id、active_buddy 校验。
2. 修改 `artifacts.py::_validate_source_run`：读取 `reservation.get("task_id")`；如果是非空字符串则必须等于 artifact `task_id`；如果为 `None` 则允许 artifact task id 来自 payload 或 current binding。
3. 在 `artifacts.py::_source_run_error` 的 `allowed_next_actions` 中加入 `Use task.create and task.set_current before artifact.create_revision when prepare was taskless.`。
4. 修改 `evidence.py::_context_matches_active_instance`：不再要求 `prepared_context.current_task_id`；校验 `run_envelope.run_id`、`context_revision`、`instance_id`、`active_buddy`。
5. 修改 `evidence.py::_write_evidence_token`：`token_scope` 和 `tool_evidence` 中 `task_id` 可为 null；`track_id` 可为 null。
6. 修改 `turn_runtime._validate_market_tool_evidence`：token scope task id 不再必填；如果 token 有 task id 且 result 有 task id，两者不一致时拒绝；token 无 task id 时只校验 run、instance、buddy、context_revision。
7. 修改 `context.py::_validate_context_payload`：supplied context 可以 `current_task_id is None`；若有 task id 才做 task lookup 和 task scope/revision checks；context revision 统一校验 run-derived value。
8. 修改 `context.py::current_context_sections`：无 binding 时返回 `task_context=None` 或 response `task_context` 为 `{"task": None, ...}` 的选择必须与 prepare contract 一致；本计划选择 env tool `context.get` 返回 section object、prepare top-level 返回 null。
9. 新增 `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_create_revision_allows_taskless_prepare_source_run_after_explicit_task_selection`：taskless prepare，task.create，task.set_current，artifact.create_revision 使用 prepare run_id，断言 artifact 写入。
10. 新增 `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_create_revision_rejects_mismatched_bound_reservation_task`：bound task prepare 后尝试给另一个 task 写 artifact，断言 `E_ARTIFACT_SOURCE_RUN`。
11. 新增 `tests/test_runtime_tool_feedback.py::RuntimeToolFeedbackTests::test_market_evidence_issue_accepts_taskless_prepare_context`：market taskless prepare 后 issue evidence，断言 token scope task_id 为 null 且 token 文件写入。
12. 修改 context binding tests 中 supplied taskless context 的 rejection 预期，改为成功读取 active unbound context。

**预期行为变化**

Artifact 仍必须关联 task，但该 task 可以在 prepare 后由 buddy 通过 task-tool 显式选择；evidence token 不再把 task 当作 run envelope 必填字段。

**对应需求编号**

`REQ-007`、`REQ-011`、`REQ-012`、`REQ-019`、`REQ-022`、`REQ-024`。

**验证命令**

```bash
python3 -m pytest -p no:cacheprovider tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_create_revision_allows_taskless_prepare_source_run_after_explicit_task_selection tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_create_revision_rejects_mismatched_bound_reservation_task -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_tool_feedback.py::RuntimeToolFeedbackTests::test_market_evidence_issue_accepts_taskless_prepare_context tests/test_context_binding_env_tool.py -q
```

**阶段完成标准**

Taskless prepare 后的 explicit task + artifact path 通过；bound reservation 仍防止 artifact 写到错误 task；Market evidence 对 taskless run 可签发 run-scoped token。

### 阶段五：清理 binding bypass 和保留显式 env tool authority

**目标**

删除所有 prepare/persist receipt-derived binding 写入，只保留 `task.set_current`、`binding.set_task`、`binding.clear` 和 PM `binding.set_track`。

**具体文件变更**

- 修改 `scripts/env/services/bindings.py`
- 修改 `scripts/turn_runtime.py`
- 修改 `scripts/runtime_kernel/broker.py`
- 修改 `scripts/env/services/runs.py`
- 修改 `tests/test_task_env_tool.py`
- 修改 `tests/test_context_binding_env_tool.py`
- 修改 `tests/test_runtime_broker.py`

**详细步骤**

1. 删除 `bindings.py::write_product_session_binding`。
2. 删除 `bindings.py::resolve_binding_from_payload`。
3. 删除 `bindings.py::persist_binding_from_payload` 和 `_receipt_has_binding_update_warning`。
4. 删除 `turn_runtime._mark_committed_binding_update_failed`，因为 persist 不再写 binding。
5. 确认 `turn_runtime._cmd_prepare` 不写 binding。
6. 确认 `turn_runtime._cmd_persist` 不写 binding。
7. 修改 `runtime_kernel.broker._persist_dispatch`，删除 `binding_service.persist_binding_from_payload` 和 `write_product_session_binding` 调用。
8. 修改 `run_service.commit_for_active_instance`，删除 persist 后 binding writeback。
9. 保留 `binding_service.write_instance_binding`，它仍被 `task_service.set_current_task`、`binding.set_task_binding`、`binding.set_track_binding`、`binding.clear_binding` 使用。
10. 修改 `tests/test_task_env_tool.py::test_set_current_and_get_current_sync_instance_binding`，继续证明 `task.set_current` 写 binding。
11. 修改 `tests/test_context_binding_env_tool.py::test_binding_get_and_set_task_sync_active_instance_json`，继续证明 `binding.set_task` 写 binding。
12. 新增 `tests/test_task_management_skill_architecture.py::test_prepare_and_persist_do_not_rewrite_instance_binding`：prepare 和 persist 前后 instance JSON byte-equivalent，除非中间执行 explicit binding env tool。
13. 修改 `tests/test_runtime_broker.py` 中 persist 成功后的 binding 预期，改为不变。

**预期行为变化**

prepare 和 persist 不再改变 active instance JSON；binding 变化只发生在显式 env tool 调用时。

**对应需求编号**

`REQ-015`、`REQ-016`、`REQ-017`、`REQ-018`、`REQ-023`、`REQ-024`。

**验证命令**

```bash
python3 -m pytest -p no:cacheprovider tests/test_task_management_skill_architecture.py::TaskManagementSkillArchitectureTests::test_prepare_and_persist_do_not_rewrite_instance_binding tests/test_task_env_tool.py::TaskManagerEnvToolTests::test_set_current_and_get_current_sync_instance_binding tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_binding_get_and_set_task_sync_active_instance_json -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py tests/test_run_env_services.py -q
```

**阶段完成标准**

`rg -n "write_product_session_binding|persist_binding_from_payload|resolve_binding_from_payload|_mark_committed_binding_update_failed" scripts` 没有命中；explicit binding env tool tests 仍通过。

### 阶段六：更新 skills、AGENTS、framework docs 和 runtime hints

**目标**

让 host-facing guidance 与新架构一致：task 是 optional workflow object，task lifecycle 只能通过 task-tool，persist 只记录 run audit。

**具体文件变更**

- 修改 `buddyswitch/skills/shared/task-tool/SKILL.md`
- 修改 `buddyswitch/skills/shared/artifact-tool/SKILL.md`
- 修改 `buddyswitch/skills/shared/track-tool/SKILL.md`
- 修改 `tools/launcher/assets/buddies/market/AGENTS.md`
- 修改 `tools/launcher/assets/buddies/pm/AGENTS.md`
- 修改 `tools/launcher/assets/buddies/design/AGENTS.md`
- 修改 `tools/launcher/assets/buddies/dev/AGENTS.md`
- 修改 `tools/launcher/assets/buddies/test/AGENTS.md`
- 修改 `framework/docs/turn-runtime-spec.md`
- 修改 `framework/docs/skill-runtime-shared-rules.md`
- 修改 `framework/docs/track-registry.md`
- 修改 `framework/docs/architecture-overview.md`
- 修改 `framework/docs/skill-architecture-best-practices.md`
- 修改 `framework/contracts/*.md` 中提到 receipt/task/persist lifecycle 的 buddy contract。
- 修改 `tests/test_repo_consistency.py`

**详细步骤**

1. 在 `task-tool/SKILL.md` Purpose 中写明：它是 task create/list/get/get-current/set-current/update/archive 的唯一 lifecycle path。
2. 在 `task-tool/SKILL.md` Guardrails 中加入：prepare 和 persist 不会创建、更新、绑定 task；unbound context 是正常状态。
3. 在 `artifact-tool/SKILL.md` Do Not Use When 中写明：persist 不再写 artifact content；创建 revision 必须使用 `artifact.create_revision`。
4. 在 `artifact-tool/SKILL.md` Payload Hints 中写明：`source_run_id` 来自 prepare reserved run；taskless prepare 后先用 task-tool 选择 task。
5. 在 `track-tool/SKILL.md` Purpose 中写明：`attach-task`/`detach-task` 是显式 task-track linkage path；persist 不会 register task to track。
6. 修改所有 buddy AGENTS 的 Receipt：`task` 改为 optional；Receipt 包含 persisted status、buddy、run id、optional task、optional track、optional artifact ids、optional handoff。
7. 修改 PM AGENTS：删除 “track permissions shown in allowed_state_effects.track” 的写法，改为 `track-tool` 和 `prepare.runtime_context.env_tools.track`。
8. 修改 `turn-runtime-spec.md`：Prepare behavior 改为读取 binding snapshot；Persist contract 改为 audit-only；Receipt task fields 改为 optional。
9. 修改 `skill-runtime-shared-rules.md`：删除 “Track lifecycle mutations must use state_effects.track” 和 “Task updates must use state_effects.task”，改为 task/track/artifact env tool。
10. 修改 `track-registry.md`：把 “Every persisted run belongs to a task” 改为 “A run may include an optional task_id association”；把 auto-register rule 限定为 track-tool attach/detach 或 env_store helper used by those services。
11. 修改 `architecture-overview.md`：BuddySwitch persists run audit; task/artifact/track writes are explicit env tools。
12. 修改 `skill-architecture-best-practices.md`：persist shape 不再列 `state_effects.task`，并声明 native skill action must call env tool for state writes。
13. 修改 buddy contract markdown：把 required task receipt 语言改为 optional task association。
14. 在 `tests/test_repo_consistency.py` 增加 `test_active_guidance_does_not_reference_persist_state_effect_task_lifecycle`，扫描 active docs、skills、AGENTS 禁止 `state_effects.task`、`state_effects.track` lifecycle 指导和 “Every persisted run belongs to a task”。

**预期行为变化**

Host-facing docs 和 runtime hints 不再把 persist 当成 task/track/artifact mutation API；buddy 可从 prepare feedback 直接看到 task-tool、track-tool、artifact-tool 命令。

**对应需求编号**

`REQ-001`、`REQ-013`、`REQ-015`、`REQ-018`、`REQ-021`、`REQ-022`、`REQ-025`。

**验证命令**

```bash
python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_exposes_tool_requirements_and_persist_payload_hints tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_runtime_context_exposes_desc_for_commit_fields -q
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
```

**阶段完成标准**

Active guidance scan 通过；prepare runtime hints 不包含 `state_effects.task` 或 `state_effects.track` 作为 persist lifecycle path；skills 指向 env tool commands。

### 阶段七：改造集成流并完成广义验证

**目标**

把旧的 persist side-effect 集成流改成显式 env tool flow，证明 taskless runs 和 explicit task workflows 都能运行。

**具体文件变更**

- 修改 `tests/test_env_layer_end_to_end.py`
- 修改 `tests/test_turn_integration.py`
- 修改 `tests/test_host_decision_surface_product_mode.py`
- 修改 `tests/test_runtime_tool_feedback.py`
- 修改 `tests/test_parallel_contracts.py`
- 修改 `tests/test_artifact_selection.py` 如果存在 receipt task 必填断言

**详细步骤**

1. 在 `tests/test_env_layer_end_to_end.py` 中保留 `_create_tracked_task`，让每个 buddy 通过 `task.create`、`track.attach_task`、`binding.set_task` 显式建 task。
2. 在 PM flow 中，用 `artifact.create_revision` 写 PRD artifact，再用 `run.commit` result 引用 `task_id`、`track_id`、`artifact_ids`、`handoff`。
3. 在 Market flow 中，先显式 task + track attach + binding，再 issue evidence，再 `artifact.create_revision` 写 market-scan，最后 audit-only `run.commit`。
4. 在 Design/Dev/Test flow 中同样用 artifact-tool 写 output artifact，然后 `run.commit` 引用 artifact id。
5. 修改集成断言：run audit `writes` 只包含 run path；artifact JSON 的 source_run_id 是 prepared run id；task status 只在 explicit `task.update` 或 `task.archive` 后变化。
6. 修改 `tests/test_turn_integration.py` 中 PM/Market/Design/Dev/Test commit fixtures，移除 embedded `artifacts` 和 `state_effects`，改为显式 env tool helper。
7. 修改 `tests/test_host_decision_surface_product_mode.py`：PM seed handoff 先通过 task/track/artifact env tool 建状态，再 audit-only persist。
8. 修改 `tests/test_runtime_tool_feedback.py`：invalid persist feedback 断言包括 task/track/artifact env tool guidance。
9. 修改 `tests/test_parallel_contracts.py`：contract freeze 对 receipt required task fields 的断言改为 optional。
10. 运行 static scan，修正遗漏的 active docs/tests 旧断言。

**预期行为变化**

端到端主路径中，所有 task、track、artifact 写入都发生在 env tool helper 中；run.commit 只保存 audit。显式 task workflow 仍能串起 track context、artifact context、handoff context。

**对应需求编号**

`REQ-001` 至 `REQ-026`。

**验证命令**

```bash
python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py tests/test_turn_integration.py tests/test_host_decision_surface_product_mode.py -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_tool_feedback.py tests/test_parallel_contracts.py -q
python3 -m pytest -p no:cacheprovider tests/test_task_management_skill_architecture.py tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py -q
```

**阶段完成标准**

所有改造后的集成流通过；三任务回归证明无隐藏第 4 个 task；explicit env tool writes 与 audit-only persist 的职责边界在 run audit、task objects、artifact objects、instance JSON 中可观察。

## 6. 迁移 / 删除策略

- 删除 runtime 中 prepare task/track creation 分支，不保留 compatibility branch。
- 删除 persist 中 task update、track update/register、artifact create、task run_ids append，不保留 `state_effects` 旧写入路径。
- 删除 receipt/refreshed-context derived binding writeback，不保留 post-persist binding fallback。
- 删除 bindings service 中只服务 runtime bypass 的 helper：`write_product_session_binding`、`resolve_binding_from_payload`、`persist_binding_from_payload`。
- 保留 env_store 低层 `create_task`、`update_task`、`register_task_to_track`、`create_artifact`，因为它们仍是 env tool services 的持久化 helper。
- 保留 `track.attach_task` 和 `track.detach_task` 在 `track-tool` 下。真实原因：它们已经是 broker-routed explicit env tool action，且 track membership 属于 track coordination state；退出条件不适用，因为这不是短期兼容路径。
- 保留 artifacts task-owned schema。真实原因：现有 object model、artifact-tool、context projection、track artifact index 都以 task-owned artifact 为事实；run-scoped artifact 是独立 schema 决策，本任务不引入。
- 不迁移历史对象。旧 task 的 `run_ids` 和 artifact slots 继续可读；新 run audit 不再向 task 追加 run id。
- 如果老测试 fixture 需要 task/track/artifact 状态，改为直接 seed env_store 或通过 env tool helper 显式创建；不通过 prepare/persist 间接创建。

## 7. 完成定义

整个任务完成必须同时满足：

- 空 binding `prepare` 不创建 task、track、artifact，不写 instance binding。
- bound stale task/track prepare 返回 stale signal，不创建替代对象。
- run reservation 可保存 `task_id: null` 并通过 persist 校验。
- taskless run commit 成功，只写 run audit 和 receipt。
- `persist` 对 `state_effects.task`、`state_effects.track`、embedded `artifacts` 返回结构化拒绝和 env tool 指引。
- 显式 `task.create` 三次只产生三份 task object。
- artifact revision 只能通过 `artifact.create_revision` 写入，且 source run 校验支持 taskless prepare 后显式选择 task。
- post-prepare 和 post-persist 不写 active instance binding。
- `task-tool`、`track-tool`、`artifact-tool`、AGENTS、framework docs、contracts 和 runtime hints 均描述 task as buddy-owned optional workflow object。
- Static scans 通过，防止 `prepare`、`persist`、run commit 路径重新调用 task mutation、track linkage、artifact creation、binding writeback helper。
- 聚焦验证命令通过：

```bash
python3 -m pytest -p no:cacheprovider tests/test_task_management_skill_architecture.py -q
python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py tests/test_prepare_runtime_context.py tests/test_run_env_services.py -q
python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_context_binding_env_tool.py -q
python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py tests/test_turn_integration.py tests/test_host_decision_surface_product_mode.py -q
```

- 最终验证命令通过：

```bash
python3 -m pytest -p no:cacheprovider tests -q
```
