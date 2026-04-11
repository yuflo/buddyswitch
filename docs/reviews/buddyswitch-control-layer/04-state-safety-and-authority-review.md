# 04. 状态安全与 Authority 审查

## 1. 本文目标

本文只回答两个问题：

1. 当前哪些约束是真正保护 BuddySwitch 状态安全的。
2. 当前 `authority / permissions / ownership` 表达中，哪些是清晰的，哪些是双轨或含混的。

## 2. 当前状态安全链路

BuddySwitch 当前的状态写入主要分 3 层：

### 2.1 运行时层

`switch_runtime.py`

负责：

- 选择 skill
- 结合 track context 计算 artifact defaults
- 校验 result payload
- 调用 store 层写入 artifact / track / summary / run content

### 2.2 store 层

`env_store.py`

负责：

- track / artifact 的结构校验
- path / id / repo-relative 安全边界
- attach / detach 自动维护对象关系
- content / run JSON 落盘

### 2.3 manual/debug API 层

- `env_tracks.py`
- `env_artifacts.py`

负责：

- 将底层 store 能力暴露为手工 CLI 命令
- 用 manifest permissions 做 actor gate

## 3. 真正属于状态安全的约束

以下约束属于合理的“系统底座约束”：

### 3.1 对象唯一性与引用存在性

- track id 必须唯一
- artifact id 必须唯一
- attach/detach 时目标对象必须存在
- artifact 的 `context_track_id` 必须引用存在的 track

### 3.2 路径与 repo 边界

- 路径必须是 repo-relative
- 禁止 `..`
- artifact / summary / content / run content 都有固定根目录
- 文件后缀必须匹配预期

### 3.3 最小结构一致性

- result payload 必须通过 output schema
- track/artifact object 必须满足结构校验
- manifest / skill runtime metadata 必须足够完整到能驱动 runtime

这些约束的共同特点是：

- 如果放松，会直接导致状态不可预测或写坏
- 失败后动作明确，只能 `reject`

## 4. 当前 authority 表达的三种来源

### 4.1 文档层 authority

文档中多次表达：

- `pm` 拥有 track lifecycle authority
- 其他 buddies 以 artifact 为主
- `persist` 负责“lightweight authority/context consistency”

### 4.2 manifest 层 authority

`buddyswitch/manifest.toml` 为每个 buddy 显式声明：

- `skills`
- `permissions`

这使 authority 至少在配置层是清晰存在的。

### 4.3 脚本层 authority

脚本层目前形成了双轨：

- `switch_runtime.py`
  - 显式 enforce 的主要是 `buddy -> skills` 与 schema
  - 并未系统性使用 `permissions` 做权限门槛
- `env_tracks.py` / `env_artifacts.py`
  - 显式用 `permissions` 做 actor gate

## 5. 当前 authority 模型的主要问题

### 5.1 同一概念在不同入口层语义不一致

当前“authority”至少有三种意思：

1. 哪个 buddy 可以被选中
2. 哪个 skill 可以运行
3. 哪个 actor 可以直接调用低层 debug API

这三件事目前没有被明确拆开。

结果是：

- 文档上看起来像统一 authority 模型
- 实现上其实是多种局部控制的叠加

### 5.2 `permissions` 已存在，但 runtime 主链路没有把它当第一等控制接口

这会带来两个风险：

- 文档容易说得比真实实现更强
- 未来团队可能继续在 runtime 里追加零碎权限 gate，形成更复杂的双轨系统

### 5.3 cleanup 类入口没有对齐当前 authority 叙事

`env_artifacts.py` 的 `cleanup-buddy` / `cleanup-all` 当前不走 `require_permission`。

这并不一定是 bug，但它说明当前 authority 并不是一个已经被统一建模的体系，而是一个混合体：

- 有些入口是严格 actor gate
- 有些入口默认认为这是管理动作

如果不明确记录，后续很容易出现“补一条权限规则”式的局部修补。

## 6. 审查结论

### 6.1 应保留的 authority 事实

- `buddy -> skills` 的映射是 runtime 主链路真正依赖的 authority
- `pm` 对 track lifecycle 的特殊角色是产品上成立的
- manual/debug APIs 使用 `permissions` gate 是成立的

### 6.2 不应继续模糊扩大的一面

- 不应再默认把文档中的 authority 描述等同于“runtime 已完整 enforce”
- 不应在未统一模型前继续把 `permissions` 扩成复杂运行时权限系统
- 不应让更多入口自行发明本地 authority 规则

## 7. 推荐边界

后续若要收敛 authority，建议先在概念上拆成两层：

### 7.1 Routing Authority

决定：

- 当前 buddy 能运行哪些 skill
- host 在 `resolve` 后有哪些合法路径

### 7.2 State Mutation Authority

决定：

- 哪些入口可以直接变更 track/artifact state
- 哪些入口需要 actor/permission gate

在这两层没有被明确前，不建议继续增加新的权限型校验。

## 8. 本轮结论对后续实现的约束

本轮审查不要求立即改 authority 模型。

但后续所有相关改动都应先声明属于哪一类：

- 路由 authority 问题
- 状态变更 authority 问题

如果说不清，就不应直接加规则。
