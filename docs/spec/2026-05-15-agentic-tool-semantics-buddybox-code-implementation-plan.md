# Agentic Tool Semantics And Buddybox Code Implementation Plan

> **For agentic workers:** Implement this plan in `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem` on branch `dev_buddy_mem`. Use `superpowers:test-driven-development` for behavior changes and `superpowers:verification-before-completion` before claiming completion.

**Goal:** Strengthen BuddySwitch host-facing tool semantics so a Codex host can infer when `buddybox` is the right private local file-output capability, when `artifact` is the product-readable deliverable path, and where to inspect full payload semantics without hardcoded trigger phrases.

**Architecture:** Keep AGENTS files as short route maps, add compact `context.summarize.tool_affordances` as the default discovery layer, keep full semantics in `context.get.tool_catalog` and `scripts/turn_runtime.py status`, and enrich buddybox responses with structured next-action options. This is a direct semantic-surface upgrade, not a new routing engine.

**Tech Stack:** Python env tool registry/services/tests, TOML manifest, Markdown runtime skills and role contracts, launcher AGENTS templates, pytest.

---

## 1. 任务目标

完成后，BuddySwitch 的运行时发现面能够让 host 从工具语义推断：PM 在只读 `projects/app` 中收到“快速做页面原型”这类需求时，应把单文件草稿/原型写入 active buddy 私有 `buddybox`，而不是修改共享产品源码；当内容需要跨 buddy 或产品流程可读时，应把可读内容写入 `artifact`。当前核心瓶颈是现有语义注册表已经存在，但默认入口 `context.summarize`、runtime AGENTS、shared skill、router feedback 和 buddybox response options 还没有把“私有本地文件输出 vs 产品可读交付物”的含义以足够紧凑、可执行、机器可读的方式暴露出来；这会让 host 依赖短语规则或猜测工具用途。

## 2. 需求提取

- `REQ-001`：运行时工具选择必须来自语义面，不得加入“某个用户短语固定路由到某个工具”的规则。
- `REQ-002`：runtime AGENTS.md 必须保持短 route map，只说明 active buddy、首个 compact context 命令、选择工具时的完整目录检查命令、运行时边界、安全约束和输出规则。
- `REQ-003`：runtime AGENTS.md 不得嵌入完整 tool schemas、buddybox action 清单细节、示例短语触发规则或 PM/Design/Dev 长决策树。
- `REQ-004`：`context.summarize` 必须新增 compact `tool_affordances` block，默认给 host 足够信号判断 buddybox 和 artifact 的适用边界。
- `REQ-005`：`tool_affordances.buddybox` 必须说明 buddybox 用于 active buddy 私有本地文件，包括 drafts、lightweight prototypes、exports、reports、logs、generated files、binary outputs。
- `REQ-006`：`tool_affordances.buddybox` 必须说明 buddybox 不用于 cross-buddy readable deliverables 或 product objects，并说明内容需要 product-readable 时使用 `artifact.create_revision` 承载可读内容。
- `REQ-007`：`tool_affordances.artifact` 必须说明 artifact 用于 task-scoped product-readable deliverables 和 revisions，不用于私有本地文件或 generated binary outputs。
- `REQ-008`：`context.summarize.tool_affordances` 必须保持 compact，不得复制 full `tool_catalog`、action payload schemas 或完整 action semantics。
- `REQ-009`：`context.get.tool_catalog` 和 `context.get.operation_semantics` 必须保留为完整 inspect 层。
- `REQ-010`：`python3 scripts/turn_runtime.py status` 必须继续暴露 full env tool catalog。
- `REQ-011`：`scripts/env/tools/semantics.py` 中 buddybox capability semantics 必须覆盖 active buddy private local workspace、private drafts、lightweight prototypes、exports、reports、logs、generated files、binary outputs。
- `REQ-012`：buddybox capability semantics 必须明确 buddybox is not collaborative、not visible to other buddies、not a product object，并用 artifact promotion 表达 product-readable 内容路径。
- `REQ-013`：buddybox semantics 不得把 artifact promotion 写成每次 buddybox write 后必须执行的唯一动作。
- `REQ-014`：buddybox action semantics 必须覆盖 `desc`、`list`、`read`、`write`、`delete` 的 what、when to use、when not to use、inputs、reads、mutates、side effects、success meaning、common failures。
- `REQ-015`：`buddybox.desc` action semantics 必须说明只返回 semantic description 和 compact state summary，不返回 file content 或完整 file list。
- `REQ-016`：`buddybox.list` action semantics 必须说明只返回 file summary rows，并解释 `path`、`size_bytes`、`updated_at`、`content_type`、`private_to_buddy` 的意义，不返回 `content` 或 `content_base64`。
- `REQ-017`：`buddybox.read` action semantics 必须说明只读取一个 active-buddy private local file，UTF-8 时返回 `content`，否则返回 `content_base64`，`encoding` 说明 body 解释方式。
- `REQ-018`：`buddybox.write` action semantics 必须说明创建或覆盖一个 active-buddy private local file，响应说明 created 或 overwritten，并说明未创建 artifact、handoff、task、track、context、evidence 等对象。
- `REQ-019`：`buddybox.delete` action semantics 必须说明删除一个 active-buddy private local file，重复删除报告 already absent，不暗示 product-state change。
- `REQ-020`：buddybox input semantics 必须说明 `path` 必须在 active buddy prefix 下，例如 `pm/prototypes/landing.html`。
- `REQ-021`：buddybox input semantics 必须说明 `content` 与 `content_base64` 互斥，`content` 是 UTF-8 text，`content_base64` 用于 binary 或 non-UTF-8 payload。
- `REQ-022`：buddybox input semantics 必须说明 `content_type` 是 MIME hint，不是 product contract；read `encoding` 是 output preference，取值为 `auto`、`utf-8`、`base64`。
- `REQ-023`：buddybox responses 必须 compact high-signal；`desc` 和 `list` 不得包含 file content 或完整工具文档。
- `REQ-024`：buddybox success responses 必须包含 actual state impact、`state_changed`、`durability`、created/updated path ids、privacy boundary 或 private ownership signal。
- `REQ-025`：buddybox rejection responses 必须引导 host 回到 active-buddy private-local path，不鼓励绕过 env tool 直接编辑文件系统。
- `REQ-026`：buddybox responses 必须保留 natural-language `allowed_next_actions`，同时为 buddybox success 和 rejection 增加 structured `allowed_next_action_options`。
- `REQ-027`：structured next-action options 必须包含 `tool`、`action`、`mutates`、`reason`、`source_refs`，并通过现有 `tool_responses.next_action_option()` helper 生成。
- `REQ-028`：buddybox write/read responses 的 structured options 必须区分 private iteration 和 conditional artifact promotion。
- `REQ-029`：artifact promotion option 只在 host 判断 content 必须 product-readable 或 cross-buddy-readable 时出现，不得被写成 mandatory。
- `REQ-030`：buddybox rejection options 必须包含 `buddybox.desc` 和 retry original buddybox action with active-buddy path 的机器可读选择。
- `REQ-031`：新增 `buddyswitch/skills/shared/buddybox-tool/SKILL.md`，说明 CLI、path convention、text vs base64 payload、list/read/write/delete/desc 行为、artifact promotion 条件和 response field 验证。
- `REQ-032`：`buddyswitch/manifest.toml` 必须注册 `buddybox-tool` skill，并将其分配给所有拥有 buddybox permissions 的 buddy。
- `REQ-033`：runtime skill materialization 必须把 `buddybox-tool` 复制进每个拥有 buddybox permissions 的 buddy workspace。
- `REQ-034`：framework role contracts 必须只加入短 boundary sentence；PM wording 必须覆盖 PM-owned private local drafts、lightweight prototypes、exports/supporting files 和 product-readable artifact path。
- `REQ-035`：Design、Dev、Test、Market role contracts 必须使用各自角色相关的短 buddybox/artifact 边界，不得复制完整工具文档。
- `REQ-036`：router rejection feedback 必须替换 retired `prepare.runtime_context.env_tools` wording，改指 `context.get.tool_catalog`、`python3 scripts/turn_runtime.py status` 和 `context.summarize.tool_affordances`。
- `REQ-037`：PM page prototype host decision scenario 必须由 semantic surfaces 支撑：PM `projects/app` read-only、quick single-file page prototype 属于 private local generated/prototype file，product-readable/cross-buddy-readable 内容必须通过 artifact content 或其他明确可读引用承载。
- `REQ-038`：handoff 不得依赖 private buddybox path 作为 target buddy readable payload；计划必须保留 existing artifact/handoff/source_ref privacy boundary。
- `REQ-039`：tests 必须包含 realistic host decision scenario，断言 semantic signals 和 expected reasoning inputs，不断言 hardcoded phrase trigger。
- `REQ-040`：不得构建 generic tool-search subsystem、MCP subsystem、rule engine、workflow engine 或长期双路径。
- `REQ-041`：所有阶段都必须有 focused verification，完成前必须运行 broader relevant verification。
- `REQ-042`：实施必须在 `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem` 和 branch `dev_buddy_mem` 内完成，不污染 main。

