# Native Multi-Skill Final Candidate

## Core Decision

采用：

> codex-cli 原生多 skill 执行 + BuddySwitch 单 result-owner persist。

这不是功能削弱，而是职责边界：

- codex-cli 负责多 SKILL 注入、上下文组合、模型自主编排。
- BuddySwitch 负责 active buddy skill materialization 和 durable state boundary。
- persist 的 `skill_id` 表示 result owner，不表示唯一参与 skill。

## Execution Contract

一次用户任务可以触发多个 skill：

1. Active buddy skills 被 materialize 到 workspace。
2. codex-cli 原生选择/注入多个 SKILL.md。
3. 模型按任务需要调用工具、派发 reviewer、整理结论。
4. 若需要持久化，模型先确定 primary durable artifact。
5. 选择对该 artifact 负责的 active buddy skill 作为 `result_owner`。
6. 调用一次 persist，提交一个 durable artifact/result。

## Owner Rule

`result_owner` 的确定方式：

- opportunity / roadmap / PRD / release decision：PM 类 owner。
- UX flow / design critique / screen spec：design 类 owner。
- implementation patch / code change summary：dev 类 owner。
- test plan / test report / release risk：test 类 owner。
- imported/community skill：只有注册进 active buddy 后才能作为 owner；否则只能作为 helper。

如果一个 query 同时要求多个 primary durable artifacts：

- 不在一个 persist 里提交多个 owner。
- 拆成多个 prepare/persist cycles。

如果只是 brainstorming 或临时讨论：

- 不 persist。

## Receipt Shape Recommendation

保持最小，不做复杂 schema 平台化。

建议在现有 receipt/final message 中清晰表达：

- `result_owner`: 持久化负责人 skill。
- `contributing_skills`: 明显参与并被写入结果的 skill。
- `artifact_kind`: 本次持久化结果类型。
- `persisted_ok`: 存储是否成功。
- `product_decision`: 如果有，单独表达产品判断，不和 persisted_ok 混淆。

## Why Single Persist Remains Right

一次 persist 多 owner 会把 BuddySwitch 带向不必要的 workflow/transaction 系统：

- partial failure 要处理。
- owner ordering 要定义。
- next_state merge 要定义。
- receipt 合并要定义。
- retry/rollback 要定义。
- arbitrary external skill ownership 会冲击 active buddy 边界。

当前产品瓶颈是“多 skill 原生能力能否清晰用出来”，不是“构建多 owner 事务引擎”。

## Minimal Rebuild Plan

1. 重写相关 runtime/prompt contract：明确 result-owner 语义和多 skill helper 语义。
2. 保持 persist validation：`skill_id` 必须属于 active buddy。
3. 在 final/receipt 中展示 contributing skills，避免 silent owner collapse。
4. 加测试覆盖：
   - multiple skills one owner
   - multi durable artifacts require split
   - inactive skill cannot own persist
   - persist failure does not imply product failure
   - helper output must be embedded to become durable

## Stop Condition

实现后，用最短验证闭环证明：

- 一个 query 能触发多个 materialized skills。
- codex 原生上下文能完整注入。
- persist 仍只接受一个 active buddy owner。
- final/receipt 能清楚说明 contributors 与 owner。
- 没有新增 workflow engine、兼容包装或多 owner 状态机。
