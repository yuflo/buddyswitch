# Message / Daemon 通讯升级边界备忘

Date: 2026-05-29

## 任务一句话

在 `actor_profile` 已提供 `RuntimeActorAddress(buddy_id, instance_id)` 的基础上，升级 message 与 daemon 的协作链路：message 负责联系人发现、显式实例级发送和 durable message data，daemon 负责 presence、可达性判断、在线通知投递、mailbox 消费和目标侧 action 触发。

## 背景

message 系统后续不只是写入消息对象，还要在目标 buddy instance 在线时，通过 daemon 主动触发目标侧读取消息。

这条链路要求系统使用同一套 runtime actor address 语言：

```text
RuntimeActorAddress(buddy_id, instance_id)
```

该身份语言由 `actor_profile` 提供。message 和 daemon 只消费它，不重新解释 buddy / instance 身份。

核心边界：

```text
actor_profile = actor_address
message = contacts / send / list + durable message data
central daemon = presence + reachability + delivery
target daemon = mailbox + event consumption + action trigger
```

## Message 运作链路

### 1. 联系人发现

`message.contacts` 是发现能力，不是强制 SOP。

buddy 如果已经从 context、上一轮工具反馈或用户输入中得到明确 `target_actor_address`，可以直接调用 `message.send`。

当 buddy 不确定当前谁可联系时，可以调用：

```json
{
  "buddy": "dev"
}
```

`buddy` 是联系人查询 filter，不是发送目标解析。

返回应表达当前可联系的在线 actor：

```json
{
  "contacts": [
    {
      "buddy_id": "dev",
      "actor_address": {
        "buddy_id": "dev",
        "instance_id": "inst-dev-..."
      },
      "contact_status": "online",
      "sendable": true,
      "last_seen_at": "..."
    }
  ]
}
```

工具描述和反馈应让 buddy 能自己决策是否查询联系人，不要把“先 contacts 再 send”写成固定流程。

### 2. 显式发送

`message.send` 的 v2 目标是明确的 instance 级地址：

```json
{
  "target_actor_address": {
    "buddy_id": "dev",
    "instance_id": "inst-dev-..."
  },
  "content": "..."
}
```

`message.send` 不做模糊的 `to_buddy -> instance` 解析。要找可发送目标，使用 `message.contacts`。

发送链路：

```text
message.send(target_actor_address, content)
  -> 校验 payload
  -> 向 daemon 确认 target_actor_address 当前 online / sendable
  -> 不在线则拒绝，不创建 message
  -> 在线则创建 durable message
  -> 投递 message.available event
  -> target daemon 消费 event
  -> target daemon 触发目标 buddy 读取消息
```

发送失败反馈应保持收窄：

```text
invalid_target_actor_address
target_not_online
delivery_failed
```

其中 `target_not_online` 可以附带 daemon 细节：

```text
registered_offline
never_registered
```

这些细节用于帮助 buddy 决策下一步，例如重新查询 `message.contacts` 或等待目标上线。

### 3. Message 数据形态

message data 应升级到 actor-address 维度：

```json
{
  "id": "msg-...",
  "from_actor_address": {
    "buddy_id": "pm",
    "instance_id": "inst-pm-..."
  },
  "to_actor_address": {
    "buddy_id": "dev",
    "instance_id": "inst-dev-..."
  },
  "content": "...",
  "created_at": "..."
}
```

`message.list` 应读取当前 actor address 的 inbox，也就是 `to_actor_address` 等于当前 runtime actor address 的消息。

### 4. 在线通知事件

message 创建成功后，请 daemon 投递 reference-only event：

```json
{
  "type": "message.available",
  "message_id": "msg-...",
  "from_actor_address": {
    "buddy_id": "pm",
    "instance_id": "inst-pm-..."
  },
  "to_actor_address": {
    "buddy_id": "dev",
    "instance_id": "inst-dev-..."
  }
}
```

事件只带引用，不带 message 正文。event 是在线通知，不是 message object transport。

## Daemon 支持能力

daemon 不负责 identity，也不解释 buddy 身份。daemon 消费 `actor_profile` 提供的 `RuntimeActorAddress`，并提供运行时通讯能力。

### 1. Presence Registration

每个 daemon 启动后注册自己的在线记录：

```json
{
  "actor_address": {
    "buddy_id": "dev",
    "instance_id": "inst-dev-..."
  },
  "endpoint": "...",
  "heartbeat": "...",
  "status": "online",
  "last_seen_at": "..."
}
```

`endpoint`、`heartbeat`、`status`、`last_seen_at` 属于 daemon / presence，不属于 `actor_profile`。

### 2. Online Contact Discovery

central daemon 为 `message.contacts` 提供在线联系人列表。

能力要求：

- 支持按 `buddy_id` filter；
- 返回明确 `actor_address`；
- 返回 `contact_status`、`sendable`、`last_seen_at` 等可决策字段；
- 不把查询结果解释为发送 SOP。

### 3. Target Reachability Check

central daemon 为 `message.send` 判断明确 `target_actor_address` 是否当前可发送。

状态至少包括：

```text
online
registered_offline
never_registered
```

message 可将非 online 状态统一反馈为 `target_not_online`，并把具体 daemon 状态放入结构化字段。

### 4. Reference-only Delivery

daemon 投递 `message.available` event，只携带 `message_id` 和 actor address 引用，不传 message 正文。

投递失败发生在 message 创建之后时，`message.send` 返回 `delivery_failed`，但 message object 已经 durable 创建。

### 5. Per-daemon Mailbox

每个 target daemon 维护自己的 mailbox，用于接收 central daemon 投递的 events。

mailbox 是 daemon 运行时通讯能力，不是 message object store。

### 6. Mailbox Consumer

target daemon 消费 `message.available`，把事件转成订阅或调度动作。

第一版只需要支撑 message 可用通知，不引入通用 workflow engine、event bus 或插件系统。

### 7. Target-side Action Trigger

到触发时机后，target daemon 通过自己的 `ActionGateway` 触发目标 buddy 读取消息，例如引导或执行 `message.list`。

message 模块不能直接控制目标 buddy 线程。

## 非目标

- 不让 `message.send` 做 `to_buddy -> instance` 模糊解析；
- 不把 `message.contacts` 写成强制 SOP；
- 不让 daemon 定义第二套 buddy identity；
- 不把 endpoint / heartbeat / presence 塞进 `actor_profile`；
- 不在 event 中传输 message 正文；
- 不在第一版实现多实例选择策略、通用 event bus、workflow engine 或插件化通讯系统。

## 完成画像

完成后，buddy 可以从工具语义和反馈中自行决策：

- 不确定联系人时，使用 `message.contacts` 查询；
- 已有明确 `target_actor_address` 时，直接 `message.send`；
- 目标不在线时，收到清晰的 `target_not_online` 与 daemon 状态细节；
- 消息成功创建后，目标 daemon 收到 reference-only event，并由目标 daemon 触发目标 buddy 读取消息。

一句话：

```text
message 负责明确实例级通信语义和 durable 数据，daemon 负责在线通讯能力，actor_profile 负责唯一 actor address 语言。
```
