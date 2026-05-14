# Env Tool Semantic Contract Test Plan

## 1. 测试设计原则

- 测试从源 memo 的功能需求、host 工作流、系统不变量和失败模式出发：host 只看 runtime contract 与 response，也能判断 capability、inputs、side effects、success impact、rejection recovery。
- 测试验证外部可观察行为：`prepare.runtime_context.env_tools`、`runtime_context.operation_semantics`、broker-routed `env.tool` JSON response、CLI stdout JSON、runtime object state、instance binding、run audit、browser/evidence token effects。
- 测试不根据即将写出的实现细节倒推“刚好能通过”的断言；断言 target 是 semantic contract 的行为与状态，不是函数被调用。
- 新 behavior 先写 failing tests。字段存在测试必须配合 quality tests，拒绝空字符串、低信号描述、docs-only coverage。
- 测试数据覆盖多个 buddies、多个 tools、read-only/validation/mutation/open-world paths，防止只硬编码 `track.join` 或单一 happy path。
- 对失败路径，测试必须断言 state snapshot 不变、`state_changed=false`、`impact` 明确、`retry_guidance` 可执行。
- 对 blocked artifact/body/source paths，测试必须断言 serialized payload 不含 hidden full content、preview、raw state path。
- Manual smoke 只补充真实 launcher 感知，不能替代 automated proof。

## 2. 需求覆盖矩阵

所有需求都适合自动化测试。真实 launcher smoke 作为补充验证，不承担 completion gate。

| Requirement | Test coverage |
| --- | --- |
| `REQ-001` | `ESC-HOST-001`, `ESC-HOST-002`, `ESC-HOST-003`, `ESC-HOST-004`, `ESC-HOST-005` |
| `REQ-002` | `ESC-CONTRACT-001`, `ESC-PREPARE-001` |
| `REQ-003` | `ESC-CONTRACT-001`, `ESC-RESP-004` |
| `REQ-004` | `ESC-CONTRACT-001`, `ESC-PREPARE-001` |
| `REQ-005` | `ESC-CONTRACT-002`, `ESC-CONTRACT-003` |
| `REQ-006` | `ESC-CONTRACT-002`, `ESC-NEG-001` |
| `REQ-007` | `ESC-CONTRACT-002`, `ESC-CONTRACT-004` |
| `REQ-008` | `ESC-CONTRACT-004`, `ESC-HOST-004` |
| `REQ-009` | `ESC-CONTRACT-001`, `ESC-PREPARE-001`, `ESC-REGRESSION-001` |
| `REQ-010` | `ESC-CONTRACT-001`, `ESC-REGRESSION-001` |
| `REQ-011` | `ESC-PREPARE-001`, `ESC-CONTRACT-005` |
| `REQ-012` | `ESC-RESP-001`, `ESC-READ-001`, `ESC-MUT-001`, `ESC-MUT-004` |
| `REQ-013` | `ESC-READ-004`, `ESC-HOST-003` |
| `REQ-014` | `ESC-READ-001`, `ESC-READ-002`, `ESC-READ-003`, `ESC-READ-004` |
| `REQ-015` | `ESC-MUT-001`, `ESC-MUT-002`, `ESC-MUT-003`, `ESC-MUT-004` |
| `REQ-016` | `ESC-RESP-002`, `ESC-RESP-003`, `ESC-NEG-002` |
| `REQ-017` | `ESC-RESP-002`, `ESC-NEG-002`, `ESC-HOST-005` |
| `REQ-018` | `ESC-NEG-002`, `ESC-NEG-003`, `ESC-NEG-004`, `ESC-NEG-006` |
| `REQ-019` | `ESC-CONTRACT-004`, `ESC-HOST-005`, `ESC-REGRESSION-002` |
| `REQ-020` | `ESC-RESP-003`, `ESC-NEG-007`, `ESC-REGRESSION-001` |
| `REQ-021` | `ESC-CONTRACT-002`, `ESC-READ-001` |
| `REQ-022` | `ESC-CONTRACT-002`, `ESC-MUT-002`, `ESC-HOST-005` |
| `REQ-023` | `ESC-CONTRACT-002`, `ESC-READ-003`, `ESC-MUT-003`, `ESC-NEG-002` |
| `REQ-024` | `ESC-CONTRACT-002`, `ESC-READ-004`, `ESC-NEG-005` |
| `REQ-025` | `ESC-CONTRACT-002`, `ESC-MUT-004`, `ESC-NEG-007` |
| `REQ-026` | `ESC-CONTRACT-002`, `ESC-READ-004`, `ESC-MUT-004` |
| `REQ-027` | `ESC-CONTRACT-002`, `ESC-READ-004`, `ESC-HOST-003`, `ESC-NEG-003` |
| `REQ-028` | `ESC-CONTRACT-002`, `ESC-MUT-004`, `ESC-NEG-004` |
| `REQ-029` | `ESC-CONTRACT-004`, `ESC-HOST-004`, `ESC-NEG-004` |
| `REQ-030` | `ESC-HOST-001` |
| `REQ-031` | `ESC-HOST-002`, `ESC-NEG-006` |
| `REQ-032` | `ESC-HOST-003`, `ESC-MUT-003` |
| `REQ-033` | `ESC-HOST-003`, `ESC-READ-004`, `ESC-MUT-004` |
| `REQ-034` | `ESC-HOST-004`, `ESC-MUT-004`, `ESC-NEG-004` |
| `REQ-035` | `ESC-NEG-002`, `ESC-NEG-003`, `ESC-NEG-004`, `ESC-NEG-006`, `ESC-HOST-005` |
| `REQ-036` | `ESC-HOST-005`, `ESC-MUT-002`, `ESC-NEG-007` |
| `REQ-037` | `ESC-CONTRACT-005`, `ESC-PREPARE-001` |
| `REQ-038` | `ESC-CONTRACT-003` |
| `REQ-039` | `ESC-CONTRACT-001`, `ESC-CONTRACT-002`, `ESC-RESP-004` |
| `REQ-040` | `ESC-REGRESSION-002` |
| `REQ-041` | `ESC-REGRESSION-001`, `ESC-REGRESSION-002`, `ESC-NEG-007` |
| `REQ-042` | `ESC-REGRESSION-003` |
| `REQ-043` | `ESC-WORKTREE-001` |

