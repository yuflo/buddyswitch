# Buddy Instance Native Turn Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 BuddySwitch 进入 buddy instance 原生会话形态：instance 先生成原生 turn context，host 只选并执行一个 SKILL，postprocess 只返回结构化 receipt 并落盘状态，产品主链路不再依赖历史文本命令。

**Architecture:** 用 `native turn context -> host single-skill execution -> structured persist/postprocess` 三段主链路替换现有历史解析产品路径。产品侧入口语义收敛为 `prepare-turn-context`，历史 parser 仅保留在 debug 工具目录，产品路径不引用。所有“下一步”信息改为结构化字段，console 和 summary 只读结构化数据，不解析文本命令。

**Tech Stack:** Python (`scripts/switch_runtime.py`, `runtime_kernel`, `runtime_store`), Bash launcher (`tools/launcher`), 静态前端 (`framework/console`), JSON contracts (`framework/contracts`), unittest/pytest。

---

## File Responsibility Map

### Runtime Core（原生 turn 上下文与持久化边界）
- Modify: `scripts/switch_runtime.py`
  - 责任：删除产品路径对历史 `switch` 文本构造/解析依赖；产出 native turn context；persist 校验 `instance`/`turn_identity`/`selected_skill`/schema；写 task/artifact/track/run audit；清理 reservation；返回结构化 receipt。
- Modify: `scripts/runtime_kernel/resolve.py`
  - 责任：对外入口对齐 `prepare-turn-context` / native turn context builder，不再委托旧 parse 路径；若保留文件名仅作为 CLI 兼容壳，产品语义不能继续叫解析路由。
- Modify: `scripts/runtime_kernel/persist.py`
  - 责任：persist 入口仅接受单 skill 结构化落盘请求，不接受编排态 payload。
- Modify: `framework/contracts/resolve-context.json`
  - 责任：冻结新的 native turn context key order（包含 `instance_id`、`active_buddy`、`request_text`、`current_task_id`、`current_track_id`、`task_context`、`track_context`、`skills`、`inputs_by_skill`/`artifact_selection_by_skill`、`run_envelope.turn_identity`）。
- Modify: `framework/contracts/persist-skill-result.json`
  - 责任：冻结新的 persist 返回结构（`receipt` 结构化字段），移除命令化 follow-up 字段契约。

### Runtime Projection & Console（只读结构化消费）
- Modify: `scripts/runtime_store/projections.py`
  - 责任：run audit 投影视图改为结构化 next-step/state 字段，移除 `reference_switches` / `recommended_switch` 投影。
- Modify: `framework/contracts/workspace-projection.json`
  - 责任：更新 `run_audit` shape，删除命令字段，新增结构化 next-step 字段类型约束。
- Modify: `framework/console/app.js`
  - 责任：删除 `SWITCH_BUDDY_PATTERN` 与基于 `recommended_switch` 的文本解析；next step/summary 仅来自结构化字段。
- Modify: `framework/console/index.html`
  - 责任：移除“命令导向”文案，保留结构化状态展示。

### Launcher / Prompt / Docs（产品链路口径）
- Modify: `tools/launcher/assets/runtime-AGENTS.md`
- Modify: `tools/launcher/assets/buddies/dev/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/pm/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/market/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/design/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/test/AGENTS.md`
- Modify: `.codex/agents/router.toml`
  - 责任：删除产品指引中的命令化输入/输出，明确普通用户输入是 `request_text`，host 只选一项 skill；同时删除“历史格式输入必须拒绝”类指令，避免把规则识别带回产品路径。
- Modify: `README.md`
- Modify: `framework/docs/switch-spec.md`
- Modify: `framework/docs/architecture-overview.md`
- Modify: `framework/docs/skill-architecture-best-practices.md`
  - 责任：文档统一切换到 native turn contract，历史 parser 标注为 debug-only。

### Debug Parser Isolation（保留但隔离）
- Move/Modify: `scripts/parse_switch.py` -> `scripts/debug/parse_switch.py`
- Move/Modify: `scripts/codex_router.py` -> `scripts/debug/codex_router.py`
  - 责任：历史 manual/debug parser 工具仅在 debug 路径存在；产品运行路径不 import/调用。
- Modify: `buddyswitch/manifest.toml`
  - 责任：同步处理 `[[adapters]]` 中指向 `scripts/codex_router.py` 的历史 adapter 路径；要么迁移到 debug adapter 明确标注 debug-only，要么从产品 manifest 中移除。
- Modify: `tests/test_switch_routing.py`
- Modify: `tests/test_switch_integration.py`
  - 责任：测试改为指向 debug 工具路径，避免产品路径反向依赖。

