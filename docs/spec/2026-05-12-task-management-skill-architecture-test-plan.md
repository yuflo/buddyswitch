# Task Management Skill Architecture Test Plan

## 1. 测试设计原则

测试从 handoff memo 的产品语义出发：系统只拥有 run 边界和 audit，task、track、artifact 写入必须由 buddy 通过 skill 和 broker-routed env tool 显式完成。测试不根据新实现的内部拆分来降低断言，而是验证外部可观察行为、持久化文件、CLI/API 输出、结构化错误和运行时提示。

- 所有 task 生命周期断言都以 `buddyswitch/objects/tasks/*.json`、active instance JSON、env tool response 和 receipt 为准。
- 所有 persist 断言都以 `buddyswitch/content/runs/*.json`、reservation 清理、receipt `next_state`、`writes` 列表为准。
- 所有 guidance 断言都使用 runtime hint、skills、AGENTS、framework docs 的静态扫描，防止旧 `state_effects.task|track` 路径回流。
- 测试数据必须包含 taskless run、bound task run、stale binding、explicit three-task creation、artifact after taskless prepare、Market evidence after taskless prepare。
- 每个高风险阶段都要有 focused pytest 命令；最终合并前必须运行整个 `tests` 目录。

## 2. 需求覆盖矩阵

| 需求 | 覆盖测试 |
| --- | --- |
| `REQ-001` | `TM-001`、`TM-008`、`TM-017`、`TM-021`、`TM-023` |
| `REQ-002` | `TM-001`、`TM-003`、`TM-018` |
| `REQ-003` | `TM-001`、`TM-002`、`TM-014`、`TM-022` |
| `REQ-004` | `TM-001`、`TM-009` |
| `REQ-005` | `TM-002`、`TM-010` |
| `REQ-006` | `TM-009`、`TM-011` |
| `REQ-007` | `TM-001`、`TM-005`、`TM-011`、`TM-012` |
| `REQ-008` | `TM-005`、`TM-006`、`TM-014`、`TM-018` |
| `REQ-009` | `TM-006`、`TM-015`、`TM-022` |
| `REQ-010` | `TM-007`、`TM-016`、`TM-022` |
| `REQ-011` | `TM-005`、`TM-012`、`TM-013`、`TM-018` |
| `REQ-012` | `TM-012`、`TM-013`、`TM-020` |
| `REQ-013` | `TM-005`、`TM-011`、`TM-021` |
| `REQ-014` | `TM-021`、`TM-024` |
| `REQ-015` | `TM-003`、`TM-017`、`TM-019`、`TM-023` |
| `REQ-016` | `TM-014`、`TM-017`、`TM-019` |
| `REQ-017` | `TM-001`、`TM-014`、`TM-019`、`TM-022` |
| `REQ-018` | `TM-007`、`TM-016`、`TM-017`、`TM-023` |
| `REQ-019` | `TM-001`、`TM-005`、`TM-011`、`TM-018` |
| `REQ-020` | `TM-003`、`TM-018` |
| `REQ-021` | `TM-015`、`TM-016`、`TM-023` |
| `REQ-022` | `TM-002`、`TM-006`、`TM-007`、`TM-012`、`TM-015` |
| `REQ-023` | `TM-022`、`TM-023` |
| `REQ-024` | `TM-012`、`TM-017`、`TM-020` |
| `REQ-025` | `TM-022`、`TM-023`、manual review `MV-001` |
| `REQ-026` | `TM-011`、`TM-012`、`TM-017`、`MV-002` |

`REQ-025` 的“不要引入 speculative abstraction”无法完全靠单个自动化测试证明，自动化扫描会禁止旧绕过路径和新增 runtime abstraction 关键字，人工验证 `MV-001` 会检查实际 diff 是否引入 workflow engine、event bus、DSL、长期双路径。`REQ-026` 的历史对象兼容性会通过既有 context/artifact/task tests 和 `MV-002` 的 fixture 检查确认，不执行数据迁移脚本。

## 3. 测试分层

### 单元测试

目的：验证 run reservation、commit normalization、association metadata、artifact source run、evidence token scope、context validation 的边界规则。

覆盖范围：

- `scripts/env/services/runs.py`
- `scripts/env/services/artifacts.py`
- `scripts/env/services/evidence.py`
- `scripts/env/services/context.py`
- `scripts/env/services/bindings.py`