## 3. 测试分层

### 单元测试

目的：验证 registry semantics、field quality、helper validation、risk hints、source refs，不依赖 runtime state。

覆盖范围：

- `scripts/env/tools/semantics.py`
- `scripts/env/tools/contracts.py`
- `scripts/env/tools/responses.py`

运行命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_semantic_contract.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_response_helpers_require_success_effect_semantics tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_response_helpers_require_rejection_impact_semantics -q
```

### 集成测试

目的：验证 broker-routed `env.tool` envelope、router、dispatch、services、runtime object state 一起输出 semantic contract。

覆盖范围：

- `runtime_kernel.broker.dispatch_runtime_request`
- `scripts/env/tools/router.py`
- `scripts/env/tools/dispatch.py`
- `scripts/env/services/*.py`
- `tests.runtime_root_test_helper.RuntimeWorkspaceTestMixin`

运行命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py tests/test_env_tool_response_contract.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_context_binding_env_tool.py tests/test_run_env_tool.py tests/test_evidence_env_tool.py tests/test_search_env_tool.py -q
```

### CLI、API、UI 或主路径运行测试

目的：验证 `prepare` projection、env client CLI stdout JSON、product-mode host decision surface、browser/search/evidence externally visible effects。

覆盖范围：

- `python3 scripts/turn_runtime.py prepare "<request>"`
- `python3 scripts/env/client.py <tool> <operation>`
- `python3 scripts/browser_evidence.py issue`
- Fake CDP browser server used by existing search/evidence tests

运行命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py tests/test_host_decision_surface_product_mode.py tests/test_market_browser_evidence.py tests/test_search_env_tool.py -q
python3 scripts/env/client.py search status --help
python3 scripts/env/client.py run validate-result --help
```

### 回归测试

目的：保证 existing registry/router/dispatch、raw state boundaries、product runtime loop、broker、run commit、skills/docs consistency 没有被 semantic layer 破坏。

覆盖范围：

- Runtime broker v2
- Turn runtime prepare/persist
- Env layer end-to-end
- Repo consistency guards
- Existing tool-specific behavior

运行命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py tests/test_turn_runtime.py tests/test_turn_integration.py tests/test_env_layer_end_to_end.py tests/test_repo_consistency.py -q
```

### 手动验证

目的：确认真实 launcher-managed instance 中 host 看到的 JSON 与 automated contract 一致。

手动步骤：

1. 在 `.worktrees/dev2258` 执行 `./buddyswitch-codex instance start --buddy dev`。
2. 在 product session 内执行 `python3 scripts/turn_runtime.py prepare "Continue an existing track from upstream artifacts"`。
3. 从 prepare output 查看 `runtime_context.env_tools.track.title` 和 `runtime_context.env_tools.artifact.action_semantics.get.success_means`。
4. 执行 `python3 scripts/env/client.py search status`，确认 response 有 `effect_summary/state_changed/durability/read_scope`。
5. 对一个无权限或缺 payload 命令执行 `python3 scripts/env/client.py artifact get`，确认 rejection 有 `human_summary/why_blocked/impact/state_changed/retryable/retry_guidance`。

Manual smoke 通过标准：stdout 是 JSON，semantic fields 与 automated tests 断言一致，没有 raw state write instruction。

## 4. 详细测试用例

### `ESC-CONTRACT-001`: registry semantics 覆盖全部 tools/actions

- 覆盖需求：`REQ-002`, `REQ-003`, `REQ-004`, `REQ-009`, `REQ-010`, `REQ-039`
- 用户 / 系统场景：新 action 加到 registry 后，如果没有 runtime-visible semantics，contract test 立即失败。
- 前置条件：`sys.path` 包含 `scripts`，可导入 `env.tools.contracts`。
- 输入：`contracts.TOOL_REGISTRY`、`contracts.env_tools_description()`、`contracts.operation_semantics()`。
- 预期输出或状态变化：9 个 tools 和 42 个 actions 全部有 capability/action semantics；operation semantics machine fields 保留。
- 断言重点：tool/action set 完全来自 registry；`operations`、`payload_fields`、`action_semantics` keys 一致；`contracts.semantic_contract_errors() == []`。
- 测试类型：单元 contract 测试。
- 建议测试文件路径和测试名称：`tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_registry_semantics_cover_every_registered_tool_and_action`。

### `ESC-CONTRACT-002`: payload、side effect、success meaning 完整性

- 覆盖需求：`REQ-005`, `REQ-006`, `REQ-007`, `REQ-021`, `REQ-022`, `REQ-023`, `REQ-024`, `REQ-025`, `REQ-026`, `REQ-027`, `REQ-028`
- 用户 / 系统场景：host 需要知道每个 action 的输入含义、写入边界、成功意义。
- 前置条件：导入 `contracts.env_tools_description()`。
- 输入：每个 action 的 `payload_fields` 和 `action_semantics`。
- 预期输出或状态变化：每个 payload field 都有解释；mutating actions 有 writes/durability/idempotency；read/validate actions 不宣称写 state。
- 断言重点：`set(payload_fields) == set(inputs_explained)`；`side_effects["mutates"] == action_spec["mutates"]`；`success_means` 非低信号文本。
- 测试类型：单元 contract 测试。
- 建议测试文件路径和测试名称：`tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_action_semantics_explain_inputs_side_effects_and_success`。

### `ESC-CONTRACT-003`: semantic text quality guard

- 覆盖需求：`REQ-005`, `REQ-038`
- 用户 / 系统场景：实现不能用空字段或 `"Use this tool"` 伪装成语义覆盖。
- 前置条件：导入 runtime projection。
- 输入：所有 `title/plain_description/use_when/do_not_use_when/inputs_explained/success_means/common_failures` 文本。
- 预期输出或状态变化：所有文本通过 quality helper。
- 断言重点：拒绝空字符串、`"N/A"`、`"Use this tool"`、少于 12 字符的 description、只等于 tool/action/field name 的 explanation。
- 测试类型：单元 contract 测试。
- 建议测试文件路径和测试名称：`tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_semantic_text_rejects_low_signal_placeholders`。

### `ESC-CONTRACT-004`: risk hints 与 action behavior 对齐

- 覆盖需求：`REQ-007`, `REQ-008`, `REQ-019`, `REQ-029`
- 用户 / 系统场景：host 需要把 browser/search open-world、run commit、broker token、binding mutation 与普通 read 区分开。
- 前置条件：导入 `contracts.env_tools_description()`。
- 输入：每个 action 的 `mutates` 和 `risk_hints`。
- 预期输出或状态变化：read-only actions 标记 `read_only=true`；`search.open_browser` 标记 `open_world=true` and `external_effect=true`；`run.commit` 标记 durable commit；`evidence.*` 标记 broker token issuance。
- 断言重点：risk hints 是 hints，不出现 `enforces_permission` 或 `authorization_decision` 这类 enforcement 字段。
- 测试类型：单元 contract 测试。
- 建议测试文件路径和测试名称：`tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_risk_hints_match_mutation_and_open_world_behavior`。

### `ESC-CONTRACT-005`: docs-only coverage 被拒绝

- 覆盖需求：`REQ-011`, `REQ-037`
- 用户 / 系统场景：只更新 docs/spec 或 framework docs 不能算 semantic contract 完成。
- 前置条件：docs 中存在 semantic contract wording。
- 输入：`framework/docs/turn-runtime-spec.md` text、`contracts.env_tools_description()`。
- 预期输出或状态变化：docs 中出现的 required semantic keys 在 runtime projection 中也出现。
- 断言重点：如果 docs mention `success_means` but runtime projection missing `success_means`，测试失败。
- 测试类型：repo consistency 测试。
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_env_semantic_contract_is_runtime_visible_not_docs_only`。

### `ESC-PREPARE-001`: prepare projects semantic contract for every buddy

- 覆盖需求：`REQ-002`, `REQ-004`, `REQ-009`, `REQ-011`, `REQ-037`
- 用户 / 系统场景：PM、Market、Design、Dev、Test 都能在 prepare context 看到同一 env tool semantic surface。
- 前置条件：使用 `PrepareRuntimeContextTests._prepare()` patch product session。
- 输入：每个 manifest buddy 的 request text。
- 预期输出或状态变化：`runtime_context.env_tools` 包含 9 个 tools、42 actions semantic rows；`runtime_context.operation_semantics` 仍包含 42 keys。
- 断言重点：不同 buddy 不丢 action semantics；active buddy capability boundaries 另由 service enforcement 决定。
- 测试类型：prepare integration 测试。
- 建议测试文件路径和测试名称：`tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_projects_env_tool_semantics_for_each_buddy`。

### `ESC-RESP-001`: success helper 强制 effect semantics

- 覆盖需求：`REQ-012`
- 用户 / 系统场景：新 service 使用 canonical helper 时不能忘记 success impact。
- 前置条件：导入 `env.tools.responses`。
- 输入：合法和非法 `tool_responses.success()` calls。
- 预期输出或状态变化：缺少 `effect_summary/state_changed/durability` 或文本为空时 raise `ValueError`；合法 payload 输出 top-level semantic fields。
- 断言重点：helper 保留 existing `ok/tool/action/active_buddy/allowed_next_actions`。
- 测试类型：单元 helper 测试。
- 建议测试文件路径和测试名称：`tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_response_helpers_require_success_effect_semantics`。

### `ESC-RESP-002`: rejection helper 强制 feedback semantics

- 覆盖需求：`REQ-016`, `REQ-017`
- 用户 / 系统场景：拒绝 response 不能只给 internal boundary 和 generic message。
- 前置条件：导入 `env.tools.responses`。
- 输入：合法和非法 `tool_responses.rejection()` calls。
- 预期输出或状态变化：缺少 `human_summary/why_blocked/impact/state_changed/retryable/retry_guidance` 时 raise `ValueError`；合法 payload 保留 `permission_boundary/allowed_next_actions`。
- 断言重点：semantic fields 不嵌入 `error` 对象，保持 host-readable top-level。
- 测试类型：单元 helper 测试。
- 建议测试文件路径和测试名称：`tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_response_helpers_require_rejection_impact_semantics`。

### `ESC-RESP-003`: router malformed envelope rejections include no-mutation impact

- 覆盖需求：`REQ-016`, `REQ-020`
- 用户 / 系统场景：host 发送 malformed env.tool envelope，router 拒绝但不改变 state。
- 前置条件：seed one dev task and active binding。
- 输入：missing tool、blank tool、unknown tool、missing action、unknown action、non-object args envelopes。
- 预期输出或状态变化：response `ok=false`，semantic rejection fields present，tasks snapshot and instance JSON unchanged。
- 断言重点：`retryable=true` for payload shape mistakes；`retry_guidance` 指向 `prepare.runtime_context.env_tools` 或 supported envelope。
- 测试类型：router integration 测试。
- 建议测试文件路径和测试名称：`tests/test_env_tool_router.py::EnvToolRouterTests::test_rejects_malformed_envelope_without_state_mutation`。

### `ESC-RESP-004`: 每个 registered action 有 response semantic coverage case

- 覆盖需求：`REQ-003`, `REQ-039`
- 用户 / 系统场景：新增 action 后如果没有 success/rejection response semantics test，coverage map 失败。
- 前置条件：`tests/test_env_tool_response_contract.py` 定义 explicit map。
- 输入：`contracts.TOOL_REGISTRY` action keys and `RESPONSE_SEMANTIC_CASES` mapping。
- 预期输出或状态变化：42 action keys 都出现在 map 中。
- 断言重点：map values 是 non-empty test case ids，不从 implementation 自动生成。
- 测试类型：contract meta-test。
- 建议测试文件路径和测试名称：`tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_all_registered_actions_have_at_least_one_response_semantics_case`。

### `ESC-READ-001`: task read responses explain no state change and artifact boundary

- 覆盖需求：`REQ-012`, `REQ-014`, `REQ-021`
- 用户 / 系统场景：host 用 task tool orient work，但不把 task.get 当 full artifact body read。
- 前置条件：seed active-buddy task with current artifact summary and foreign relation-readable task。
- 输入：`task.list`、`task.get`、`task.get_current` broker envelopes。
- 预期输出或状态变化：each response `state_changed=false`, `durability="none"`, `read_scope` non-empty; no artifact full `content` in task responses。
- 断言重点：`allowed_next_actions` 或 `follow_up_affordances` 指向 `artifact.get` for full body。
- 测试类型：tool integration 测试。
- 建议测试文件路径和测试名称：`tests/test_task_env_tool.py::TaskManagerEnvToolTests::test_task_read_responses_include_semantic_no_state_change_and_artifact_boundary`。

### `ESC-READ-002`: track read responses explain orientation scope

- 覆盖需求：`REQ-014`, `REQ-022`
- 用户 / 系统场景：host 用 track list/get/current orient cross-buddy work。
- 前置条件：seed track with PM/Design/Dev tasks, current artifacts, recent handoff。
- 输入：`track.list`、`track.get`、`track.get_current`。
- 预期输出或状态变化：responses read-only semantic fields present; `track.get` says current artifact summaries are summary-only; no full artifact `content` appears。
- 断言重点：`read_scope` includes track summary/context/current binding; `state_changed=false`。
- 测试类型：tool integration 测试。
- 建议测试文件路径和测试名称：`tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_read_responses_include_semantic_orientation_scope`。

### `ESC-READ-003`: artifact read and validation semantics distinguish full body vs summary vs validation

- 覆盖需求：`REQ-014`, `REQ-023`, `REQ-032`
- 用户 / 系统场景：host needs to know whether artifact tool read full content or only validated payload.
- 前置条件：seed owned artifact, relation-readable current artifact, create payload with valid source run.
- 输入：`artifact.list`、`artifact.get`、`artifact.get_current`、`artifact.validate_payload`。
- 预期输出或状态变化：list read scope says summary only; get success says full body read; validate payload says validation-only and no state changed。
- 断言重点：`artifact.validate_payload.validation_only=true`; `artifact.list` serialized output has no `content` key。
- 测试类型：tool integration 测试。
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_read_and_validation_responses_explain_scope_and_state`。

### `ESC-READ-004`: context, binding, handoff, run read/validation semantics

- 覆盖需求：`REQ-013`, `REQ-014`, `REQ-024`, `REQ-026`, `REQ-027`, `REQ-033`
- 用户 / 系统场景：host orients via context/binding/handoff/run without accidental state mutation.
- 前置条件：prepare context exists; run receipt fixture exists; handoff validation payload valid.
- 输入：`context.get/summarize/list_sources`、`binding.get`、`handoff.list/validate`、`run.validate_result/get_receipt/get_raw`。
- 预期输出或状态变化：read responses have read scope and no state change; validation responses have validation-only and follow-up affordance.
- 断言重点：state snapshot unchanged after every call。
- 测试类型：integration 测试。
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_binding_handoff_run_read_and_validate_responses_are_semantic_and_non_mutating`。

### `ESC-MUT-001`: task mutation responses explain actual changed object

- 覆盖需求：`REQ-012`, `REQ-015`
- 用户 / 系统场景：host creates, updates, archives, and selects a task.
- 前置条件：dev instance active; one dev task exists after create.
- 输入：`task.create`、`task.update`、`task.archive`、`task.set_current`。
- 预期输出或状态变化：create/update/archive change runtime task object; set_current changes instance binding.
- 断言重点：`state_changed=true`; `durability` is `runtime_object` or `instance_binding`; `state_changes[*].object_type` matches task or instance_binding; file snapshots reflect response ids.
- 测试类型：tool integration 测试。
- 建议测试文件路径和测试名称：`tests/test_task_env_tool.py::TaskManagerEnvToolTests::test_task_mutation_responses_describe_actual_state_changes`。

### `ESC-MUT-002`: track join/lifecycle/membership responses explain boundary and impact

- 覆盖需求：`REQ-015`, `REQ-022`, `REQ-036`
- 用户 / 系统场景：PM mutates lifecycle; Dev joins or attaches task without lifecycle mutation.
- 前置条件：PM and Dev instances; active track.
- 输入：`track.join` as Dev; `track.create/update/advance/archive` as PM; `track.attach_task/detach_task` as Dev.
- 预期输出或状态变化：PM actions write track object; join writes or reuses task plus binding; attach/detach writes membership only.
- 断言重点：join effect summary explicitly says lifecycle fields unchanged; non-PM lifecycle mutation covered in `ESC-HOST-005`。
- 测试类型：tool integration 测试。
- 建议测试文件路径和测试名称：`tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_track_mutation_responses_describe_lifecycle_join_and_membership_impacts`。

### `ESC-MUT-003`: artifact create/update responses explain revision and metadata impact

- 覆盖需求：`REQ-015`, `REQ-023`, `REQ-032`
- 用户 / 系统场景：host validates then creates an artifact revision and updates metadata.
- 前置条件：active-buddy task and prepared run id exist.
- 输入：`artifact.create_revision` and `artifact.update_metadata`。
- 预期输出或状态变化：create writes artifact revision and task current slot; metadata update changes title/summary/source_run_id only.
- 断言重点：`state_changes` includes artifact id; update metadata response says content unchanged。
- 测试类型：tool integration 测试。
- 建议测试文件路径和测试名称：`tests/test_artifact_env_tool.py::ArtifactManagerEnvToolTests::test_artifact_write_responses_describe_revision_and_metadata_impacts`。

### `ESC-MUT-004`: binding, handoff, run, evidence, search mutation semantics

- 覆盖需求：`REQ-015`, `REQ-025`, `REQ-026`, `REQ-027`, `REQ-028`, `REQ-029`, `REQ-033`, `REQ-034`
- 用户 / 系统场景：host distinguishes instance binding writes, handoff record writes, run commits, evidence token issuance, and browser session mutation.
- 前置条件：prepared contexts for PM/Market/Dev; fake CDP server for browser; valid handoff payload; valid run commit payload.
- 输入：`binding.set_task/set_track/clear`、`handoff.create`、`run.commit`、`evidence.issue_browser/approve_downgrade`、`search.open_browser`。
- 预期输出或状态变化：each response `state_changed=true`; durability matches object class; created/updated ids match actual files or browser call state.
- 断言重点：`run.commit` durability `run_commit`; evidence durability `broker_token`; search open_browser durability `browser_session` and `risk_hints.open_world=true` in registry.
- 测试类型：integration/main-path 测试。
- 建议测试文件路径和测试名称：`tests/test_runtime_tool_feedback.py::RuntimeToolFeedbackTests::test_binding_handoff_run_evidence_search_mutations_describe_durable_impact`。

### `ESC-HOST-001`: direct source intake host judgment scenario

- 覆盖需求：`REQ-001`, `REQ-030`
- 用户 / 系统场景：Dev sees a track id and needs upstream artifact full body.
- 前置条件：PM track contains current PRD artifact; Dev can inspect track.
- 输入：prepare Dev context, inspect `env_tools.track.action_semantics.get`, call `track.get`, inspect returned artifact id, call `artifact.get`.
- 预期输出或状态变化：semantics justify `track.get -> artifact.get`; `track.get` summary read no state change; `artifact.get` full body read no state change.
- 断言重点：test never imports service modules for decision; it uses runtime context and responses.
- 测试类型：host decision integration 测试。
- 建议测试文件路径和测试名称：`tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_runtime_env_tool_semantics_support_direct_source_intake_decision`。

### `ESC-HOST-002`: missing relation recovery host judgment scenario

- 覆盖需求：`REQ-001`, `REQ-031`, `REQ-035`
- 用户 / 系统场景：Dev artifact.get is blocked, then host joins track and retries.
- 前置条件：PM artifact exists; Dev has no track relation.
- 输入：`artifact.get` rejected; inspect `retry_guidance` and `allowed_next_action_options`; call `track.join`; retry `artifact.get`.
- 预期输出或状态变化：blocked read no state change; join changes task/binding; retry reads full body with no additional state change.
- 断言重点：recovery step is safe/useful/allowed from response alone.
- 测试类型：host decision integration 测试。
- 建议测试文件路径和测试名称：`tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_join_recovery_response_explains_safe_next_step_and_impact`。

### `ESC-HOST-003`: artifact write and run validate/commit judgment scenario

- 覆盖需求：`REQ-001`, `REQ-032`, `REQ-033`
- 用户 / 系统场景：host validates artifact payload, creates artifact, validates run result, commits run.
- 前置条件：active task, prepared context, valid result.
- 输入：`artifact.validate_payload -> artifact.create_revision -> run.validate_result -> run.commit`。
- 预期输出或状态变化：validation steps no state change; create writes artifact revision; commit writes run audit.
- 断言重点：host can explain difference between validation-only success and durable commit.
- 测试类型：host decision integration 测试。
- 建议测试文件路径和测试名称：`tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_artifact_validate_create_and_run_validate_commit_explain_state_impact`。

### `ESC-HOST-004`: search/browser open-world judgment scenario

- 覆盖需求：`REQ-001`, `REQ-008`, `REQ-029`, `REQ-034`
- 用户 / 系统场景：host decides whether search/browser output is trusted and whether browser state changed.
- 前置条件：fake CDP server; product instance has browser port.
- 输入：inspect `search.request` and `search.open_browser` semantics; call `search.status`; call `search.open_browser`.
- 预期输出或状态变化：semantics mark open-world; status read no state change; open_browser mutates browser session.
- 断言重点：external web content risk is visible before and after action.
- 测试类型：integration/browser-adjacent 测试。
- 建议测试文件路径和测试名称：`tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_search_browser_semantics_mark_open_world_and_browser_session_effect`。

### `ESC-HOST-005`: PM-only lifecycle rejection judgment scenario

- 覆盖需求：`REQ-001`, `REQ-017`, `REQ-036`
- 用户 / 系统场景：Dev attempts PM-only `track.update`.
- 前置条件：active track exists; active buddy dev.
- 输入：broker envelope `{"tool":"track","action":"update","args":{"track_id":"track-x","status":"done"}}`。
- 预期输出或状态变化：response rejected; no state change; non-retryable as Dev; normal-language summary says PM owns lifecycle.
- 断言重点：`permission_boundary` stable; `retry_guidance` says ask/use PM or perform Dev-owned task/artifact work, not retry same action.
- 测试类型：host decision negative integration 测试。
- 建议测试文件路径和测试名称：`tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_non_pm_lifecycle_rejection_explains_authority_without_service_code`。

### `ESC-NEG-001`: missing payload data and invalid argument shape

- 覆盖需求：`REQ-006`, `REQ-035`
- 用户 / 系统场景：host omits required args or sends empty values.
- 前置条件：dev instance active.
- 输入：`task.get {}`、`track.get {}`、`artifact.get {}`、`run.get_receipt {}`、`evidence.approve_downgrade` without reason、`search.request` without backend.
- 预期输出或状态变化：each response rejected with semantic feedback and no state change.
- 断言重点：`retryable=true` for fixable payload shape; `retry_guidance` names exact field.
- 测试类型：negative integration 测试。
- 建议测试文件路径和测试名称：`tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_missing_payload_rejections_name_required_field_and_preserve_state`。

### `ESC-NEG-002`: blocked artifact read no-leak semantics

- 覆盖需求：`REQ-016`, `REQ-017`, `REQ-018`, `REQ-023`, `REQ-035`
- 用户 / 系统场景：unrelated buddy attempts foreign artifact full body read.
- 前置条件：PM artifact content contains sentinel string `"full body must not appear"`; Dev unrelated.
- 输入：`artifact.get --artifact-id <pm-artifact-id>`。
- 预期输出或状态变化：rejection includes semantic fields, `no_content_leak=true`, state unchanged.
- 断言重点：serialized response lacks sentinel, `"content"`, preview, `buddyswitch/objects`, `runs/raw`。
- 测试类型：negative/no-leak integration 测试。
- 建议测试文件路径和测试名称：`tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_collaboration_critical_rejections_include_no_leak_recovery_fields`。

### `ESC-NEG-003`: stale context and run reservation rejection semantics

- 覆盖需求：`REQ-018`, `REQ-027`, `REQ-035`
- 用户 / 系统场景：host validates or commits run with stale/mismatched context.
- 前置条件：prepare context exists, then reservation is consumed or context revision modified in test fixture.
- 输入：`run.validate_result` and `run.commit` with stale context.
- 预期输出或状态变化：rejection semantic fields present; run audit not written; reservation state unchanged except explicit test setup.
- 断言重点：impact says no run committed; retry guidance says rerun prepare or use current context.
- 测试类型：negative integration 测试。
- 建议测试文件路径和测试名称：`tests/test_run_env_tool.py::RunManagerEnvToolTests::test_stale_run_context_rejections_explain_no_commit_impact`。

### `ESC-NEG-004`: browser/search/evidence dependency failures

- 覆盖需求：`REQ-018`, `REQ-028`, `REQ-029`, `REQ-034`, `REQ-035`
- 用户 / 系统场景：browser port missing, search API unavailable, evidence token requested without browser readiness.
- 前置条件：market/dev instances with no browser port or fake CDP server returning failure.
- 输入：`search.open_browser`, `search.request` with `backend=search_api`, `evidence.issue_browser`。
- 预期输出或状态变化：rejections describe unavailable dependency and no BuddySwitch state change.
- 断言重点：browser/session/token files are not created on rejection; retry guidance names browser ensure or approved downgrade path.
- 测试类型：negative dependency integration 测试。
- 建议测试文件路径和测试名称：`tests/test_search_env_tool.py::SearchEnvToolTests::test_browser_and_search_dependency_rejections_include_semantic_impact` and `tests/test_evidence_env_tool.py::EvidenceEnvToolTests::test_evidence_dependency_rejections_include_semantic_impact`。

### `ESC-NEG-005`: empty state and empty collection boundaries

- 覆盖需求：`REQ-024`, `REQ-035`
- 用户 / 系统场景：fresh instance has no current task/track or artifacts.
- 前置条件：new dev instance, empty runtime object directories.
- 输入：`task.get_current`, `track.get_current`, `artifact.get_current`, `context.summarize`, `handoff.list` with no track.
- 预期输出或状态变化：successful read responses explain empty result and no state change.
- 断言重点：no fake ids; `effect_summary` says no current binding or empty collection.
- 测试类型：boundary integration 测试。
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_empty_runtime_state_read_responses_explain_no_state_change`。

### `ESC-NEG-006`: duplicate and ambiguous operation semantics

- 覆盖需求：`REQ-018`, `REQ-031`, `REQ-035`
- 用户 / 系统场景：host repeats create or joins track with multiple candidate tasks.
- 前置条件：task id already exists; track has two active-buddy tasks.
- 输入：`task.create` with duplicate `task_id`; `track.join` without explicit `task_id`.
- 预期输出或状态变化：rejected; no new task; no binding change.
- 断言重点：duplicate may be retryable with a different id; ambiguous join retry guidance names explicit `task_id` options.
- 测试类型：negative integration 测试。
- 建议测试文件路径和测试名称：`tests/test_track_env_tool.py::TrackManagerEnvToolTests::test_duplicate_and_ambiguous_mutations_explain_no_state_change_and_recovery`。

### `ESC-NEG-007`: permission, path, config, and raw state boundaries

- 覆盖需求：`REQ-020`, `REQ-025`, `REQ-036`, `REQ-041`
- 用户 / 系统场景：non-PM lifecycle mutation, foreign task binding, raw state edit intent in run result, malformed product-mode env.
- 前置条件：PM-owned track/task; Dev active; malformed env fixture for runtime error.
- 输入：`track.update` as Dev, `binding.set_task` with PM task, `run.validate_result` containing retired mutation/raw state fields, product CLI with partial product env.
- 预期输出或状态变化：rejected; no runtime objects changed; no raw state write path suggested.
- 断言重点：`permission_boundary` stable; `impact` says no track/task/artifact/binding/run/browser/evidence state changed; `allowed_next_actions` avoids raw state file edits.
- 测试类型：negative boundary/regression 测试。
- 建议测试文件路径和测试名称：`tests/test_runtime_tool_feedback.py::RuntimeToolFeedbackTests::test_permission_path_config_and_raw_state_rejections_include_semantic_boundaries`。

### `ESC-REGRESSION-001`: existing registry/router/dispatch and action surface remain stable

- 覆盖需求：`REQ-009`, `REQ-010`, `REQ-020`, `REQ-041`
- 用户 / 系统场景：semantic work must not introduce a second env tool system.
- 前置条件：existing tests.
- 输入：registry, router, dispatch action maps.
- 预期输出或状态变化：all maps match; no manager residue returns.
- 断言重点：`dispatch_handler_actions() == registry actions`; no raw state command hints.
- 测试类型：regression contract 测试。
- 建议测试文件路径和测试名称：`tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions` and `tests/test_env_tool_router.py::EnvToolRouterTests::test_router_residue_guards_require_dispatch_only_surface`。

### `ESC-REGRESSION-002`: no heavy abstraction or enforcement drift

- 覆盖需求：`REQ-019`, `REQ-040`, `REQ-041`
- 用户 / 系统场景：implementation must not become MCP server/tool search/workflow engine/permission language.
- 前置条件：repo files available.
- 输入：`rg --files` and text scan in repo consistency test.
- 预期输出或状态变化：forbidden files/tokens absent.
- 断言重点：reject `mcp_server.py`, `tool_search_subsystem`, `workflow_engine`, `permission_language`, `schema_generation_framework`, `semantic_v1`, `semantic_v2` tokens outside this spec wording.
- 测试类型：repo consistency 测试。
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_env_semantic_contract_avoids_heavy_abstraction_and_enforcement_drift`。

### `ESC-REGRESSION-003`: framework docs describe the runtime contract actually projected

- 覆盖需求：`REQ-042`
- 用户 / 系统场景：runtime docs remain accurate and executable.
- 前置条件：`framework/docs/turn-runtime-spec.md` exists.
- 输入：docs text and runtime projection.
- 预期输出或状态变化：docs mention required sections; projection has those fields.
- 断言重点：docs do not instruct host to read `scripts/env/services/*.py` for tool meaning.
- 测试类型：repo consistency/docs 测试。
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_turn_runtime_spec_documents_projected_env_semantic_contract`。

### `ESC-WORKTREE-001`: dev2258 worktree isolation

- 覆盖需求：`REQ-043`
- 用户 / 系统场景：work is performed in `.worktrees/dev2258`, not main checkout.
- 前置条件：test runner or final verification shell is in worktree.
- 输入：`pwd` and `git status --short --branch`.
- 预期输出或状态变化：working directory path ends with `.worktrees/dev2258`; branch is `dev2258`.
- 断言重点：document generation and implementation changes are scoped to this worktree.
- 测试类型：manual/final verification command.
- 建议 command：`pwd` and `git status --short --branch`。

## 5. 负向与边界测试

- 缺失数据：`task.get {}`、`track.get {}`、`artifact.get {}`、`run.get_receipt {}`、`evidence.approve_downgrade` without `reason`，覆盖 `ESC-NEG-001`。
- 无效状态：stale run context、consumed reservation、inactive instance、foreign task binding、non-PM lifecycle mutation，覆盖 `ESC-NEG-003` 和 `ESC-NEG-007`。
- 重复操作：duplicate `task.create` id、repeat `run.commit` idempotency path、repeat `track.join` reuse path，覆盖 `ESC-NEG-006` 和 existing run idempotency tests。
- 并发或顺序敏感行为：`run.validate_result` before `run.commit` no state change，`run.commit` after validation durable state change，browser evidence token before Market artifact-producing persist，覆盖 `ESC-HOST-003` 和 `ESC-MUT-004`。
- 空输入：empty search query、empty title、empty summary allowed where service already allows it、empty context object mismatch，覆盖 `ESC-NEG-001`。
- 空集合：fresh instance with no current task/track/artifacts/handoffs returns successful read with empty state explanation，覆盖 `ESC-NEG-005`。
- 权限异常：Dev attempts PM `track.update`、active buddy lacks manifest permission、foreign artifact write attempt，覆盖 `ESC-HOST-005` 和 `ESC-NEG-007`。
- 路径异常：raw state edit intent in run result rejected; command hints cannot contain `buddyswitch/objects`, `buddyswitch/content/runs`, or `runs/raw`，覆盖 `ESC-NEG-007`。
- 配置异常：partial product-mode env and missing browser port produce semantic feedback，覆盖 `ESC-NEG-004` 和 `ESC-NEG-007`。
- 外部依赖异常：search API unavailable and fake CDP failure produce no-state-changed rejection，覆盖 `ESC-NEG-004`。

## 6. 作弊防护

- Runtime projection tests (`ESC-PREPARE-001`) prevent docs-only implementation; semantics must appear in `prepare.runtime_context.env_tools` for every buddy.
- Action coverage tests (`ESC-CONTRACT-001`, `ESC-RESP-004`) derive action set from `TOOL_REGISTRY`, so adding an action without semantic metadata or response coverage fails.
- Text quality tests (`ESC-CONTRACT-003`) reject empty or generic phrases, so implementation cannot satisfy tests with placeholder prose.
- Payload explanation tests (`ESC-CONTRACT-002`) compare exact `payload_fields` to `inputs_explained`, so implementation cannot omit field-level semantics.
- State snapshot assertions in `ESC-RESP-003`, `ESC-READ-004`, `ESC-NEG-002`, `ESC-NEG-003`, `ESC-NEG-004`, `ESC-NEG-006`, and `ESC-NEG-007` verify behavior and state, not just field presence.
- Host judgment scenario tests do not import service modules for decisions; they inspect runtime context and responses only.
- Test data uses PM, Market, Design, Dev, Test, owned artifacts, foreign current artifacts, foreign historical artifacts, missing relation, joined relation, browser-ready and browser-missing instances.
- No-leak assertions scan serialized payloads for sentinel full-body strings and raw state paths.
- Risk hint tests require `search.open_browser` and browser/search paths to mark open-world/external effects; implementation cannot mark all actions read-only.
- Regression guard rejects heavy architecture tokens and files so adding a parallel protocol cannot bypass the direct registry-backed contract.

## 7. 验证命令清单

Focused semantic contract commands:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_semantic_contract.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_projects_env_tool_semantics_for_each_buddy -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_response_helpers_require_success_effect_semantics tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_response_helpers_require_rejection_impact_semantics tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_all_registered_actions_have_at_least_one_response_semantics_case -q
```

Focused response and scenario commands:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py tests/test_env_tool_response_contract.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_host_decision_surface_product_mode.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_tool_feedback.py tests/test_market_browser_evidence.py tests/test_search_env_tool.py -q
```

Broader verification commands:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_context_binding_env_tool.py tests/test_run_env_tool.py tests/test_evidence_env_tool.py tests/test_search_env_tool.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py tests/test_turn_runtime.py tests/test_turn_integration.py tests/test_env_layer_end_to_end.py tests/test_run_env_services.py tests/test_repo_consistency.py -q
```

Final verification before claiming completion:

```bash
pwd
git status --short --branch
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_semantic_contract.py tests/test_prepare_runtime_context.py tests/test_env_tool_router.py tests/test_env_tool_response_contract.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_context_binding_env_tool.py tests/test_run_env_tool.py tests/test_evidence_env_tool.py tests/test_search_env_tool.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_tool_feedback.py tests/test_host_decision_surface_product_mode.py tests/test_env_layer_end_to_end.py tests/test_market_browser_evidence.py tests/test_runtime_broker.py tests/test_turn_runtime.py tests/test_turn_integration.py tests/test_run_env_services.py tests/test_repo_consistency.py -q
```
