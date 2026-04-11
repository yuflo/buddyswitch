# 01. 审查章程与方法

## 1. 审查目标

本轮审查只回答 4 个问题：

1. BuddySwitch 当前控制层的职责边界是否清晰。
2. `switch` 入口是否正在被当成 LLM-native invocation，而不是格式规则入口。
3. 当前校验中，哪些属于必要的状态安全门槛，哪些属于不必要的规则化实现。
4. 当前文档、测试和真实行为是否一致。

## 2. 范围

### 2.1 纳入审查

- `switch` 文本入口、parser 与 router
- runtime 的 `resolve / persist`
- manifest 与 skill runtime metadata 装载逻辑
- output schema 校验逻辑
- track / artifact object store
- manual/debug CLI APIs
- 相关文档与测试

### 2.2 不纳入本轮主审

- skill 业务内容本身的“质量好不好”
- context panel 的 UI 交互与视觉层
- `projects/app/` 中的业务代码
- 实际 LLM prompt 设计细节

这些内容如果影响控制层判断，只在 backlog 中登记，不作为本轮主审对象。

## 3. 证据来源

### 3.1 代码

- `scripts/parse_switch.py`
- `scripts/codex_router.py`
- `scripts/switch_runtime.py`
- `scripts/env_manifest.py`
- `scripts/output_schema.py`
- `scripts/env_store.py`
- `scripts/env_tracks.py`
- `scripts/env_artifacts.py`

### 3.2 文档

- `README.md`
- `AGENTS.md`
- `framework/docs/switch-spec.md`
- `framework/docs/skill-architecture-best-practices.md`
- `framework/docs/track-registry.md`
- `docs/buddyswitch/04-switch-protocol.md`

### 3.3 测试

- `tests/test_switch_runtime.py`
- `tests/test_repo_consistency.py`

## 4. 审查基准

### 4.1 LLM-native 基准

控制层应尽量把“语义理解”交给 LLM/CLI，把“结构化消费和状态保护”交给 runtime。

在这个基准下：

- 文本输入应尽量被视为 tool invocation 原始输入
- router 应尽量暴露清晰结构，而不是扩大文本格式约束
- runtime 不应承担业务质量评审角色

### 4.2 最小状态安全基准

只有以下两类问题适合成为硬性 `reject`：

- 会导致误路由或无法进入正确工作流
- 会导致状态文件写坏、对象关系损坏或路径越界

### 4.3 失败动作基准

本审查统一使用以下 4 种动作：

#### `normalize`

输入可自动规整，规整后继续。

适用场景：

- 空白差异
- 大小写或轻微格式变体
- 非关键别名

#### `warn`

允许继续，但返回风险提示或质量提示。

适用场景：

- 缺少辅助信息
- 质量不足但仍可执行
- 环境条件不理想但不阻断

#### `ask`

需要用户或 host 补一个关键决策，否则继续会产生高风险歧义。

适用场景：

- 多种候选目标都合理
- 明确缺少高影响上下文

#### `reject`

必须停止，因为继续会导致误路由或写坏状态。

适用场景：

- 无法识别 `buddy`
- 输出不满足最小持久化结构
- 引用的 track/artifact 不存在且不能安全降级

## 5. 审查方法

每个子系统统一按下列模板审查：

1. 当前职责
2. 当前输入输出
3. 当前显式校验
4. 当前失败动作
5. 是否符合 LLM-native 架构原则
6. 保留项 / 降级项 / 删除项建议

## 6. 审查结果的使用方式

本轮审查结果不是“立即改代码的 patch list”，而是后续收敛的决策底稿。

后续任何控制层重构建议，都应先回答：

1. 改动针对的是哪条已记录的校验或边界问题。
2. 它属于 `P0 / P1 / P2` 中哪一级。
3. 它的失败动作是否已经清楚。

如果不能回答这三点，不建议直接进入实现。