运行命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_run_env_services.py tests/test_artifact_env_tool.py tests/test_runtime_tool_feedback.py tests/test_context_binding_env_tool.py -q
```

### 集成测试

目的：验证 broker prepare、env.tool、run.commit、artifact-tool、task-tool、track-tool 在同一个 runtime workspace 中组合后仍遵守权限边界。

覆盖范围：

- `tests/test_task_management_skill_architecture.py`
- `tests/test_turn_runtime.py`
- `tests/test_prepare_runtime_context.py`
- `tests/test_env_layer_end_to_end.py`
- `tests/test_turn_integration.py`

运行命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_task_management_skill_architecture.py tests/test_turn_runtime.py tests/test_prepare_runtime_context.py tests/test_env_layer_end_to_end.py tests/test_turn_integration.py -q
```

### CLI 或主路径运行测试

目的：验证 `scripts/env/client.py` 暴露给 skill 的命令是真实可用路径，`prepare` 和 `persist` 不是隐式 task 写入口。

覆盖范围：

- `task create`
- `task set-current`
- `track attach-task`
- `artifact create-revision`
- `run commit`

运行命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_env_tool_response_contract.py -q
```

### 回归测试

目的：防止第四个隐藏 task、persist side effects、receipt task 必填、post-persist binding writeback、runtime static bypass 重新出现。

覆盖范围：

- `tests/test_task_management_skill_architecture.py`
- `tests/test_repo_consistency.py`
- `tests/test_parallel_contracts.py`
- `tests/test_host_decision_surface_product_mode.py`

运行命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_task_management_skill_architecture.py tests/test_repo_consistency.py tests/test_parallel_contracts.py tests/test_host_decision_surface_product_mode.py -q
```

### 手动验证

目的：检查自动化不易完整表达的架构范围控制和历史数据不迁移承诺。

验证项：

- `MV-001`：查看最终 diff，确认没有新增 workflow engine、event bus、rule engine、plugin system、DSL、长期双路径 compatibility wrapper。
- `MV-002`：查看最终 diff，确认没有修改 `buddyswitch/objects/tasks/*.json`、`buddyswitch/objects/artifacts/*.json`、`buddyswitch/objects/tracks/*.json` 的历史 schema fixture 或迁移脚本。

## 4. 详细测试用例

### `TM-001` unbound prepare creates no task files

- 覆盖需求：`REQ-001`、`REQ-002`、`REQ-003`、`REQ-004`、`REQ-007`、`REQ-017`、`REQ-019`
- 用户/系统场景：PM buddy 收到普通用户输入，active instance 没有 current task binding。
- 前置条件：临时 runtime workspace；active instance JSON 存在；`buddyswitch/objects/tasks` 为空或不存在。
- 输入：broker `prepare` payload，`request_text` 为“创建3个task关于为三款产品分别制作简单的landing page”。
- 预期输出或状态变化：prepare response `ok=true`；`current_task_id is None`；`task_context is None`；`binding_state.state == "unbound"`；reservation JSON `task_id is None`；tasks 目录没有 json 文件。
- 断言重点：无 task file、无 instance binding 写入、reservation task nullable。
- 测试类型：集成回归。
- 建议测试文件路径和测试名称：`tests/test_task_management_skill_architecture.py::TaskManagementSkillArchitectureTests::test_unbound_prepare_creates_no_task_files`

### `TM-002` stale task binding is reported without repair

- 覆盖需求：`REQ-003`、`REQ-005`、`REQ-022`
- 用户/系统场景：instance JSON 指向已不存在的 task。
- 前置条件：active instance `current_task_id="task-missing"`；tasks 目录没有 `task-missing.json`。
- 输入：broker `prepare` payload。
- 预期输出或状态变化：prepare response `ok=true`；`binding_state.state == "stale"`；warnings 包含 `W_STALE_TASK_BINDING`；未创建 `task-missing.json`。
- 断言重点：stale feedback 取代 auto-repair。
- 测试类型：集成负向。
- 建议测试文件路径和测试名称：`tests/test_task_management_skill_architecture.py::TaskManagementSkillArchitectureTests::test_stale_task_binding_is_reported_without_repair`

### `TM-003` three explicit task creates produce exactly three task files

