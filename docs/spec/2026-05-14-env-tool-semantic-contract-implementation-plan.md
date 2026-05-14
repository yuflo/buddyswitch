# Env Tool Semantic Contract Code Implementation Plan

## 1. 任务目标

完成后，BuddySwitch 的 env tool runtime contract 和 tool response 能让 host 仅凭 `prepare.runtime_context.env_tools`、`prepare.runtime_context.operation_semantics`、以及之前 tool call 的 response 判断下一步该用哪个能力、调用结果改了什么、失败后恢复动作是否安全且有意义。当前核心瓶颈是 env tool 已经能列出、路由和执行，但 product meaning 仍散落在 `scripts/env/services/*.py` 里，`codex-cli` 需要读实现代码才能判断能力选择、成功影响和失败恢复；这直接阻塞可靠自动执行，比继续新增工具或 command hint 更重要。

## 2. 需求提取

- `REQ-001`：host 必须能在不读取 `scripts/env/services/*.py` 的情况下回答五个问题：现在该用哪个 capability、输入需要什么且含义是什么、调用会读或改什么、成功意味着什么、拒绝意味着什么以及如何恢复。
- `REQ-002`：语义 contract 必须覆盖全部当前 env tools：`task`、`track`、`artifact`、`context`、`binding`、`handoff`、`run`、`evidence`、`search`。
- `REQ-003`：语义 contract 必须覆盖当前 42 个 env actions：`task.create/list/get/get_current/set_current/update/archive`，`track.list/get/join/get_current/create/update/advance/archive/attach_task/detach_task`，`artifact.list/get/get_current/validate_payload/create_revision/update_metadata`，`context.get/summarize/list_sources`，`binding.get/set_task/set_track/clear`，`handoff.list/validate/create`，`run.commit/get_receipt/get_raw/validate_result`，`evidence.issue_browser/approve_downgrade`，`search.status/request/open_browser`。
- `REQ-004`：每个 tool 在 `runtime_context.env_tools` 中必须暴露 capability-level semantics：`title`、`plain_description`、`use_when`、`do_not_use_when`、`capability_boundary`。
- `REQ-005`：每个 action 必须暴露 action-level semantics：`title`、`plain_description`、`use_when`、`do_not_use_when`、`inputs_explained`、`side_effects`、`risk_hints`、`success_means`、`common_failures`。
- `REQ-006`：每个 action 的 `payload_fields` 中出现的字段都必须在 `inputs_explained` 中有非空解释；没有 payload 的 action 必须显式使用空对象。
- `REQ-007`：每个 `mutates != "none"` 的 action 必须解释可能写入的对象、不会写入的对象、durability、idempotency；`mutates == "none"` 的 action 必须解释 read scope 或 validation-only scope。
- `REQ-008`：`risk_hints` 必须包含 `read_only`、`destructive`、`idempotent`、`open_world`、`requires_human_approval`、`external_effect`，并正确标记 browser/search open-world、broker token issuance、run commit、instance binding mutation、PM lifecycle mutation。
- `REQ-009`：现有 registry fields 必须保留：`tool`、`command`、`scope`、`operations`、`payload_fields`、`kind`、`mutates`、`required_permission`、`authority`、`requires`、`returns`。
- `REQ-010`：`operation_semantics()` 必须继续输出现有 machine contract；新增 semantic layer 不能替代或削弱 `kind/mutates/required_permission/authority/requires/returns`。
- `REQ-011`：`env_tools_description()` 必须把 capability semantics 和 action semantics 投影到 `prepare.runtime_context.env_tools`，而不是只存在于 docs、skills 或 service code。
- `REQ-012`：成功 response 必须包含 `effect_summary`、`state_changed`、`durability`，并在有意义时包含 `state_changes`、`created_ids`、`updated_ids`、`binding_changed`、`read_scope`、`validation_only`、`follow_up_affordances`。
- `REQ-013`：validation-only success 必须明确 `state_changed=false`、`durability="none"`、`validation_only=true`，并给出下一步 commit/create 的 affordance。
- `REQ-014`：read-only success 必须明确 `state_changed=false`、`durability="none"`、`read_scope`，并说明 response 读取的是 summary、full body、binding、receipt、raw run、context section 或 backend status。
- `REQ-015`：mutation success 必须明确 `state_changed=true`，列出实际变化对象和 durability：runtime object、instance binding、run commit、broker token、browser session。
- `REQ-016`：拒绝 response 必须保留 `ok=false`、`tool`、`action`、`active_buddy`、`error.code`、`error.message`、`permission_boundary`、`allowed_next_actions`、`allowed_next_action_options`、`command_hint`。
- `REQ-017`：拒绝 response 必须新增 normal-language semantic fields：`human_summary`、`why_blocked`、`impact`、`state_changed`、`retryable`、`retry_guidance`。
- `REQ-018`：拒绝 response 必须说明失败前是否改变了 state。当前 env tool 服务应保持失败前不部分写入；如果实现发现某个 action 会部分写入后失败，必须先重构为预检后写入，不能把 partial state 当作正常 contract。
- `REQ-019`：permission/risk semantics 只作为 host guidance；权限、ownership、PM lifecycle、broker、service validation 的 runtime enforcement 必须继续由 broker 和 service code 执行。
- `REQ-020`：key recovery paths 必须保留 command hints 和 structured next actions，且 `allowed_next_action_options[*].source_refs` 指向可解析的 `runtime_context.operation_semantics['<tool>.<action>']`。
- `REQ-021`：`task` semantics 必须区分 task ownership reads/writes、current binding selection、archive 不删除、track relation orientation、artifact full body 读取应转到 `artifact.get`。
- `REQ-022`：`track` semantics 必须区分 read orientation、`track.join` active-buddy participation、PM-only lifecycle mutation、attach/detach membership mutation；非 PM lifecycle rejection 必须用普通语言解释 authority boundary。
- `REQ-023`：`artifact` semantics 必须区分 summary list、full body read、current task convenience read、validation-only payload normalization、revision creation、metadata-only update；blocked body read 必须保持 no-leak recovery fields。
- `REQ-024`：`context` semantics 必须说明它是 active instance runtime snapshot、summary 和 source descriptor surface，不是 direct full artifact body read API。
- `REQ-025`：`binding` semantics 必须说明 instance binding 是 launcher instance state，`set_task` 绑定 active-buddy task，`set_track` 只允许 PM lifecycle context，`clear` 只清除 binding 不删除 objects。
- `REQ-026`：`handoff` semantics 必须说明 list/validate/create 的差异，create 只写 explicit handoff record，不静默推进 track lifecycle。
- `REQ-027`：`run` semantics 必须说明 `validate_result` 不写 state，`commit` 是 durable run audit commit，`get_receipt/get_raw` 是 scoped reads。
- `REQ-028`：`evidence` semantics 必须说明 broker token issuance、Market evidence profile、browser cockpit readiness、approved downgrade 需要 explicit reason。
- `REQ-029`：`search` semantics 必须说明 native Codex web search disabled、browser/search_api backend boundary、browser session mutation、open-world/untrusted external content risk。
- `REQ-030`：必须验证 direct source intake scenario：`track_id -> track.get -> artifact ids -> artifact.get`，host 可从 context/response 解释下一步和影响。
- `REQ-031`：必须验证 joining work scenario：missing relation rejection -> `track.join` -> new/reused active-buddy task binding -> `artifact.get` 可读。
- `REQ-032`：必须验证 artifact write scenario：`artifact.validate_payload` 不改 state，`artifact.create_revision` 写 artifact revision 并可关联 run。
- `REQ-033`：必须验证 run scenario：`run.validate_result` validation-only，`run.commit` durable commit，并且 response 说明 actual impact。
- `REQ-034`：必须验证 search/browser scenario：status/request/open_browser 能表达 backend boundary、browser session effect、open-world risk 和 evidence requirement。
- `REQ-035`：必须验证 blocked operations：无 state change、why blocked、impact、retryability、allowed next action 在同一 response 中。
- `REQ-036`：必须验证 PM-only lifecycle changes 与 non-PM task/artifact work 的 authority boundary 语义。
- `REQ-037`：测试必须拒绝 docs-only coverage；语义字段必须出现在 runtime projection 或 actual responses 中。
- `REQ-038`：测试必须拒绝低信号语义文本，例如空字符串、`"Use this tool"`、`"N/A"`、重复 field name 的解释、只改写 action 名称的 description。
- `REQ-039`：新增 tool/action 时测试必须失败，直到 capability/action semantics、payload field explanations、side effects、risk hints、result/feedback semantics 覆盖完整。
- `REQ-040`：不得实现 full MCP server、external MCP registry integration、新 host-side tool search、browser UI、generic schema-generation framework、workflow engine、plugin system、generic permission language、long-lived compatibility path。
- `REQ-041`：不得重建 task/track/artifact product behavior，不改变 core permission enforcement，不引入新的 raw state host write path。
- `REQ-042`：需要更新 docs/spec 或 framework docs 中定义 runtime env semantic contract 的内容，使 durable contract 与代码一致。
- `REQ-043`：实施必须在 `.worktrees/dev2258` 内完成，不能污染 main worktree。

