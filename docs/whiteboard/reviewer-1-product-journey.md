# Reviewer 1 - Product Journey Scenarios

## Lens

关注 end-to-end 产品体验：market、PM、design、dev、test 多阶段是否自然，用户是否理解“多个 skill 协作，一个 owner 落库”。

## Scenario 1 - Market Discovery

Query:

> 分析竞品市场定位，给出下一版功能切入点，并沉淀成产品机会。

Skills involved:

- market-research
- pm-strategy
- design-sensemaking

V1 flow:

- market-research 负责外部信息和竞品洞察。
- pm-strategy 把洞察压成机会判断。
- design-sensemaking 辅助判断用户体验差异。
- result-owner = pm-strategy。

Experience review:

- 合理，因为 durable output 是“产品机会判断”，不是原始竞品资料。
- 需要让 market-research 的证据以引用或 appendix 形式被 owner 带入 receipt，否则会像丢失工作。

## Scenario 2 - PRD Draft

Query:

> 基于上面的机会，写一个 MVP PRD，附带验收标准和设计注意点。

Skills involved:

- pm-prd
- test-acceptance
- design-ux

V1 flow:

- pm-prd 是 owner。
- test/design 贡献章节。
- persist 一个 PRD artifact。

Experience review:

- 合理。PRD 是一个主文档，owner 清晰。
- 不应该让 test skill 单独 persist 验收标准，否则 PRD 和测试标准容易变成两个 truth。

## Scenario 3 - Design Iteration

Query:

> 把 PRD 转成低保真页面流，指出哪些需求要砍掉。

Skills involved:

- design-flow
- pm-scope
- dev-feasibility

V1 flow:

- design-flow owner，输出页面流和交互取舍。
- pm/dev 作为约束输入。

Experience review:

- 基本合理。
- 如果“砍需求”是主目标，owner 应该改成 pm-scope；owner 需要由 durable artifact 类型决定，而不是由最先触发的 skill 决定。

## Scenario 4 - Release Readiness

Query:

> 检查这个功能能不能发版，列出阻塞项和下一步。

Skills involved:

- test-risk
- dev-review
- pm-release

V1 flow:

- pm-release owner，输出 release decision。
- test/dev 作为证据输入。

Experience review:

- 合理，因为 durable output 是“发版决策”。
- 必须在 receipt 中区分 `persisted_ok` 和 `release_approved`，避免“已落库”被误读成“可以发版”。

## Reviewer Recommendation

V1 方向成立，但 owner 选择必须按“本次要持久化的产品结果类型”决定：

- opportunity / PRD / release decision 通常由 PM owner。
- screen flow / UX spec 通常由 design owner。
- implementation patch 通常由 dev owner。
- test report / risk report 通常由 test owner。
