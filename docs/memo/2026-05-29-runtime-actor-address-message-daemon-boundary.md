# Runtime Actor Address 与 Message/Daemon 边界对齐任务备忘

Date: 2026-05-29

## 任务一句话

在 `actor_profile` 中补齐统一的 `RuntimeActorAddress(buddy_id, instance_id)` 契约，让 daemon registry、message routing、runtime presence 使用同一套 buddy runtime actor 身份语言，同时保持 presence、routing、delivery、message data 各自归属清晰。

## 背景

当前 `actor_profile` 已经开始承担运行时 actor 身份归一化职责：

- 从本地可信 instance record 解析 `instance_id`；
- 解析当前运行实例的 `active_buddy`；
- 为 role auth 生成 `AuthSubject`；
- 为 env.tool 调用链提供统一的本地运行时身份输入。

下一步 message 系统会从“只写 durable message object”升级为：

```text
message.send(to_buddy)
  -> 写入 durable message object
  -> 查询 central daemon presence
  -> 找到目标 buddy 当前 online actor_address
  -> 投递 online notification event 到目标 daemon
  -> 目标 daemon 消费事件并触发 message.list / subscription action
```

这条链路要求系统能统一回答：

```text
这个 runtime actor 是哪个 buddy 的哪个 instance？
```

这个答案不能由 daemon、message 各自读取 JSON 后重新拼装，否则会出现第二套 buddy/instance 身份解释规则。

## 当前共识

BuddySwitch 保持 only one buddy identity/address language：

```text
RuntimeActorAddress(buddy_id, instance_id)
```

但所有围绕 buddy 的运行时事实不都属于 identity。

| 领域 | Owner | 说明 |
| --- | --- | --- |
| runtime actor identity/address | `actor_profile` | 定义这个 runtime actor 是谁 |
| presence + routing | central daemon / daemon registry | 维护谁在线、如何选择目标 |
| online notification delivery | daemon delivery | 负责在线事件投递 |
| durable message data | message module | 负责消息数据本体 |

核心边界：

```text
actor_profile 定义 actor_address 这套唯一身份/address 语言；
central daemon 基于 actor_address 维护在线事实和路由；
message 不依赖在线状态保证数据写入；
daemon notification 只是在线触发信号。
```

## actor_profile 最小交付

### 1. 新增 RuntimeActorAddress

新增稳定数据结构：

```python
RuntimeActorAddress(
    buddy_id: str,
    instance_id: str,
)
```

它表示：

```text
某个 buddy 的某个具体 runtime instance 的可路由身份
```

### 2. RuntimeActorProfile 暴露 actor_address

在现有 runtime profile 上新增：

```python
RuntimeActorProfile.actor_address
```

兼容关系必须稳定成立：

```python
profile.active_buddy == profile.actor_address.buddy_id
profile.instance_id == profile.actor_address.instance_id
```

本阶段暂不强制 rename `active_buddy`。后续 tool-facing 语义可以逐步从 `active_buddy` 收敛到 `actor_address.buddy_id`。

### 3. 提供稳定序列化/反序列化入口

daemon registry 写入、读取、message routing 消费时，不应该自己解释 `{buddy_id, instance_id}`。

建议提供：

```python
address.to_payload()
RuntimeActorAddress.from_payload(payload)
```

目标是让跨模块 JSON 传递仍然复用 `actor_profile` 的解析与校验规则，而不是在 daemon/message 中复制一份规则。

## ID 合法性规则

### buddy_id

复用 manifest 中的安全 buddy id 规则：

```text
^[a-z][a-z0-9-]*$
```

### instance_id

建议统一为当前 launcher 语义的收紧版本：

```text
^inst-[a-z][a-z0-9-]*-[0-9a-f]{12}$
```

语义：

```text
inst-<buddy_id>-<random_hex_12>
```

理由：

- 与现有 launcher 生成形态一致；
- buddy 信息可读；
- 随机后缀足够避免同 buddy 多实例冲突；
- 禁止大写、点、下划线，减少跨 JSON、路径、日志、routing key 的歧义；
- 校验逻辑简单，daemon/message 不需要各自发明规则。

如果旧测试 fixture 使用 `inst-dev-example` 这类非最终形态，应优先更新 fixture 到产品规则，而不是为了测试放宽运行时契约。

## actor_profile 不负责

`actor_profile` 不应该扩大为 runtime/presence 模块。

明确不负责：

- supported buddy list；
- online presence；
- buddy_id 到 online actor 的选择；
- daemon endpoint；
- heartbeat；
- health check；
- routing policy；
- delivery status；
- message 业务规则；
- durable message 存储；
- daemon event 投递。

这些分别属于 manifest/runtime 配置、central daemon、daemon delivery、message module。

## daemon / presence 责任

