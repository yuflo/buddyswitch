# 06. 优化 Backlog

## 1. 使用原则

本 backlog 不是立即执行清单，而是后续迭代的优先级参考。

每项都按以下格式记录：

- 问题
- 原因
- 预期收益
- 实施前提
- 是否需要代码改动

## 2. P0 必须收敛

### P0-1 明确 `switch` 的 LLM-native 入口语义

- 问题
  当前 `switch` 同时被当成 canonical directive 和文本 parser 协议，团队容易把复杂度加在格式规则上。
- 原因
  入口结构没有被明确提升为第一等概念，parser 和 spec 共同承担了过多“语法权威感”。
- 预期收益
  后续所有入口改动都会围绕“结构化唤起”而不是“空格/冒号细节”展开。
- 实施前提
  需要先在规范中统一：
  - canonical form
  - 最小 invocation schema
  - parser/routing/host 的职责边界
- 是否需要代码改动
  初期不一定。先改规范也有价值。

### P0-2 为每条控制层校验补“失败动作定义”

- 问题
  当前多处校验只有错误消息，没有统一动作模型。
- 原因
  系统先实现了规则，后定义其控制语义。
- 预期收益
  便于后续明确哪些校验保留、哪些降级、哪些删除。
- 实施前提
  采用统一动作集合：`normalize / warn / ask / reject`。
- 是否需要代码改动
  不一定。可先体现在规范和审查文档中。

### P0-3 收敛 `permissions` 在不同入口层的语义

- 问题
  runtime 主链路与 debug APIs 对 `permissions` 的使用强度不同。
- 原因
  authority 模型尚未被拆成 routing authority 与 state mutation authority。
- 预期收益
  避免后续继续形成双轨权限系统。
- 实施前提
  需要先做概念拆分，再决定是否要让 runtime 显式 enforce 更多权限。
- 是否需要代码改动
  大概率需要，但应在概念明确后再动。

## 3. P1 推荐重构

### P1-1 重新定义 `required_env` / `required_tools` 的产品语义

- 问题
  这两个字段当前既存在于 metadata，又会影响 resolve eligibility，但失败后恢复动作不清晰。
- 原因
  元数据字段先被引入，后被部分赋予 gate 语义。
- 预期收益
  避免未来继续增加“环境规则复杂度”。
- 实施前提
  需要明确它们到底属于：
  - 文档提示
  - warning
  - ask
  - reject
- 是否需要代码改动
  可能需要。

### P1-2 让 `resolve` 输出更明确地表达下一步动作

- 问题
  当前 `resolve` 返回了丰富上下文，但 host 还需要自行推断“现在该做什么”。
- 原因
  输出是“结构充足”，但“操作提示不完整”。
- 预期收益
  降低 host 实现时的隐性决策负担。
- 实施前提
  先明确 `resolve` 的职责是否严格限制为“只给上下文”。
- 是否需要代码改动
  可能需要。

### P1-3 增加控制层针对性测试，而不是继续扩 general tests

- 问题
  当前 tests 更偏 runtime happy path 和 repo consistency。
- 原因
  控制层边界尚未被测试矩阵化。
- 预期收益
  让未来重构 parser/runtime/authority 时更安全。
- 实施前提
  先确定哪些边界是最终要保留的。
- 是否需要代码改动
  是，主要是新增测试。

## 4. P2 可观察迭代

### P2-1 已完成：清理历史文档与现行规范之间的表述漂移

- 问题
  旧产品规划文档曾提供产品心智影响，但不是现行 source of truth。
- 原因
  旧文档保留有价值，但未与现行规范形成明确映射。
- 预期收益
  降低团队在旧文档和现行行为之间来回切换的成本。
- 实施前提
  已通过移除 `docs/buddyswitch/` 闭环。
- 是否需要代码改动
  否。

### P2-2 对 cleanup / admin 类入口单独建模

- 问题
  cleanup 类命令当前不完全遵循 debug API 的 permission gate 模式。
- 原因
  这类命令更接近管理能力，而不是普通 buddy 动作。
- 预期收益
  避免团队误以为它们只是“忘了加权限校验”。
- 实施前提
  先区分 admin tooling 与 normal debug API。
- 是否需要代码改动
  不一定。

## 5. 建议的后续迭代顺序

1. 先统一入口语义与失败动作词表。
2. 再收敛 `permissions` 与 `required_env/tools` 这两类最容易复杂化的控制点。
3. 最后再补测试和文档对齐，不要反过来先把当前模糊规则固化成回归测试。