## 3. 现状探索摘要

### 关键目录、文件、测试、运行命令

- `AGENTS.md`：BuddySwitch SHARP、testing-bound、no verification no done、direct replacement over wrappers。
- `README.md`：product runtime loop、`prepare`、`persist`、`env.tool` CLI 主路径。
- `projects/app/README.md`：确认 `projects/app` 是 runtime mount point，本任务不改 product app。
- `docs/memo/2026-05-14-env-tool-semantic-contract-memo.md`：本任务源需求。
- `framework/docs/turn-runtime-spec.md`：`prepare.runtime_context.env_tools`、`operation_semantics`、structured feedback 现有 contract。
- `scripts/env/tools/contracts.py`：当前 9 tools/42 actions registry、`env_tools_description()`、`operation_semantics()`。
- `scripts/env/tools/responses.py`：当前 `next_action_option()`、`success()`、`rejection()` helpers，只含 machine/action fields。
- `scripts/env/tools/router.py`：envelope validation rejection，目前本地 `_reject()` 未带 semantic impact fields。
- `scripts/env/tools/dispatch.py`：registry-backed service dispatch 和 run/evidence exception feedback wrapper。
- `scripts/turn_runtime.py`：`_build_env_tools_desc()` projection、`runtime_error()`、prepare/persist response construction。
- `scripts/browser_evidence.py`：browser evidence CLI wrapper error envelope。
- `scripts/env/services/tasks.py`：task read/write/current binding service，局部 `_error_payload()` 和直接 success dict。
- `scripts/env/services/tracks.py`：track list/get/join/lifecycle/attach/detach，已有 `_success_payload()` 和局部 errors。
- `scripts/env/services/artifacts.py`：artifact list/get/validate/create/update，已有 no-leak recovery fields 但缺统一 effect/impact semantics。
- `scripts/env/services/context.py`：context get/summarize/list_sources 和 decision surface。
- `scripts/env/services/bindings.py`：binding get/set_task/set_track/clear 和 `write_instance_binding()`。
- `scripts/env/services/handoffs.py`：handoff list/validate/create。
- `scripts/env/services/runs.py`：run validate/commit/get_receipt/get_raw，commit writes run audit。
- `scripts/env/services/evidence.py`：broker evidence token issuance。
- `scripts/env/services/search.py`：search status/request/open_browser，已使用 response helpers。
- `scripts/env/services/track_relations.py`：current command hint、track relation、artifact read decision helpers。
- `tests/test_prepare_runtime_context.py`：prepare projection and runtime context behavior。
- `tests/test_env_tool_router.py`：registry/router/dispatch consistency。
- `tests/test_env_tool_response_contract.py`：canonical success/rejection response fields、no-leak、next action validation。
- `tests/test_runtime_tool_feedback.py`：structured runtime feedback and state snapshot checks。
- `tests/test_host_decision_surface_product_mode.py`：PM -> Market -> Design host decision scenarios。
- `tests/test_task_env_tool.py`、`tests/test_track_env_tool.py`、`tests/test_artifact_env_tool.py`、`tests/test_context_binding_env_tool.py`、`tests/test_run_env_tool.py`、`tests/test_evidence_env_tool.py`、`tests/test_search_env_tool.py`：tool-specific broker-routed behavior。
- `tests/test_repo_consistency.py`：repo-wide residue and guidance consistency checks。

探索命令：

```bash
pwd
git status --short --branch
rg --files -g 'AGENTS.md' -g 'CLAUDE.md' -g 'README.md' -g 'pyproject.toml' -g 'package.json' -g 'pytest.ini' -g 'Makefile'
sed -n '1,760p' scripts/env/tools/contracts.py
sed -n '1,220p' scripts/env/tools/responses.py
sed -n '1,180p' scripts/env/tools/router.py
rg -n "^def |^class |responses\\.success|responses\\.rejection|tool_responses\\.success|tool_responses\\.rejection|runtime_error\\(" scripts/env/services scripts/env/tools scripts/turn_runtime.py
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py tests/test_env_tool_router.py tests/test_env_tool_response_contract.py -q
```

### 保留、替换、删除、迁移