central daemon registry 消费 `actor_profile` 输出的 `actor_address`，并维护在线事实：

```json
{
  "actor_address": {
    "buddy_id": "dev",
    "instance_id": "inst-dev-1a2b3c4d5e6f"
  },
  "endpoint": "...",
  "heartbeat": "...",
  "status": "online",
  "last_seen_at": "..."
}
```

`endpoint`、`heartbeat`、`status`、`last_seen_at` 都不属于 `actor_profile`。

daemon 可以按 `buddy_id` 建在线索引，但目标选择属于 presence/routing，不属于 identity。

## v1 cardinality 决策

当前明确：

```text
一个 buddy runtime instance 对应一个 daemon instance。
```

但 `actor_profile` 不承诺：

```text
buddy_id -> actor_address 是全局唯一映射
```

因为“某个 buddy 当前有哪些在线实例”“重复在线时怎么选”是 presence/daemon registry 的策略。

message direct notification v1 的建议策略：

| online actor_address 数量 | notification_status |
| --- | --- |
| 0 | `skipped_offline` |
| 1 | `delivered` 或 delivery attempted |
| >1 | `ambiguous_online_actor` |

`ambiguous_online_actor` 只影响 notification status，不回滚 durable message。

## message 语义

message data 和 daemon notification 必须分离。

规则：

- `message.send` 先 durable 写入 message object；
- 目标 buddy 离线时，message 创建仍成功；
- daemon notification 是附加在线触发信号；
- 在线投递失败不回滚已创建 message；
- response 可返回 `notification_status`；
- daemon event 只携带引用，不承载 message 正文。

建议 event payload：

```json
{
  "type": "message.available",
  "message_id": "msg-...",
  "from_actor_address": {
    "buddy_id": "pm",
    "instance_id": "inst-pm-1a2b3c4d5e6f"
  },
  "to_actor_address": {
    "buddy_id": "dev",
    "instance_id": "inst-dev-7a8b9c0d1e2f"
  }
}
```

原则固定：

```text
event 是 notification，不是 message object transport。
```

## 验收标准

### actor_profile tests

- 新增 `RuntimeActorAddress`；
- `RuntimeActorProfile.actor_address` 稳定暴露 `{buddy_id, instance_id}`；
- `profile.active_buddy == profile.actor_address.buddy_id`；
- `profile.instance_id == profile.actor_address.instance_id`；
- `RuntimeActorAddress.to_payload()` 输出稳定 JSON projection；
- `RuntimeActorAddress.from_payload(payload)` 复用同一套校验；
- 空 buddy / instance 被拒绝；
- 非法 buddy id 被拒绝；
- 非法 instance id 被拒绝；
- `actor_profile` 不包含 endpoint / heartbeat / presence / status 字段。

### daemon tests

- daemon registration 使用 `actor_profile` 生成的 `actor_address`；
- registry 身份字段统一命名为 `actor_address`；
- endpoint / heartbeat / status / last_seen_at 保持在 registry 层；
- daemon 不新增 `daemon_buddy`、`target_buddy_instance` 等第二套身份模型；
- presence 查询可以按 buddy_id 找到 online actor_address；
- v1 多 online actor 返回 `ambiguous_online_actor`，不在 actor_profile 中做选择。

### message tests

- offline 时仍成功创建 durable message；
- online delivery 只影响 `notification_status`；
- 投递失败不回滚 message object；
- message routing 不直接解析目标 instance JSON；
- message 只消费 central daemon 返回的 `actor_address`；
- daemon event 只带 `message_id` 与 actor address 引用，不传 message 正文。

## 非目标

- 不把 presence registry 塞进 `actor_profile`；
- 不让 `actor_profile` 查询目标 buddy 是否在线；
- 不在本阶段重命名或删除 `active_buddy`；
- 不把 message delivery 成功作为 message 创建成功的前置条件；
- 不实现多 online actor 的选择策略；
- 不引入新的泛化 routing engine、permission framework、event bus 或插件化身份系统。

## 实施顺序建议

1. 在 `actor_profile` 内补 `RuntimeActorAddress`、payload projection、校验和 profile projection。
2. 更新 daemon registration 使用 `profile.actor_address.to_payload()`。
3. 让 central daemon registry 统一使用 `actor_address` 字段承载身份。
4. message routing 只消费 daemon presence 返回的 `actor_address`，不解析 instance record。
5. message.send 保持 durable write 优先，notification status 作为附加结果返回。

## 完成定义

本任务完成时应满足：

- 运行时身份/address 只有一套规范语言；
- daemon/message 不再各自解释 buddy_id + instance_id；
- presence、routing、delivery、message data 没有被塞进 `actor_profile`；
- 旧的 `active_buddy` 兼容关系仍然成立；
- 相关 actor_profile、daemon、message 测试覆盖上述边界。