- 覆盖需求：`REQ-002`、`REQ-015`、`REQ-020`
- 用户/系统场景：PM buddy 按 skill 显式创建三个 landing page task。
- 前置条件：taskless prepare 已完成；tasks 目录为空。
- 输入：三次 `env.tool task.create`，task ids 为 `task-pm-landing-page-50cefcd4`、`task-pm-landing-page-ab3fd1f8`、`task-pm-landing-page-7ad912e7`。
- 预期输出或状态变化：tasks 目录只包含这三个 json 文件；不存在 `task-pm-3-task-landing-page-*`。
- 断言重点：没有系统派生第四个 task。
- 测试类型：集成回归。
- 建议测试文件路径和测试名称：`tests/test_task_management_skill_architecture.py::TaskManagementSkillArchitectureTests::test_three_explicit_task_creates_produce_exactly_three_task_files`

### `TM-004` task env tool preserves explicit ownership checks

- 覆盖需求：`REQ-015`、`REQ-024`
- 用户/系统场景：非 active buddy 试图更新另一个 buddy 的 task。
- 前置条件：PM 创建 task；active buddy 切换为 dev。
- 输入：`env.tool task.update` payload 指向 PM task。
- 预期输出或状态变化：response `ok=false`；error code 表示 scope 或 ownership 拒绝；PM task JSON 不变。
- 断言重点：显式 task path 仍保留权限边界。
- 测试类型：单元/集成负向。
- 建议测试文件路径和测试名称：`tests/test_task_env_tool.py::TaskManagerEnvToolTests::test_update_rejects_cross_buddy_task`

### `TM-005` taskless persist writes run audit only

- 覆盖需求：`REQ-008`、`REQ-011`、`REQ-013`、`REQ-019`
- 用户/系统场景：buddy 认为请求不需要 task，仅记录本轮 audit。
- 前置条件：taskless prepare 已完成；tasks/tracks/artifacts 目录为空。
- 输入：`run.commit` result `{"execution_summary":"recorded taskless discussion"}`。
- 预期输出或状态变化：receipt `ok=true`；receipt 不含 required `task_id`；`next_state.mode=="taskless_audit"`；仅新增 `buddyswitch/content/runs/<run-id>.json`；tasks/tracks/artifacts 目录仍为空。
- 断言重点：persist 只写 run audit。
- 测试类型：集成回归。
- 建议测试文件路径和测试名称：`tests/test_task_management_skill_architecture.py::TaskManagementSkillArchitectureTests::test_taskless_persist_writes_run_audit_only`

### `TM-006` persist rejects state_effects.task with task-tool guidance

- 覆盖需求：`REQ-009`、`REQ-022`
- 用户/系统场景：旧 host 尝试通过 persist 更新 task。
- 前置条件：taskless prepare 已完成。
- 输入：`run.commit` result 含 `state_effects: {"task": {"status": "done"}}`。
- 预期输出或状态变化：response `ok=false`；`permission_boundary=="persist.state_effects"`；`allowed_next_actions` 包含 `python3 scripts/env/client.py task update --payload <json-file>`；无 run audit 写入。
- 断言重点：拒绝旧 task side effect，并提供明确命令。
- 测试类型：负向回归。
- 建议测试文件路径和测试名称：`tests/test_task_management_skill_architecture.py::TaskManagementSkillArchitectureTests::test_persist_rejects_state_effects_task_with_task_tool_guidance`

### `TM-007` persist rejects state_effects.track with track-tool guidance

- 覆盖需求：`REQ-010`、`REQ-018`、`REQ-022`
- 用户/系统场景：旧 host 尝试通过 persist attach task to track。
- 前置条件：taskless prepare 已完成。
- 输入：`run.commit` result 含 `state_effects: {"track": {"task_ids": ["task-a"]}}`。
- 预期输出或状态变化：response `ok=false`；`allowed_next_actions` 包含 `track update`、`track attach-task` 或 `track detach-task` 命令；无 track JSON 写入。
- 断言重点：persist 不再是 track mutation surface。
- 测试类型：负向回归。
- 建议测试文件路径和测试名称：`tests/test_task_management_skill_architecture.py::TaskManagementSkillArchitectureTests::test_persist_rejects_state_effects_track_with_track_tool_guidance`

### `TM-008` persist rejects embedded artifact creation