- 保留：`env.tool -> router -> dispatch -> services` 主路径。
- 保留：`TOOL_REGISTRY` 作为 action surface 的 registry-backed source。
- 保留：`operation_semantics()` 的 machine contract 输出。
- 保留：现有 service-owned enforcement，包括 manifest permission、active buddy scope、PM lifecycle authority、artifact relation、run reservation、broker boundary、browser readiness。
- 保留：现有 `allowed_next_actions`、`allowed_next_action_options`、`command_hint`，并为它们补足 semantic meaning。
- 替换：`env_tools_description()` 只输出 operations/payload fields 的弱 projection，改为同时输出 capability/action semantics。
- 替换：各 service 中只表达 machine failure 的局部 `_error_payload()`，改为同一 response shape 包含 human summary、blocked reason、impact、retryability。
- 替换：success response 中只表达 returned objects 的 dict，改为明确 effect summary、state_changed、durability 和 follow-up affordance。
- 迁移：`search` 中已使用 `tool_responses.success/rejection` 的 call sites 随 helper signature 一次性更新。
- 迁移：`run`/`evidence` exception wrapper in `scripts/env/tools/dispatch.py` 输出 semantic rejection fields。
- 迁移：`turn_runtime.runtime_error()` 对 prepare/persist CLI feedback 中已有 allowed next actions 的分支补足 semantic impact fields。
- 删除：任何只存在于 docs/skills、没有投影到 runtime context 或 actual response 的“语义覆盖”。
- 删除：新旧 response semantic 双路径；实施完成时不得保留 `legacy_success_payload()`、`compat_semantics`、`semantic_v1/semantic_v2` 这类并行结构。
- 不迁移：不改已有 raw state JSON 数据形态，不批量重写 tracks/tasks/artifacts/runs。

## 4. 最终目标架构

### 文件结构与职责

- 新增 `scripts/env/tools/semantics.py`
  - 存放 concrete semantic metadata，不引入 DSL 或 schema-generation framework。
  - 定义 `CAPABILITY_SEMANTICS: dict[str, dict[str, Any]]`，key 为 tool id。
  - 定义 `ACTION_SEMANTICS: dict[str, dict[str, Any]]`，key 为 `"<tool>.<action>"`。
  - 定义 `semantic_coverage_errors(tool_registry: list[dict[str, Any]]) -> list[str]`，供 tests 和 projection sanity check 使用。
  - 定义 `capability_semantics(tool: str) -> dict[str, Any]` 和 `action_semantics(tool: str, action: str) -> dict[str, Any]`，返回 copy，避免 callers mutate source dictionaries。

- 修改 `scripts/env/tools/contracts.py`
  - Import `env.tools.semantics`。
  - `env_tools_description()` 对每个 tool row 增加 `title`、`plain_description`、`use_when`、`do_not_use_when`、`capability_boundary`。
  - `env_tools_description()` 对每个 action 增加 `action_semantics[action]`，并保留 `operations`、`payload_fields`。
  - 新增 `semantic_contract_errors() -> list[str]`，委托 `semantics.semantic_coverage_errors(TOOL_REGISTRY)`，测试可直接调用。
  - `operation_semantics()` 保持 existing keys，并新增 `risk_hints` 只在不破坏现有 tests 时加入；如果加入，必须仍保留 `kind/mutates/required_permission/authority/requires/returns`。

- 修改 `scripts/env/tools/responses.py`
  - 扩展 `success()` required keyword fields：`effect_summary: str`、`state_changed: bool`、`durability: str`。
  - 扩展 `success()` optional keyword fields：`state_changes`、`created_ids`、`updated_ids`、`binding_changed`、`read_scope`、`validation_only`、`follow_up_affordances`。
  - 扩展 `rejection()` required keyword fields：`human_summary: str`、`why_blocked: str`、`impact: str`、`state_changed: bool`、`retryable: bool`、`retry_guidance: str`。
  - 保留 `next_action_option()`，并新增 `follow_up_affordance(tool, action, reason, source_refs=None) -> dict[str, Any]`；结构与 `next_action_option` 接近，但用于 success response 的 meaningful next step。
  - 新增 `_require_non_empty_text(value, field)`、`_require_bool(value, field)` 的本地 validation，保证 helper call sites 不能输出空 semantic fields。

- 修改 `scripts/env/tools/router.py`
  - `_reject()` 增加 semantic fields，并为 missing tool、unsupported tool、missing action、unsupported action、non-object args 明确 `state_changed=false`、`durability="none"`、`retryable` 和 `retry_guidance`。
  - `dispatch_env_tool_request()` 不改变 routing/enforcement 行为。

- 修改 `scripts/env/tools/dispatch.py`
  - `_runtime_feedback_error()` 和 `_runtime_feedback_from_exception()` 增加 semantic rejection fields。
  - 保留 `dispatch_handler_actions()`，不新增 action mapping。

- 修改 `scripts/turn_runtime.py`
  - `_build_env_tools_desc()` 继续调用 `tool_contracts.env_tools_description()`。
  - `runtime_error()` 在 payload 包含 `allowed_next_actions` 时补齐 semantic rejection fields；prepare/persist success shape 不改变 frozen top-level contract。
  - `_market_evidence_feedback()` 中 browser evidence rejection guidance 保留原字段并补齐 semantic fields。
  - `framework/contracts/prepare-turn-context.json` 不需要新增 frozen schema；runtime context 是 dict projection，测试验证其 semantic content。

- 修改 `scripts/browser_evidence.py`
  - `_runtime_error()` 输出语义 rejection fields，确保 CLI wrapper 与 env tool evidence path 一致。

- 修改服务文件：
  - `scripts/env/services/tasks.py`：更新 `_error_payload()` 和 7 个 action success returns。
  - `scripts/env/services/tracks.py`：更新 `_error_payload()`、`_success_payload()`、join ambiguity/lifecycle/payload/lookup rejections 和 10 个 action success returns。
  - `scripts/env/services/artifacts.py`：更新 `_error_payload()`、no-leak `_artifact_read_rejection()` 和 6 个 action success returns。
  - `scripts/env/services/context.py`：更新 `_error_payload()`、context boundary rejections 和 3 个 action success returns。
  - `scripts/env/services/bindings.py`：更新 `_error_payload()` 和 4 个 action success returns。
  - `scripts/env/services/handoffs.py`：更新 `_error_payload()` 和 3 个 action success returns。
  - `scripts/env/services/runs.py`：更新 `_payload_error()` 和 4 个 action success returns。
  - `scripts/env/services/evidence.py`：更新 `_payload_error()`、profile/context/browser readiness RuntimeFeedbackError details、2 个 action success returns。
  - `scripts/env/services/search.py`：更新 helper call sites，3 个 action success returns 和 backend/query/engine/browser/search_api rejections。

