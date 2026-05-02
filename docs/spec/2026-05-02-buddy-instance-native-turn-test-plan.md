# 2026-05-02 Buddy Instance 原生会话单轮测试计划

## 1. 目标与边界

**目标链路（仅三段）**

1. Instance 内生 context 准备完成。
2. Host（codex-cli）基于该 instance 的 active buddy + capabilities 理解 `request_text`，本阶段只选择并执行一个 SKILL。
3. Postprocess 将结构化结果持久化到 BuddySwitch state，并产出结构化 receipt/next-state 供 summary/console 消费。

**明确不在通过路径**

- 历史结构化命令兼容（用户侧）。
- 规则化 parser 作为产品入口。
- workflow engine / DAG / 多 skill 编排。
- 跨 buddy 自动调度。
- 过渡双轨（同一入口同时走“旧命令路径 + 新原生路径”）。

---

## 2. 可观测验收面（外部行为优先）

- 入口行为：`./buddyswitch-codex instance start --buddy <buddy>` 后，用户直接输入自然语言 `request_text`。
- 结构化接口：`turn_context`、`persist` 返回的 JSON 顶层契约（`{ok, ...}`；`{ok, receipt, refreshed_context}`）。
- 状态写入：
  - `buddyswitch/objects/tasks/*.json`
  - `buddyswitch/objects/tracks/*.json`
  - `buddyswitch/objects/artifacts/*.json`
  - `buddyswitch/content/runs/*.json`
  - `runs/raw/`（仅原始日志/调试材料，不作为业务真值）
- Run audit：`run_id / task_id / buddy / skill_id / execution_summary / artifact_ids / next_state / receipt_paths`。
- Console/终端：只展示 `Receipt -> Summary`，读取结构化字段，不从自由文本反向解析命令。

---

## 3. Coverage Matrix（功能需求 -> 验证 -> 预期结果）

| 需求ID | 功能需求 | 验证方式 | 预期用户结果 | 预期状态/结构化结果 |
| --- | --- | --- | --- | --- |
| R1 | 用户在 buddy instance 输入自然语言，系统按 active buddy + capabilities 执行当前唯一 SKILL | 单元 + 集成 + 产品路径 | 用户无需写历史命令，一次请求完成一次 skill 执行 | `turn_context.active_buddy` 等于当前 instance buddy；`turn_context.request_text` 保留用户输入；`persist.receipt.skill_id` 为单个值且来自 `turn_context.skills`；run audit 写入成功 |
| R2 | 主链路不要求、识别或拒绝历史结构化文本；用户输入就是普通 `request_text` | 负向 + 手工验收 | 普通自然语言直接可用；即使文本看起来像历史格式也按需求文本处理 | 无需解析历史格式才能成功；`request_text` 原样进入 context/audit；不会从文本中推导 buddy/task/track |
| R3 | Instance context 内生准备（identity/workspace/runtime projection/current task/track/skills 来自 runtime context/manifest） | 单元 + launcher 集成 | 用户不需要提供 buddy/task/track/skill 清单 | `BUDDYSWITCH_ACTIVE_BUDDY` + instance metadata 生效；skills 来自 manifest；instance state 的 task/track 绑定更新 |
| R4 | 当前阶段 exactly one SKILL per turn；不做多 skill 编排/跨 buddy 调度/规则 parser 路由 | 单元 + 集成 + 负向 | 一轮只能选一个 skill；含多意图请求也不会自动拆分编排 | persist 仅接受单一 `skill_id`；无法明确单 skill 时停在 host 选择边界，不产生多次持久化 |
| R5 | Persist/postprocess 以结构化结果校验并写 state；summary/console 读取结构化 receipt/next-state，不解析文本 | 单元 + 集成 + console contract | 用户看到标准化 `Receipt -> Summary`，而不是“命令建议拼接器” | `persist` 返回 `{ok, receipt, refreshed_context}`；receipt.paths 对应对象文件存在；console next-step 来自结构化字段 |
| R6 | 历史解析器若存在，仅 debug/manual tool，不进入产品路径 | 回归 + 产品路径 | 产品会话中不依赖历史解析器才能工作 | 产品入口测试覆盖中不调用历史解析器；debug 路径独立可用但不影响产品行为 |

---

## 4. 详细测试设计

## 4.1 单元测试（契约边界）

**建议文件**

- `tests/test_switch_runtime.py`
- `tests/test_parallel_contracts.py`
- `tests/test_console_app_contract.py`

**用例清单**

1. `UT-01` 自然语言请求在产品会话中成功准备 turn context
- 输入：active buddy = `pm`，`request_text="Draft onboarding PRD"`。
- 断言：`ok=true`；`active_buddy=pm`；`request_text` 保留原文本；`run_envelope.status=reserved`。
- 外部证据：task 对象与 reservation 文件实际存在。

