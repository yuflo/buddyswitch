# Codex Native Multi-Skill Flow V1

## Target

把 BuddySwitch 的多 SKILL 执行尽量贴近 codex-cli 原生机制：

- Codex 负责识别、读取、注入多个 SKILL.md。
- 模型负责多 skill 的实际排序、协作、取舍。
- BuddySwitch 只负责在 active buddy 范围内 materialize skills，并在 persist 阶段记录一个明确的 durable result owner。

## Confirmed Baseline

- codex-cli 原生多 skill 不是工作流引擎。
- 多个显式 skill 会被收集、去重、读取、注入 prompt。
- skill 的执行顺序不是 host runtime 调度出来的，而是模型根据注入上下文完成。
- BuddySwitch dev0210 已经基本走原生 codex-cli：active buddy skills 被 materialize 到 `.agents/skills/<skill-id>`，launcher 从 instance workspace 启动 codex。
- 现有限制在 BuddySwitch durable boundary：一次 `persist` 仍只提交一个 `skill_id`。

## V1 Decision

保留“一次 prepare/persist 一个 result-owner skill_id”：

- `skill_id` 表示本次 durable result 的 owner，不表示本轮只用了这个 skill。
- 多个 helper/reviewer/research/design/test skill 可以参与，但它们的输出要被 owner 整合。
- 如果用户需要多个并列 durable 结果，拆成多个 prepare/persist cycle，而不是一个 prepare 多次 persist。

## Runtime Flow

1. Active buddy materializes allowed skills into workspace.
2. User query may mention or trigger multiple skills.
3. codex-cli injects all selected skill instructions.
4. Model executes native multi-skill reasoning and tool use.
5. When output needs durable state, choose one result owner.
6. Owner produces one receipt/artifact/task state through `persist`.

## Product Rule

用户体验上应该表达为：

> 这轮可以用多个 skill 协作，但最终只有一个 skill 对这份持久化结果负责。

## Open Risk

- 多 skill 贡献可能被 owner collapse 后丢失可见性。
- 用户可能以为所有参与 skill 都各自留下 durable artifact。
- 需要在 prompt/runtime contract 里明确：未 persist 的 skill output 只是上下文，不是 durable state。
