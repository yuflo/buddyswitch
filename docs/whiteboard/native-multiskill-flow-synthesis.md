# Multi-Agent Evaluation Synthesis

## Stable Findings

五个 reviewer 的结论基本一致：

- codex-cli 原生多 skill 应该继续作为 runtime 执行模型。
- BuddySwitch 不应该重新实现多 skill scheduler。
- 一次 persist 一个 owner 是合理的，只要 owner 被定义为 durable result owner。
- 最大风险不是执行能力不足，而是 durable truth 表达不清。

## Main Product Risks

1. 用户以为多个 skill 都分别落库，但实际只有一个 owner persist。
2. owner 按触发顺序或 skill 权重选择，会和产品结果类型错位。
3. sub-agent 或 helper skill 的输出停留在临时上下文，没有被写入目标 artifact。
4. persist 成功容易被误解成产品决策成功。
5. 未注册社区 skill 如果能直接 persist，会污染 active buddy 边界。

## Design Constraints

保持精简：

- 不引入 workflow engine。
- 不引入 multi-owner transaction。
- 不引入 arbitrary skill_id persist。
- 不做历史兼容双轨。
- 不把 helper output 自动变成 durable state。

需要补强：

- owner rule
- visible contribution summary
- multi artifact split guidance
- failure wording
- exact-path verification for docs/sub-agent dumps

## Final Direction

BuddySwitch 多 skill 编排应该是：

> codex-native execution + BuddySwitch single-owner durable commit。

也就是：

- 多 skill 由 codex-cli 原生注入和模型编排。
- BuddySwitch 在 persist boundary 要求一个 active buddy owner。
- 多个 durable 结果用多个 cycles，不把一个 cycle 变成分布式事务。

## Why Not Multiple Persists In One Cycle

不合理点：

- 一个 prepare 当前对应一个 run/context envelope，多次 persist 会改变生命周期语义。
- 多 owner 需要合并 receipt、next_state、rollback、partial failure、ordering。
- helper skill 输出是否可持久化会变成隐式规则。
- 用户很难判断哪个 artifact 是 primary truth。
- 会把现在清晰的 durable boundary 变成小型 workflow engine。

结论：多次 persist 不是当前瓶颈的最短路径。
