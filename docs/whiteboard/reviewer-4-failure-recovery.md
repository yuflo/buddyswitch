# Reviewer 4 - Failure And Recovery Scenarios

## Lens

关注 persist 失败、权限阻塞、用户中断、多 skill 结果不完整时，产品体验是否可恢复。

## Scenario 1 - Persist Fails After Multi-Skill Work

Query:

> 做完市场分析和 MVP scope 后保存到任务状态。

Skills involved:

- market
- pm-scope

Failure:

- model 完成多 skill 推理。
- persist 因 validation 或 lock 失败。

Risk:

- 用户看到完整回答，但系统没有 durable state。

Recommendation:

- final answer 必须区分 `analysis_completed` 和 `persisted`。
- persist fail 时要给出 retry owner 和 artifact kind，不要伪装成功。

## Scenario 2 - Owner Skill Not Active

Query:

> 用外部 design skill 产出设计方案并落库。

Skills involved:

- imported-design
- active buddy owner

Failure:

- imported-design 未注册进 active buddy，不能作为 persist owner。

Risk:

- codex 可能读到通用 skill，但 BuddySwitch persist validation 不接受。

Recommendation:

- 未 active 的 skill 可以作为本轮上下文，但不能成为 durable owner。
- 要落库，先注册/materialize 到 active buddy，或者由 active buddy 内 skill 承接 owner。

## Scenario 3 - User Interrupts Before Owner Selection

Query:

> 先停，刚才那些分析别保存。

Skills involved:

- any

Risk:

- 如果系统自动 persist，会违背用户意图。

Recommendation:

- persist 应只在 durable intent 明确时发生。
- interrupt 后保留 conversational summary，不写 durable state。

## Scenario 4 - Product Success vs Storage Success

Query:

> 检查能不能上线，并保存结果。

Skills involved:

- test
- dev
- pm-release

Risk:

- `persisted_ok=true` 容易被误读为 `release_ok=true`。

Recommendation:

- receipt 字段或文案必须区分 storage result 和 product decision。

## Reviewer Recommendation

V1 应加入 recovery language：

- One persist attempt has one owner and one artifact.
- If persist fails, no hidden second owner retry.
- Retry should reuse the same intended owner unless product intent changes.
- A saved negative decision is still a valid durable artifact.