- 修改 docs：
  - `framework/docs/turn-runtime-spec.md`：补充 env semantic contract fields、result semantics、feedback semantics、risk hints 和 out-of-scope boundary。
  - `docs/spec/2026-05-14-env-tool-semantic-contract-implementation-plan.md` 与 `docs/spec/2026-05-14-env-tool-semantic-contract-test-plan.md` 作为实施与测试 handoff。

### 核心数据模型

Capability semantics object:

```python
{
    "title": str,
    "plain_description": str,
    "use_when": list[str],
    "do_not_use_when": list[str],
    "capability_boundary": {
        "identity_source": str,
        "authority_source": str,
        "raw_state_access": str,
    },
}
```

Action semantics object:

```python
{
    "title": str,
    "plain_description": str,
    "use_when": list[str],
    "do_not_use_when": list[str],
    "inputs_explained": dict[str, str],
    "side_effects": {
        "mutates": str,
        "writes": list[str],
        "does_not_write": list[str],
        "durability": str,
        "idempotency": str,
    },
    "risk_hints": {
        "read_only": bool,
        "destructive": bool,
        "idempotent": bool | str,
        "open_world": bool,
        "requires_human_approval": bool,
        "external_effect": bool,
    },
    "success_means": str,
    "common_failures": list[str],
}
```

Success semantic envelope:

```python
{
    "ok": True,
    "tool": str,
    "action": str,
    "active_buddy": str,
    "effect_summary": str,
    "state_changed": bool,
    "durability": "none" | "runtime_object" | "instance_binding" | "runtime_object+instance_binding" | "run_commit" | "broker_token" | "browser_session",
    "state_changes": list[dict[str, str]],
    "created_ids": list[str],
    "updated_ids": list[str],
    "binding_changed": bool,
    "read_scope": str,
    "validation_only": bool,
    "follow_up_affordances": list[dict[str, Any]],
    "allowed_next_actions": list[str],
}
```

Rejection semantic envelope:

```python
{
    "ok": False,
    "tool": str,
    "action": str,
    "active_buddy": str,
    "error": {"code": str, "message": str},
    "permission_boundary": str,
    "human_summary": str,
    "why_blocked": str,
    "impact": str,
    "state_changed": False,
    "retryable": bool,
    "retry_guidance": str,
    "allowed_next_actions": list[str],
    "allowed_next_action_options": list[dict[str, Any]],
}
```

### Action side-effect table

| Action group | Actions | Required semantic side effect |
| --- | --- | --- |
| Read-only task | `task.list`, `task.get`, `task.get_current` | `read_only=true`, `state_changed=false`, durability `none`, read scope names task summary/current binding/relation and artifact summary ids only. |
| Task writes/binds | `task.create`, `task.update`, `task.archive`, `task.set_current` | Runtime object writes for create/update/archive, instance binding for set_current; archive marks status and does not delete; set_current updates current task/track binding and does not write task content. |
| Read-only track | `track.list`, `track.get`, `track.get_current` | `state_changed=false`, read scope names track summaries/context/current binding/recent handoffs/current artifact summaries. |
| Track participation | `track.join`, `track.attach_task`, `track.detach_task` | Runtime object write and, for join, instance binding mutation; no PM lifecycle fields changed. |
| PM lifecycle track | `track.create`, `track.update`, `track.advance`, `track.archive` | Runtime object write; authority PM lifecycle; destructive false because archive is status change not delete; non-PM rejection non-retryable as same buddy. |
| Artifact reads | `artifact.list`, `artifact.get`, `artifact.get_current` | Read-only; list/get_current explain summary/full owned reads; get explains full body read only when owner or allowed relation. |
| Artifact validation/write | `artifact.validate_payload`, `artifact.create_revision`, `artifact.update_metadata` | validate has no state change; create writes runtime artifact revision and task slot currentness; update writes metadata only and not content. |
| Context reads | `context.get`, `context.summarize`, `context.list_sources` | Read-only runtime snapshot/projection; not full foreign artifact body API. |
| Binding | `binding.get`, `binding.set_task`, `binding.set_track`, `binding.clear` | get read-only; set/clear mutate launcher instance binding only, not task/track/artifact objects. |
| Handoff | `handoff.list`, `handoff.validate`, `handoff.create` | list read-only; validate no state change; create writes handoff record and does not advance track lifecycle. |
| Run | `run.validate_result`, `run.commit`, `run.get_receipt`, `run.get_raw` | validate no state change; commit durable run audit commit; receipt/raw scoped reads only. |
| Evidence | `evidence.issue_browser`, `evidence.approve_downgrade` | Broker token issuance, external effect false, browser issue requires browser cockpit readiness; approved downgrade requires human-approved reason. |
| Search | `search.status`, `search.request`, `search.open_browser` | status/read boundary; request with search_api open-world provider-dependent read/request and no BuddySwitch state write; open_browser mutates browser session and is open-world. |

### 调用流

Prepare projection:

```text
turn_runtime.prepare_turn_context
  -> _build_runtime_context
  -> _build_env_tools_desc
  -> env.tools.contracts.env_tools_description
  -> env.tools.semantics capability/action dictionaries
  -> runtime_context.env_tools
```

Env tool execution:

```text
runtime_kernel.broker.dispatch_runtime_request(method="env.tool")
  -> env.tools.router.dispatch_env_tool_request
  -> env.tools.dispatch.dispatch_registered_env_tool
  -> scripts/env/services/<tool>.py action handler
  -> env.tools.responses.success or env.tools.responses.rejection
  -> host-readable effect/impact fields in response
```

## 5. 分阶段实施计划

### Phase 1: Registry-backed semantic metadata and runtime projection

目标：让 `prepare.runtime_context.env_tools` 对 9 个 tools 和 42 个 actions 暴露完整 capability/action semantics，同时保持现有 operation semantics。

具体文件变更：

- Create `scripts/env/tools/semantics.py`
- Modify `scripts/env/tools/contracts.py`
- Modify `tests/test_prepare_runtime_context.py`
- Create `tests/test_env_tool_semantic_contract.py`
- Modify `framework/docs/turn-runtime-spec.md`

详细步骤：