### Tests & Guardrails（契约防回归）
- Modify: `tests/test_switch_runtime.py`
- Modify: `tests/test_parallel_contracts.py`
- Modify: `tests/test_console_app_contract.py`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_buddyswitch_launcher.py`
  - 责任：冻结新 contract；防止 `_build_plain_text_switch`、`parse_switch` 产品引用、`switch_fingerprint`、`reference_switches`、`recommended_switch`、命令化 prompt/docs 回流。

### 本次不新增兼容层
- 不新增“历史命令兼容包装层”。
- 不新增 rule engine / workflow engine / DAG / 多 skill orchestration。
- 不修改测试计划文档（`docs/spec/*test-plan*.md`）。

---

## 已确认关键现状（用于计划输入）

- `scripts/switch_runtime.py` 仍直接 import 并调用 parser：`from parse_switch import ... parse_switch`，且 `_build_resolve_context()` 内调用 `parse_switch(...)`。
- 产品路径仍使用文本命令桥接：存在 `_build_plain_text_switch` 与 `_adapt_resolve_text_for_product_session`。
- run envelope 仍用 `switch_fingerprint` 防篡改，不是 `turn_identity`。
- persist 与投影仍输出 `reference_switches` / `recommended_switch`。
- `framework/console/app.js` 通过 `SWITCH_BUDDY_PATTERN` 解析 `recommended_switch` 推导推荐 buddy。
- `framework/contracts/workspace-projection.json` 的 `run_audit` shape 仍包含 `reference_switches` / `recommended_switch`。
- launcher instance 记录当前只持久化 identity/buddy/workspace/task/track/browser，不缓存 skills（`tools/launcher/env.sh` 的 `instance.json` 字段无 skills）。
- `buddyswitch/manifest.toml` 的 `[[adapters]]` 仍指向 `scripts/codex_router.py`，这是历史 router 迁移时必须同步处理的引用。

---

## 分阶段开发任务

### Task 1: 冻结 Native Turn Contract（先测后改）

**Files:**
- Modify: `framework/contracts/resolve-context.json`
- Modify: `framework/contracts/persist-skill-result.json`
- Modify: `tests/test_switch_runtime.py`
- Modify: `tests/test_parallel_contracts.py`

- [ ] **Step 1: 先写失败测试，定义新 context/receipt 形状**
  - `resolve-context` 断言新增字段：`instance_id`, `active_buddy`, `request_text`, `current_task_id`, `current_track_id`, `inputs_by_skill`（或 `artifact_selection_by_skill`）, `run_envelope.turn_identity`。
  - 断言移除字段：`switch`（产品路径）、`inputs`（顶层单列表）。
  - `persist-skill-result` 断言 receipt 仅结构化字段，不再包含命令型 follow-up 字段。
- [ ] **Step 2: 更新 contract JSON 的 key order 与字段说明**
  - 合同与测试保持一一对应，先失败后驱动实现。
- [ ] **Step 3: 运行最小契约测试**

Run:
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_parallel_contracts.py -q
```

Expected:
- 在 Runtime 实现改动前失败，且失败点仅在字段/key order 不匹配。

---

### Task 2: 替换产品入口为 Native Turn Context（删除历史桥接）

**Files:**
- Modify: `scripts/switch_runtime.py`
- Modify: `scripts/runtime_kernel/resolve.py`
- Modify: `tests/test_switch_runtime.py`

- [ ] **Step 1: 移除产品路径历史入口**
  - 删除 `_build_plain_text_switch`。
  - 删除 `_adapt_resolve_text_for_product_session`。
  - 删除产品路径对 `parse_switch` 的 import/call。
- [ ] **Step 2: 实现 native turn context builder**
  - 输入：`product_session(active_buddy, instance_id, current_task_id/current_track_id)` + `request_text`。
  - 输出：native turn context（包含 `task_context`, `track_context`, `skills`, `inputs_by_skill`/`artifact_selection_by_skill`, `run_envelope{run_id,status,context_revision,turn_identity}`）。
  - `skills` 每 turn 从 manifest/runtime context 实时读取，不从 launcher 缓存读取。
- [ ] **Step 3: 收敛产品 API 命名**
  - 产品文档、prompt、contract 中使用 `prepare-turn-context` / `turn_context`。
  - 如果 CLI 子命令名短期仍为 `resolve`，只作为外层兼容命令名存在；内部函数、contract、prompt 不再把产品路径解释成解析规则。
- [ ] **Step 4: 保留 debug parser 能力但不进入产品路径**
  - `resolve` 产品模式不再经过 parse grammar。
  - 非产品 debug 路径后续在 Task 5 隔离到 `scripts/debug/`。
- [ ] **Step 5: 校验 reservation 与 instance binding**
  - `run_envelope` 中 `turn_identity` 成为 persist 校验依据；不再依赖 `switch_fingerprint`。

Run:
```bash
rg -n "from parse_switch import|parse_switch\(" scripts/switch_runtime.py scripts/runtime_kernel -S
rg -n "_build_plain_text_switch|_adapt_resolve_text_for_product_session|switch_fingerprint" scripts/switch_runtime.py -S
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py::ResolveRuntimeTests -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests -q
```

Expected:
- 产品 runtime 文件不再出现 parser 调用、plain-text switch 构造、`switch_fingerprint`。
- resolve 测试通过，且返回 native turn context 字段。

---

### Task 3: Persist/Postprocess 结构化改造（单 SKILL、结构化 receipt）

**Files:**
- Modify: `scripts/switch_runtime.py`
- Modify: `scripts/runtime_kernel/persist.py`
- Modify: `tests/test_switch_runtime.py`

- [ ] **Step 1: persist 强校验四项**
  - `instance_id` 一致性。
  - `turn_identity` 一致性。
  - persist 输入的 `skill_id` 必须是单个合法值，且必须属于当前 `turn_context.skills` / 当前 instance capabilities（拒绝数组、编排描述、其他 buddy 的 skill）。
  - `result` 必须通过该 skill schema。
- [ ] **Step 2: 移除历史命令字段**
  - receipt 删除 `reference_switches`、`recommended_switch`。
  - run audit 删除 `reference_switches`、`recommended_switch`。
- [ ] **Step 3: 引入结构化 next-step/ownership 字段**
  - 用显式字段记录 `current_buddy`、`next_buddy`、`task_id`、`track_id`、`mode`（如 `continue_current_task`/`handoff`），供 console/summary 消费。
- [ ] **Step 4: reservation 清理与 postprocess 收口**
  - persist 成功后必须清理 reservation。
  - 返回结构化 receipt；不得返回命令模板文本。

Run:
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py::PersistSkillResultTests -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py::ResolveAndPersistContractTests -q
```

Expected:
- persist 全链路只接受单 skill 并结构化落盘。
- 历史命令字段相关断言全部迁移为结构化字段断言。

---

### Task 4: Projection 与 Console 全量改成结构化消费

**Files:**
- Modify: `scripts/runtime_store/projections.py`
- Modify: `framework/contracts/workspace-projection.json`
- Modify: `framework/console/app.js`
- Modify: `framework/console/index.html`
- Modify: `tests/test_console_app_contract.py`
- Modify: `tests/test_switch_runtime.py`（workspace projection 相关用例）

- [ ] **Step 1: run_audit 投影字段切换**
  - 删除 `reference_switches` / `recommended_switch` 输出。
  - 增加结构化 next-step 字段（与 Task 3 receipt/audit 一致）。
- [ ] **Step 2: console 去文本解析**
  - 删除 `SWITCH_BUDDY_PATTERN`、`deriveRecommendedSwitch`、`switchBuddyId` 及其调用。
  - next-step 卡片直接读取结构化字段。
- [ ] **Step 3: console contract tests 改造**
  - 测试不再注入 `recommended_switch` 文本。
  - 测试断言来自结构化字段，且不含命令解析逻辑。

Run:
```bash
rg -n "SWITCH_BUDDY_PATTERN|deriveRecommendedSwitch|switchBuddyId|recommended_switch|reference_switches" framework/console/app.js -S
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_console_app_contract.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py::WorkspaceProjectionFacadeTests -q
```

Expected:
- console JS 不再包含 switch 文本解析器。
- workspace projection 与 console contract 测试通过。

---

### Task 5: 历史 Parser 隔离到 Debug 路径，产品路径零引用

**Files:**
- Move/Modify: `scripts/parse_switch.py` -> `scripts/debug/parse_switch.py`
- Move/Modify: `scripts/codex_router.py` -> `scripts/debug/codex_router.py`
- Modify: `tests/test_switch_routing.py`
- Modify: `tests/test_switch_integration.py`
- Modify: `framework/contracts/switch-grammar.json`（如需更新路径注释）
- Modify: `framework/agent-registry.md`（引用路径更新）
- Modify: `buddyswitch/manifest.toml`

- [ ] **Step 1: 迁移 debug 工具文件路径**
  - 明确 `scripts/debug/` 为唯一历史 parser 工具目录。
- [ ] **Step 2: 更新测试与文档引用**
  - parser/router 相关测试只验证 debug 工具，不得覆盖产品 resolve 主路径。
- [ ] **Step 3: 更新或移除 manifest adapter 引用**
  - 当前 `[[adapters]] path = "scripts/codex_router.py"` 不能继续作为产品 adapter 残留。
  - 若保留 adapter，只能指向 `scripts/debug/codex_router.py` 并明确 debug-only；产品 launcher/runtime/prompt 不得依赖该 adapter。
- [ ] **Step 4: 做产品路径零引用检查**
  - 任意产品 runtime 文件不得 import `scripts/debug/parse_switch.py`。

Run:
```bash
rg -n "parse_switch|codex_router" scripts tools/launcher framework tests buddyswitch/manifest.toml -S
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_routing.py tests/test_switch_integration.py -q
```

Expected:
- parser/router 仅在 `scripts/debug/`、debug/manual 测试、以及明确 debug-only 的 manifest/doc 引用中出现；其他路径命中才算失败。
- 产品 runtime 代码无 parser 依赖。

---

### Task 6: Prompt/Docs/Launcher 口径收敛（去命令化、去双轨）

**Files:**
- Modify: `tools/launcher/assets/runtime-AGENTS.md`
- Modify: `tools/launcher/assets/buddies/*/AGENTS.md`
- Modify: `.codex/agents/router.toml`
- Modify: `README.md`
- Modify: `framework/docs/switch-spec.md`
- Modify: `framework/docs/architecture-overview.md`
- Modify: `framework/docs/skill-architecture-best-practices.md`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: 文档与 prompt 去命令化**
  - 删除产品用户输入中的结构化命令引导。
  - 删除 `Structural ... commands must be rejected` / `must reject before parse` 这类历史格式拒绝指令；看起来像历史格式的用户文本也必须作为普通 `request_text`。
  - 明确普通输入是 `request_text`，active buddy 来自 instance metadata。
- [ ] **Step 2: launcher 角色边界固化**
  - 文档/测试明确 launcher 只负责 identity/workspace/state projection/prompt/env。
  - 增加 guardrail：instance record 不得出现 skill 缓存字段。
- [ ] **Step 3: 修正现有测试期待**
  - 如 `tests/test_buddyswitch_launcher.py` 中对 `receipt -> commands -> summary` 的期待改为结构化输出约束。

Run:
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -q
```

