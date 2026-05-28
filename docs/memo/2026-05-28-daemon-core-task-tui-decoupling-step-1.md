# Daemon Core / Task TUI 解耦第一步任务备忘

## 任务一句话

把 daemon 从 Task TUI 第一版实现里剥离出来，形成独立的实例级后台容器；但不扩展新能力、不改变现有行为。

## 核心目标

第一步完成后，daemon 的身份要从：

`Task TUI 的后台实现`

变成：

`可挂载 Task Checkout Handler 的 daemon core`

Task TUI 仍然可用，但它只是 daemon 当前的第一个 handler。

## 要做的事

### 1. 拆出 daemon core

保留 daemon 的基础运行职责：

- `start / stop / status / run`
- app-server 连接
- main thread bind
- notification loop
- daemon 基础状态：live、ready、last_error、pid、log、state file

daemon core 只表达后台服务能力，不包含 Task TUI 的业务语义。

### 2. 拆出 Task Checkout Handler

把现有 STOP Task TUI 业务从 daemon core 中移出去，集中到独立 handler：

- 识别 main thread 的 `turn/completed`
- 忽略非 completed / 非 main thread / daemon-origin turn
- 读取 task snapshot
- 渲染 STOP Task TUI
- 调用 app-server `turn/start`
- 记录 checkout turn id 和 checkout error

### 3. 建立显式 handler 调用

daemon core 收到 notification 后，只做：

- 遍历当前 handler 列表
- 调用 handler
- 捕获 handler 错误
- 记录错误

daemon core 不写 Task TUI 业务判断。

### 4. 保持 launcher 边界

launcher start thread 的空 rollout / bootstrap 问题仍由 launcher 原生处理。

daemon 不负责：

- thread start
- rollout materialize
- bootstrap 修复
- instance start 流程补丁

daemon 只在 launcher 已经完成 thread bootstrap 后启动并绑定主线程。

### 5. 保持现有行为不变

- `instance start` 后 daemon 仍启动
- 主线程 turn completed 后仍触发一次 STOP Task TUI
- daemon-origin turn 仍不循环触发
- `instance stop` 仍停止 daemon
- `instance status` 仍能看到 daemon 状态

## 不做的事

- 不做 message handler
- 不做插件系统
- 不做动态 handler 注册
- 不做通用 event bus
- 不改 Task TUI 文案
- 不改 launcher bootstrap 职责
- 不把 daemon 变成 start/resume 的修复层
- 不引入新产品行为

## 成功画像

第一步完成后：

- daemon core 不再直接 import `task_tui` / `task_management`
- 打开 daemon core，只看到后台服务基础能力
- Task TUI 逻辑集中在 `Task Checkout Handler`
- 移除 Task Checkout Handler 后，daemon 仍能启动、连接、监听、报告状态
- 未来 message 团队能看到明确扩展点：新增 handler，而不是修改 daemon 主循环

一句话：第一步是拆归属、稳边界、保行为。
