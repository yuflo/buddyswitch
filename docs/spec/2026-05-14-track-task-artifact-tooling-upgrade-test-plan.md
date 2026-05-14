# Track/Task/Artifact Tooling Upgrade Test Plan

## 1. 测试设计原则

- 测试从源 proposal 的外部可观察行为出发：用户看见 `track_id`、`task_id`、`artifact_id` 后，能通过同名 env tool 继续读取、加入、验证、提交。
- 测试验证 response JSON、CLI 参数、runtime state、instance binding、persisted handoff records、run audit、skill/AGENTS 文本投影；不只验证 service function 被调用。
- 测试优先覆盖用户工作流、系统不变量和失败模式：summary 不泄漏 full content，合法 relation 可读，非法 relation 可恢复，writes 不修改 foreign state，run commit 不修复状态。
- 新行为先写 failing tests；每个实现阶段都有 focused verification，不等最后统一发现 contract drift。
- 测试数据使用 PM、Design、Dev、Test、unrelated buddy、多 track、多 artifact revision，防止实现只硬编码单一 buddy、单一 kind、单一 id。
- 对 blocked artifact body reads，断言 serialized payload 不含 `content` key、seeded body string、preview、raw state path。
- 对 command hints 和 next actions，断言 action 存在于 `scripts/env/tools/contracts.py` registry，命令只能走 `python3 scripts/env/client.py ...`。

## 2. 需求覆盖矩阵

| Requirement | Test coverage |
| --- | --- |
| `REQ-001` | `TTA-E2E-001`, `TTA-TRACK-002`, `TTA-ART-003`, `TTA-TASK-002` |
| `REQ-002` | `TTA-CONTRACT-001`, `TTA-CLI-001`, `TTA-HANDOFF-001` |
| `REQ-003` | `TTA-TRACK-001` |
| `REQ-004` | `TTA-TRACK-002` |
| `REQ-005` | `TTA-TRACK-002`, `TTA-LEAK-001` |
| `REQ-006` | `TTA-JOIN-001`, `TTA-JOIN-002` |
| `REQ-007` | `TTA-JOIN-001`, `TTA-JOIN-004` |
| `REQ-008` | `TTA-JOIN-002`, `TTA-JOIN-003` |
| `REQ-009` | `TTA-ART-001`, `TTA-CLI-002` |
| `REQ-010` | `TTA-ART-001` |
| `REQ-011` | `TTA-ART-002`, `TTA-ART-003` |
| `REQ-012` | `TTA-ART-002` |
| `REQ-013` | `TTA-ART-003`, `TTA-E2E-001` |
| `REQ-014` | `TTA-ART-003` |
| `REQ-015` | `TTA-ART-004` |
| `REQ-016` | `TTA-ART-004`, `TTA-NEG-001`, `TTA-NEG-002`, `TTA-NEG-003` |
| `REQ-017` | `TTA-LEAK-001`, `TTA-LEAK-002` |
| `REQ-018` | `TTA-LEAK-001`, `TTA-CONTRACT-002` |
| `REQ-019` | `TTA-TASK-001` |
| `REQ-020` | `TTA-TASK-002` |
| `REQ-021` | `TTA-TASK-002`, `TTA-LEAK-003` |
| `REQ-022` | `TTA-HANDOFF-001` |
| `REQ-023` | `TTA-HANDOFF-002`, `TTA-HANDOFF-004` |
| `REQ-024` | `TTA-HANDOFF-003` |
| `REQ-025` | `TTA-RUN-001`, `TTA-RUN-002` |
| `REQ-026` | `TTA-RUN-003` |
| `REQ-027` | `TTA-CONTEXT-001`, `TTA-PREPARE-001` |
| `REQ-028` | `TTA-CONTEXT-002`, `TTA-REPO-001` |
| `REQ-029` | `TTA-CONTRACT-001`, `TTA-REPO-001` |
| `REQ-030` | `TTA-TRACK-002`, `TTA-ART-001`, `TTA-TASK-002` |
| `REQ-031` | `TTA-WRITE-001`, `TTA-RUN-003` |
| `REQ-032` | `TTA-WRITE-001`, `TTA-WRITE-002` |
| `REQ-033` | `TTA-CONTRACT-002`, `TTA-LEAK-001` |
| `REQ-034` | `TTA-CONTRACT-003`, `TTA-REPO-001` |
| `REQ-035` | `TTA-SKILL-002`, `TTA-AGENTS-001` |
| `REQ-036` | `TTA-SKILL-001`, `TTA-SKILL-002` |
| `REQ-037` | `TTA-REPO-001`, `TTA-CONTRACT-001` |
| `REQ-038` | `TTA-CONTRACT-001`, `TTA-CONTRACT-002`, `TTA-TRACK-002`, `TTA-ART-003`, `TTA-JOIN-001`, `TTA-HANDOFF-003`, `TTA-RUN-001`, `TTA-E2E-001` |
| `REQ-039` | `TTA-E2E-001` |
| `REQ-040` | `TTA-WORKTREE-001` |

所有需求都适合自动化测试。可选手动验证只用于真实 product instance CLI smoke，不替代 automated proof。

## 3. 测试分层

### 单元测试

目的：验证纯函数、store validation、relation decision、payload normalization、no-leak payload builder。

覆盖范围：

- `scripts/env/services/track_relations.py`
- `scripts/env_store.py`
- `scripts/env/services/handoffs.py`
- `scripts/env/services/runs.py`
- `scripts/env/tools/contracts.py`