## 3. 现状探索摘要

### 关键目录、文件、测试、命令

- `docs/memo/2026-05-15-agentic-tool-semantics-buddybox-memo.md`：本计划需求源。
- `AGENTS.md`：仓库级 SHARP/testing-bound 指导，要求最短可验证路径、避免 speculative abstraction、无验证不完成。
- `README.md`：runless runtime loop，已说明 `context.get|context.summarize` 和 active buddy private buddybox path。
- `scripts/env/tools/semantics.py`：已有 capability/action semantics registry；buddybox 已包含 private/local 基础 wording，但缺少 drafts/prototypes/exports/reports/logs/generated/binary 等完整 file-output affordances 和逐 action output meaning。
- `scripts/env/tools/contracts.py`：`env_tools_description()` 已投影 full `tool_catalog`；缺少 compact `tool_affordances` helper。
- `scripts/env/services/context.py`：`context.get` 已返回 `tool_catalog`、`operation_semantics`、`buddybox_desc`；`context.summarize` 尚未返回 `tool_affordances`。
- `scripts/env/services/buddybox.py`：active-buddy local root、`desc/list/read/write/delete`、content/base64、安全 path enforcement 已存在；responses 只有 string `allowed_next_actions`，没有 action-specific `allowed_next_action_options`。
- `scripts/env/tools/responses.py`：已存在 `next_action_option()`、`follow_up_affordance()`、`allowed_next_action_options` canonical fields，可直接复用。
- `scripts/env/tools/router.py`：unsupported tool/action/args feedback 仍引用 `prepare.runtime_context.env_tools`，需要直接替换。
- `scripts/turn_runtime.py`：`status` 已输出 `env_tools` full catalog，是 inspect layer。
- `scripts/env/client.py`：已有 `context get|summarize|list-sources` 和 `buddybox desc|list|read|write|delete` CLI。
- `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md`：已提示 `context summarize`、private local buddybox、structured feedback；缺少选择工具时检查 `context get` 或 `turn_runtime.py status` 的 route map。
- `scripts/runtime_agents.py`：校验 AGENTS 模板；缺少 full catalog route command 检查。
- `framework/contracts/{pm,design,dev,test,market}.md`：role contracts 已有 buddybox wording；PM wording 仍是 weaker “supporting scratch files”，Design/Test 有 “durable file outputs” 旧语义，需要短句替换。
- `buddyswitch/manifest.toml`：已有 shared `track-tool`、`artifact-tool`、`task-tool`、`handoff-tool`；缺少 `buddybox-tool` skill row 和 buddy skill membership。
- `buddyswitch/skills/shared/{task-tool,track-tool,artifact-tool,handoff-tool}/SKILL.md`：shared tool skill 样式来源。
- `tests/test_context_binding_env_tool.py`：context discovery tests，适合加入 compact `tool_affordances` assertions。
- `tests/test_env_tool_semantic_contract.py`：semantic registry tests，适合加强 buddybox complete affordance、input/output meaning、anti-trigger assertions。
- `tests/test_env_tool_response_contract.py` 和 `tests/test_buddybox_env_tool.py`：response tests，适合验证 `allowed_next_action_options`。
- `tests/test_runtime_agents.py`、`tests/test_repo_consistency.py`：runtime AGENTS 和 active surface grep gates。
- `tests/test_runtime_skills.py`、`tests/test_buddyswitch_launcher.py`：shared skill manifest/materialization tests。
- `tests/test_env_tool_router.py`：router feedback tests，适合验证不再出现 `prepare.runtime_context.env_tools`。
- `tests/test_host_decision_surface_product_mode.py`：product-mode decision surface tests，适合加入 PM prototype semantic scenario。