- 覆盖需求：`REQ-008`、`REQ-011`、`REQ-022`
- 用户/系统场景：旧 host 尝试在 persist result 中携带 artifact content。
- 前置条件：prepare 已完成；artifacts 目录为空。
- 输入：`run.commit` result 含 `artifacts: [{"kind":"prd","content":"..."}]`。
- 预期输出或状态变化：response `ok=false`；`allowed_next_actions` 包含 `python3 scripts/env/client.py artifact create-revision --payload <json-file>`；artifacts 目录仍为空。
- 断言重点：artifact content 只能走 artifact-tool。
- 测试类型：负向回归。
- 建议测试文件路径和测试名称：`tests/test_run_env_services.py::RunEnvServiceTests::test_commit_rejects_embedded_artifacts_with_artifact_tool_guidance`

### `TM-009` prepare context revision derives from run envelope

- 覆盖需求：`REQ-004`、`REQ-006`
- 用户/系统场景：同一个 taskless instance 连续 prepare 两次。
- 前置条件：active instance 无 task binding。
- 输入：两次 broker `prepare` payload，request text 不同。
- 预期输出或状态变化：每次 response 的 `context_revision == "ctx-" + run_id`；不依赖 task run count；两次 run id 和 context revision 不同。
- 断言重点：revision 不从 task object 推导。
- 测试类型：单元/集成。
- 建议测试文件路径和测试名称：`tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_taskless_prepare_context_revision_derives_from_run_envelope`

### `TM-010` stale track binding is reported without repair

- 覆盖需求：`REQ-003`、`REQ-005`
- 用户/系统场景：instance JSON 指向不存在的 track。
- 前置条件：active instance `current_track_id="track-missing"`；tracks 目录没有该文件。
- 输入：broker `prepare` payload。
- 预期输出或状态变化：`binding_state.state=="stale"`；warnings 包含 `W_STALE_TRACK_BINDING`；未创建 track JSON。
- 断言重点：prepare 不修复 track binding。
- 测试类型：集成负向。
- 建议测试文件路径和测试名称：`tests/test_task_management_skill_architecture.py::TaskManagementSkillArchitectureTests::test_stale_track_binding_is_reported_without_repair`

### `TM-011` run reservation accepts null task id and preserves identity checks

- 覆盖需求：`REQ-006`、`REQ-007`、`REQ-013`、`REQ-019`、`REQ-026`
- 用户/系统场景：taskless run 被 prepare reserved，再用错误 instance id commit。
- 前置条件：taskless prepare 已完成；reservation `task_id is None`。
- 输入：`run.commit` payload 的 instance id 与 reservation 不一致。
- 预期输出或状态变化：response `ok=false`；error 指向 reservation identity mismatch；reservation 未被清理。
- 断言重点：task nullable 不削弱 run、instance、buddy、context_revision 校验。
- 测试类型：单元负向。
- 建议测试文件路径和测试名称：`tests/test_run_env_services.py::RunEnvServiceTests::test_taskless_reservation_still_requires_matching_instance_identity`

### `TM-012` artifact create revision allows taskless prepare source run after explicit task selection

- 覆盖需求：`REQ-007`、`REQ-011`、`REQ-012`、`REQ-022`、`REQ-024`、`REQ-026`
- 用户/系统场景：buddy taskless prepare 后决定创建 task，再写 artifact revision。
- 前置条件：taskless prepare 已完成；PM 通过 `task.create` 和 `task.set-current` 选择 task。
- 输入：`artifact.create_revision` payload 含 explicit `task_id`、`source_run_id` 为 prepare run id、artifact kind 和 content。
- 预期输出或状态变化：artifact JSON 写入；artifact source run id 等于 reserved run id；task id 等于 explicit selected task。
- 断言重点：artifact 仍 task-owned，但 source run 可来自 taskless reservation。
- 测试类型：集成。
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_create_revision_allows_taskless_prepare_source_run_after_explicit_task_selection`

### `TM-013` artifact create revision rejects mismatched bound reservation task

- 覆盖需求：`REQ-011`、`REQ-012`
- 用户/系统场景：bound task prepare 后试图把 source run 用于另一个 task 的 artifact。
- 前置条件：task A 已绑定并 prepare；task B 存在。
- 输入：`artifact.create_revision` payload 指向 task B，`source_run_id` 为 task A 的 reservation run id。
- 预期输出或状态变化：response `ok=false`；error code 为 `E_ARTIFACT_SOURCE_RUN`；未写 artifact JSON。
- 断言重点：taskless 放宽不破坏 bound reservation task 校验。
- 测试类型：负向集成。
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_create_revision_rejects_mismatched_bound_reservation_task`

### `TM-014` persist does not mutate task object or instance binding