运行命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_store_v2.py tests/test_artifact_env_tool.py tests/test_context_binding_env_tool.py tests/test_run_env_services.py tests/test_env_tool_router.py -q
```

### 集成测试

目的：验证 broker-routed `env.tool` envelope、registry、dispatch、services、runtime object writes 一起工作。

覆盖范围：

- `runtime_kernel.broker.dispatch_runtime_request`
- `scripts/env/tools/router.py`
- `scripts/env/tools/dispatch.py`
- Track/artifact/task/handoff/run services
- `tests.runtime_root_test_helper.RuntimeWorkspaceTestMixin`

运行命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_task_env_tool.py tests/test_context_binding_env_tool.py tests/test_run_env_tool.py tests/test_env_tool_response_contract.py -q
```

### CLI、API、UI 或主路径运行测试

目的：验证 skill-facing CLI 参数、dash/underscore action mapping、broker-unavailable structured JSON、product source intake 主路径。

覆盖范围：

- `python3 scripts/env/client.py track join --track-id <track-id>`
- `python3 scripts/env/client.py artifact list --track-id <track-id>`
- `python3 scripts/env/client.py artifact get --artifact-id <artifact-id>`
- `python3 scripts/env/client.py handoff list --track-id <track-id>`
- `python3 scripts/env/client.py handoff create --payload <json>`
- `python3 scripts/env/client.py run validate-result --context <json> --result <json>`

运行命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_cli_prints_structured_json_for_track_commands tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_cli_prints_structured_json_for_artifact_commands tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_handoff_cli_exposes_list_validate_and_create -q
python3 scripts/env/client.py track join --help
python3 scripts/env/client.py artifact list --help
python3 scripts/env/client.py handoff create --help
```

### 回归测试

目的：防止破坏 existing env tool contracts、artifact write rules、context projection、runtime skills、run commit audit behavior。

覆盖范围：

- Existing task/track/artifact write tests
- Context/binding tests
- Run idempotency and validation tests
- Runtime skill materialization
- Repo consistency scans

运行命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_task_env_tool.py tests/test_context_binding_env_tool.py tests/test_run_env_tool.py tests/test_run_env_services.py tests/test_env_tool_router.py tests/test_env_tool_response_contract.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

### 手动验证

目的：在真实 launcher workspace 中确认 direct-id commands 的 stdout shape 和人工可读 command hints。

手动步骤：

1. 在 dev2258 启动 Dev product instance：`./buddyswitch-codex instance start --buddy dev`。
2. 在已 seed track 的 runtime workspace 中执行 `python3 scripts/env/client.py track get --track-id <track-id>`。
3. 使用返回的 artifact id 执行 `python3 scripts/env/client.py artifact get --artifact-id <artifact-id>`。
4. 如果响应拒绝，执行返回的 `command_hint`。
5. 再次执行相同 `artifact.get`，确认 full body 出现在 success response 中。

手动验证只记录 observed JSON shape 和 command hint 可执行性；最终完成仍以 automated tests 为准。

## 4. 详细测试用例

### `TTA-CONTRACT-001`: registry、router、dispatch 覆盖目标 action surface

- 覆盖需求：`REQ-002`, `REQ-029`, `REQ-037`, `REQ-038`
- 用户 / 系统场景：runtime context 宣告的 env tool actions 与 router/dispatch 实际支持的 actions 一致。
- 前置条件：导入 `env.tools.contracts`、`env.tools.router`、`env.tools.dispatch`。
- 输入：读取 `TOOL_REGISTRY`，调用 `dispatch_handler_actions()`。
- 预期输出或状态变化：`track` 包含 `join`；`artifact.list` payload fields 为 `["track_id"]`；`handoff` 包含 `list`、`validate`、`create`；不存在 context artifact read actions 和 normal-path explain actions。
- 断言重点：registry、router `_TOOL_ACTIONS`、dispatch handler action sets 完全相同。
- 测试类型：contract 单元测试。
- 建议测试文件路径和测试名称：`tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions`。

### `TTA-CONTRACT-002`: collaboration-critical rejection fields

- 覆盖需求：`REQ-018`, `REQ-033`, `REQ-038`
- 用户 / 系统场景：artifact body read 被拒绝，工具响应本身说明如何恢复。
- 前置条件：PM artifact 存在，Dev 未 join 相关 track。
- 输入：broker envelope `{"tool":"artifact","action":"get","args":{"artifact_id":"art-pm-prd-r1"}}`。
- 预期输出或状态变化：`ok=false`；payload 包含 `why`、`permission_boundary`、`relation`、`missing_preconditions`、`next_actions`、`command_hint`、`no_content_leak=true`。
- 断言重点：不只返回 `permission denied`；恢复 action 可执行。
- 测试类型：contract 集成测试。
- 建议测试文件路径和测试名称：`tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_collaboration_critical_rejections_include_no_leak_recovery_fields`。

### `TTA-CONTRACT-003`: next actions 和 command hints 不指向 raw state

- 覆盖需求：`REQ-034`
- 用户 / 系统场景：tool feedback 给出下一步命令。
- 前置条件：构造 blocked artifact read、ambiguous join、invalid handoff、invalid run validate。
- 输入：收集每个 response 的 `next_actions` 和 `command_hint`。
- 预期输出或状态变化：每个 `next_actions[*].tool/action` 能在 registry 中解析；每个 `command_hint` 以 `python3 scripts/env/client.py` 开头。
- 断言重点：不包含 `buddyswitch/objects`、`buddyswitch/content/runs`、`runs/raw`、不存在 action 名称。
- 测试类型：contract 集成测试。
- 建议测试文件路径和测试名称：`tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_next_actions_reference_registered_tools_and_command_hints_use_env_client`。

### `TTA-TRACK-001`: `track.list` 返回 relevant candidate ordering

- 覆盖需求：`REQ-003`
- 用户 / 系统场景：Market/Dev 找到与自己最相关的 track。
- 前置条件：seed 四条 tracks：latest handoff target、next buddy only、participant only、unrelated。
- 输入：active buddy `market` 调用 `track.list`。
- 预期输出或状态变化：candidate order 为 handoff+next、next-only、participant；unrelated 不在 candidate summary。
- 断言重点：rows 包含 id、title、status、current buddy、next buddy、latest handoff summary、active-buddy relation、command hint。
- 测试类型：集成测试。
- 建议测试文件路径和测试名称：`tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_list_returns_relevance_ordered_candidates_with_next_command`。

### `TTA-TRACK-002`: `track.get` 返回 current artifact rows 且不泄漏 content

- 覆盖需求：`REQ-001`, `REQ-004`, `REQ-005`, `REQ-030`
- 用户 / 系统场景：Dev 查看 track，获得 PM PRD 和 Design handoff artifact ids。
- 前置条件：track 包含 PM task 和 Design task，各有 current artifact full body。
- 输入：active buddy `dev` 调用 `track.get --track-id track-landing`。
- 预期输出或状态变化：response 包含 `current_artifacts` rows，字段为 artifact id、kind、title、summary、source buddy、source task id、source run id、revision、currentness、readable flag、next action。
- 断言重点：serialized response 不含 seeded full body strings 和 `content` key。
- 测试类型：集成测试。
- 建议测试文件路径和测试名称：`tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_get_returns_current_artifact_rows_with_readability_and_next_actions`。

### `TTA-ART-001`: `artifact.list --track-id` 返回 summary rows

- 覆盖需求：`REQ-009`, `REQ-010`, `REQ-030`
- 用户 / 系统场景：用户想按 track 查看所有 current outputs。
- 前置条件：PM、Design、Dev tasks on same track; each has current artifact。
- 输入：`artifact.list` args `{"track_id":"track-landing"}`。
- 预期输出或状态变化：response `track_id` 正确，`artifacts` 包含全部 current rows；每行有 readability flag 和 next action。
- 断言重点：不返回 full content；rows 与 `track.get.current_artifacts` artifact id set 相同。
- 测试类型：集成测试。
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_list_by_track_returns_summary_rows_without_content`。