### 保留、替换、删除、迁移

- 保留：`buddybox` active-buddy private local storage under `buddyswitch/local/buddybox/<active_buddy>/**`。
- 保留：`buddybox.desc/list/read/write/delete` operation set、path safety、text/base64 behavior、product object non-mutation behavior。
- 保留：`context.get.tool_catalog`、`context.get.operation_semantics`、`scripts/turn_runtime.py status.env_tools` full inspect layer。
- 保留：artifact/handoff/source_ref private buddybox provenance boundary already implemented by the local workspace work.
- 替换：`context.summarize` compact payload from “candidate ids + buddybox_desc only” to “candidate ids + buddybox_desc + tool_affordances”。
- 替换：buddybox semantic wording from merely private-local to complete file-output affordance wording.
- 替换：buddybox response next-action strings-only guidance with strings plus structured options.
- 替换：router retry guidance from `prepare.runtime_context.env_tools` to current discovery surfaces.
- 替换：role contract weak buddybox lines with short role-specific buddybox/artifact boundary lines.
- 新增：`buddyswitch/skills/shared/buddybox-tool/SKILL.md` and manifest registration.
- 删除：active references to `prepare.runtime_context.env_tools` in runtime feedback.
- 不迁移：no data migration; this work changes semantic surfaces and guidance, not buddybox storage layout.
- 不保留双路径：no phrase router, no compatibility “prototype means HTML” rule, no generic tool search layer.

## 4. 最终目标架构

### 最终文件结构与职责

- Modify `scripts/env/tools/semantics.py`
  - Own canonical full buddybox capability/action meaning.
  - Add `compact_tool_affordances() -> dict[str, dict[str, str]]` returning compact rows for `buddybox` and `artifact`.
  - Strengthen buddybox capability/action semantics with exact file-output affordances, input meanings, output meanings, side effects, common failures, and anti-mandatory-promotion language.

- Modify `scripts/env/tools/contracts.py`
  - Add `compact_tool_affordances() -> dict[str, dict[str, str]]` that delegates to `semantics.compact_tool_affordances()`.
  - Keep `env_tools_description()` as full catalog and `operation_semantics()` as machine-readable inspect map.

- Modify `scripts/env/services/context.py`
  - Add `tool_affordances` only to `context.summarize` response extra.
  - Keep `context.get` full inspect payload unchanged except it continues to include `tool_catalog` and `operation_semantics`.

- Modify `scripts/env/services/buddybox.py`
  - Add small helpers that produce action-specific structured next-action options via `tool_responses.next_action_option()`.
  - Pass `allowed_next_action_options` on `desc`, `list`, `read`, `write`, `delete`, payload rejection, and scope rejection responses.
  - Keep desc/list content-free and keep artifact promotion conditional.

- Modify `scripts/env/tools/router.py`
  - Replace all `prepare.runtime_context.env_tools` retry and action hints with `context.get.tool_catalog`, `python3 scripts/turn_runtime.py status`, and `context.summarize.tool_affordances`.

- Add `buddyswitch/skills/shared/buddybox-tool/SKILL.md`
  - Teach CLI usage for `buddybox desc/list/read/write/delete`.
  - Explain active buddy path convention, `content` vs `content_base64`, `content_type`, read `encoding`, response verification, and artifact promotion boundary.

- Modify `buddyswitch/manifest.toml`
  - Register skill row `id = "buddybox-tool"` with path `buddyswitch/skills/shared/buddybox-tool`.
  - Add `buddybox-tool` to all buddies that include `buddybox.read`, `buddybox.write`, or `buddybox.delete`.

- Modify `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md`
  - Add one route-map bullet: use `context get` or `python3 scripts/turn_runtime.py status` when selecting env tools or checking payload semantics.
  - Keep files short and avoid tool schemas or trigger phrases.

- Modify `scripts/runtime_agents.py`
  - Validate the new route-map bullet by requiring one of `context get`, `scripts/turn_runtime.py status`, or equivalent full tool catalog wording.

- Modify `framework/contracts/{pm,design,dev,test,market}.md`
  - Replace weak buddybox lines with one role-specific private-local/artifact boundary sentence per contract.

- Modify tests:
  - `tests/test_context_binding_env_tool.py`
  - `tests/test_env_tool_semantic_contract.py`
  - `tests/test_env_tool_response_contract.py`
  - `tests/test_buddybox_env_tool.py`
  - `tests/test_runtime_agents.py`
  - `tests/test_runtime_skills.py`
  - `tests/test_buddyswitch_launcher.py`
  - `tests/test_env_tool_router.py`
  - `tests/test_host_decision_surface_product_mode.py`
  - `tests/test_repo_consistency.py`

### 核心数据模型

`context.summarize.tool_affordances`:

```json
{
  "tool_affordances": {
    "buddybox": {
      "use_for": "active buddy private local files: drafts, lightweight prototypes, exports, reports, logs, generated files, binary outputs",
      "not_for": "cross-buddy readable deliverables, product objects, shared source edits, or handoff-readable payloads",
      "promote_with": "artifact.create_revision when readable content must become product-readable",
      "inspect_with": "context.get.tool_catalog['buddybox'] or python3 scripts/turn_runtime.py status"
    },
    "artifact": {
      "use_for": "task-scoped product-readable deliverables and revisions",
      "not_for": "private local files, generated binary outputs, or active-buddy scratch work",
      "inspect_with": "context.get.tool_catalog['artifact'] or python3 scripts/turn_runtime.py status"
    }
  }
}
```

`allowed_next_action_options` rows are produced by `tool_responses.next_action_option()`:

```json
{
  "id": "confirm_private_buddybox_file",
  "tool": "buddybox",
  "action": "read",
  "mutates": "none",
  "preconditions": ["path references an active buddy private local file"],
  "reason": "Confirm the private local file just written.",
  "source_refs": [
    "context.get.tool_catalog['buddybox']",
    "context.get.operation_semantics['buddybox.read']"
  ]
}
```

