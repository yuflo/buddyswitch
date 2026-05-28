# Daemon Service MVP 第二步任务备忘

## 任务一句话

把已经从 Task TUI 中拆出来的 daemon core，继续推进成可承接多个业务团队需求的 `Daemon Service MVP`。

第一步是：

`拆归属、稳边界、保行为`

第二步是：

`建接入面、稳服务能力、让其它团队能标准接入`

## 背景前提

第一步完成后，daemon 已经不再是 Task TUI 的后台实现。

当前合理状态应是：

- daemon core 负责实例级后台容器能力
- Task Checkout Handler 负责 STOP Task TUI 业务逻辑
- Task TUI 只是第一个挂在 daemon 上的扩展能力
- launcher 仍然负责 start / clear 的 thread bootstrap 和空 rollout 处理

第二步不是继续拆 Task TUI，而是把 daemon core 对外沉淀为一个稳定的服务接入面。

## 核心目标

第二步完成后，daemon 的身份要从：

`可挂载 Task Checkout Handler 的 daemon core`

变成：

`可被 Task TUI、message、未来其它团队稳定接入的 Daemon Service MVP`

业务团队不应该再改 daemon 主循环，也不应该复制 app-server 连接、通知监听、origin tracking、状态记录、错误隔离这些 runtime 代码。

它们应该实现自己的 handler，并使用 daemon service 提供的基础能力。

## Daemon Service 的定位

daemon service 是 BuddySwitch 的实例级后台 runtime service。

它不是某个业务功能，也不是 Task TUI 专用进程。

它对业务团队提供的是后台共性能力：

- runtime event 感知
- handler 分发
- 后台 action 出口
- origin tracking / loop guard
- handler state namespace
- handler failure isolation
- daemon / handler observability

## 要做的事

### 1. 定义 Handler Contract

明确业务团队接入 daemon 时必须实现什么。

Handler contract 至少要说明：

- handler 有稳定 `name`
- handler 接收 daemon runtime notification
- handler 能访问当前 `DaemonContext`
- handler 能使用 daemon 提供的 action gateway
- handler 能读写自己的 namespaced state
- handler 返回明确结果：ignored / handled / failed
- handler 抛错时由 daemon core 捕获和记录

目标是让未来 message 团队知道：

`新增 handler，而不是修改 daemon loop`

### 2. 抽出 Action Gateway

不要让每个 handler 直接拼 app-server JSON-RPC 调用细节。

Action Gateway 至少提供：

- `turn_start(...)`
- 自动使用当前 main thread
- 自动使用 daemon permissions
- 统一构造 text input payload
- 统一解析 returned turn id
- 统一记录 daemon-origin turn id
- 统一暴露 app-server action error

Task Checkout Handler 后续通过 Action Gateway 投递 STOP Task TUI。

未来 message handler 也应通过 Action Gateway 执行它需要的 daemon-side action。

### 3. 完善 Handler State Namespace

每个 handler 必须有独立状态命名空间。

目标形态：

```json
{
  "handlers": {
    "task_checkout": {
      "last_handled_at": "...",
      "last_origin_turn_id": "...",
      "last_action_turn_id": "...",
      "last_error": null
    },
    "message": {
      "last_handled_at": "...",
      "last_error": null
    }
  }
}
```

daemon generic state 和 handler business state 要分开。

daemon generic state 包括：

- instance id
- main thread id
- ready
- live / pid
- daemon-origin turn ids
- top-level last fatal error

handler state 包括：

- handler 自己最近处理了什么
- handler 自己最近发起了什么 action
- handler 自己最近失败原因

### 4. 强化 Failure Isolation

一个 handler 失败，不应该拖垮 daemon service。

规则：

- 单个 handler 抛错时，daemon core 捕获错误
- 错误写入该 handler 的 state
- daemon loop 继续运行
- 其它 handler 仍然能处理同一个或后续 event
- fatal app-server / bind / runtime 错误才影响 daemon 本体健康

目标是让多个团队共用 daemon 时，互相不要因为单个 handler bug 产生连带故障。

### 5. 增强 Observability

`instance status` 和 daemon status 不应只知道 daemon live / ready。

第二步要让 status 能看见 handler 级别状态：

- registered handlers
- handler enabled / active 状态
- handler last_handled_at
- handler last_error
- handler last origin / action 信息

这样业务团队接入后，能够判断：

- daemon 是否在线
- handler 是否被加载
- handler 最近是否处理过 event
- handler 最近为什么失败

### 6. 把 Task Checkout Handler 作为标准接入样例

Task Checkout Handler 不是特殊逻辑。

它应该成为第一个标准 handler 示例：

- 使用 Handler Contract 接收 event
- 使用 Action Gateway 发起 `turn_start`
- 使用 handler namespace 写入状态
- 使用 daemon origin tracking 防循环
- 使用 handler observability 暴露最近 checkout 结果

message 团队后续接入时，应能照着 Task Checkout Handler 的形态实现自己的 handler。

### 7. 保持 launcher 边界

launcher start / clear thread 的空 rollout / bootstrap 问题仍由 launcher 原生处理。

daemon service 不负责：

- thread start
- rollout materialize
- thread bootstrap
- bootstrap 修复
- instance start / resume 流程补丁

daemon service 只在 launcher 已经准备好 main thread 后绑定并监听。

### 8. 保持现有产品行为

第二步是 service 接入面建设，不是产品行为扩展。

现有行为必须保持：

- Task Checkout Handler 仍在主线程 completed turn 后触发 STOP Task TUI
- daemon-origin turn 仍不会循环触发
- input Task TUI 不迁入 daemon
- `instance start / resume / clear / stop / status` 用户可见行为不变

## 不做的事

- 不做动态插件系统
- 不做配置化 handler registry
- 不做通用 event bus
- 不做 workflow engine
- 不实现 message 业务
- 不提前抽象未知团队需求
- 不改 Task TUI 文案
- 不改 input Task TUI 路径
- 不改 launcher bootstrap 职责
- 不让 daemon 变成 launcher start / clear 的修复层
- 不引入新的用户可见产品行为

## 测试与验收重点

第二步测试要覆盖 daemon service 的接入面，而不是只证明 Task TUI 还可用。

至少应验证：

- handler contract 可被 fake handler 使用
- daemon core 能按顺序 dispatch 多个 handler
- 一个 handler 抛错不影响其它 handler
- Action Gateway 能正确发起 `turn/start`
- Action Gateway 能记录 daemon-origin turn
- handler state 写入自己的 namespace
- daemon status 输出 handler 状态
- Task Checkout Handler 改用标准 contract / gateway / state 后行为不变
- launcher bootstrap 仍发生在 daemon bind 之前
- input Task TUI 路径不经过 daemon

## 成功画像

第二步完成后，message 团队来接需求时，daemon 团队可以明确说明：

“不要改 daemon core。你们实现一个 handler，使用 daemon service 提供的 event、action、state、origin、status 能力即可。”

具体体现：

- daemon core 仍然不含 Task TUI / message 业务语义
- Task Checkout Handler 只是标准 handler 列表中的一个
- 新增第二个 handler 不需要复制 app-server 连接和通知 loop
- 新增第二个 handler 不需要自己实现 origin tracking
- status 能看见每个 handler 的健康状态
- 单个 handler 失败不会拖垮 daemon

一句话：第二步是把 daemon 从“独立后台容器”推进到“可被多个团队稳定接入的 daemon service MVP”。