- 覆盖需求：`REQ-003`、`REQ-008`、`REQ-016`、`REQ-017`
- 用户/系统场景：buddy 已显式绑定 task，persist 只记录 run audit。
- 前置条件：`task.create` 和 `task.set-current` 已完成；保存 task JSON 与 instance JSON byte snapshot。
- 输入：`run.commit` result 含 `execution_summary` 和 optional `task_id`。
- 预期输出或状态变化：run audit 写入；task JSON 与 instance JSON 完全等于 commit 前快照。
- 断言重点：task association metadata 不触发 task update 或 binding update。
- 测试类型：集成回归。
- 建议测试文件路径和测试名称：`tests/test_task_management_skill_architecture.py::TaskManagementSkillArchitectureTests::test_persist_does_not_mutate_task_object_or_instance_binding`

### `TM-015` runtime hints remove state_effects.task

- 覆盖需求：`REQ-009`、`REQ-021`、`REQ-022`
- 用户/系统场景：host 读取 prepare response 中的 persist payload hints。
- 前置条件：任意 buddy prepare 成功。
- 输入：prepare response `runtime_context.decision_surface` 和 persist command hints。
- 预期输出或状态变化：field descriptions 不包含 `state_effects.task`；包含 `task_id` optional association metadata；task write guidance 指向 `task-tool`。
- 断言重点：runtime 不再提示旧路径。
- 测试类型：集成回归。
- 建议测试文件路径和测试名称：`tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_runtime_context_exposes_desc_for_commit_fields`

### `TM-016` runtime hints remove state_effects.track

- 覆盖需求：`REQ-010`、`REQ-018`、`REQ-021`
- 用户/系统场景：PM host 读取 track-related guidance。
- 前置条件：PM prepare 成功。
- 输入：prepare response `runtime_context.env_tools.track` 和 persist hints。
- 预期输出或状态变化：persist hints 不包含 `state_effects.track`；track mutation guidance 指向 `track-tool` commands。
- 断言重点：track lifecycle 显式工具化。
- 测试类型：集成回归。
- 建议测试文件路径和测试名称：`tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_exposes_tool_requirements_and_persist_payload_hints`

### `TM-017` explicit binding and track linkage env tools remain valid

- 覆盖需求：`REQ-001`、`REQ-015`、`REQ-016`、`REQ-018`、`REQ-024`、`REQ-026`
- 用户/系统场景：PM 创建 task 与 track，并显式 attach task、set current task。
- 前置条件：active PM instance；tasks/tracks 目录为空。
- 输入：`task.create`、`track.create`、`track.attach-task`、`task.set-current`、`binding.get`。
- 预期输出或状态变化：task JSON 存在；track JSON `task_ids` 包含 task id；instance JSON current task 等于 task id；所有 response `ok=true`。
- 断言重点：显式 env tool authority 保留。
- 测试类型：CLI/集成。
- 建议测试文件路径和测试名称：`tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_explicit_task_track_binding_flow_replaces_persist_side_effects`

### `TM-018` end-to-end PM three-task workflow has no hidden fourth task

- 覆盖需求：`REQ-002`、`REQ-008`、`REQ-011`、`REQ-019`、`REQ-020`
- 用户/系统场景：原始问题中的 PM request 走完整 prepare、task.create 三次、run.commit。
- 前置条件：fresh PM workspace。
- 输入：原始 request text；三次 task create；audit-only commit。
- 预期输出或状态变化：tasks 目录恰好三个 task JSON；run audit 恰好一个；receipt `next_state.mode` 为 `taskless_audit` 或 explicit association mode，取决于 PM 是否显式 set current；不存在 hidden prepared task。
- 断言重点：复现并修复第四任务问题。
- 测试类型：端到端回归。
- 建议测试文件路径和测试名称：`tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_pm_three_explicit_tasks_do_not_create_hidden_prepare_task`

### `TM-019` prepare and persist never rewrite instance binding

- 覆盖需求：`REQ-015`、`REQ-016`、`REQ-017`
- 用户/系统场景：active instance binding 在 runtime prepare/persist 前后保持稳定。
- 前置条件：instance JSON 已有 current task 和 current track；保存 byte snapshot。
- 输入：broker `prepare` 后 `run.commit`。
- 预期输出或状态变化：instance JSON bytes 等于 snapshot；只有显式 `task.set-current` 或 `binding.set-task` 测试会改变它。
- 断言重点：删除 receipt/refreshed-context derived binding writeback。
- 测试类型：集成回归。
- 建议测试文件路径和测试名称：`tests/test_task_management_skill_architecture.py::TaskManagementSkillArchitectureTests::test_prepare_and_persist_do_not_rewrite_instance_binding`

