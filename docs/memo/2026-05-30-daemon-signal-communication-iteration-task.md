# Daemon Signal 通信解耦迭代备忘

Date: 2026-05-30

## 任务一句话

本次 daemon 迭代要把当前偏 `message.available` 专用的 mailbox 通知链路，解耦为通用的跨 buddy 在线 `DaemonSignal` 通信能力；同时保留 Task TUI 现有的本地 runtime 协同链路不变，为后续 message 升级提供清晰、干净、可扩展的 daemon 支撑。

## Daemon 的定位

daemon 不是某个业务系统的后台进程。

daemon 的定位是：

```text
actor runtime guard + online actor coordination layer
```

它负责两类能力：

```text
Local Runtime Coordination
Cross-Actor Communication
```

两者最终都可能通过 `ActionGateway` 触发本地 buddy runtime，但触发来源和依赖能力不同。

## 两条能力线

### 1. Local Runtime Coordination

这是 daemon 与本地 runtime 的协同能力。

典型业务：Task TUI。

链路：

```text
local app-server notification: turn/completed
  -> instance daemon
  -> TaskCheckoutHandler
  -> ActionGateway.submit_turn
  -> same local buddy main thread
```

它依赖 daemon：

- 绑定本地 app-server 和 main thread；
- 监听本地 runtime notification；
- 识别 daemon-origin turn，避免自触发循环；
- 通过 `ActionGateway.submit_turn` 唤醒同一个 buddy；
- 记录 handler 状态和错误。

它不依赖：

- central daemon routing；
- target actor reachability；
- daemon mailbox；
- 跨 buddy signal；
- 远程 actor source。

因此，本次通信解耦不应该重构 Task TUI 的业务语义。Task TUI 可以继续保持本地 notification handler 模式。

### 2. Cross-Actor Communication

这是 daemon 支撑跨 buddy / 跨 actor 在线通信的能力。

典型业务：后续 message 升级。

链路：

```text
source business tool
  -> central daemon
  -> target daemon mailbox
  -> target signal handler
  -> ActionGateway.submit_turn
  -> target local buddy main thread
```

它依赖 daemon：

- actor presence registration；
- online contacts discovery；
- target actor reachability；
- central daemon signal routing；
- target daemon mailbox ingress；
- local signal handler dispatch；
- 目标侧 `ActionGateway` 触发。

message 使用这条线时，daemon 负责“通知和唤醒”，不负责 message 正文和 durable message 数据。

## 当前状态

已经落地：

- `actor_profile` 提供 `RuntimeActorAddress(buddy_id, instance_id)`；
- central daemon 独立进程已存在；
- daemon 启动后向 central daemon 注册 `actor_address`、endpoint、heartbeat、status；
- central daemon 支持 contacts / reachability；
- instance daemon 已有 mailbox socket；
- target daemon 收到 `message.available` 后可以通过 `MessageAvailableHandler` 调用 `ActionGateway.submit_turn`；
- Task TUI 已通过本地 `turn/completed` notification 触发 `TaskCheckoutHandler`。

当前问题：

```text
daemon mailbox 仍然理解 message.available / message_id 这类 message 业务字段。
```

这会让 daemon 的通信底座被 message 业务污染。后续如果 task、request、artifact 等业务也接入跨 buddy 通信，就会继续把业务 shape 塞进 mailbox。

## 本次迭代目标

本次只改 daemon 的 Cross-Actor Communication 线。

目标是：

```text
message-specific mailbox event
  -> generic DaemonSignalEnvelope
```

收敛后，daemon 基础层只认识跨 actor signal 信封，不认识 message 业务字段。

## 核心概念

### 1. DaemonSignalEnvelope

跨 actor 在线通信信封。

建议形态：

```json
{
  "signal_id": "sig-...",
  "type": "message.available",
  "source_actor_address": {
    "buddy_id": "pm",
    "instance_id": "inst-pm-..."
  },
  "target_actor_address": {
    "buddy_id": "dev",
    "instance_id": "inst-dev-..."
  },
  "payload": {
    "message_id": "msg-..."
  },
  "created_at": "..."
}
```

