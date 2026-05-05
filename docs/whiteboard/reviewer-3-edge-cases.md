# Reviewer 3 - Edge Cases

## Lens

关注 V1 在边界场景下是否会制造错误状态，尤其是“看起来多 skill 都完成了，但实际上只有一个 durable output”。

## Scenario 1 - Silent Owner Collapse

Query:

> 让 market、PM、design 都给建议，最后形成路线图。

Skills involved:

- market
- pm-roadmap
- design-strategy

Risk:

- final answer 可能列出三方贡献，但 persist 只写 pm-roadmap。
- 用户以后查 design artifact 时找不到对应结果。

Recommendation:

- final receipt 必须声明：哪些 skill contributed，哪个 skill persisted。
- 不要暗示所有参与 skill 都有独立 durable artifact。

## Scenario 2 - Conflicting Skill Advice

Query:

> 市场建议做 A，开发说 A 太重，帮我决定。

Skills involved:

- market
- dev-feasibility
- pm-decision

Risk:

- 多 skill 冲突时，如果 owner 只是合并摘要，会掩盖 tradeoff。

Recommendation:

- owner 输出必须包含 decision rationale。
- helper skill 的冲突意见应该以 evidence/alternatives 形式保留。

## Scenario 3 - Parallel Reviewers

Query:

> 找 5 个 reviewer 分别评估这个方案，然后给最终方案。

Skills involved:

- reviewer agents
- pm-owner or architect-owner

Risk:

- reviewer 的产物可能留在 forked workspace，没有同步到主 worktree。
- 这就是本次白板文件缺失暴露出来的问题。

Recommendation:

- sub-agent 输出不能被假定为 durable。
- 父 agent 必须显式把需要保留的内容写入目标 worktree，并验证路径。

## Scenario 4 - No Durable Intent

Query:

> 先 brainstorm 一下，有哪些可能方向？

Skills involved:

- brainstorming
- market
- design

Risk:

- 为了满足 persist contract，强行选择 owner，产生过早结构化 artifact。

Recommendation:

- 没有 durable intent 时不要 persist。
- 多 skill 可以只服务当前对话思考。

## Reviewer Recommendation

V1 应加强“durability truth”：

- participated skills are runtime context.
- result-owner is durable truth owner.
- helper output is only durable if owner includes it in the persisted artifact.
- sub-agent dump must be parent-verified in the exact target path.