### `TM-020` Market evidence accepts taskless prepare context

- 覆盖需求：`REQ-012`、`REQ-024`
- 用户/系统场景：Market buddy 在 taskless run 中签发浏览器证据 token。
- 前置条件：Market taskless prepare 已完成；Market evidence policy enabled。
- 输入：`env.tool evidence.issue` payload 使用 prepare context revision 和 run id，不包含 task id。
- 预期输出或状态变化：response `ok=true`；token file 写入；token scope `task_id is None`；token scope 包含 run id、instance id、active buddy、context revision。
- 断言重点：taskless 不削弱 Market evidence identity。
- 测试类型：集成。
- 建议测试文件路径和测试名称：`tests/test_runtime_tool_feedback.py::RuntimeToolFeedbackTests::test_market_evidence_issue_accepts_taskless_prepare_context`

### `TM-021` persist contract makes task fields optional

- 覆盖需求：`REQ-001`、`REQ-013`、`REQ-014`
- 用户/系统场景：contract freeze 检查 receipt 结构。
- 前置条件：`framework/contracts/persist-buddy-run.json` 已更新。
- 输入：load contract JSON。
- 预期输出或状态变化：`receipt_required_keys` 不包含 `task_id` 和 `task_title`；`commit_optional_keys` 包含 `task_id`、`track_id`、`artifact_ids`；contract 文案声明 task association optional。
- 断言重点：外部合同不再要求 every run belongs to task。
- 测试类型：合同回归。
- 建议测试文件路径和测试名称：`tests/test_parallel_contracts.py::ParallelContractsTests::test_persist_receipt_task_fields_are_optional`

### `TM-022` static scan blocks runtime bypass APIs

- 覆盖需求：`REQ-003`、`REQ-009`、`REQ-010`、`REQ-017`、`REQ-023`、`REQ-025`
- 用户/系统场景：开发者意外把 task mutation helper 加回 prepare 或 persist。
- 前置条件：repo checkout。
- 输入：扫描 `scripts/turn_runtime.py`、`scripts/env/services/runs.py`、`scripts/runtime_kernel/broker.py`。
- 预期输出或状态变化：禁止 token 不出现：`create_task(`、`update_task(`、`add_run_to_task(`、`create_artifact(`、`register_task_to_track(`、`write_product_session_binding(`、`persist_binding_from_payload(`。
- 断言重点：静态防线覆盖最容易回流的绕过点。
- 测试类型：静态回归。
- 建议测试文件路径和测试名称：`tests/test_task_management_skill_architecture.py::TaskManagementSkillArchitectureTests::test_prepare_and_persist_paths_do_not_call_task_mutation_apis`

### `TM-023` active guidance does not reference persist lifecycle state effects