### `TTA-ART-002`: `artifact.get` 读取 owned current 和 owned historical

- 覆盖需求：`REQ-011`, `REQ-012`
- 用户 / 系统场景：Dev 读取自己任务的当前和上一版 implementation report。
- 前置条件：Dev task 有两版 `implementation-report` artifacts，revision 1 superseded，revision 2 current。
- 输入：分别调用 `artifact.get` with revision 1 id and revision 2 id。
- 预期输出或状态变化：两次 response `ok=true`，包含 full `content`，`relation="owner"`。
- 断言重点：owned historical read allowed；foreign historical 另测。
- 测试类型：集成测试。
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_get_allows_owned_artifacts_including_historical_revision`。

### `TTA-ART-003`: `artifact.get` 覆盖五种 legal track relation

- 覆盖需求：`REQ-001`, `REQ-011`, `REQ-013`, `REQ-014`
- 用户 / 系统场景：不同 buddy 因不同关系读取 current track artifact full body。
- 前置条件：每个 subtest seed current PM PRD artifact。
- 输入：active buddy 分别为 PM、Dev participant、Design current_buddy、Test next_buddy、Dev latest handoff recipient。
- 预期输出或状态变化：每个 subtest `artifact.get` success，`artifact.content` 等于 seeded body；relation 分别为 `pm_lifecycle_owner`、`participant`、`current_buddy`、`next_buddy`、`handoff_recipient`。
- 断言重点：只用 current artifact；不依赖 context action。
- 测试类型：集成测试。
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_get_allows_current_track_artifact_for_each_reasonable_relation`。

### `TTA-ART-004`: stale foreign artifact 被拒绝

