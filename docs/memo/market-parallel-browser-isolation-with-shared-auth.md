# Market Parallel Browser Isolation With Shared Auth Memo

## Bottom Line

当前 `market` 的浏览器执行模型更适合：

- 单人
- 串行
- 连续研究

它不适合：

- 多个 `buddyswitch-codex` 并行跑 `market`
- 多个研究 run 同时操作浏览器
- 用户希望“互不干扰，但尽量不要重复登录”

这不是一个“小窗口管理问题”，而是一个更底层的执行模型问题。

当前共享的是：

- 同一个 `chrome-devtools-cockpit`
- 同一个 remote debugging port
- 同一个 Chrome profile
- 同一个 session continuity 约定

所以“新开一个窗口”本身不能提供真正隔离。

补充一个当前已经确认的运行事实：

- 默认多开 `buddyswitch-codex`
- 第二个实例如果也执行 `switch market`
- 不会自动获得第二套独立浏览器研究环境
- 而是继续接到同一个 `chrome-devtools-cockpit` / `shared-browser`

因此如果短期要支持“多开管理”，当前最现实的落点仍然是：

`通过多窗口管理共享浏览器里的并行操作`

这不是完整隔离方案，只是当前结构下更现实的管理方案。

这份 memo 只记录这个方向的设计边界、约束、候选方案和最新结论。

## Current Model

当前 `market` 合同明确要求：

- `browser_executor = "chrome-devtools-cockpit"`
- `browser_mode = "headed-only"`
- `browser_profile = "shared-browser"`
- `session_continuity = "shared-cockpit"`

这意味着：

1. 所有 `market` run 默认接入同一个浏览器控制面
2. 所有 `market` run 默认复用同一个浏览器用户数据目录
3. 登录态、cookie、localStorage、tab 状态天然共享
4. 页面 ownership 没有按 run 隔离

这个模型的优点很明确：

- 登录成本低
- 冷启动便宜
- 对单人连续研究顺手
- takeover 之后的连续访问体验好

它的缺点在并行场景下也很明确：

- 多个 session 会互相打断
- page/tab/window 的归属不清
- takeover 可能污染别的 run
- 用户看到同一个浏览器界面被多个 agent 操作，体验差

## Why “Open A New Window” Is Not Enough

人的直觉是：

- 我手动研究时会新开一个窗口
- 然后在这个窗口里继续开标签页
- 这样看起来彼此独立

但在当前 BuddySwitch 结构里，这种“独立窗口”只是视觉上的，不是执行上的。

只要底层还是：

- 同一个 profile
- 同一个 debugging port
- 同一个 cockpit MCP target

那么即使再开新窗口，仍然会遇到这些问题：

1. 运行 A 打开的窗口，运行 B 仍然可能看到并操作
2. 一个窗口里的登录/跳转状态会被别的运行继承
3. page selection / focus 仍然可能串
4. 用户无法明确判断“这个窗口属于哪个 run”

所以“独立窗口”只有在它背后同时意味着独立的执行上下文时，才真正成立。

## The Real Design Goal

后续要解决的不是“一个窗口还是两个窗口”，而是两个更核心的问题：

1. **操作面隔离**
   - A run 的页面、窗口、焦点、滚动、标签页不应该干扰 B run

2. **认证能力尽量共享**
   - 用户不应该因为每次并行研究都被迫重新登录

这两个目标天然有冲突：

- 隔离做得越彻底，越容易丢登录态
- 登录态共享越彻底，越容易互相污染

后续方案评估的核心，就是在这两个目标之间找最合适的平衡点。

## Non-Goals

后续设计不应该扩到这些方向：

- 不做通用浏览器多租户平台
- 不把所有 buddy 都改成多浏览器隔离架构
- 不为了这个问题先重写 BuddySwitch 全部 launcher
- 不把“窗口管理”误当成“认证共享”问题的完整答案

这件事应该严格收敛在：

`market 并行研究时的浏览器执行模型`

## Constraints

后续方案必须面对这些现实约束。

### 1. Login State Lives In Profile

最现实的一条：

登录态通常就在浏览器 profile 里。

所以只要方案采用：

- 独立 profile

那么默认就意味着：

- 独立 cookie
- 独立 localStorage
- 独立 session
- 用户可能要重新登录

这不是 BuddySwitch 特有问题，而是浏览器工作方式本身决定的。

### 2. Shared Profile Gives Continuity But Weak Isolation

反过来，如果所有运行都继续共享同一个 profile：

- 登录态保住了
- 但隔离就天然变弱

也就是说：

- “共享 profile + 真正并发隔离”

这不是一个可以轻松同时成立的组合。

### 3. MCP Control Plane Works On Browser Targets, Not Human Ownership

当前工具层管理的是 page targets，而不是“哪个窗口属于哪个 run”。