- 覆盖需求：`REQ-001`、`REQ-015`、`REQ-018`、`REQ-021`、`REQ-023`、`REQ-025`
- 用户/系统场景：host 或 agent 阅读 skills、AGENTS、framework docs。
- 前置条件：docs and skill files updated。
- 输入：扫描 `buddyswitch/skills/shared/*.md`、`tools/launcher/assets/buddies/*/AGENTS.md`、`framework/docs/*.md`、`framework/contracts/*.json`。
- 预期输出或状态变化：active guidance 不把 `state_effects.task` 或 `state_effects.track` 描述为 lifecycle 写入路径；不出现 “Every persisted run belongs to a task”。
- 断言重点：prompt/guidance 与 runtime 边界一致。
- 测试类型：静态回归。
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_active_guidance_does_not_reference_persist_state_effect_task_lifecycle`

### `TM-024` run.validate_result accepts audit-only result

- 覆盖需求：`REQ-014`
- 用户/系统场景：host 在 commit 前调用 validation env tool。
- 前置条件：prepare 已完成。
- 输入：`run.validate_result` result `{"execution_summary":"validated audit only"}`。
- 预期输出或状态变化：response `ok=true`；durable signals 包含 `task_association: null`、`track_association: null`、`artifact_refs: []`；不要求 artifacts 或 task effects。
- 断言重点：validation contract 和 commit contract 一致。
- 测试类型：CLI/API。
- 建议测试文件路径和测试名称：`tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_run_validate_result_accepts_audit_only_payload`

## 5. 负向与边界测试

缺失数据：

- `TM-001` 覆盖无 task binding。
- `TM-002` 覆盖缺失 task object。
- `TM-010` 覆盖缺失 track object。
- `TM-020` 覆盖 taskless evidence token。

无效状态：

- `TM-004` 覆盖 cross-buddy task update。
- `TM-011` 覆盖 reservation identity mismatch。
- `TM-013` 覆盖 bound reservation task mismatch。

重复操作：

- 在 `tests/test_task_env_tool.py::TaskManagerEnvToolTests::test_create_rejects_duplicate_task_id` 保留或新增断言：重复 `task.create` 返回 structured error，原 task JSON 不变。
- 在 `tests/test_track_env_tool.py::TrackEnvToolTests::test_attach_task_is_idempotent_for_existing_membership` 保留或新增断言：重复 attach 不产生重复 task id。

并发或顺序敏感行为：

- `TM-011` 确认 taskless reservation 仍校验 instance identity。
- 现有 task-level reservation test 修改为：只有 explicit task binding 时才拒绝同 task active reservation；taskless reservations 依 run id 和 instance identity 校验。

空任务 / 空 track / 空 artifact：

- `TM-005` 覆盖没有 task、track、artifact 的 commit。
- `TM-012` 覆盖 taskless prepare 后 artifact 需要 explicit task selection。
- `TM-024` 覆盖 empty optional associations 的 validation response。

权限、路径、manifest、运行状态异常：

- `TM-004` 覆盖 active-buddy ownership。
- `TM-020` 覆盖 Market evidence policy。
- `tests/test_runtime_broker.py` 保留 inactive instance、wrong method、wrong active buddy、malformed envelope 的拒绝断言。
- `tests/test_prepare_runtime_context.py` 保留 manifest buddy membership 和 skill materialization 断言。

## 6. 作弊防护

- 三任务回归使用三个固定 task id，并断言 tasks 目录全集，而不是只断言 create response `ok=true`。
- Taskless persist 测试同时检查 receipt、run audit 文件、tasks/tracks/artifacts 目录和 instance JSON，防止实现只隐藏 receipt 字段。
- `state_effects.task`、`state_effects.track`、embedded `artifacts` 三个负向测试分别验证 response code、permission boundary、allowed next actions 和无持久化写入。
- Artifact tests 同时覆盖 taskless reservation allowed 和 bound reservation mismatch rejected，防止简单删除 task 校验。
- Static scan 覆盖 `turn_runtime.py`、`runs.py`、`broker.py` 三个 bypass 高风险文件，禁止关键 mutation token。
- Guidance scan 覆盖 skills、AGENTS、framework docs、contracts，防止代码改了但 host 继续被提示走旧路径。
- 测试数据包含 PM、Market、Design/Dev/Test 主路径，避免只为单一 buddy 硬编码。
- 所有断言验证状态和持久化结果，不只验证某个函数被调用。
- 负向测试不得因为实现困难而改成 weaker assertion；如果实际错误字段名不同，先统一 RuntimeFeedbackError contract，再更新断言名称。

## 7. 验证命令清单

Focused test commands:

```bash
python3 -m pytest -p no:cacheprovider tests/test_task_management_skill_architecture.py -q
python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py tests/test_prepare_runtime_context.py tests/test_run_env_services.py -q
python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_context_binding_env_tool.py -q
```

Broader verification commands:

```bash
python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py tests/test_turn_integration.py tests/test_host_decision_surface_product_mode.py -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_tool_feedback.py tests/test_env_tool_response_contract.py tests/test_parallel_contracts.py tests/test_repo_consistency.py -q
```

Static verification commands:

```bash
rg -n "create_task\\(|update_task\\(|add_run_to_task\\(|create_artifact\\(|register_task_to_track\\(|write_product_session_binding\\(|persist_binding_from_payload\\(" scripts/turn_runtime.py scripts/env/services/runs.py scripts/runtime_kernel/broker.py
rg -n "state_effects\\.task|state_effects\\.track|Every persisted run belongs to a task" buddyswitch/skills/shared tools/launcher/assets/buddies framework/docs framework/contracts
```

The expected result for both static commands is no output after implementation is complete.

Final verification command:

```bash
python3 -m pytest -p no:cacheprovider tests -q
```
