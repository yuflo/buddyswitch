# 02. `switch` 唤起与 Router 审查

## 1. 当前角色定位

BuddySwitch 当前把 `switch <buddy>: <task>` 作为顶层触发协议。

从产品意图看，它更像一个显式 tool invocation：

- 用户明确表达 `intent = switch`
- 用户明确提供目标 `buddy`
- 用户提供自由任务体 `task`

从实现看，它目前仍主要通过文本 parser 和 runtime 规则来消费这一触发协议。

这导致系统同时存在两种心智模型：

- 产品模型：显式唤起某个 buddy
- 实现模型：先走文本匹配，再走规则过滤

## 2. 当前实现链路

### 2.1 `parse_switch.py`

当前 parser 的实际职责是：

- 接受一段原始文本
- 判断是否以 `switch` 开头
- 用正则抽取 `buddy` 与 `task`
- 用 manifest 校验 `buddy` 是否存在
- 返回结构：
  - `ok`
  - `agent` / `buddy`
  - `task`
  - 或 `error`

### 2.2 `codex_router.py`

当前 router 的职责是：

- 复用 `parse_switch`
- 读取 manifest
- 加载当前 buddy 的 profile 和 skill docs
- 返回一段比 parser 更丰富的 route payload

当前 router 输出的重点是：

- `buddy`
- `task`
- `profile.scope`
- `profile.permissions`
- `profile.skills`

### 2.3 `switch_runtime.py resolve`

`resolve` 进一步把 parser/router 的结果扩展为运行时上下文：

- `eligible_skills`
- `skill_cards`
- `track_context_by_skill`
- `task_hints`
- `required_output_schema_by_skill`

## 3. 当前问题判断

### 3.1 `switch` 的本质已经接近 tool call，但接口描述仍偏文本协议

当前实现里，真正被消费的结构其实已经很清楚：

- `buddy`
- `task`
- 由 `buddy` 派生的 skill candidates

问题不在“结构缺失”，而在“结构不是第一等概念”。

当前链路仍把 `switch` 首先当作一段文本去严格解释，而不是当作一个需要被 LLM/CLI 稳定提取的唤起 schema。

### 3.2 parser 现在承担了不该过重承担的入口权威感

`parse_switch.py` 当前既负责：

- 文本触发识别
- buddy 校验
- 错误展示

但它的输入仍是自由文本，而且错误返回是围绕“语法正确性”组织的。

这会自然诱导后续实现继续往 parser 加规则，而不是改进“LLM/CLI 应该提取什么结构”。

### 3.3 router 暴露的是 profile，但没有显式暴露 invocation schema

当前 router 会暴露：

- `syntax`
- `example`
- `buddy`
- `task`
- `profile`

但没有明确告诉 host：

- 本次调用的结构化语义是什么
- router 已经标准化了什么
- host 还能对输入做哪些 normalization

这会使“parser 负责什么、router 负责什么、LLM 负责什么”边界继续含糊。

## 4. LLM-native 评估

### 4.1 符合的地方

- 用户显式选择 buddy，而不是隐藏路由。
- host Codex session 负责读 skill、执行工作流、生成结构化输出。
- runtime 没有引入第二套 LLM backend 做内部 routing。

### 4.2 不符合的地方

- `switch` 仍主要被当成“文本格式协议”而不是“唤起 schema”。
- 当前规范文档对“canonical syntax”的表达强于真实产品所需。
- parser / spec / runtime 对 minor formatting variation 的容忍度和表述并不一致。

## 5. 审查结论

### 5.1 保留

- `switch` 作为显式 framework directive 的产品决策
- 用户必须明确选择 buddy
- router 向 host 暴露 buddy profile 与 skill context

### 5.2 需要收敛表达

- `switch <buddy>: <task>` 应被定义为 canonical form，而不是格式洁癖入口
- parser 失败时应优先回答“是否真的无法识别意图”，而不是“是否符合某个格式习惯”
- router 应更明确承担“把唤起结构暴露给 host”这一职责

### 5.3 本轮审查建议

- 后续任何 parser/routing 改动，都应优先从“结构化唤起 schema 是否清楚”出发，而不是从“再加哪条正则”出发。
- 入口层的校验，只保留那些会导致：
  - 无法识别 `intent/buddy/task`
  - 明显误路由
  的情况。

## 6. 建议采用的审查基准结构

本轮不修改实现，但建议后续所有控制层讨论都使用下列最小结构作为思考对象：

```json
{
  "intent": "switch",
  "buddy": "market",
  "task": "research sierra for landing page",
  "raw_text": "switch market: research sierra for landing page"
}
```

这个结构不是当前实现 contract，而是后续优化与审查的统一基准。

它的作用是避免团队继续把复杂度投注在“原始字符串长什么样”，而忽略“host 到底需要什么结构”。