所以即使未来做多窗口，也必须回答：

- 一个 run 如何只看到自己的 targets
- 一个 run 如何不误操作别的 run 的窗口
- target ownership 如何表达

如果不解决这个层面，单纯多窗口还是会串。

### 4. User Experience Matters More Than Purity

这类设计不能只追求技术上最干净。

如果方案导致：

- 每次都要重新登录
- takeover 成本非常高
- 用户必须理解太多浏览器隔离细节

那即使技术上隔离更纯，也不一定是更好的产品。

## Viable Directions

这里只记录后续真正值得讨论的方向。

### Option A: Keep Today’s Shared Cockpit

含义：

- 继续共用同一个 `shared-browser`
- 继续共用同一个 cockpit
- 不做并行隔离

优点：

- 最简单
- 登录体验最好
- 不需要新增架构

缺点：

- 并行时 UX 差
- 容易互相干扰
- page ownership 不清

判断：

- 适合作为现状基线
- 不适合作为长期并行体验方案

### Option B: Full Isolation Per Launcher / Per Run

含义：

- 每个 `buddyswitch-codex` 拥有独立 profile
- 独立 debugging port
- 独立 MCP target
- 可以对应独立窗口

优点：

- 隔离最彻底
- 并行最干净
- ownership 最清楚

缺点：

- 用户需要重复登录
- takeover 成本高
- 会丢掉共享 session continuity 的优势

判断：

- 从纯工程角度最稳定
- 从真实产品体验角度，登录摩擦很重

### Option C: Shared Auth Source + Isolated Working Context

这是最值得研究的方向。

目标不是“完全共享 profile”，也不是“完全独立 profile”，而是：

- 认证能力尽量复用
- 运行中的操作面尽量隔离

直觉上可以理解成：

- 有一个“认证来源”
- 但每个运行有自己的“工作面”

它的吸引力在于：

- 有机会同时兼顾登录成本和并行隔离

但它也是最复杂的，因为要回答：

- 认证状态如何安全复用
- 哪些状态能共享，哪些状态不能共享
- 是启动时复制、运行时同步，还是只做一次性种子

这条方向现在最有价值，但不应在吃饭前拍脑袋定实现。

### Option D: Shared Browser, But Stronger Window Ownership

含义：

- 继续共享一个浏览器 profile
- 继续共享一个 cockpit
- 但通过更强的 run/window 绑定，尽量降低互相干扰

优点：

- 登录态保持最好
- 实现可能比完整隔离轻

缺点：

- 本质仍然是共享控制面
- ownership 很容易做成“看起来隔离，实际还会串”
- 只能缓解，不能彻底解决

判断：

- 可以作为过渡策略
- 但不太像最终答案

## Recommendation

基于当前已经确认的运行行为，以及对产品体验的重新权衡，当前结论更新为：

### 结论一

默认多开 `buddyswitch-codex` 并执行 `switch market` 时，多个会话实际上仍然在争用同一个共享浏览器控制面。

也就是说：

- 不是“两个 launcher = 两套独立浏览器”
- 而是“两个 launcher = 两个 agent 抢同一个 shared cockpit”

### 结论二

因此，如果近期真的要支持“多开管理”，当前更现实的方案仍然是：

- 多窗口
- 每个并行 buddy 尽量固定在自己的窗口内
- 每个窗口内部再通过多标签页继续研究

换句话说：

- 当前更像是“共享浏览器里的窗口管理问题”
- 还不是“已经具备完整隔离能力的多实例浏览架构”

### 结论三

这不等于“多窗口就是最终答案”。

它只是说明：

- 在现有 `shared-browser + shared-cockpit` 前提下
- 如果要做并行管理
- 多窗口仍然是最现实、最贴近当前实现约束的入口

### 结论四

这个话题暂时不继续推进。

当前只把最新判断固定下来：

- 短期并行管理 => 仍然优先考虑多窗口
- 完整隔离问题 => 后续有时间再单独展开

## Questions To Answer Later

后续如果要重新打开这个话题，这几个问题仍然值得优先回答：

1. 我们要管理的是“每个 launcher 的窗口归属”，还是“每个 market run 的窗口归属”？
2. 多窗口管理只做到 UX 层，还是要进一步补 target ownership / attach guard？
3. 什么情况下我们才值得从“窗口管理”升级到“真正独立实例 / 真正独立 profile”？
4. 登录连续性、takeover 成本、串扰风险三者之间，后续真正优先级怎么排？

## Suggested Next Conversation

这个议题目前先暂停。

后续如果重新继续，建议直接从这两个问题恢复：

1. 多窗口管理要做到什么边界才算“够用”？
2. 什么时候值得从“共享浏览器管理”切到“真正隔离实例”？
