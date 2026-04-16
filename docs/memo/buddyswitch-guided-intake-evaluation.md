# BuddySwitch Guided Intake 交互增强评估 Memo

## 目的

这份 memo 只记录一件事：

`BuddySwitch 未来是否值得、以及如何演进出带 option 的引导式交互能力。`

它不是本期 `design` skill 重构方案本身。

本期主线仍然是 `design` buddy 的 skill 重构；这里记录的是后续很值得做、但不一定在这一期落地的产品增强方向。

## 问题背景

BuddySwitch 当前的核心交互仍然是：

```text
switch <buddy>: <demand>
```

这种形式在用户已经知道自己要什么时很好用，但现实里很多用户并不清楚自己的真实 task。

他们更常说的是：

- “帮我搞一下这个产品”
- “这个流程有点乱”
- “用户总担心 AI 会乱操作”
- “这个功能我不知道该怎么设计”
- “帮我看看接下来应该做什么”

这些表达方式对人类协作者是正常的，但对纯命令式路由系统来说，它们通常还不够结构化。

因此，BuddySwitch 很值得考虑增加一层能力：

- 在用户意图不够清晰时
- 通过少量高价值问题
- 把模糊目标收敛成更准确的 task
- 然后再进入真正的 skill 执行

这就是本 memo 所说的：

`guided intake`

## 为什么这件事值得做

## 1. 它能直接提升 BuddySwitch 的产品体验

如果 BuddySwitch 只能处理“已经表达很准确的命令”，那它更像一个面向熟练用户的控制层。

如果 BuddySwitch 能在必要时帮助用户澄清任务，它就会更像一个真正的协作产品：

- 用户不必先学会内部 skill 体系
- 用户不必先掌握设计、产品或研究术语
- 用户可以先说目标或症状，系统再帮助收敛
- 最终被执行的 task 会更准确

这类增强的价值不在于“更像聊天”，而在于：

`把任务定义这一步也产品化。`

## 2. 它特别适合 BuddySwitch 的目标场景

BuddySwitch 面向的是小团队、独立开发者、快速迭代场景。

这类用户最常见的状态不是“知道内部最优 skill 名字”，而是：

- 有产品目标
- 有一些直觉或担忧
- 有一点模糊的下一步
- 但还没有把问题定义成一个清晰任务

如果系统能在这一步提供短而准的引导，它的价值会非常直接。

## 3. 它与 `design` buddy 的未来体验高度相关

虽然这不是本期主线，但从所有 buddy 中看，`design` 最适合率先吃到这类能力。

原因很简单：

- `design` 任务的歧义度通常最高
- 用户最容易“不知道自己该如何准确描述”
- 设计类任务常常从症状开始，而不是从规范任务开始
- `design` 主要产出 artifact，试点风险比直接动代码的 buddy 更低

因此，这个方向不是抽象想象，而是和当前 `design` buddy 演进天然相连。

## 当前 BuddySwitch 架构是否适合做这件事

结论是：

`适合，而且是增量式可行。`

BuddySwitch 当前已经有清晰的运行边界：

- `parse`
- `resolve`
- `run`
- `persist`

从 `framework/docs/switch-spec.md` 可以看到，控制层已经定义了：

- `normalize`
- `warn`
- `ask`
- `reject`

其中 `ask` 已经说明了一个重要方向：

BuddySwitch 的控制层本来就允许“停下来索取更多意图或明确选择”，只是现在还没有形成一套正式的交互协议。

这意味着：

- 当前架构并不排斥引导式交互
- 反而已经给了一个很合适的接入点

最自然的位置是：

`resolve -> run`

也就是：

1. 用户输入 `switch ...`
2. `resolve` 判断信息是否足够
3. 如果不足，返回一个结构化交互请求
4. host 和用户完成简短交互
5. 再继续 `run`
6. `persist` 仍然只负责最终落盘

这条链路非常适合做 additive 增强，而不是推翻当前框架。

## 从 Codex 本地源码得到的关键启发

为了判断这种能力是否值得设计成正式协议，本轮查看了 `tmp/codex` 里的相关实现。

结论很明确：

`带 option 的用户交互不应该只是 prompt 技巧，而应该是正式协议能力。`

关键线索来自：

- `tmp/codex/codex-rs/protocol/src/request_user_input.rs`

这里的 question 结构包含：

- `id`
- `header`
- `question`
- `options`
- `isOther`
- `isSecret`

这说明在 Codex 里，“选项 + 允许自定义输入”是协议层明确定义的，不是 UI 偶然长出来的行为。

进一步看 app-server 和 TUI 侧实现，也能确认：

- 这是一个被正式处理的 interaction event
- 前端会渲染成专门的交互界面
- 但 transport 结构本身保持很轻

对 BuddySwitch 最重要的启发不是“照着做一模一样的 UI”，而是：

### 正确方向

- 先定义 `interaction contract`
- 再让 host 选择如何渲染
- rich UI 是增强，不是前提
- 没有 UI 时，仍可降级成文本问答

### 错误方向

- 让某个 skill 自己吐 Markdown 选项列表
- 让 prompt 自己模拟表单
- 把交互逻辑写死在某个特定 terminal harness 里

## 对 BuddySwitch 的推荐设计原则

如果未来要做 guided intake，我建议遵守这几条原则。

## 1. 交互能力必须是 additive，而不是全局强制

不能把所有 `switch` 调用都变成 wizard。

更合理的做法是：

- 默认不交互
- 只有在高歧义任务时才触发
- 只有需要时才出现 `options + other`

这意味着协议设计上应允许：

- `interaction_mode = none`
- `interaction_mode = clarify`
- `interaction_mode = guided-intake`

