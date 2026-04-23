# BuddySwitch Online Loop Skill Selection And Next-Turn Memo

## Bottom Line

当前 BuddySwitch online loop 对 Host Codex 的要求可以压缩成两句：

1. `拿到 resolve_context 后，从 resolve_context.skills 里选一个 skill_id 执行这一轮。`
2. `persist 成功后，先看 refreshed_context 能不能继续；能继续时，再由 Host 判断这件事是否还需要下一轮。`

最关键的区分是：

- `refreshed_context.ok` 只回答：`现在能不能继续下一轮`
- 它不回答：`这件事该不该继续下一轮`

`该不该继续` 仍然是 Host Codex / LLM 的任务完成度判断。

## Actual Prompt Source

运行时真正生效的 prompt 源不是 README，而是 launcher 复制进 runtime worktree 根目录的 `AGENTS.md`。

- 模板来源：`tools/launcher/assets/runtime-AGENTS.md`
- 复制逻辑：`tools/launcher/workspace.sh`

所以讨论“现在的 prompt 怎么写”，应以 `runtime-AGENTS.md` 为主，README 和 `framework/docs/switch-spec.md` 主要是同义说明和公开文档。

## Prompt 1: How Host Chooses A Skill

运行时主提示是：

> Let the host Codex session choose one `skill_id` from `resolve_context.skills`.
> For multi-skill buddies, choose from `resolve_context.skills` using the skill metadata plus `task_context` / `track_context`, then read the selected skill's `instruction_path` ...

这段提示的真实含义是：

- 每一轮只能选一个 `skill_id`
- 多 skill buddy 不会被 runtime 自动串联
- Host 要用三类信息做判断：
  - `resolve_context.skills`
  - `task_context`
  - `track_context`
- 选完以后，Host 还要继续读该 skill 的 `instruction_path`，而不是只靠 `skill card` 简介执行

换句话说，runtime 负责把候选 skill 和上下文交给 Host，但 `选哪个 skill` 这一步是 Host 决策，不是 runtime 决策。

## Prompt 2: How Host Decides Whether To Continue

运行时技术提示是：

> Check `refreshed_context.ok`; continue from `refreshed_context` when it is true, or rerun `resolve` when `refreshed_context.error.code = E_RUNTIME_REFRESH_CONTEXT`.

README 里的补充提示是：

> Continue from `refreshed_context` when the task needs another turn.

这两句合起来，实际意思是分两层：

### Layer 1: Technical Continuation Check

Host 先判断：

- `refreshed_context.ok = true`
  - 说明下一轮上下文已经准备好，可以直接继续
- `refreshed_context.ok = false` 且 `error.code = E_RUNTIME_REFRESH_CONTEXT`
  - 说明本轮 persist 已经成功，但下一轮上下文预留失败
  - 这时不是任务失败，而是要重新 `resolve`

### Layer 2: Product / Task Completion Judgment

只有在“技术上可以继续”之后，Host 才继续判断：

- 这次用户目标是否已经完成
- 如果没完成，是否值得再开一轮
- 如果要再开一轮，下一轮应该继续同一个 skill，还是切到另一个 skill

这一层没有被 runtime 硬编码。

## What The Current Mechanism Really Means

当前 BuddySwitch 的 online loop 不是：

- runtime 自动编排多 skill workflow
- persist 后系统自动决定下一步 skill

而是：

1. `resolve_context`
2. Host 选一个 skill
3. Host 执行这一轮
4. `persist-skill-result`
5. Host 看 `refreshed_context`
6. Host 决定结束，或者继续下一轮并重新选 skill

因此，多 skill online loop 的本质是：

`Host-managed turn-by-turn orchestration`

不是：

`runtime-managed automatic multi-skill chaining`

## Practical Rule

如果只保留一句最实用的判断规则，应该写成：

`先用 refreshed_context 判断“能不能继续”，再由 Host 判断“要不要继续”。`

对应到职责划分：

- BuddySwitch runtime 负责：`can continue`
- Host Codex / LLM 负责：`should continue`

## Why This Matters

这条边界会直接影响 Host 的执行质量。

如果 Host 把 `refreshed_context.ok = true` 误解成“应该自动继续”，就容易：

- 无意义多跑一轮
- 错把技术可继续当成任务未完成
- 在 multi-skill buddy 下产生不必要的 skill 串联

如果 Host 没意识到 `should continue` 仍然归自己判断，就会把多 skill online loop 误以为是 runtime 的职责。

这正是当前 BuddySwitch online loop 最容易被误读的地方。