1. 在 `tests/test_env_tool_semantic_contract.py` 新增 `EnvToolSemanticContractTests`，导入 `env.tools.contracts`。
2. 新增测试 `test_every_registered_tool_has_decision_semantics`：遍历 `contracts.TOOL_REGISTRY`，断言每个 tool 在 `contracts.env_tools_description()` 中有 `title/plain_description/use_when/do_not_use_when/capability_boundary`，且文本通过 quality helper。
3. 新增测试 `test_every_registered_action_has_complete_semantics`：遍历所有 registry actions，断言 `env_tools_description()[tool]["action_semantics"][action]` 有 action semantic required keys。
4. 新增测试 `test_every_payload_field_has_runtime_explanation`：断言 `set(payload_fields) == set(inputs_explained)`；空 payload action 的 `inputs_explained == {}`。
5. 新增测试 `test_mutating_actions_explain_writes_and_risk_hints`：当 action `mutates != contracts.MUTATES_NONE`，断言 `side_effects["writes"]` 非空、`side_effects["does_not_write"]` 非空、`risk_hints["read_only"] is False`；当 `mutates == "none"`，断言 `side_effects["writes"] == []`、`risk_hints["read_only"] is True`。
6. 新增测试 `test_semantic_text_rejects_low_signal_placeholders`：text quality helper 拒绝空字符串、少于 12 个字符的 description、`"Use this tool"`、`"N/A"`、只等于 field/action/tool name 的解释。
7. 新增测试 `test_operation_semantics_machine_contract_is_preserved`：断言每个 `operation_semantics()[f"{tool}.{action}"]` 仍有 `kind/mutates/required_permission/authority/requires/returns`。
8. 在 `tests/test_prepare_runtime_context.py` 新增 `test_prepare_projects_env_tool_semantics_for_each_buddy`：对 manifest 中每个 buddy 调用 prepare，断言 `runtime_context.env_tools` 含 9 个 tools，每个 action semantic 可见。
9. 创建 `scripts/env/tools/semantics.py`，写入 `CAPABILITY_SEMANTICS` 和 `ACTION_SEMANTICS`，覆盖 REQ-002/REQ-003 的全部 tools/actions。
10. 在 `scripts/env/tools/semantics.py` 中实现 `semantic_coverage_errors()`，检查 missing tool、missing action、missing payload field explanation、missing risk hints、mutating action without writes、read-only action with writes。
11. 修改 `scripts/env/tools/contracts.py::env_tools_description()`，把 `semantics.capability_semantics(tool)` merge 到 tool row，把每个 action 的 `semantics.action_semantics(tool, action)` 放入 `action_semantics`。
12. 修改 `scripts/env/tools/contracts.py`，新增 `semantic_contract_errors()`，返回 `semantics.semantic_coverage_errors(TOOL_REGISTRY)`。
13. 更新 `framework/docs/turn-runtime-spec.md` 的 `runtime_context.env_tools` 段落，明确 capability/action semantics fields、risk hints、语义不是 enforcement boundary。

预期行为变化：

- `prepare.runtime_context.env_tools.task.title` 等 capability fields 可见。
- `prepare.runtime_context.env_tools.track.action_semantics.join.success_means` 可见。
- Existing `operations`、`payload_fields`、`operation_semantics` 不变。

对应需求编号：`REQ-001` 至 `REQ-011`、`REQ-019`、`REQ-021` 至 `REQ-029`、`REQ-037` 至 `REQ-043`。

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_semantic_contract.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_projects_env_tool_semantics_for_each_buddy -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions -q
```

阶段完成标准：

- `contracts.semantic_contract_errors()` 返回空 list。
- prepare projection 中 9 tools/42 actions 的 semantic fields 完整可见。
- Existing registry/router/dispatch action coverage test 仍通过。

### Phase 2: Canonical response helper semantics and router feedback

目标：让 response helper、router validation feedback、run/evidence exception wrapper 能输出 success effect semantics 和 rejection impact semantics。

具体文件变更：

- Modify `scripts/env/tools/responses.py`
- Modify `scripts/env/tools/router.py`
- Modify `scripts/env/tools/dispatch.py`
- Modify `scripts/env/services/search.py`
- Modify `tests/test_env_tool_response_contract.py`
- Modify `tests/test_env_tool_router.py`

详细步骤：

1. 在 `tests/test_env_tool_response_contract.py` 新增 `test_response_helpers_require_success_effect_semantics`：直接调用 `tool_responses.success()`，覆盖缺 `effect_summary`、空 `effect_summary`、缺 `state_changed`、缺 `durability` 的失败分支，并断言合法 payload 保留 `ok/tool/action/active_buddy/allowed_next_actions`。
2. 新增 `test_response_helpers_require_rejection_impact_semantics`：直接调用 `tool_responses.rejection()`，覆盖缺 `human_summary/why_blocked/impact/state_changed/retryable/retry_guidance` 的失败分支，并断言合法 payload 包含新增 fields。
3. 在 `tests/test_env_tool_router.py` 修改 `test_rejects_malformed_envelope_without_state_mutation`：对 missing tool、unsupported tool、missing action、unsupported action、non-object args 断言 `human_summary/why_blocked/impact/state_changed/retryable/retry_guidance`，并继续断言 state snapshot 不变。
4. 修改 `scripts/env/tools/responses.py::success()` signature，新增 required semantic kwargs；函数内验证文本非空、bool 类型正确、`state_changes/created_ids/updated_ids/follow_up_affordances` 为 list when provided。
5. 修改 `scripts/env/tools/responses.py::rejection()` signature，新增 required semantic kwargs；函数内验证新增 fields，并继续把 `permission_boundary/allowed_next_actions` 保持 top-level。
6. 新增 `follow_up_affordance()`，默认 `source_refs` 为 `runtime_context.operation_semantics['<tool>.<action>']`。
7. 修改 `scripts/env/tools/router.py::_reject()`，不依赖 action service，直接补齐 semantic rejection fields：
   - malformed envelope：`state_changed=false`、`retryable=true`、`retry_guidance="Fix the env.tool envelope and retry with supported tool/action/args."`
   - unsupported tool/action：`retryable=true`，guidance 指向 `prepare.runtime_context.env_tools`。
8. 修改 `scripts/env/tools/dispatch.py::_runtime_feedback_error()` 和 `_runtime_feedback_from_exception()`，把 run/evidence RuntimeFeedbackError wrapper 的 impact 写为 no state changed unless exception came after service commit；当前 wrapper 只处理 pre-write validation/error，写 `state_changed=false`。
9. 修改 `scripts/env/services/search.py` 中所有 `tool_responses.success()` 和 `tool_responses.rejection()` call sites：
   - `search.status` success：`state_changed=false`、`durability="none"`、`read_scope="search capability boundary and backend status"`。
   - `search.request` browser backend success：`state_changed=false`、`durability="none"`、open-world risk reflected in semantics。
   - `search.open_browser` success：`state_changed=true`、`durability="browser_session"`、state change object type `browser_session`。
   - query/engine/backend/browser/search_api rejection：state unchanged and retry guidance specific to payload/backend/browser ensure.

预期行为变化：

- Helper-created responses cannot omit semantic effect/impact fields.
- Router-level rejections become host-readable without reaching service code.
- Search responses satisfy new helper contract and keep existing backend fields.

对应需求编号：`REQ-012` 至 `REQ-020`、`REQ-029`、`REQ-034`、`REQ-035`、`REQ-037` 至 `REQ-041`。

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_response_helpers_require_success_effect_semantics tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_response_helpers_require_rejection_impact_semantics -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py::EnvToolRouterTests::test_rejects_malformed_envelope_without_state_mutation -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_search_env_tool.py -q
```

