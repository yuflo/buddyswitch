# Reviewer 5 - Community Skill And Import Scenarios

## Lens

关注 SKILL 不局限于 BuddySwitch 现有技能时，codex-cli 原生能力和 BuddySwitch durable contract 怎么衔接。

## Scenario 1 - Use External Skill As Helper

Query:

> 用一个社区增长 skill 帮我分析 onboarding，然后由 PM 输出下一步。

Skills involved:

- community-growth
- pm-prioritization

Evaluation:

- 如果 community-growth 只是上下文/helper，可以通过 codex native skill 注入参与。
- durable owner = pm-prioritization。

Product experience:

- 合理，外部 skill 增强推理，但不必进入 BuddySwitch 状态模型。

## Scenario 2 - External Skill Wants Durable Ownership

Query:

> 用社区 design-review skill 产出正式设计评审记录。

Skills involved:

- community-design-review

Issue:

- 如果该 skill 没有被 BuddySwitch 注册进 active buddy，persist 不能直接接受它的 `skill_id`。

Recommendation:

- 要成为 result-owner，必须被 active buddy manifest/runtime materialization 接纳。
- 否则由 active buddy 内的 design owner 承接 durable artifact。

## Scenario 3 - Skill Creator Imports New Skill

Query:

> 把这个社区 skill 导入，之后让它负责增长实验记录。

Skills involved:

- skill-creator/importer
- growth-experiment

Evaluation:

- import 是一个 separate setup action。
- import 完成后，growth-experiment 才能成为 active buddy 的 durable owner。

Product experience:

- 合理，但不能在同一个未经注册的上下文里假装新 skill 已经有 durable 权限。

## Scenario 4 - Multiple External Specialists

Query:

> 用 pricing、analytics、growth 三个社区 skill 帮我定下一轮实验。

Skills involved:

- pricing
- analytics
- growth
- pm-experiment-owner

Evaluation:

- 多个社区 skill 可以参与。
- durable owner 仍应是 pm-experiment-owner，除非其中某个 skill 已被注册为 active buddy owner。

Recommendation:

- 不要为了支持外部 skill 直接 persist 而放宽 persist validation。
- 先保持 active buddy boundary，避免 durable state 被任意 skill_id 污染。

## Reviewer Recommendation

V1 对社区 skill 的限制是合理的：

- native codex multi-skill can include helper skills.
- BuddySwitch durable ownership requires active buddy membership.
- Import/register is the boundary-crossing action.
- Do not make persist accept arbitrary skill ids.
