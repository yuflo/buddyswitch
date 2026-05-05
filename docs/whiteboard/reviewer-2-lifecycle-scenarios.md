# Reviewer 2 - Lifecycle Scenarios

## Lens

关注跨阶段请求里的 owner 选择是否稳定，尤其是一个 query 同时覆盖 market、PM、dev、test、design 时是否会变混乱。

## Scenario 1 - Ambiguous Discovery To Scope

Query:

> 看一下这个方向有没有市场机会，顺便定一下第一版做什么。

Skills involved:

- market-analysis
- pm-scope

V1 evaluation:

- 如果 durable output 是“机会判断”，owner = market-analysis。
- 如果 durable output 是“MVP scope”，owner = pm-scope。

Issue:

- 用户 query 里有两个 durable intent：“有没有机会”和“第一版做什么”。
- V1 如果强行一次 persist，会丢掉一个主语。

Recommendation:

- 允许一次对话执行多 skill。
- 但 durable 提交前，模型应选择一个 primary artifact。
- 如果两个 primary artifact 都必须落库，应拆成两个 prepare/persist cycles。

## Scenario 2 - PM To Design

Query:

> 根据 PRD 做页面结构，并指出 PRD 哪里不合理。

Skills involved:

- design-ia
- pm-review

V1 evaluation:

- owner = design-ia，如果最终产物是页面结构。
- pm-review 的修改建议必须进入 design artifact 的 assumptions/risks。

Issue:

- 如果用户主要想“审 PRD”，design owner 不合理。

Recommendation:

- Owner 不按 skill 数量、触发先后、强度决定，只按 durable artifact 决定。

## Scenario 3 - Dev Implementation With Tests

Query:

> 实现这个功能并补测试。

Skills involved:

- dev-implementation
- test-driven-development

V1 evaluation:

- owner = dev-implementation。
- test skill 是执行约束和验证手段。

Issue:

- test output 不需要单独 persist，除非用户明确要测试计划或测试报告。

Recommendation:

- 将 helper skill 的贡献写入 final receipt 的 evidence，而不是另建 durable state。

## Scenario 4 - Post-Launch Learning

Query:

> 根据上线数据和用户反馈，判断下一轮怎么改。

Skills involved:

- analytics
- user-research
- pm-prioritization

V1 evaluation:

- owner = pm-prioritization。

Issue:

- analytics/user-research 的原始材料可能重要，但不一定都是 durable product artifact。

Recommendation:

- Owner receipt 应保留 traceable evidence 列表。
- 不要把 helper skill 都变成 persist participant，否则 runtime 边界复杂度上升。

## Reviewer Recommendation

V1 缺少一个清晰的 owner selection rule。建议加入：

> result-owner = 对本次 primary durable artifact 负责的 skill。

如果没有 primary durable artifact，先不 persist；如果有多个 primary durable artifact，拆成多个 cycle。