### 函数、接口、调用流

- Host starts with `python3 scripts/env/client.py context summarize`.
- `scripts/env/client.py` sends broker `env.tool` with `tool="context"`, `action="summarize"`.
- `scripts/env/services/context.py::summarize_context()` calls `_current_context_sections()` and adds `tool_affordances = tool_contracts.compact_tool_affordances()`.
- If `tool_affordances` is insufficient, host calls `python3 scripts/env/client.py context get` or `python3 scripts/turn_runtime.py status`.
- `scripts/env/tools/contracts.py::env_tools_description()` continues to expose full `action_semantics` from `scripts/env/tools/semantics.py`.
- When host calls `buddybox.write`, `scripts/env/services/buddybox.py::write_buddybox_for_active_buddy()` writes exactly one private local file and returns both `allowed_next_actions` and `allowed_next_action_options`.
- If content must be cross-buddy/product-readable, host calls `artifact.create_revision` with readable content; buddybox path remains private provenance only.

## 5. 分阶段实施计划

### 阶段 1：加入 compact `tool_affordances` discovery layer

**目标**

让默认 `context.summarize` 在不加载 full catalog 的情况下暴露 buddybox 与 artifact 的核心适用边界。

**具体文件变更**

- Modify `tests/test_context_binding_env_tool.py`
- Modify `scripts/env/tools/semantics.py`
- Modify `scripts/env/tools/contracts.py`
- Modify `scripts/env/services/context.py`
- Modify `tests/test_repo_consistency.py`

**详细步骤**

1. 在 `tests/test_context_binding_env_tool.py` 新增 `ContextBindingEnvToolTests::test_context_summarize_exposes_compact_tool_affordances`。
   - Seed active buddy `dev` with no special product state.
   - Dispatch `context.summarize`.
   - Assert top-level `tool_affordances` exists.
   - Assert exact keys are `buddybox` and `artifact`.
   - Assert `buddybox.use_for` contains `private local`, `drafts`, `lightweight prototypes`, `exports`, `reports`, `logs`, `generated files`, `binary outputs`.
   - Assert `buddybox.not_for` contains `cross-buddy readable` and `product objects`.
   - Assert `buddybox.promote_with` contains `artifact.create_revision`.
   - Assert `artifact.use_for` contains `product-readable deliverables`.
   - Assert the compact block does not contain `payload_fields`, `action_semantics`, `content`, or `content_base64`.
2. Run the focused test and confirm it fails because `tool_affordances` is absent:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_exposes_compact_tool_affordances -q
```

3. In `scripts/env/tools/semantics.py`, add `compact_tool_affordances()` returning the exact data model from section 4.
4. In `scripts/env/tools/contracts.py`, add `compact_tool_affordances()` delegating to `semantics.compact_tool_affordances()`.
5. In `scripts/env/services/context.py::summarize_context()`, add `"tool_affordances": tool_contracts.compact_tool_affordances()` to `summary`.
6. Keep `context.get` unchanged so full `tool_catalog` and `operation_semantics` remain inspect-only surfaces.
7. In `tests/test_repo_consistency.py::test_env_tool_surface_is_runtime_visible_and_runless`, assert `tool_contracts.compact_tool_affordances()` has `buddybox` and `artifact`, and assert `turn_runtime._build_env_tools_desc()` remains full catalog.
8. Run focused verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_context_binding_env_tool.py tests/test_repo_consistency.py::RepoConsistencyTests::test_env_tool_surface_is_runtime_visible_and_runless -q
```

**预期行为变化**

`context.summarize` returns a compact `tool_affordances` block that lets the host infer buddybox/private-file vs artifact/product-readable boundaries without reading full action schemas.

**对应需求编号**

`REQ-004`, `REQ-005`, `REQ-006`, `REQ-007`, `REQ-008`, `REQ-009`, `REQ-010`, `REQ-037`, `REQ-040`

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_context_binding_env_tool.py tests/test_repo_consistency.py::RepoConsistencyTests::test_env_tool_surface_is_runtime_visible_and_runless -q
```

**阶段完成标准**

- `context.summarize` contains `tool_affordances`.
- The compact block is limited to the four string fields per tool.
- `context.get` still contains full `tool_catalog` and `operation_semantics`.
- `turn_runtime.py status` remains the full env tool catalog path.

### 阶段 2：强化 canonical buddybox full semantics

**目标**

让 full catalog 中 buddybox capability/action semantics 足以通过 “intern test”：不读 service code 也能知道何时用 buddybox、何时不用、payload 字段含义、成功/失败意味着什么。

**具体文件变更**

- Modify `tests/test_env_tool_semantic_contract.py`
- Modify `scripts/env/tools/semantics.py`

**详细步骤**

1. 在 `tests/test_env_tool_semantic_contract.py` 新增 `EnvToolSemanticContractTests::test_buddybox_semantics_cover_file_output_affordances_and_output_meanings`。
   - Pack `contracts.env_tools_description()["buddybox"]`.
   - Assert capability text contains `active buddy`, `private`, `local workspace`, `drafts`, `lightweight prototypes`, `exports`, `reports`, `logs`, `generated files`, `binary outputs`, `not collaborative`, `not visible to other buddies`, `not product object`, `artifact`, `product-readable`.
   - Assert `action_semantics["desc"].success_means` contains `semantic description` and `compact local summary only`.
   - Assert `action_semantics["list"].success_means` contains `summaries only` and `no file content`.
   - Assert `action_semantics["read"].success_means` contains `one active buddy private local file` and either `content` or `content_base64`.
   - Assert `action_semantics["write"].success_means` contains `created or overwrote one active buddy private local file` and `did not create artifact/handoff/task/track/context/evidence`.
   - Assert `action_semantics["delete"].success_means` contains `absent` and `no product/collaboration object changed`.
2. Extend existing input assertion in `test_action_semantics_explain_inputs_side_effects_and_success` by adding buddybox-specific checks:
   - `write.content` explains UTF-8 text.
   - `write.content_base64` explains binary or non-UTF-8 payloads.
   - `write.content_type` explains MIME hint and not product contract.
   - `read.encoding` explains `auto`, `utf-8`, `base64`.
   - `list.path`, `read.path`, `write.path`, `delete.path` mention active buddy prefix.
3. Extend `test_buddybox_semantics_keep_host_decision_space`:
   - Assert no buddybox semantics contain `prototype means`, `hardcoded trigger`, `always create artifact`, `must create artifact`, `only next action`.
   - Assert artifact promotion text includes `when host decides` or `when content must become product-readable`.
4. Run the new semantic tests and confirm they fail on missing exact affordances/output wording:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_buddybox_semantics_cover_file_output_affordances_and_output_meanings tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_buddybox_semantics_keep_host_decision_space -q
```