阶段完成标准：

- Router malformed envelope tests 证明无 state mutation 且 rejection 语义完整。
- Search helper call sites 不再使用旧 success/rejection shape。
- No response helper test accepts missing semantic fields.

### Phase 3: Read and validation action response semantics

目标：覆盖所有 read-only 和 validation-only env actions 的 success/rejection semantic fields，并验证 state unchanged。

具体文件变更：

- Modify `scripts/env/services/tasks.py`
- Modify `scripts/env/services/tracks.py`
- Modify `scripts/env/services/artifacts.py`
- Modify `scripts/env/services/context.py`
- Modify `scripts/env/services/bindings.py`
- Modify `scripts/env/services/handoffs.py`
- Modify `scripts/env/services/runs.py`
- Modify `tests/test_env_tool_response_contract.py`
- Modify `tests/test_runtime_tool_feedback.py`
- Modify tool-specific tests listed below

详细步骤：

1. 在 `tests/test_env_tool_response_contract.py` 新增 `test_read_and_validation_success_responses_include_effect_semantics`，cases 覆盖：
   - `task.list`、`task.get`、`task.get_current`
   - `track.list`、`track.get`、`track.get_current`
   - `artifact.list`、`artifact.get`、`artifact.get_current` with readable fixtures
   - `artifact.validate_payload`
   - `context.get`、`context.summarize`、`context.list_sources`
   - `binding.get`
   - `handoff.list`、`handoff.validate`
   - `run.validate_result`、`run.get_receipt`、`run.get_raw`
   - `search.status`、`search.request`
2. 在同一测试 helper 中断言 read actions：`state_changed is False`、`durability == "none"`、`read_scope` 是非空 string、没有 `created_ids` 非空。
3. 在同一测试 helper 中断言 validation actions：`state_changed is False`、`durability == "none"`、`validation_only is True`、`follow_up_affordances` 指向 create/commit action。
4. 在 `tests/test_env_tool_response_contract.py` 新增 `test_read_and_validation_rejections_include_feedback_semantics`，cases 覆盖 missing task id、missing track id、blocked artifact body read、invalid context payload、invalid handoff payload、missing run id、invalid search backend。
5. 修改 `scripts/env/services/tasks.py`：
   - `_error_payload()` 增加 semantic args，调用或对齐 `tool_responses.rejection()` shape。
   - `list_tasks_for_active_buddy()` success 增加 `effect_summary="Listed task records readable by <active_buddy>; no state changed."`、`state_changed=false`、`durability="none"`、`read_scope="active-buddy tasks and relation-readable task summaries"`。
   - `get_task_for_active_buddy()` success 增加 full task orientation read scope，明确 artifact body 未读取。
   - `get_current_task()` success 在 no binding 时 effect summary 明确 “No current task binding exists; no state changed.”
6. 修改 `scripts/env/services/tracks.py`：
   - `_error_payload()` 增加 semantic fields。
   - `_success_payload()` 接受 `effect_summary/read_scope/validation_only` 并写入 success semantic fields。
   - `list/get/get_current` 填写 read scope；`get_current` no binding 时明确 no current track。
7. 修改 `scripts/env/services/artifacts.py`：
   - `_error_payload()` 增加 semantic fields。
   - `_artifact_read_rejection()` 增加 `human_summary`、`why_blocked`、`impact`、`state_changed=false`、`retryable`、`retry_guidance`，并保留 `no_content_leak=true`、`relation`、`missing_preconditions`、`next_actions`、`command_hint`。
   - `list_artifacts_for_track()` success 增加 summary-only read scope。
   - `get_artifact_for_active_buddy()` success 增加 full-body read scope 和 relation explanation。
   - `get_current_artifacts_for_active_task()` success 增加 owned current artifact read scope。
   - `validate_artifact_payload()` success 增加 validation-only semantics and follow-up `artifact.create_revision` affordance。
8. 修改 `scripts/env/services/context.py`：
   - `_error_payload()` 和 `_context_boundary_error()` 增加 semantic fields。
   - `get/summarize/list_sources` success 增加 read scope；`context.get` 明确 it reads runtime context sections, not foreign full artifact bodies.
9. 修改 `scripts/env/services/bindings.py`：
   - `_error_payload()` 增加 semantic fields。
   - `get_binding()` success 增加 read-only semantics。
10. 修改 `scripts/env/services/handoffs.py`：
   - `_error_payload()` 和 `_payload_error()` 增加 semantic fields。
   - `list_handoffs_for_active_buddy()` success 增加 read scope。
   - `validate_handoff()` success 增加 validation-only semantics and follow-up `handoff.create` affordance。
11. 修改 `scripts/env/services/runs.py`：
   - `_payload_error()` 增加 semantic fields。
   - `validate_result_for_active_instance()` success 增加 validation-only semantics and follow-up `run.commit` affordance。
   - `get_receipt_for_active_instance()` and `get_raw_for_active_instance()` success 增加 scoped read semantics。
12. 修改 `tests/test_runtime_tool_feedback.py::_state_snapshot()` reuse in new assertions，确保 all read/validate cases state unchanged。

预期行为变化：

- 所有 read-only action success 明确 no state change 和 read scope。
- 所有 validation-only action success 明确 no state change 和下一步 write/commit affordance。
- Blocked artifact read 的 no-leak response 同时具备 semantic feedback fields。