2. `UT-02` 请求文本包含单词 `switch` 但不是结构化命令，仍按自然语言处理
- 输入：`"Help users switch plans without data loss"`。
- 断言：`ok=true`；`request_text` 原样保留；无“命令语法错误”。

3. `UT-03` 看起来像历史格式的文本仍按普通 `request_text` 处理
- 输入：`"switch pm: ..."`、`"switch dev: ..."`。
- 断言：`ok=true`；`request_text` 原样保留；`active_buddy` 仍等于当前 instance buddy；不会从文本里的 buddy/task/track 字样改写 instance binding。

4. `UT-04` context 来源于 instance runtime/manifest，而非用户输入拼接
- 设置：instance 已绑定当前 task/track。
- 输入：普通 request_text（不包含 task_id/track_id）。
- 断言：turn context 携带当前绑定；skills 清单与 manifest 对应。

5. `UT-05` exactly-one-skill 约束
- 设置：multi-skill buddy（如 market）准备 turn context 后返回多个 skills。
- 断言：persist 未提供 `skill_id` 时失败；提供单一且属于当前 `turn_context.skills` 的 `skill_id` 时成功；提供其他 buddy/global/cached capability 的单个 `skill_id` 时失败且无写入；不存在一次 persist 处理多个 skill 的通道。

6. `UT-06` persist 严格依赖结构化结果 schema
- 输入：缺字段/类型错误的 result payload。
- 断言：`ok=false`；无 canonical state 写入（run/task/artifact 不新增）。

7. `UT-07` persist 返回契约与 key 顺序稳定
- 断言：顶层键为 `ok, receipt, refreshed_context`；不得回退到文本命令输出驱动。

8. `UT-08` console/summary 基于结构化 next-step 生成
- 输入：含 `next_state` / `receipt_paths` / `task_id` / `track_id` 的 run_audit。
- 断言：UI 状态字段存在且不暴露“可复制命令驱动”；summary 不从自由文本反解析。

9. `UT-09` debug parser 不可用时产品主链路仍可执行
- 设置：debug parser/router 被移除出 import path 或 monkeypatch 为抛错。
- 断言：产品 `prepare-turn-context -> persist` 主链路仍成功；失败时不得写入任何 state。

## 4.2 集成测试（prepare-turn-context -> host 选 skill -> persist）

**建议文件**

- `tests/test_switch_integration.py`
- `tests/test_switch_runtime.py`

**用例清单**

1. `IT-01` 单轮主链路成功
- 流程：prepare-turn-context(自然语言) -> 选择 1 个 skill -> persist(结构化 result)。
- 验证：
  - 终端/API 返回成功；
  - `receipt.run_id == turn_context.run_envelope.run_id`；
  - `receipt.paths.run/task/artifacts(/track)` 均可落盘读取。

2. `IT-02` postprocess 后状态一致性
- 验证 task `run_ids` 包含本次 run；artifact `source_run_id` 正确；run audit 引用 task/artifact/track 一致。

3. `IT-03` 成功 persist 后不隐式保留下一轮 reservation
- 验证：被消费 reservation 删除；`refreshed_context` 不携带新的 run_envelope；若要下一轮只能显式再次准备 turn context。

4. `IT-04` 运行审计可被 workspace projection/console 正确消费
- 验证：`/api/workspace` 或等价投影包含新增 run_audit；console 可显示下一步状态摘要。

5. `IT-05` 多意图输入不触发自动多 skill 编排
- 输入：一个请求里包含多个动作。
- 验证：系统仍要求“单 skill 选择”；不会自动拆成多次持久化。

6. `IT-06` 看起来像历史格式的文本完整链路落盘
- 流程：在 `pm` instance 输入 `"switch dev: draft onboarding PRD"` -> prepare-turn-context -> 选择当前 context 内一个 skill -> persist。
- 验证：run audit 中 `request_text` 原样保留；receipt/run audit 的 active buddy、task、track 归属仍来自当前 instance context；没有创建跨 buddy run；没有额外 persist。

## 4.3 CLI / Launcher 产品路径测试

**建议文件**

- `tests/test_buddyswitch_launcher.py`
- `tests/test_switch_runtime.py`

**关键场景**

1. `E2E-01` `instance start --buddy pm` 后直接自然语言请求可走通。
2. `E2E-02` 同场景输入看起来像历史格式的文本仍作为普通 `request_text`，不得改写 active buddy 或隐式跳转。
3. `E2E-03` instance runtime projection 正确：状态写入到 shared state，非主 checkout 临时目录。
4. `E2E-04` active buddy 绑定生效：用户文本无法把当前 turn 自动切到其他 buddy。
5. `E2E-05` 输出契约：终端最终输出遵循 `Receipt -> Summary`（无 `Commands` 段作为主输出）。