5. In `scripts/env/tools/semantics.py`, update `_CAPABILITIES["buddybox"]`:
   - `plain_description`: mention active buddy private local workspace for private drafts, lightweight prototypes, exports, reports, logs, generated files, and binary outputs; state it is not collaborative, not visible to other buddies, and not a product object.
   - `use_when`: include private file outputs and conditional artifact promotion.
   - `do_not_use_when`: include cross-buddy readable deliverables, product objects, shared source edits, and handoff-readable payloads.
   - `capability_boundary`: state only active buddy private local root paths are allowed and buddybox paths do not grant cross-buddy read authority.
6. In the buddybox action rows:
   - Rewrite `plain_description`, `use_when`, `do_not_use_when`, `inputs_explained`, `success_means`, and `common_failures` per `REQ-014` through `REQ-022`.
   - For `write.success_means`, include exact product-object non-write list: artifact, handoff, task, track, context, evidence.
   - For `list.inputs_explained.path`, explain active buddy prefix filter.
   - For `read.inputs_explained.encoding`, list `auto`, `utf-8`, `base64`.
   - For `write.inputs_explained.content_type`, state MIME hint only, not a product contract.
7. Run focused verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_semantic_contract.py -q
```

**预期行为变化**

Full catalog semantics explain buddybox as a generalized private file-output capability, not a phrase-triggered prototype rule, and each action explains observable output meanings.

**对应需求编号**

`REQ-001`, `REQ-011`, `REQ-012`, `REQ-013`, `REQ-014`, `REQ-015`, `REQ-016`, `REQ-017`, `REQ-018`, `REQ-019`, `REQ-020`, `REQ-021`, `REQ-022`, `REQ-039`, `REQ-040`

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_semantic_contract.py -q
```

**阶段完成标准**

- `contracts.semantic_contract_errors()` returns `[]`.
- Buddybox full semantics pass all required vocabulary and anti-trigger assertions.
- No buddybox semantic text makes artifact promotion mandatory after every write.

### 阶段 3：新增 shared `buddybox-tool` skill 并注册到 manifest

**目标**

把 buddybox 操作知识从 AGENTS.md 移到 shared skill，使运行时默认 guidance 保持短，同时拥有 buddybox permissions 的 buddies 自动获得 task-level tool usage guidance。

**具体文件变更**

- Add `buddyswitch/skills/shared/buddybox-tool/SKILL.md`
- Modify `buddyswitch/manifest.toml`
- Modify `tests/test_runtime_skills.py`
- Modify `tests/test_buddyswitch_launcher.py`
- Modify `tests/test_repo_consistency.py`

**详细步骤**

1. In `tests/test_runtime_skills.py`, change `required = {"track-tool", "artifact-tool", "task-tool", "handoff-tool"}` to include `"buddybox-tool"`.
2. Add `RuntimeSkillsTests::test_buddybox_tool_skill_teaches_private_local_file_workflow`:
   - Read `buddyswitch/skills/shared/buddybox-tool/SKILL.md`.
   - Assert it contains `python3 scripts/env/client.py buddybox`, `desc`, `list`, `read`, `write`, `delete`, `<active_buddy>/`, `content`, `content_base64`, `content_type`, `encoding`, `artifact.create_revision`, `allowed_next_actions`, `allowed_next_action_options`.
   - Assert it does not contain `prepare`, `persist`, `directly edit`, `always create artifact`, `prototype means`.
3. In `tests/test_buddyswitch_launcher.py::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy`, assert `"buddybox-tool"` is present in `installed_skill_ids` for every buddy with buddybox permission.
4. In `tests/test_repo_consistency.py::test_shared_skills_are_runless`, include `buddyswitch/skills/shared/buddybox-tool/SKILL.md` in `shared`.
5. Run focused tests and confirm failures due to missing skill and manifest rows:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_buddyswitch_launcher.py::BuddyswitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy tests/test_repo_consistency.py::RepoConsistencyTests::test_shared_skills_are_runless -q
```

6. Create `buddyswitch/skills/shared/buddybox-tool/SKILL.md` with this content shape:

```markdown
---
name: buddybox-tool
description: Use when you need to describe, list, read, write, or delete active-buddy private local files through runtime env tools.
---

# buddybox-tool

## Purpose
- Manage active buddy private local files through broker-routed env tools.
- Use for private drafts, lightweight prototypes, exports, reports, logs, generated files, and binary outputs.
- Use `artifact.create_revision` when readable content must become product-readable or cross-buddy-readable.

## Runtime Contract
- CLI: `python3 scripts/env/client.py buddybox <operation>`
- Broker method: `env.tool`
- Operations: `desc`, `list`, `read`, `write`, `delete`
- Path convention: every path stays under `<active_buddy>/...`, such as `pm/prototypes/landing.html`.

## Payload Hints
- `write` accepts exactly one of `content` or `content_base64`.
- `content` is UTF-8 text.
- `content_base64` is for binary or non-UTF-8 payloads.
- `content_type` is a MIME hint for the file, not a product contract.
- `read --encoding` accepts `auto`, `utf-8`, or `base64`.

## Response Checks
- Confirm response JSON has `ok=true` before relying on a file operation.
- `desc` and `list` do not return file bodies.
- `write` reports whether the file was created or overwritten.
- `delete` reports whether the file was deleted or already absent.
- Follow `allowed_next_actions` and `allowed_next_action_options`; do not edit `buddyswitch/local/buddybox/**` directly.
```

7. In `buddyswitch/manifest.toml`, add:
   - A `[[skills]]` row with `id = "buddybox-tool"` and `path = "buddyswitch/skills/shared/buddybox-tool"`.
   - `"buddybox-tool"` to every buddy `skills` list containing buddybox permissions: `market`, `pm`, `design`, `dev`, `test`.
8. Run focused verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_buddyswitch_launcher.py::BuddyswitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy tests/test_repo_consistency.py::RepoConsistencyTests::test_shared_skills_are_runless -q
```

