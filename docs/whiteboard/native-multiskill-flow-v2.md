# Codex Native Multi-Skill Flow V2

## What Changed From V1

V1 的核心方向保留，但补上三个产品边界：

- owner selection rule
- durable visibility rule
- failure/recovery rule

## Owner Selection Rule

`result-owner skill_id` 不是“本轮最重要的 skill”，而是：

> 对本次 primary durable artifact 负责的 active buddy skill。

选择顺序：

1. 判断本轮是否有 durable intent。
2. 判断 primary durable artifact 是什么。
3. 选择对该 artifact 负责的 active buddy skill 作为 owner。
4. 如果有多个 primary durable artifacts，拆成多个 prepare/persist cycles。
5. 如果没有 active buddy skill 能负责，不 persist；先注册/import，或由已有 owner 承接。

## Durable Visibility Rule

一次 native multi-skill run 可以有多种参与者：

- `selected_skills`: codex 注入并参与推理的 skills。
- `contributing_skills`: 对结果有明显贡献的 skills。
- `result_owner`: 本次 durable artifact 的唯一 owner。

只有 `result_owner` 的 persist 结果是 durable truth。

Helper skill 的输出只有在 owner artifact 中被引用、摘要或列为 evidence，才成为 durable 内容的一部分。

## Failure And Recovery Rule

必须区分：

- analysis completed
- artifact decided
- persist attempted
- persist succeeded
- product decision positive/negative

`persisted_ok=true` 只表示存储成功，不表示产品判断为正。

persist 失败时：

- 不自动换 owner。
- 不做隐藏第二次 persist。
- 返回 intended owner、artifact kind、失败原因和 retry action。

## Product Copy

建议在 final answer 或 receipt 中使用这种表达：

> 本轮使用了 A/B/C 协作；持久化结果由 X 负责。Y/Z 的结论已作为 evidence 写入 X 的 artifact。未写入 artifact 的中间输出不是 durable state。

## Runtime Implication

不新增 workflow engine。

最小改造点应是：

- prompt/contract 明确 owner rule。
- persist receipt 可展示 contributing skills。
- tests 覆盖 owner selection、multi artifact split、inactive skill rejection、persist failure wording。