## 4.4 手工产品体验验收（必做）

1. 启动：`./buddyswitch-codex instance start --buddy pm`。
2. 在 instance 会话中直接输入自然语言需求（不写 `switch` 前缀）。
3. 确认 host 只选择一个 skill 执行。
4. 确认最终展示为 `Receipt -> Summary`，并能定位 run/task/artifact。
5. 启动 context panel（`python3 scripts/serve_context_panel.py`）并刷新，确认 run history/next-step 与 receipt 一致。
6. 边界手工检查：输入看起来像历史格式的文本，不应触发跨 instance/跨 buddy 跳转；最终 receipt 仍归属于当前 instance 的 active buddy。

## 4.5 回归与负向测试

**建议文件**

- `tests/test_repo_consistency.py`
- `tests/test_parallel_contracts.py`
- `tests/test_console_app_contract.py`

**用例清单**

1. `NEG-01` 历史解析器仍可作为 debug/manual tool 使用，但产品路径测试不依赖它；repo consistency 使用 allowlist 证明 parser/router 只出现在 `scripts/debug/**`、debug/manual 测试和明确 debug-only 的 manifest/doc 引用。
2. `NEG-02` 产品模式环境变量缺失或部分缺失时 fail-closed，不可静默降级成错误路由。
3. `NEG-03` tampered turn context（buddy/task/run 改写）在 persist 时被拒绝，且无写入副作用。
4. `NEG-04` console 不通过自由文本或历史格式片段推导产品下一步；下一步信息来自结构化字段。
5. `NEG-05` 文档/提示词回归防线：产品提示资产继续要求 `Receipt -> Summary`，不得回退到 `Receipt -> Commands -> Summary`。

---

## 5. 禁止作弊测试原则（必须执行）

1. 不为当前 helper 名称或私有函数调用写脆弱断言。
2. 不通过 mock 核心主链路（prepare-turn-context/persist）来“伪造通过”。
3. 不允许“只 grep 到一个字符串”就宣称产品路径正确。
4. 每个关键结论必须同时有“入口行为证据 + 状态结果证据”。
5. 至少一组测试必须跨越完整边界：`instance start` -> 自然语言请求 -> 单 skill -> persist -> state/run audit -> summary/console。
6. 负向场景必须验证“无副作用写入”，而不只看错误码。
7. 合同类测试必须校验结构化字段与路径存在性，不接受“日志看起来像成功”。

---

## 6. 建议测试文件映射

- `tests/test_switch_runtime.py`
  - 产品输入边界、exactly-one-skill、persist 结构化校验、无副作用保障。
- `tests/test_switch_integration.py`
  - prepare-turn-context/persist 主链路与 receipt/state 一致性。
- `tests/test_buddyswitch_launcher.py`
  - launcher instance 生命周期、runtime projection、active buddy 绑定。
- `tests/test_console_app_contract.py`
  - next-step/summary 来源于结构化数据而非命令文本解析。
- `tests/test_parallel_contracts.py`
  - 对外 contract surface（`turn-context` / `persist-skill-result`）冻结；若旧合同文件名短期未改，测试语义必须按 `turn_context` 校验。
- `tests/test_repo_consistency.py`
  - 产品提示资产与文档回归防线（`Receipt -> Summary`、debug 与产品边界）。

---

## 7. 建议执行命令（示例）

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_integration.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_console_app_contract.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_parallel_contracts.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
```

> 说明：实际落地时可先跑最小子集（按本计划用例 ID 对应 `-k` 过滤），再跑全量回归。

---

## 8. 完整验收标准

满足以下条件才可判定“Buddy instance 原生单轮会话”通过：

1. Coverage Matrix 的 `R1-R6` 各至少有 1 个自动化用例通过，且包含 1 个 CLI/launcher 产品路径证据。
2. 手工验收 `4.4` 六步全部通过。
3. 任一负向场景失败时，必须证明“无错误写入”后才允许继续。
4. 终端/console 输出契约维持 `Receipt -> Summary`，不依赖命令文本解析。
5. 全部相关测试运行通过后，无 blocker 级缺陷（P0/P1）。

---

## 9. Stop Condition

当且仅当以下条件同时成立时结束本轮测试：

1. `R1-R6` 覆盖完成且证据可追溯到测试输出与状态文件。
2. 自动化测试与手工验收均通过。
3. 已完成“禁止作弊测试”自检，未出现按实现细节硬编码的脆弱断言。
4. 结果能够证明产品主链路成立：自然语言输入 -> 单 skill 执行 -> 结构化持久化与展示。