daemon 基础层只校验：

- `signal_id`；
- `type`；
- `source_actor_address`；
- `target_actor_address`；
- `payload` 是 object；
- `created_at`。

daemon 基础层不校验：

- `message_id`；
- message content；
- task/request/artifact 业务字段；
- 业务对象是否存在；
- 业务权限。

### 2. DaemonMailbox

每个 instance daemon 的在线接收入口。

职责：

```text
receive DaemonSignalEnvelope
validate target_actor_address == local actor_address
dispatch to local signal handlers
return delivery / handling result
```

不负责：

- 保存业务数据；
- 保存离线 signal；
- 校验业务 payload；
- 执行业务工具；
- 根据远端要求任意执行命令。

### 3. SignalHandler

目标 daemon 本地注册的 signal handler。

第一版不要引入重型 `Subscription` 系统。更准确的 v1 模型是：

```text
local SignalHandler subscribes to signal.type
```

接口语义：

```text
handles(signal) -> bool
handle_signal(context, state, actions, signal) -> HandlerResult
```

handler 自己负责：

- 判断是否处理某个 `signal.type`；
- 校验业务 payload；
- 决定 ignored / handled / failed；
- 必要时通过 `ActionGateway` 触发本地 buddy。

## Message 如何依赖 daemon

message 后续升级会同时依赖 daemon 的两段能力。

第一段：跨 buddy 通信。

```text
A buddy message.send
  -> message 写 durable message object
  -> central daemon 判断 B actor 是否在线
  -> central daemon 投递 DaemonSignalEnvelope(type="message.available")
  -> B daemon mailbox 收到 signal
```

第二段：目标侧 runtime 协同。

```text
B daemon mailbox
  -> MessageAvailableHandler
  -> ActionGateway.submit_turn
  -> B buddy main thread
  -> B buddy 调用 message.list 读取 durable message
```

message durable 数据仍归 message 模块：

```text
message owns durable message data
daemon owns online notification and local runtime trigger
```

message 正文不进入 daemon signal，不进入 daemon mailbox，不写入 target daemon 目录。

## Task TUI 如何依赖 daemon

Task TUI 只依赖 daemon 的本地 runtime 协同能力。

链路：

```text
local turn/completed notification
  -> TaskCheckoutHandler
  -> ActionGateway.submit_turn
  -> same buddy main thread
```

Task TUI 不需要：

- central daemon；
- mailbox；
- target actor address；
- cross-actor signal；
- message 通信能力。

因此本次 daemon 通信解耦不应该改变 Task TUI 业务行为。

## 本次改造范围

### P1. 引入通用 signal 信封

新增或调整 daemon 通信模型，使基础层接收 `DaemonSignalEnvelope`。

要求：

- 字段命名使用 `source_actor_address` / `target_actor_address`；
- 不再使用 message-specific `from_actor_address` / `to_actor_address` 作为 daemon 基础层主字段；
- `payload` 保持业务透明。

### P2. central daemon 投递通用 signal

将当前 message-specific `event.deliver` 主路径收敛为通用 signal delivery。

建议命名：

```text
signal.deliver
```

如果为了局部改动保留 `event.deliver`，其 payload 也必须是 `DaemonSignalEnvelope`，不能再是 message-specific event。

返回语义至少区分：

```text
delivery_status: delivered | target_not_online | delivery_failed | invalid_signal
handling_status: handled | ignored | failed
```

delivery 表示是否送到 target daemon；handling 表示 target daemon 本地 handler 是否处理成功。

### P3. mailbox 只认识通用 signal

`DaemonMailbox` 只做：

- protocol 校验；
- signal envelope 校验；
- target actor 校验；
- handler dispatch；
- 返回处理结果。

必须移除：

- mailbox 对 `message.available` 的专用判断；
- mailbox 对 `message_id` 的校验；
- mailbox 对 message forbidden fields 的业务判断。

### P4. MessageAvailableHandler 迁移为 SignalHandler

`MessageAvailableHandler` 成为第一个跨 actor signal handler。

它处理：

```text
signal.type == "message.available"
```