**预期行为变化**

Every buddy that can call buddybox receives a shared skill that teaches exact buddybox CLI and verification behavior. AGENTS.md no longer needs detailed buddybox operation docs.

**对应需求编号**

`REQ-002`, `REQ-003`, `REQ-031`, `REQ-032`, `REQ-033`, `REQ-040`

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_buddyswitch_launcher.py::BuddyswitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy tests/test_repo_consistency.py::RepoConsistencyTests::test_shared_skills_are_runless -q
```

**阶段完成标准**

- Manifest skill rows remain `id` and `path` only.
- All buddy skill lists with buddybox permissions contain `buddybox-tool`.
- Launcher materializes `buddybox-tool` into runtime `.agents/skills`.
- Shared skill contains no prepare/persist or hardcoded trigger wording.

### 阶段 4：为 buddybox responses 增加 structured next-action options

**目标**

让 buddybox operation responses 同时给人类可读 next actions 和机器可读 next-action choices，明确 private iteration 与 conditional artifact promotion。

**具体文件变更**

- Modify `tests/test_buddybox_env_tool.py`
- Modify `tests/test_env_tool_response_contract.py`
- Modify `scripts/env/services/buddybox.py`

**详细步骤**

1. In `tests/test_buddybox_env_tool.py`, add helper `_assert_option(payload, option_id, tool, action)` that:
   - Reads `payload["allowed_next_action_options"]`.
   - Finds row by `id`.
   - Asserts `tool`, `action`, `mutates`, `reason`, `source_refs`, and `preconditions` are present.
2. Extend `test_buddybox_desc_returns_private_local_workspace_summary`:
   - Assert desc response has options for `buddybox.list` and `buddybox.write`.
3. Extend `test_buddybox_text_and_binary_lifecycle_uses_local_root`:
   - After `write`, assert options:
     - `confirm_private_buddybox_file` with `tool="buddybox"`, `action="read"`, `mutates="none"`.
     - `inspect_private_buddybox_summaries` with `tool="buddybox"`, `action="list"`.
     - `promote_readable_content_when_needed` with `tool="artifact"`, `action="create_revision"`.
   - Assert promotion option `reason` contains `when` and does not contain `must`.
   - After `read`, assert options:
     - `replace_private_buddybox_file` with `buddybox.write`.
     - `promote_readable_content_when_needed` with `artifact.create_revision`.
   - After `list`, assert no row contains `content` or `content_base64`.
4. Extend `test_pm_cannot_read_list_write_or_delete_foreign_private_paths`:
   - Assert rejection responses include `review_buddybox_private_boundary` with `buddybox.desc`.
   - Assert rejection responses include `retry_active_buddy_private_path` using the rejected buddybox action.
   - Assert `state_changed` is `False`.
5. In `tests/test_env_tool_response_contract.py::test_success_responses_cover_read_write_and_target_scoped_evidence`, assert `written_file["allowed_next_action_options"]` includes one `artifact.create_revision` option and one `buddybox.read` option.
6. Run focused tests and confirm failures due to missing `allowed_next_action_options` in buddybox service:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddybox_env_tool.py tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_success_responses_cover_read_write_and_target_scoped_evidence -q
```

7. In `scripts/env/services/buddybox.py`, add helpers:
   - `_operation_semantic_ref(action: str) -> str` returning `context.get.operation_semantics['buddybox.<action>']`.
   - `_tool_catalog_ref(tool: str) -> str` returning `context.get.tool_catalog['<tool>']`.
   - `_next_option(tool: str, action: str, option_id: str, reason: str, preconditions: list[str] | None = None) -> dict[str, Any]` calling `tool_responses.next_action_option()` with explicit source refs.
   - `_buddybox_retry_option(action: str) -> dict[str, Any]` for retrying the same buddybox action under active-buddy path rules.
8. Add response option lists:
   - Desc: `inspect_private_buddybox_summaries` (`buddybox.list`), `write_private_buddybox_file` (`buddybox.write`).
   - List: `read_private_buddybox_file` (`buddybox.read`), `write_private_buddybox_file` (`buddybox.write`).
   - Read: `replace_private_buddybox_file` (`buddybox.write`), `promote_readable_content_when_needed` (`artifact.create_revision`).
   - Write: `confirm_private_buddybox_file` (`buddybox.read`), `inspect_private_buddybox_summaries` (`buddybox.list`), `promote_readable_content_when_needed` (`artifact.create_revision`).
   - Delete: `inspect_private_buddybox_summaries` (`buddybox.list`), `write_private_buddybox_file` (`buddybox.write`).
   - Rejections: `review_buddybox_private_boundary` (`buddybox.desc`) and `retry_active_buddy_private_path` for the same buddybox action.
9. Pass these lists to `tool_responses.success(..., allowed_next_action_options=...)` and `tool_responses.rejection(..., allowed_next_action_options=...)`.
10. Keep existing `allowed_next_actions` strings intact unless changing wording is required to remove mandatory artifact language.
11. Run focused verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddybox_env_tool.py tests/test_env_tool_response_contract.py -q
```

**预期行为变化**

Buddybox responses include structured next-action choices that a host can evaluate without parsing prose. File content remains absent from `desc` and `list`, and artifact promotion remains conditional.

**对应需求编号**

`REQ-023`, `REQ-024`, `REQ-025`, `REQ-026`, `REQ-027`, `REQ-028`, `REQ-029`, `REQ-030`

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddybox_env_tool.py tests/test_env_tool_response_contract.py -q
```

**阶段完成标准**

- Every buddybox success/rejection response has non-empty `allowed_next_action_options`.
- Structured options contain `tool`, `action`, `mutates`, `reason`, `source_refs`.
- Write/read options include both private iteration and conditional artifact promotion.
- Rejection options guide to `buddybox.desc` and retry under active buddy root.

### 阶段 5：更新 AGENTS route map、role contracts、router feedback