- 覆盖需求：`REQ-015`, `REQ-016`
- 用户 / 系统场景：Dev 是 participant，但尝试读取 PM superseded artifact。
- 前置条件：PM PRD revision 1 superseded by revision 2；Dev task attached to track。
- 输入：Dev 调用 `artifact.get` revision 1 id。
- 预期输出或状态变化：`ok=false`，`permission_boundary="artifact.currentness"`，`no_content_leak=true`。
- 断言重点：response 不含 revision 1 body；relation-wide historical browsing 被阻止。
- 测试类型：负向集成测试。
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_get_rejects_stale_foreign_artifact_even_when_participant`。

### `TTA-JOIN-001`: `track.join` 创建、attach、select，且不改 lifecycle

- 覆盖需求：`REQ-006`, `REQ-007`
- 用户 / 系统场景：Dev 看到 track id 后直接 join。
- 前置条件：track exists with PM lifecycle fields; no Dev task on track。
- 输入：Dev 调用 `track.join --track-id track-landing`。
- 预期输出或状态变化：new Dev task created and attached；instance json current task/track updated；response `created_task=true`、`current_task_selected=true`、`relation="participant"`。
- 断言重点：track `status`、`current_buddy`、`next_buddy` unchanged；only task membership changes.
- 测试类型：集成写测试。
- 建议测试文件路径和测试名称：`tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_join_creates_attaches_and_selects_active_buddy_task_without_lifecycle_mutation`。

### `TTA-JOIN-002`: `track.join` 复用单个 existing task

- 覆盖需求：`REQ-006`, `REQ-008`
- 用户 / 系统场景：Dev 重复 join 同一个 track。
- 前置条件：one non-archived Dev task already attached to track。
- 输入：call `track.join` twice。
- 预期输出或状态变化：both responses return same `task_id`; second response `created_task=false`; track task_ids has no duplicate。
- 断言重点：idempotent reuse。
- 测试类型：集成写测试。
- 建议测试文件路径和测试名称：`tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_join_reuses_single_existing_active_buddy_task_idempotently`。

### `TTA-JOIN-003`: 多个 existing tasks 要求显式 task id

- 覆盖需求：`REQ-008`
- 用户 / 系统场景：Dev 在同一 track 有两个 active tasks，join 无法猜测。
- 前置条件：two non-archived Dev tasks attached to same track。
- 输入：join without `task_id`，then join with selected `task_id`。
- 预期输出或状态变化：first rejects with `permission_boundary="track.join_ambiguity"` and candidate task ids；second succeeds and selects specified task。
- 断言重点：first call no mutation；recovery command includes `--task-id`。
- 测试类型：边界集成测试。
- 建议测试文件路径和测试名称：`tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_join_rejects_multiple_existing_active_buddy_tasks_with_explicit_task_recovery`。

### `TTA-JOIN-004`: join 不接受 foreign task 或 other-track task

- 覆盖需求：`REQ-007`, `REQ-016`
- 用户 / 系统场景：Dev 提供不合法 `--task-id`。
- 前置条件：one PM task, one Dev task bound to another track。
- 输入：Dev calls join with each task id。
- 预期输出或状态变化：foreign task rejects `task.buddy_scope`; other-track task rejects `track.task_linkage`; no track/task/instance mutation。
- 断言重点：不能通过 join 夺取 foreign task 或跨 track 偷换 binding。
- 测试类型：负向写测试。
- 建议测试文件路径和测试名称：`tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_join_rejects_foreign_or_other_track_task_without_mutation`。

### `TTA-TASK-001`: `task.list` 包含 owned 和 relation-readable track tasks

- 覆盖需求：`REQ-019`
- 用户 / 系统场景：Dev 需要围绕相关 track 的其他 buddy tasks 定位 artifact ids。
- 前置条件：PM、Design、Dev tasks on related track；unrelated PM task on other track。
- 输入：Dev calls `task.list`。
- 预期输出或状态变化：related PM/Design/Dev tasks present；unrelated task absent。
- 断言重点：rows include task id、track id、owner buddy、status、current artifact ids、current-work status。
- 测试类型：集成读测试。
- 建议测试文件路径和测试名称：`tests/test_task_env_tool.py::TaskManagerEnvToolTests::test_task_list_includes_owned_and_relation_readable_track_tasks_with_current_artifact_ids`。

### `TTA-TASK-002`: `task.get` 返回 artifact summaries，不返回 bodies

- 覆盖需求：`REQ-001`, `REQ-020`, `REQ-021`, `REQ-030`
- 用户 / 系统场景：Dev 看到 PM task id 后 orient。
- 前置条件：Dev has participant relation to PM task track; PM task has current PRD with body string。
- 输入：Dev calls `task.get --task-id task-pm-prd`。
- 预期输出或状态变化：response includes task metadata、relation、current artifact summary rows and next action `artifact.get`。
- 断言重点：serialized response does not include PM body string or `content`。
- 测试类型：集成读测试。
- 建议测试文件路径和测试名称：`tests/test_task_env_tool.py::TaskManagerEnvToolTests::test_task_get_returns_artifact_summaries_and_points_to_artifact_get_without_body`。

### `TTA-HANDOFF-001`: `handoff.list` 合并 explicit records 和 run audit handoffs

- 覆盖需求：`REQ-002`, `REQ-022`
- 用户 / 系统场景：Dev 查看某 track handoffs，判断是否是 authorized recipient。
- 前置条件：one `buddyswitch/objects/handoffs/*.json` record to Dev；one run audit handoff to Test。
- 输入：Dev calls `handoff.list --track-id track-landing`。
- 预期输出或状态变化：rows include both records with source/target/source task/source run/artifact ids/status；Dev row `read_authorizes_active_buddy=true`。
- 断言重点：source_type differentiates `handoff_record` and `run_audit`; no lifecycle mutation。
- 测试类型：集成读测试。
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_handoff_list_merges_explicit_records_and_run_audit_handoffs`。

### `TTA-HANDOFF-002`: `handoff.validate` 校验 source ownership、ids、currentness

- 覆盖需求：`REQ-023`
- 用户 / 系统场景：Design 交付 design artifact 给 Dev 前先预检。
- 前置条件：Design task on track with current design artifact；also seed foreign PM artifact and superseded Design artifact。
- 输入：valid payload, then payloads with foreign artifact, superseded artifact missing historical flag, unknown target buddy, missing track。
- 预期输出或状态变化：valid response `ok=true` with normalized target; invalid responses have specific boundaries。
- 断言重点：no mutation for validate；historical artifact requires explicit marker。
- 测试类型：单元/集成负向测试。
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_handoff_validate_rejects_foreign_source_artifact_non_current_without_historical_flag_and_hidden_lifecycle_fields`。

### `TTA-HANDOFF-003`: `handoff.create` 写显式 record，不改 lifecycle

- 覆盖需求：`REQ-024`
- 用户 / 系统场景：Design creates handoff to Dev after writing design artifact。
- 前置条件：Design source task and current artifact exist on active track。
- 输入：`handoff.create` payload with track id, source task id, source run id, target buddy Dev, artifact ids, reason, context。
- 预期输出或状态变化：handoff object persisted under runtime root `buddyswitch/objects/handoffs`; response has handoff id and next action。
- 断言重点：track status/current buddy/next buddy unchanged。
- 测试类型：集成写测试。
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_handoff_create_validates_owned_sources_and_does_not_mutate_track_lifecycle`。

### `TTA-HANDOFF-004`: handoff hidden lifecycle fields rejected

- 覆盖需求：`REQ-023`
- 用户 / 系统场景：payload tries to smuggle lifecycle mutation through handoff。
- 前置条件：valid Design source task and artifact。
- 输入：handoff payload contains `track_status`, `current_buddy`, `next_buddy_override`, or `state_effects`。
- 预期输出或状态变化：`ok=false`, `permission_boundary="handoff.lifecycle_boundary"`。
- 断言重点：no handoff object is created；track unchanged。
- 测试类型：负向写测试。
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_handoff_create_rejects_hidden_lifecycle_fields_without_mutation`。

### `TTA-RUN-001`: `run.validate_result` catches invalid ids and handoff payloads

- 覆盖需求：`REQ-025`
- 用户 / 系统场景：before commit, result references invalid task/track/artifact/handoff ids。
- 前置条件：prepared PM or Dev context; runtime objects seeded。
- 输入：result variants with unknown task id, unknown track id, unknown artifact id, foreign artifact id, unknown target buddy, non-current artifact without historical marker。
- 预期输出或状态变化：each rejects with specific `permission_boundary`。
- 断言重点：validation does not write run audit。
- 测试类型：集成 validate test。
- 建议测试文件路径和测试名称：`tests/test_run_env_tool.py::RunManagerEnvToolTests::test_run_validate_result_rejects_invalid_handoff_ids_and_retired_mutation_fields`。

### `TTA-RUN-002`: retired mutation fields rejected with direct tool hints

- 覆盖需求：`REQ-025`, `REQ-034`
- 用户 / 系统场景：result tries to use retired persist-time lifecycle mutation or embedded artifacts。
- 前置条件：valid prepared context。
- 输入：result contains `state_effects` and result contains embedded `artifacts`。
- 预期输出或状态变化：reject boundaries `persist.state_effects` and `persist.artifacts`。
- 断言重点：allowed next actions mention `track update` / `track advance` / `track join` / `artifact create-revision`; no nonexistent `artifact.list_revisions` and no raw state path。
- 测试类型：regression negative test。
- 建议测试文件路径和测试名称：`tests/test_run_env_tool.py::RunManagerEnvToolTests::test_run_validate_result_rejects_retired_mutation_fields_with_existing_tool_hints`。

### `TTA-RUN-003`: `run.commit` 不修复 missing relation

- 覆盖需求：`REQ-026`, `REQ-031`
- 用户 / 系统场景：commit payload references a task/track/artifact shape that requires prior explicit tool action。
- 前置条件：Dev task not attached to referenced track; valid owned artifact exists on untracked task。
- 输入：`run.commit` with `task_id`, `track_id`, `artifact_ids`。
- 预期输出或状态变化：commit rejects; task remains untracked; track task_ids unchanged; no run audit written。
- 断言重点：commit is audit-only, not repair path。
- 测试类型：集成 write negative test。
- 建议测试文件路径和测试名称：`tests/test_run_env_tool.py::RunManagerEnvToolTests::test_run_commit_does_not_repair_missing_join_or_handoff_relation`。

### `TTA-CONTEXT-001`: context projection remains summary/snapshot surface

- 覆盖需求：`REQ-027`
- 用户 / 系统场景：prepared runtime context still provides summaries and candidate tracks.
- 前置条件：active buddy has bound task and track with current artifacts。
- 输入：prepare, `context.get`, `context.summarize`。
- 预期输出或状态变化：context contains `runtime_context.env_tools`, active binding, current summaries, candidate tracks。
- 断言重点：context projection does not advertise itself as direct artifact body read API。
- 测试类型：integration regression。
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_get_and_summarize_return_same_decision_surface_for_active_binding`。

### `TTA-CONTEXT-002`: context feedback 不出现 forbidden artifact read actions

- 覆盖需求：`REQ-028`
- 用户 / 系统场景：unbound user receives guidance after context summary.
- 前置条件：track with upstream artifacts exists; active buddy unbound。
- 输入：`context.summarize`, `context.get`, prepare payload。
- 预期输出或状态变化：serialized response contains `track.get` or `artifact.get` guidance, not forbidden context actions。
- 断言重点：forbidden strings absent: `context.get_track_artifacts`, `context.inspect_track_outputs`, `context.explain_track_access`, `context.validate_sources_available`。
- 测试类型：regression text/JSON test。
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_feedback_points_to_direct_artifact_tools_not_context_read_actions`。

### `TTA-PREPARE-001`: prepare exposes direct-id env tools

- 覆盖需求：`REQ-027`
- 用户 / 系统场景：host reads `prepare.runtime_context.env_tools` before acting。
- 前置条件：prepare for Dev and Design instances。
- 输入：broker `prepare` result。
- 预期输出或状态变化：`env_tools.track.operations` includes `join`; `env_tools.artifact.payload_fields.list == ["track_id"]`; `env_tools.handoff.operations` includes list/validate/create。
- 断言重点：operation semantics show mutability and authority；no context artifact read operations。
- 测试类型：prepare integration。
- 建议测试文件路径和测试名称：`tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_projects_direct_id_tool_surface_for_track_artifact_task_handoff`。

### `TTA-WRITE-001`: artifact writes remain active-buddy-owned

- 覆盖需求：`REQ-031`, `REQ-032`
- 用户 / 系统场景：Dev tries to write revision on PM task or update PM artifact metadata。
- 前置条件：PM task/artifact and Dev task/artifact exist。
- 输入：`artifact.create_revision` with PM task id; `artifact.update_metadata` with PM artifact id。
- 预期输出或状态变化：both reject with ownership boundary; snapshots unchanged。
- 断言重点：relation-aware reads do not weaken writes。
- 测试类型：regression negative write test。
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_foreign_artifact_reads_do_not_grant_write_or_metadata_update_scope`。

### `TTA-WRITE-002`: payload validation precedes revision creation

- 覆盖需求：`REQ-032`
- 用户 / 系统场景：Dev sends bad kind, non-object content, stale source run。
- 前置条件：Dev current task exists, run reservation fixture prepared。
- 输入：bad `artifact.create_revision` payload variants。
- 预期输出或状态变化：reject before artifact file creation。
- 断言重点：artifact/task snapshots unchanged。
- 测试类型：regression negative write test。
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_kind_content_source_run_and_update_metadata_boundaries_do_not_mutate`。

### `TTA-LEAK-001`: blocked body read 不泄漏 content

- 覆盖需求：`REQ-005`, `REQ-017`, `REQ-018`, `REQ-033`
- 用户 / 系统场景：unrelated Dev calls `artifact.get` on PM secret PRD。
- 前置条件：PM artifact content contains unique string `do-not-leak-cross-buddy-body`。
- 输入：Dev `artifact.get`。
- 预期输出或状态变化：reject with no-leak fields。
- 断言重点：`json.dumps(response)` does not contain unique string, `content`, `preview`, `partial`, raw state paths。
- 测试类型：negative security regression。
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_get_rejects_unrelated_foreign_artifact_with_no_content_leak_contract`。

### `TTA-LEAK-002`: malformed/unknown artifact id 也返回 no-leak body rejection

- 覆盖需求：`REQ-016`, `REQ-017`
- 用户 / 系统场景：host passes unknown or malformed artifact id。
- 前置条件：active Dev instance with no matching artifact。
- 输入：`artifact.get` with `artifact_id="missing-artifact"` and `artifact_id="../bad"`。
- 预期输出或状态变化：missing returns `artifact.lookup`; malformed returns `request-payload`; both include `no_content_leak=true`。
- 断言重点：no stack trace, no raw path。
- 测试类型：negative boundary test。
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_get_lookup_and_payload_errors_keep_body_no_leak_contract`。

### `TTA-LEAK-003`: task and track summaries never include foreign body

- 覆盖需求：`REQ-021`, `REQ-030`
- 用户 / 系统场景：Dev uses `track.get` and `task.get` on related PM data。
- 前置条件：PM artifact content includes unique body string。
- 输入：Dev `track.get`; Dev `task.get` on PM task。
- 预期输出或状态变化：both success summary responses。
- 断言重点：neither serialized payload contains body string or `content` key under foreign artifact rows。
- 测试类型：regression leak test。
- 建议测试文件路径和测试名称：`tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_and_task_summary_surfaces_do_not_include_foreign_artifact_body`。

### `TTA-NEG-001`: archived track blocks foreign relation read

- 覆盖需求：`REQ-016`
- 用户 / 系统场景：Dev has participant task on archived track but tries to read PM current artifact。
- 前置条件：track status archived, PM and Dev tasks attached。
- 输入：Dev `artifact.get` PM artifact id。
- 预期输出或状态变化：reject with `permission_boundary="track.lifecycle_status"` and `no_content_leak=true`。
- 断言重点：archived relation invalid。
- 测试类型：negative boundary test。
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_get_rejects_archived_track_relation_without_content`。

### `TTA-NEG-002`: artifact missing task/track association blocks foreign read

- 覆盖需求：`REQ-016`
- 用户 / 系统场景：artifact exists but its task is missing or not linked to track.
- 前置条件：orphan artifact JSON in runtime object store produced through controlled test fixture。
- 输入：Dev `artifact.get` orphan artifact id。
- 预期输出或状态变化：reject with `permission_boundary="artifact.track_association"` or `artifact.ownership"`。
- 断言重点：no full content; feedback names missing association。
- 测试类型：negative data consistency test。
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_get_rejects_missing_task_or_track_association_without_content`。

### `TTA-NEG-003`: artifact.list requires valid track id

- 覆盖需求：`REQ-016`
- 用户 / 系统场景：user calls `artifact.list` with missing, malformed, or unknown track id。
- 前置条件：active Dev instance。
- 输入：CLI no `--track-id`; service args `{}`; service args `{"track_id":"../bad"}`; service args `{"track_id":"track-missing"}`。
- 预期输出或状态变化：CLI returns exit 2 for missing; service rejects malformed/unknown with structured fields。
- 断言重点：no state mutation; command hint points to `track.list`。
- 测试类型：CLI and service negative test。
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_list_requires_existing_track_id`。

### `TTA-CLI-001`: CLI exposes new direct-id operations

- 覆盖需求：`REQ-002`
- 用户 / 系统场景：skill uses CLI help or commands。
- 前置条件：repo root dev2258; no broker needed for help。
- 输入：`python3 scripts/env/client.py track join --help`, `artifact list --help`, `handoff list --help`, `handoff create --help`。
- 预期输出或状态变化：help includes required flags。
- 断言重点：dash CLI maps to underscore action names in broker payload。
- 测试类型：CLI test。
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_handoff_cli_exposes_list_validate_and_create` plus existing track/artifact CLI tests.

### `TTA-CLI-002`: artifact CLI no-arg list is rejected

- 覆盖需求：`REQ-009`
- 用户 / 系统场景：old current-task list command is attempted。
- 前置条件：no broker needed for argparse path。
- 输入：`python3 scripts/env/client.py artifact list`。
- 预期输出或状态变化：exit code 2; stderr mentions required `--track-id`。
- 断言重点：no silent old semantics。
- 测试类型：CLI regression test。
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_cli_requires_track_id_for_list`。

### `TTA-SKILL-001`: shared skills teach direct workflow

- 覆盖需求：`REQ-036`
- 用户 / 系统场景：runtime skills are projected into product instance。
- 前置条件：manifest lists track/artifact/task/handoff/run shared skills。
- 输入：materialize runtime skills using existing runtime skill fixture。
- 预期输出或状态变化：projected skills include `track-tool`, `artifact-tool`, `task-tool`, `handoff-tool`, `run-tool`。
- 断言重点：artifact skill contains `artifact get --artifact-id`; track skill contains `track join --track-id`; no forbidden context read action strings。
- 测试类型：runtime skill regression。
- 建议测试文件路径和测试名称：`tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_tool_skills_project_direct_id_guidance`。

### `TTA-SKILL-002`: AGENTS guidance stays short and direct

- 覆盖需求：`REQ-035`, `REQ-036`
- 用户 / 系统场景：launcher projects buddy AGENTS.md。
- 前置条件：read `tools/launcher/assets/buddies/{pm,design,dev,test,market}/AGENTS.md`。
- 输入：plain text scan。
- 预期输出或状态变化：each template contains direct id lines and raw state prohibition。
- 断言重点：does not contain multi-step context route for artifact body read。
- 测试类型：repo text regression。
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_buddy_agents_contain_direct_id_artifact_read_boundary`。

### `TTA-AGENTS-001`: cannot claim artifact content without `artifact.get`

- 覆盖需求：`REQ-035`
- 用户 / 系统场景：buddy host instruction protects against summary-only claims。
- 前置条件：read all buddy AGENTS templates。
- 输入：text scan。
- 预期输出或状态变化：each file contains sentence equivalent to `Do not claim artifact content was read unless artifact.get returned the full body for that artifact id.`。
- 断言重点：instruction is present once and remains concise。
- 测试类型：repo text regression。
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_buddy_agents_require_artifact_get_before_claiming_content_read`。

### `TTA-REPO-001`: forbidden paths and speculative surfaces stay absent

- 覆盖需求：`REQ-028`, `REQ-029`, `REQ-034`, `REQ-037`
- 用户 / 系统场景：future edits do not reintroduce rejected proposal paths。
- 前置条件：scan active code, framework docs, skills, buddy AGENTS; exclude memo/spec archives。
- 输入：`rg` or test file scan for forbidden tokens。
- 预期输出或状态变化：no occurrence of context artifact read action names, normal-path `explain_*` tool names, generic ACL engine names, raw state recovery command hints。
- 断言重点：allows historical docs under `docs/memo` and `docs/spec`; blocks active guidance and code。
- 测试类型：repo consistency regression。
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_no_context_artifact_read_actions_or_raw_state_recovery_guidance`。

### `TTA-E2E-001`: PM -> Design -> Dev -> Test direct artifact id intake

- 覆盖需求：`REQ-001`, `REQ-013`, `REQ-039`
- 用户 / 系统场景：完整协作流通过 direct ids 读取 sources。
- 前置条件：runtime sandbox；PM, Design, Dev, Test instances。
- 输入：
  - PM creates track, task, PRD artifact。
  - Design reads PRD through `artifact.get`, writes design handoff artifact, creates handoff to Dev。
  - Dev uses `track.get`, `artifact.get`, `track.join`, `artifact.get` to read PM and Design sources, writes implementation artifact, creates handoff to Test。
  - Test uses `track.get` and `artifact.get` to read Dev output and upstream sources。
- 预期输出或状态变化：all full body reads come from `artifact.get`; each produced artifact is persisted on owned task; handoffs are explicit records or run audits。
- 断言重点：`env_tool_calls` contains no context-specific artifact read action; Dev/Test source body strings were observed only in `artifact.get` success responses。
- 测试类型：end-to-end acceptance。
- 建议测试文件路径和测试名称：`tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_pm_design_dev_test_direct_artifact_id_source_intake_without_context_read_action`。

### `TTA-WORKTREE-001`: changes stay in dev2258

- 覆盖需求：`REQ-040`
- 用户 / 系统场景：implementation does not pollute main checkout。
- 前置条件：run from `/Users/chen/Dev/buddyswitch/.worktrees/dev2258`。
- 输入：`pwd`, `git rev-parse --show-toplevel`, `git branch --show-current`, `git status --short`。
- 预期输出或状态变化：top-level path is `.worktrees/dev2258`; branch is `dev2258`; modified files are task-scoped。
- 断言重点：no edits in `/Users/chen/Dev/buddyswitch` main worktree。
- 测试类型：manual command verification before final handoff。
- 建议测试文件路径和测试名称：not automated; final verification command output must be recorded in implementation completion summary.

## 5. 负向与边界测试

- 缺失数据：
  - `artifact.get` missing artifact id: `TTA-LEAK-002`。
  - `artifact.list` missing track id: `TTA-NEG-003`。
  - `task.get` missing task id: existing response contract rejection plus new task tests。
  - `handoff.validate/create` missing source task id, target buddy, track id, reason, context: `TTA-HANDOFF-002` and existing handoff payload tests。
  - `run.validate_result` missing context/result: existing run payload tests plus `TTA-RUN-001`。
- 无效状态：
  - archived track relation: `TTA-NEG-001`。
  - missing task/track association: `TTA-NEG-002`。
  - superseded foreign artifact with participant relation: `TTA-ART-004`。
  - hidden lifecycle fields in handoff/run payload: `TTA-HANDOFF-004`, `TTA-RUN-002`。
- 重复操作：
  - repeated `track.join` reuses one existing task: `TTA-JOIN-002`。
  - duplicate artifact ids in run result dedupe remains covered by run service tests and must be preserved.
  - `handoff.create` with same payload creates a distinct auditable handoff id; list order and status are deterministic by timestamp/id.
- 并发或顺序敏感行为：
  - `track.join` multiple active-buddy tasks rejects before selecting: `TTA-JOIN-003`。
  - `run.commit` before explicit join rejects rather than repairing: `TTA-RUN-003`。
  - `artifact.get` before join rejects, same artifact after join succeeds: `TTA-E2E-001`。
- 空输入、空集合、空记录、空配置：
  - no tracks: existing `track.list` returns empty rows and candidate summary.
  - track with no tasks: `artifact.list --track-id` returns empty `artifacts` with command hint to `track.join` for active buddy.
  - task with no artifacts: `task.get` returns empty `current_artifacts` and no `content`.
  - handoff.list for track with no handoffs returns empty `handoffs` and command hint to `handoff.create` when active buddy has source task.
- 权限、路径、配置、运行状态、外部依赖：
  - foreign write attempts rejected: `TTA-WRITE-001`。
  - raw state recovery hints absent: `TTA-CONTRACT-003`, `TTA-REPO-001`。
  - malformed ids rejected without stack trace: `TTA-LEAK-002`, `TTA-NEG-003`。
  - broker unavailable CLI still returns structured JSON for supported commands: existing CLI tests extended for new commands.

## 6. 作弊防护

- 多 buddy、多 relation 测试防止实现把 Dev 或 PM 特判成唯一成功路径：`TTA-ART-003` 覆盖 PM、participant、current buddy、next buddy、handoff recipient。
- 多 artifact revision 测试防止实现只看 track relation 不看 currentness：`TTA-ART-002` and `TTA-ART-004` 区分 owned historical 和 foreign historical。
- No-leak tests 用 unique body strings 并序列化整个 response，防止实现只从 `artifact` field 删除 content 但从 error message、summary、preview 泄漏。
- Next action tests 反查 registry，防止 hardcoded nonexistent commands such as `artifact.list_revisions`。
- Snapshot tests 比较 track/task/artifact/instance JSON before and after rejected operations，防止实现先 mutate 再 reject。
- E2E records actual `env_tool_calls`，防止实现偷偷依赖 context-specific artifact body read action。
- Repo consistency scans 防止通过 skills/AGENTS 重新教旧 context route，而工具层测试已经要求 direct route。
- CLI tests 覆盖 dash operation names and service action names，防止只在 Python service 内通过而 skill-facing commands broken。
- Run commit tests 验证 state not repaired，防止把 hidden orchestration 塞进 audit commit path。
- `artifact.list --track-id` and `track.get` compare artifact id sets，防止一个 surface 漏掉 Design handoff 或 PM PRD。

## 7. 验证命令清单

Focused test commands:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_collaboration_critical_rejections_include_no_leak_recovery_fields -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_get_returns_current_artifact_rows_with_readability_and_next_actions -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_get_allows_current_track_artifact_for_each_reasonable_relation -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_join_creates_attaches_and_selects_active_buddy_task_without_lifecycle_mutation -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_handoff_create_validates_owned_sources_and_does_not_mutate_track_lifecycle -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_run_env_tool.py::RunManagerEnvToolTests::test_run_validate_result_rejects_invalid_handoff_ids_and_retired_mutation_fields -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_pm_design_dev_test_direct_artifact_id_source_intake_without_context_read_action -q
```

Broader verification commands:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_task_env_tool.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_context_binding_env_tool.py tests/test_run_env_tool.py tests/test_run_env_services.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py tests/test_env_tool_response_contract.py tests/test_prepare_runtime_context.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_repo_consistency.py tests/test_env_layer_end_to_end.py -q
```

Final verification before completion:

```bash
pwd
git rev-parse --show-toplevel
git branch --show-current
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_task_env_tool.py tests/test_context_binding_env_tool.py tests/test_run_env_tool.py tests/test_run_env_services.py tests/test_env_tool_response_contract.py tests/test_env_tool_router.py tests/test_prepare_runtime_context.py tests/test_env_layer_end_to_end.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
rg -n "context\\.get_track_artifacts|context\\.inspect_track_outputs|context\\.explain_track_access|context\\.validate_sources_available|artifact\\.list_revisions|buddyswitch/objects/.*recovery|runs/raw/.*recovery" scripts buddyswitch tools framework tests
git status --short
```