对应需求编号：`REQ-012` 至 `REQ-018`、`REQ-020` 至 `REQ-027`、`REQ-030`、`REQ-032`、`REQ-035`、`REQ-037` 至 `REQ-041`。

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_read_and_validation_success_responses_include_effect_semantics tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_read_and_validation_rejections_include_feedback_semantics -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_context_binding_env_tool.py tests/test_run_env_tool.py -q
```

阶段完成标准：

- Read/validation response contract tests 覆盖所有 non-mutating actions。
- State snapshot 在 read/validation rejection and success cases 前后相等。
- Existing no-leak assertions 继续通过。

### Phase 4: Mutation, commit, evidence, binding, and browser session response semantics

目标：覆盖所有 state-changing env actions 的 actual impact semantics，并证明 rejection path 不改变 state。

具体文件变更：

- Modify `scripts/env/services/tasks.py`
- Modify `scripts/env/services/tracks.py`
- Modify `scripts/env/services/artifacts.py`
- Modify `scripts/env/services/bindings.py`
- Modify `scripts/env/services/handoffs.py`
- Modify `scripts/env/services/runs.py`
- Modify `scripts/env/services/evidence.py`
- Modify `scripts/env/services/search.py`
- Modify `scripts/turn_runtime.py`
- Modify `scripts/browser_evidence.py`
- Modify `tests/test_env_tool_response_contract.py`
- Modify `tests/test_runtime_tool_feedback.py`
- Modify `tests/test_market_browser_evidence.py`
- Modify `tests/test_search_env_tool.py`

详细步骤：

1. 在 `tests/test_env_tool_response_contract.py` 新增 `test_mutating_success_responses_include_actual_impact_semantics`，cases 覆盖：
   - `task.create/update/archive/set_current`
   - `track.join/create/update/advance/archive/attach_task/detach_task`
   - `artifact.create_revision/update_metadata`
   - `binding.set_task/set_track/clear`
   - `handoff.create`
   - `run.commit`
   - `evidence.issue_browser/approve_downgrade`
   - `search.open_browser`
2. 对 mutating success helper 断言 `state_changed is True`、`durability` 匹配 action group、`effect_summary` 非空、`state_changes` 至少一项、`created_ids/updated_ids/binding_changed` 与 action effect 一致。
3. 在 `tests/test_runtime_tool_feedback.py` 新增 `test_mutating_rejections_include_no_state_changed_impact`，cases 覆盖 duplicate task create、non-PM track update、ambiguous track.join、artifact create invalid source run、binding set_task foreign task、handoff create invalid target、run commit stale context、evidence issue without browser, search open_browser without endpoint。
4. 修改 `scripts/env/services/tasks.py` mutating actions：
   - `create_task_for_active_buddy()`：state change object `task`, change `created`, `created_ids=[task_id]`, durability `runtime_object`。
   - `set_current_task()`：state change object `instance_binding`, change `current_task_id/current_track_id updated`, `binding_changed=true`, durability `instance_binding`。
   - `update_task_for_active_buddy()`：state change object `task`, change `updated fields: <sorted patch keys>`, `updated_ids=[task_id]`。
   - `archive_task_for_active_buddy()`：change `status set to archived`, no deletion.
5. 修改 `scripts/env/services/tracks.py` mutating actions：
   - `join_track_for_active_buddy()`：state changes include task `created` or `reused/attached` and instance binding updated; `created_ids` only when task created; `updated_ids` includes reused/attached task id when relation changed。
   - `create/update/advance/archive`：state changes target track, durability `runtime_object`, PM lifecycle authority explained。
   - `attach_task/detach_task`：state changes target task track relation and maybe track task list, no lifecycle fields changed。
6. 修改 `scripts/env/services/artifacts.py` mutating actions：
   - `create_artifact_revision()`：state changes include artifact revision `created` and task artifact slot `current revision updated`; durability `runtime_object`。
   - `update_artifact_metadata()`：state change `metadata updated`, `does_not_write` already says content not written。
7. 修改 `scripts/env/services/bindings.py`:
   - `set_task_binding()`、`set_track_binding()`、`clear_binding()` success include state_changes object type `instance_binding` and `binding_changed=true`。
8. 修改 `scripts/env/services/handoffs.py`:
   - `create_handoff_for_active_buddy()` success include state change object type `handoff`, `created_ids=[handoff_id]`, durability `runtime_object`, effect says track lifecycle unchanged。
9. 修改 `scripts/env/services/runs.py`:
   - `commit_for_active_instance()` wraps `commit_buddy_run()` payload with `effect_summary`, `state_changed=true`, `durability="run_commit"`, `state_changes` containing `run` audit committed and reservation consumed when applicable。
10. 修改 `scripts/env/services/evidence.py`:
    - `_payload_error()` and RuntimeFeedbackError details include semantic rejection fields。
    - `_issue()` success include `state_changed=true`, `durability="broker_token"`, `state_changes` object type `evidence_token`, `created_ids` with token id if available, effect says token must be included in next artifact-producing persist。
11. 修改 `scripts/env/services/search.py::open_browser_for_active_instance()` success to include browser session mutation semantics; browser open failure rejection says no BuddySwitch state changed and retry after browser ensure。
12. 修改 `scripts/turn_runtime.py::runtime_error()` and `scripts/browser_evidence.py::_runtime_error()` so product CLI feedback with allowed next actions includes semantic rejection fields and state unchanged unless payload already contains a more specific state_changed value。

预期行为变化：

- Every mutating success tells host exactly which state class changed.
- Every mutating rejection explains no state changed and how to recover.
- Run/evidence/search open-world and token/browser durability are explicit.

对应需求编号：`REQ-012`、`REQ-015` 至 `REQ-020`、`REQ-021` 至 `REQ-029`、`REQ-031` 至 `REQ-036`、`REQ-039` 至 `REQ-041`。

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_mutating_success_responses_include_actual_impact_semantics -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_tool_feedback.py::RuntimeToolFeedbackTests::test_mutating_rejections_include_no_state_changed_impact -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_evidence_env_tool.py tests/test_market_browser_evidence.py tests/test_search_env_tool.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_context_binding_env_tool.py tests/test_run_env_tool.py -q
```

阶段完成标准：

- Mutating action success contract 覆盖全部 state-changing actions。
- Mutating rejection snapshot tests 证明失败前后 tracks/tasks/artifacts/runs/binding/evidence token/browser test state 符合 response impact。
- Product CLI feedback 仍输出 structured JSON。

### Phase 5: Host judgment scenarios and repo consistency

目标：用 realistic host scenarios 验证 semantic quality，不只验证字段存在。

具体文件变更：

- Modify `tests/test_host_decision_surface_product_mode.py`
- Modify `tests/test_env_layer_end_to_end.py`
- Modify `tests/test_env_tool_response_contract.py`
- Modify `tests/test_repo_consistency.py`
- Modify `framework/docs/turn-runtime-spec.md`

详细步骤：