**目标**

把 host 的默认指引改成 layered discovery：AGENTS 指路，`context.summarize` 给 compact affordances，`context.get`/`turn_runtime.py status` 给 full catalog；同时删除 retired prepare wording。

**具体文件变更**

- Modify `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md`
- Modify `scripts/runtime_agents.py`
- Modify `framework/contracts/{pm,design,dev,test,market}.md`
- Modify `scripts/env/tools/router.py`
- Modify `tests/test_runtime_agents.py`
- Modify `tests/test_repo_consistency.py`
- Modify `tests/test_env_tool_router.py`

**详细步骤**

1. In `tests/test_runtime_agents.py::test_runtime_agents_point_to_runless_context_discovery`, add assertions for each runtime AGENTS template:
   - Contains `python3 scripts/env/client.py context get` or `python3 scripts/turn_runtime.py status`.
   - Contains `tool catalog` or `payload semantics`.
   - Does not contain `payload_fields`, `action_semantics`, `prototype means`, `always create artifact`.
2. In `tests/test_repo_consistency.py`, add `RepoConsistencyTests::test_active_runtime_feedback_points_to_current_tool_discovery_surfaces`:
   - Scan `scripts`, `tools`, `framework`, `buddyswitch`, `README.md`, `AGENTS.md`.
   - Exclude `docs/memo/**` and `docs/spec/**`.
   - Assert no hit for `prepare.runtime_context.env_tools`.
   - Assert `scripts/env/tools/router.py` contains `context.get.tool_catalog`, `context.summarize.tool_affordances`, and `scripts/turn_runtime.py status`.
3. In `tests/test_env_tool_router.py::test_rejects_malformed_envelope_without_state_mutation`, assert for each malformed response:
   - `retry_guidance` and `allowed_next_actions` do not contain `prepare.runtime_context`.
   - Unsupported tool/action/args cases mention `context.get.tool_catalog` or `scripts/turn_runtime.py status`.
4. Add `RepoConsistencyTests::test_role_contracts_keep_buddybox_guidance_short_and_role_specific`:
   - PM contract contains `PM-owned private local drafts`, `lightweight prototypes`, `artifact when content must become product-readable`.
   - Design contract contains `private local prototypes` or `exports`, and artifact for design handoffs/prototype briefs.
   - Dev contract contains `private logs`, `generated files` or `binary outputs`, and artifact for implementation reports.
   - Test contract contains `private logs` or `raw evidence files`, and artifact for pass/fail reports.
   - Market contract contains `private research exports` or `logs`, and artifact for market deliverables.
   - Each contract does not contain `payload_fields`, `action_semantics`, `prepare.runtime_context`, `always create artifact`.
5. Run focused tests and confirm failures on missing route-map/full-catalog wording and stale router text:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_agents.py tests/test_env_tool_router.py tests/test_repo_consistency.py::RepoConsistencyTests::test_active_runtime_feedback_points_to_current_tool_discovery_surfaces tests/test_repo_consistency.py::RepoConsistencyTests::test_role_contracts_keep_buddybox_guidance_short_and_role_specific -q
```

6. Update each `tools/launcher/assets/buddies/<buddy>/AGENTS.md` under `## Runtime Boundary`:
   - Keep `Start with python3 scripts/env/client.py context summarize`.
   - Add one bullet: `When selecting env tools or payload semantics, use python3 scripts/env/client.py context get or python3 scripts/turn_runtime.py status for the full tool catalog.`
   - Do not add action schemas or example trigger phrases.
7. Update `scripts/runtime_agents.py::validate_runtime_agents_template()`:
   - Add `_require_contains_any()` for full catalog route wording with needles:
     - `python3 scripts/env/client.py context get`
     - `python3 scripts/turn_runtime.py status`
   - Add a negative check raising `RuntimeAgentsError` if `payload_fields`, `action_semantics`, `prototype means`, or `always create artifact` appears in runtime AGENTS templates.
8. Update role contracts:
   - `framework/contracts/pm.md`: replace scratch wording with `Use buddybox for PM-owned private local drafts, lightweight prototypes, exports, or supporting files; use artifact when content must become product-readable.`
   - `framework/contracts/design.md`: replace durable file output wording with `Use buddybox for private local prototypes or exports; use artifact for design handoffs or prototype briefs another buddy must read.`
   - `framework/contracts/dev.md`: replace non-object supporting files wording with `Use buddybox for private logs, generated files, binary outputs, or local reports; use artifact for implementation reports and technical conclusions the product workflow must read.`
   - `framework/contracts/test.md`: replace durable logs/evidence wording with `Use buddybox for private logs, raw evidence files, or local reports; use artifact for pass/fail reports the product workflow must read.`
   - `framework/contracts/market.md`: add `Use buddybox for private research exports, logs, or local reports; use artifact for market deliverables PM, Design, or Dev must read.`
9. Update `scripts/env/tools/router.py` strings:
   - Unsupported tool `retry_guidance`: `Inspect context.get.tool_catalog, context.summarize.tool_affordances, or python3 scripts/turn_runtime.py status, then retry with a supported tool.`
   - Unsupported tool `allowed_next_actions`: include `Use context.get for tool_catalog and operation_semantics.` and `Run python3 scripts/turn_runtime.py status for the full env tool catalog.`
   - Unsupported action `retry_guidance`: point to `context.get.operation_semantics` and `scripts/turn_runtime.py status`.
   - Non-object args `allowed_next_actions`: point to `context.get.tool_catalog['<tool>'].payload_fields`.
10. Run focused verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_agents.py tests/test_env_tool_router.py tests/test_repo_consistency.py -q
```

**预期行为变化**

Runtime guidance and feedback now direct hosts to current runless discovery surfaces. No active runtime text points to retired prepare payloads.

**对应需求编号**

`REQ-002`, `REQ-003`, `REQ-034`, `REQ-035`, `REQ-036`, `REQ-040`

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_agents.py tests/test_env_tool_router.py tests/test_repo_consistency.py -q
```

**阶段完成标准**

- All runtime AGENTS templates remain short and include both compact and full discovery routes.
- Role contracts contain short role-specific buddybox/artifact boundary sentences.
- `rg -n "prepare\\.runtime_context\\.env_tools" scripts tools framework buddyswitch README.md AGENTS.md` returns no active hits.