Expected:
- 产品文档/提示词无命令化用户引导。
- launcher 边界被测试固定，无 skills 缓存行为。

---

### Task 7: 全量验证与回归收口

**Files:**
- Modify: `tests/test_switch_runtime.py`
- Modify: `tests/test_parallel_contracts.py`
- Modify: `tests/test_console_app_contract.py`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: 运行核心测试矩阵**
- [ ] **Step 2: 运行遗留字段禁用 grep 断言**
- [ ] **Step 3: 抽样手工链路验证（prepare-turn-context -> host one skill -> persist）**

Run:
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_switch_runtime.py \
  tests/test_parallel_contracts.py \
  tests/test_console_app_contract.py \
  tests/test_repo_consistency.py \
  tests/test_buddyswitch_launcher.py -q

rg -n "_build_plain_text_switch|_adapt_resolve_text_for_product_session|switch_fingerprint|reference_switches|recommended_switch" scripts/switch_runtime.py scripts/runtime_kernel scripts/runtime_store framework/console framework/contracts tools/launcher README.md -S
rg -n "from parse_switch import|parse_switch\(" scripts/switch_runtime.py scripts/runtime_kernel -S
```

Expected:
- 核心测试矩阵通过。
- 产品路径中无历史桥接函数、命令型字段、parser 调用。

---

## Stop Condition

满足以下条件立即停工并交付：

1. 产品 `prepare-turn-context`/persist 主路径完成 native turn 三段链路，且 host 执行模型固定为 **exactly one SKILL**。
2. `scripts/switch_runtime.py` 产品路径中已删除 `_build_plain_text_switch`、`_adapt_resolve_text_for_product_session`、`parse_switch` 调用、`switch_fingerprint`。
3. receipt / run_audit / projection / console 中不再存在 `reference_switches` 与 `recommended_switch`。
4. 历史 parser/router 仅在 `scripts/debug/`（或等价 debug 专属路径）并且不被产品路径引用。
5. prompt/docs 不再引导产品用户输入命令化 `switch ...`。
6. 核心验证命令通过。

## Definition of Done

- [ ] 当前核心瓶颈（buddy instance 原生 turn）已被实质推进并可验证。
- [ ] 变更范围仅围绕 native turn 主链路，无额外平台化扩展。
- [ ] 所有关键合同与测试已更新并通过。
- [ ] 代码与文档比变更前更清晰，不引入兼容包装层。
- [ ] 新的 durable 约束（单 skill、结构化 receipt、debug parser 隔离）已被测试与文档固化。