这样现有 buddy 不需要同步改造，也不会被硬性打断。

## 2. 用户永远说产品语言，不说 skill 语言

交互的目标不是教用户系统术语，而是帮助系统理解用户真实意图。

因此问题应该像这样：

- 这个任务最重要的用户是谁
- 你更想先出一版完整方案，还是先解决某个明显问题
- AI 在这里应该直接执行，还是先建议给用户确认
- 用户最不能接受的错误是什么

而不是：

- 你是否要使用 recovery-and-escalation skill
- 这是 copilot 还是 proactive 形态
- 你要不要 trust-controls-spec

BuddySwitch 的强大之处应该来自：

`用户不需要懂内部结构，系统自己完成翻译。`

## 3. 问题数必须极少

交互不是审问。

如果每次 `switch` 都要回答很多问题，体验会迅速恶化。

建议把触发后的问题数控制在：

- 1 到 3 个

而且只问高杠杆问题。

判断标准应是：

- 这个问题的答案会显著改变 skill 选择或输出方向吗
- 如果不知道这个答案，是否真的会影响执行质量

如果不会，就不该问。

## 4. 信息足够时应直接执行

guided intake 不是必须经过的仪式。

如果用户输入已经足够明确，就直接执行，不要为了“显得聪明”而强行补问题。

理想体验应该是：

- 简单请求直接跑
- 模糊请求再收敛

而不是：

- 所有请求都先进 intake

## 5. host-agnostic，UI-enhanced

BuddySwitch 不应该把这项能力绑死在某一个 host 的原生 UI 上。

正确做法是：

- 协议层定义统一结构
- 有 rich UI 的 host 渲染为选项交互
- 没有 rich UI 的 host 退化成文本提问

这样这项能力才能成为 BuddySwitch 的产品能力，而不是某个终端环境的偶发能力。

## 一个合理的最小协议长什么样

这不是正式 RFC，只是当前最稳妥的方向草图。

`resolve` 可以在现有返回结构上新增一个可选块：

- `clarification_needed`
- `interaction_mode`
- `interaction_spec`

其中每个问题对象的最小结构可以是：

- `id`
- `header`
- `prompt`
- `options`
- `allow_other`
- `required`
- `why_this_matters`

如果参考 Codex 的思路，保持 transport 简洁是对的。

BuddySwitch 并不需要一开始就设计很重的表单 schema。相反，应该优先保证：

- 简单
- 可扩展
- 可降级
- 不破坏当前 resolve/run/persist 边界

## 为什么建议先在 `design` buddy 上试点

如果以后决定真正做这件事，我仍然建议先从 `design` 开始，而不是同时改所有 buddy。

原因如下：

### 1. `design` 的歧义度最高

相比 `dev` 或 `test`，`design` 的用户请求通常更模糊：

- “帮我做一下这个产品设计”
- “用户体验有点怪”
- “上手不好”
- “感觉不够放心”

这类输入非常适合 guided intake。

### 2. `design` 的风险更适合试点

`design` 产出的是 artifact，不是直接改代码或推进 track lifecycle。

这意味着：

- 即使交互策略还不完美，试点风险也可控
- 它更适合先验证“交互是否真的提升体验”

### 3. 它与当前主线天然相邻

我们本来就要重构 `design` skill。

虽然本期不一定把 guided intake 一并落地，但至少可以在设计新 skill map 时预留这条演进路径，避免未来还要反向拆结构。

## 对其它 buddy 的影响评估

这个方向最重要的前提之一是：

`不要让其它 buddy 被被动卷入。`

如果未来按 additive 协议做，且默认值是：

- `interaction_mode = none`

那么其它 buddy 即使完全不接入，也不会出问题。

这意味着：

- `pm` 可以继续按原有模式执行
- `market` 可以继续按原有模式执行
- `dev/test` 可以继续保持偏直接、低交互的工作流

只有当某个 buddy 明确需要这项能力时，才逐步接入。

因此，这不是“全局同时迁移”的方案，而是：

- 一个通用协议
- 少量 buddy 先用
- 逐步扩大覆盖范围

## 当前的推荐判断

基于这轮讨论和本地源码对照，我对这个方向的判断是：

### 值不值得做

非常值得。

这很可能是 BuddySwitch 未来最有价值的产品级增强之一，因为它直接作用在：

- 用户如何下达任务
- 系统如何理解任务
- skill 如何被更准确地路由与执行

### 是否适合现在就全量推进

不适合。

更合理的是：

- 先把 `design` skill 重构做好
- 再单独起一份 interaction contract RFC
- 如果要试点，就先在 `design` buddy 做最小可行版本

### 是否会影响其它 buddy

如果协议是 additive 且默认关闭，就不会。

这点很关键。

BuddySwitch 完全可以在不破坏 `pm / market / dev / test` 现有执行方式的前提下，逐步长出更强的交互能力。

## 建议的后续动作

等本期 `design` skill 重构推进到稳定阶段后，可以按下面顺序继续：

1. 单独起草一份 BuddySwitch `interaction contract` RFC
2. 明确触发条件：
   什么情况下直接执行，什么情况下进入 guided intake
3. 设计最小 question schema
4. 规定 host 有 UI / 没 UI 时的降级策略
5. 选择 `design` buddy 作为第一个试点对象
6. 等试点验证后，再考虑是否扩展到 `pm` 或 `market`

## 一句话总结

BuddySwitch 未来完全有必要长出“选项 + 自定义输入”的引导式交互能力；  
正确方向不是 prompt 小技巧，而是协议级的 guided intake，并且最适合作为后续在 `design` buddy 上先行试点的产品增强。