### 阶段 6：加入 PM prototype host decision scenario 并运行最终验证

**目标**

证明 PM “先做一个简单页面原型”场景由 semantic surfaces 支撑，而不是由 hardcoded phrase routing 支撑。

**具体文件变更**

- Modify `tests/test_host_decision_surface_product_mode.py`
- Modify `tests/test_context_binding_env_tool.py`
- Modify `tests/test_env_tool_semantic_contract.py`
- Modify `tests/test_repo_consistency.py`

**详细步骤**

1. In `tests/test_host_decision_surface_product_mode.py`, add `HostDecisionSurfaceProductModeTests::test_pm_page_prototype_decision_surface_prefers_private_buddybox_without_phrase_rule`.
2. Test setup:
   - Use active buddy `pm`.
   - Use existing PM runtime AGENTS/profile text to assert `project.access=read-only`.
   - Dispatch `context.summarize`.
3. Test assertions:
   - `tool_affordances.buddybox.use_for` contains `lightweight prototypes` and `private local files`.
   - `tool_affordances.buddybox.not_for` contains `product objects` and `cross-buddy readable deliverables`.
   - `tool_affordances.buddybox.promote_with` contains `artifact.create_revision`.
   - `tool_affordances.artifact.use_for` contains `product-readable deliverables`.
   - `context.get.tool_catalog["buddybox"]["action_semantics"]["write"]` explains `content` and `content_base64`.
   - The semantic payload does not contain `prototype means` or `quickly build means`.
4. In the same test, dispatch `buddybox.write` with:

```json
{
  "path": "pm/prototypes/simple-page.html",
  "content": "<!doctype html><html><body><h1>Prototype</h1></body></html>",
  "content_type": "text/html"
}
```

5. Assert:
   - File exists under `buddyswitch/local/buddybox/pm/prototypes/simple-page.html`.
   - Response says no artifact/handoff/task/track/context/evidence state changed.
   - Response options include `buddybox.read`, `buddybox.list`, and conditional `artifact.create_revision`.
6. In `tests/test_repo_consistency.py`, add grep guard `test_no_hardcoded_intent_to_buddybox_phrase_routing`:
   - Scan active code/docs excluding `docs/memo/**` and `docs/spec/**`.
   - Reject phrases `prototype means`, `quickly build means`, `simple page prototype means`, `route prototype to buddybox`, `hardcoded trigger`.
7. Run focused test and confirm failures before implementation pieces are complete:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_pm_page_prototype_decision_surface_prefers_private_buddybox_without_phrase_rule tests/test_repo_consistency.py::RepoConsistencyTests::test_no_hardcoded_intent_to_buddybox_phrase_routing -q
```

8. If earlier phases already satisfy the assertions, keep this phase as scenario-level proof and do not add new production code.
9. Run focused verification target:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_runtime_agents.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_buddybox_env_tool.py \
  tests/test_env_tool_router.py -q
```

10. Run broader relevant verification target:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_memory_removal_contract.py \
  tests/test_env_tool_router.py \
  tests/test_runless_runtime_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_agents.py \
  tests/test_runtime_skills.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_buddybox_env_tool.py \
  tests/test_buddyswitch_launcher.py::BuddyswitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy \
  tests/test_repo_consistency.py -q
```

**预期行为变化**

PM prototype scenario has a tested semantic path: default summary identifies buddybox as private prototype output, full catalog explains payload semantics, buddybox write produces private file and conditional artifact promotion option.

**对应需求编号**

`REQ-001`, `REQ-004`, `REQ-005`, `REQ-006`, `REQ-007`, `REQ-008`, `REQ-023`, `REQ-024`, `REQ-026`, `REQ-028`, `REQ-029`, `REQ-037`, `REQ-038`, `REQ-039`, `REQ-040`, `REQ-041`, `REQ-042`

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_host_decision_surface_product_mode.py tests/test_repo_consistency.py::RepoConsistencyTests::test_no_hardcoded_intent_to_buddybox_phrase_routing -q
```

**阶段完成标准**

- PM scenario test passes without any phrase-routing implementation.
- Focused target passes.
- Broader relevant target passes.
- Active grep gates show no retired prepare tool-catalog wording and no hardcoded prototype routing phrase.

## 6. 迁移 / 删除策略

- No runtime data migration is required because this task does not change buddybox storage layout or product object schemas.
- Delete retired `prepare.runtime_context.env_tools` references from active router feedback; no compatibility wording remains because runless `context.get` and `turn_runtime.py status` are the current inspect surfaces.
- Do not create any phrase router, compatibility trigger table, generic routing framework, workflow engine, or MCP-style tool-search subsystem.
- Do not keep detailed buddybox operation docs in AGENTS.md after adding `buddybox-tool`; the skill is the task-specific documentation surface.
- Keep existing artifact/handoff/source_ref privacy boundary and tests; no dual path allowing private buddybox paths as handoff-readable payloads.
- Short-term compatibility is not needed. The only accepted stable surfaces are `context.summarize.tool_affordances`, `context.get.tool_catalog`, `context.get.operation_semantics`, `turn_runtime.py status.env_tools`, and structured tool responses.

## 7. 完成定义

The full task is complete when:

- `context.summarize` exposes compact `tool_affordances` for buddybox and artifact without dumping full schemas.
- `context.get` and `scripts/turn_runtime.py status` still expose full tool/action semantics.
- Buddybox capability/action semantics cover all required file-output affordances, input meanings, output meanings, side effects, success meanings, common failures, and anti-hardcoded-routing constraints.
- Buddybox success and rejection responses include both prose `allowed_next_actions` and structured `allowed_next_action_options`.
- `buddybox-tool` exists, is manifest-registered, and materializes for all buddybox-capable buddies.
- Runtime AGENTS remain short route maps and point to full discovery commands.
- Role contracts contain short role-specific buddybox/artifact boundary wording.
- Router feedback no longer references `prepare.runtime_context.env_tools`.
- PM page prototype scenario is covered by semantic-surface tests, not hardcoded trigger behavior.
- Focused and broader verification commands from stage 6 pass.
- `git status --short` shows changes only in this worktree and only for this task plus pre-existing user/untracked memo files.