1. 在 `tests/test_host_decision_surface_product_mode.py` 新增 `test_runtime_env_tool_semantics_support_direct_source_intake_decision`：prepare dev context，读取 `runtime_context.env_tools.track.action_semantics.get` 和 `artifact.action_semantics.get`，断言 host 能从 semantics 判断先 `track.get` 再 `artifact.get`，不检查 service code。
2. 在同文件新增 `test_join_recovery_response_explains_safe_next_step_and_impact`：seed PM track/artifact，Dev 未 relation，`artifact.get` rejected，断言 response says no state changed、retryable via `track.join`；执行 `track.join`，断言 response says task/binding changed；再执行 `artifact.get`，断言 full content success says read-only no state changed。
3. 在同文件新增 `test_artifact_validate_create_and_run_validate_commit_explain_state_impact`：`artifact.validate_payload` -> `artifact.create_revision` -> `run.validate_result` -> `run.commit`，断言 validation-only 与 durable writes 区分清楚。
4. 在同文件新增 `test_search_browser_semantics_mark_open_world_and_browser_session_effect`：prepare market/dev context，断言 search action semantics for request/open_browser `open_world=true`，用 fake CDP server 执行 open_browser，response says browser session changed。
5. 在同文件新增 `test_non_pm_lifecycle_rejection_explains_authority_without_service_code`：Dev 调 `track.update`，断言 `permission_boundary` stable，`human_summary` normal-language，`retryable=false`，allowed next options include `track.get` or `handoff.create` not retry same action as Dev。
6. 在 `tests/test_env_layer_end_to_end.py` 增强 existing end-to-end flow，断言每一步 used response has `effect_summary/state_changed/durability`，blocked recovery has semantic feedback fields。
7. 在 `tests/test_env_tool_response_contract.py` 新增 `test_all_registered_actions_have_at_least_one_response_semantics_case`：维护 explicit coverage map `{ "tool.action": "test-case-id" }`，断言覆盖全部 42 actions；该 map 是测试 contract，不根据 implementation 自动生成 pass。
8. 在 `tests/test_repo_consistency.py` 新增 `test_env_semantic_contract_not_docs_only`：扫描 `docs/memo` 和 `framework/docs` 中的 semantic contract key mentions，同时断言 `contracts.semantic_contract_errors()` empty and `env_tools_description()` contains same fields；如果只有 docs mentions 而 projection missing，测试失败。
9. 在 `tests/test_repo_consistency.py` 新增 `test_no_heavy_semantic_contract_abstractions`：拒绝新增文件或 tokens：`mcp_server.py`、`tool_search_subsystem`、`workflow_engine`、`permission_language`、`schema_generation_framework`、`semantic_v1`、`semantic_v2`。
10. 更新 `framework/docs/turn-runtime-spec.md`，把 host judgment acceptance scenarios 写成 verifiable contract：direct source intake、joining work、artifact write、run validate/commit、search/browser、blocked operations、PM-only lifecycle vs non-PM work。

预期行为变化：

- Reviewer 可从 runtime context 和 sample responses 解释 next step 和 actual impact。
- Tests reject empty/prose-only semantics。
- Repo consistency guards prevent heavy abstraction drift。

对应需求编号：`REQ-001`、`REQ-030` 至 `REQ-043`。

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_host_decision_surface_product_mode.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_all_registered_actions_have_at_least_one_response_semantics_case -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
```

阶段完成标准：

- Host judgment scenarios all pass。
- Coverage map includes all 42 registered actions。
- Repo consistency tests prove semantics are runtime-visible and no heavy deferred architecture was introduced。

### Phase 6: Final focused and broad verification

目标：证明 full task complete，且 existing env tool behavior has not regressed.

具体文件变更：

- No new implementation files in this phase.
- Update `framework/docs/turn-runtime-spec.md` only if Phase 5 tests exposed wording mismatch.

详细步骤：

1. Run focused semantic contract suite.
2. Run all env tool service suites.
3. Run runtime feedback and host decision suites.
4. Run repo consistency suite.
5. Run broad test suite for runtime/broker/tool surfaces used by this work.
6. Inspect `git diff --stat` and `git diff -- docs/spec framework/docs scripts/env tools tests` to confirm scope stayed on semantic contract work.

预期行为变化：

- No behavior change beyond runtime semantic projection and response meaning fields.
- All current env tools still route through existing broker/service path.

对应需求编号：`REQ-001` 至 `REQ-043`。

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_semantic_contract.py tests/test_prepare_runtime_context.py tests/test_env_tool_router.py tests/test_env_tool_response_contract.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_context_binding_env_tool.py tests/test_run_env_tool.py tests/test_evidence_env_tool.py tests/test_search_env_tool.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_tool_feedback.py tests/test_host_decision_surface_product_mode.py tests/test_env_layer_end_to_end.py tests/test_market_browser_evidence.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py tests/test_turn_runtime.py tests/test_turn_integration.py tests/test_run_env_services.py tests/test_repo_consistency.py -q
```

阶段完成标准：

- Listed verification commands exit 0.
- `contracts.semantic_contract_errors()` remains empty.
- No new raw state write path, no MCP server, no workflow engine, no permission language, no long-lived compatibility path.

## 6. 迁移 / 删除策略

- 直接替换 weak runtime projection：`env_tools_description()` 不保留 old-only path；现有 `operations/payload_fields` 作为字段保留，semantic projection 同步输出。
- 直接替换 response helper shape：`tool_responses.success()` 和 `tool_responses.rejection()` 不提供 old semantic-free mode；search call sites 与 helper 同阶段迁移。
- 服务局部 `_error_payload()` 可以保留为 per-service convenience，但必须输出 canonical semantic rejection fields；不得保留仅 machine fields 的 legacy helper。
- 直接更新 direct dict success returns；不新增 wrapper layer hiding old responses。
- `operation_semantics()` 不删除，因为现有 next_action source refs 和 runtime spec 依赖它；新增 semantic layer 是补足 host judgment，不是 replacement。
- Runtime enforcement 不迁移到 semantic metadata；broker/services 仍是 authority。
- 短期兼容仅限保留既有 output fields，例如 `allowed_next_actions`、`next_actions`、`command_hint`、service-specific ids，真实原因是 existing tests and host workflows already consume them。退出条件是没有 current consumer reads those fields and a separate source-backed cleanup request exists；本任务不删除这些 established fields。
- 删除或拒绝新增 speculative structures：MCP server、catalog/inspect subsystem、tool search implementation、generic schema generator、workflow engine、permission language、semantic v1/v2 dual path。

## 7. 完成定义

整个任务完成必须同时满足：

- `prepare.runtime_context.env_tools` 为 9 tools 和 42 actions 投影完整 capability/action semantics。
- `operation_semantics()` machine contract 保持可用，next action `source_refs` 可解析。
- 每个 payload field 有 runtime-visible explanation。
- 每个 mutating action 描述 writes、does_not_write、durability、idempotency 和 risk hints。
- 每个 success response 描述 actual effect、state_changed、durability，并在有意义时列出 created/updated/bound/read/validation-only impact。
- 每个 rejection response 描述 human summary、blocked reason、impact、state_changed、retryability、retry guidance，并保留 existing command hints and structured next actions。
- Runtime enforcement remains in broker/service code; semantic metadata is guidance only。
- Host judgment scenario tests 覆盖 direct source intake、joining work、artifact write、run validate/commit、search/browser、blocked operations、PM-only lifecycle vs non-PM work。
- Tests fail when a new tool/action lacks semantic coverage or when semantic text is empty/low-signal。
- Framework docs state the new semantic contract and out-of-scope boundaries。
- No heavy new abstraction layer, no second tool system, no docs-only coverage。
- Final verification commands in Phase 6 pass in `.worktrees/dev2258`。