它自己校验：

```text
payload.message_id
```

然后通过：

```text
ActionGateway.submit_turn
```

提示目标 buddy 使用 `message.list` 读取消息。

### P5. daemon runtime 入口保持双线清晰

`instance_daemon` 应保持两类入口清晰：

```text
local runtime notification handlers
remote mailbox signal handlers
```

第一版不强行把 `turn/completed` 也改成 `DaemonSignal`。

Task TUI 继续作为本地 runtime notification handler。

## 非目标

本次不做：

- message durable object 改造；
- message.contacts / message.send / message.list 完整升级；
- Task TUI 业务重构；
- app-server notification 全部 signal 化；
- 离线 signal 持久队列；
- delayed signal scheduler；
- workflow engine；
- plugin system；
- remote tool execution；
- 动态 subscription 注册/取消；
- broadcast 主路径。

## 影响面判断

### message 当前业务

当前 message 主路径还没有依赖 daemon signal delivery，因此本次 daemon 解耦不应影响当前 `message.send/list` 行为。

会影响的是后续 message 升级要使用的 daemon 预备接口，例如：

```text
deliver_message_available
```

应收敛为更通用的：

```text
deliver_signal
```

### Task TUI

Task TUI 会受到测试和接口命名层面的轻微影响，但业务行为不应变化。

必须保持：

- `turn/completed` 仍触发 STOP Task TUI；
- 非 main thread notification 仍忽略；
- 非 completed status 仍忽略；
- daemon-origin turn 仍忽略；
- `ActionGateway.submit_turn` 行为不变；
- handler failure 仍记录错误；
- daemon 遇到单个 handler failure 后仍继续运行。

## 验收标准

### 通信边界

- daemon mailbox 基础层不出现 message-specific `message_id` 校验；
- daemon mailbox 基础层不出现 `message.available` 专用 shape；
- daemon signal envelope 不包含 message content；
- daemon signal envelope 不包含 `from_buddy` / `to_buddy`；
- daemon 基础层只消费 `RuntimeActorAddress` payload，不解析 instance JSON。

### message.available handler

- `MessageAvailableHandler` 只在 handler 内理解 `signal.type == "message.available"`；
- `payload.message_id` 校验在 handler 内完成；
- handler 通过 `ActionGateway.submit_turn` 触发目标 buddy；
- handler 不读取 message 正文。

### Task TUI

- Task TUI 本地 runtime notification 行为保持不变；
- Task TUI 不依赖 central daemon / mailbox / signal delivery；
- daemon-origin turn 防循环逻辑保持有效。

### delivery result

- target 不在线时返回 `target_not_online`；
- mailbox 无法连接时返回 `delivery_failed`；
- signal payload 不合法时返回 `invalid_signal`；
- target daemon 收到但没有 handler 处理时能表达 `handling_status = ignored`；
- handler 抛错或返回 failed 时能表达 `handling_status = failed`。

## 后续 message 升级的接入点

daemon 这次完成后，message 升级应只消费这些 daemon 能力：

```text
contacts.list
actor.check_reachability
signal.deliver
```

message.send 后续链路：

```text
message.send(target_actor_address, content)
  -> check reachability
  -> create durable message
  -> deliver signal:
       type = "message.available"
       payload = { "message_id": "msg-..." }
  -> return message result + notification status
```

target daemon 链路：

```text
mailbox receives DaemonSignalEnvelope
  -> dispatch MessageAvailableHandler
  -> ActionGateway.submit_turn
  -> target buddy uses message.list
```

## 收敛结论

本次任务不是“给 message 做通知”，也不是“做通用事件平台”。

本次任务是：

```text
daemon cross-actor signal delivery decoupling
```

完成后，daemon 的职责边界应清晰稳定：

```text
actor_profile owns runtime actor address
daemon owns presence / reachability / online signal delivery / local action trigger
business modules own durable data and payload semantics
```

一句话：

```text
message 使用 daemon 的跨 buddy 在线 signal 通信，并在目标侧使用 daemon 的 runtime 协同；Task TUI 只使用 daemon 的本地 runtime 协同。
```
