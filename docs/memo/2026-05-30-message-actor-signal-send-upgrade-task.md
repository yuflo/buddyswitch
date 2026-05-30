# Message Actor Signal Send 升级任务备忘

Date: 2026-05-30

## 任务一句话

在 daemon signal envelope 已完成后，把 `message` 从旧的 buddy 级 `to_buddy` inbox，升级为基于 `RuntimeActorAddress`、central daemon presence/reachability、`signal.deliver` 的明确实例级发送能力。

核心业务语义：

```text
message.send 成功 =
  durable message 已创建
  + message.available signal 已投递到目标 daemon
  + 目标 buddy 会被唤醒读取 message
```

否则就是发送失败。

## 本备忘修正的旧结论

旧 message/daemon 备忘中曾写过：

```text
signal delivery failed after durable message creation
  -> message 保留
  -> response 返回 delivery_failed
```

这个结论已经废弃。

原因是对 buddy 来说只有一个业务动作：`message.send`。如果工具返回失败但仍留下可读 message，会破坏业务正确性，让 Codex-cli 不知道该不该重试、是否会造成重复、目标是否已经能读到消息。

新的结论：

```text
message.send 是业务原子动作。
signal 失败时，message 模块必须清理刚创建的 message。
清理失败时，必须返回不确定状态，禁止普通重试。
```

## 当前已完成的 daemon 基础

daemon 侧已经提供 message 升级所需的通信底座：

- `RuntimeActorAddress(buddy_id, instance_id)` 已存在；
- central daemon 维护在线 actor registry；
- central daemon 支持 `contacts.list`；
- central daemon 支持 `actor.check_reachability`；
- central daemon 主投递 API 是 `signal.deliver`；
- instance daemon 维护 mailbox socket；
- mailbox 基础层只理解通用 signal envelope；
- `MessageAvailableHandler` 只在 handler 层理解 `message.available` 和 `payload.message_id`；
- target daemon 可以通过本地 `ActionGateway.submit_turn` 唤醒目标 buddy。

因此，下一步不是继续补 daemon，而是让 `message` 成为 daemon actor network 的第一条真实业务消费者。

## 领域边界

### actor_profile

只负责唯一 actor 身份语言：

```text
RuntimeActorAddress(buddy_id, instance_id)
```

不负责：

- presence；
- contacts；
- reachability；
- daemon endpoint；
- delivery status；
- message 业务状态。

### central daemon

负责在线通信基础能力：

- actor registration；
- online contacts discovery；
- target reachability；
- `signal.deliver` 路由；
- delivery / handling result 返回。

daemon 不负责：

- message 正文；
- message durable store；
- message send 是否提交或回滚；
- message cleanup。

### target daemon

负责本地 mailbox 和 signal handler：

- 接收 `DaemonSignalEnvelope`；
- 校验 target actor 是本地 actor；
- 分发给 `MessageAvailableHandler`；
- 通过 `ActionGateway` 唤醒目标 buddy。

### message

负责完整业务语义：

- `message.contacts`；
- `message.send`；
- `message.list`；
- durable message 数据；
- send 原子提交；
- signal 失败后的 cleanup；
- tool response 和 context cues。

## Tool surface 目标形态

### message.contacts

发现能力，不是强制 SOP。

输入：

```json
{
  "buddy": "dev"
}
```

`buddy` 是可选 filter，不是发送目标解析。

返回在线可联系 actor：

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
  ],
  "count": 1
}
```

`message.contacts` 通过 `context.daemon.list_contacts(...)` 消费 central daemon，不自己扫 instance JSON，不自己维护 presence。

### message.send

主路径输入：

```json
{
  "target_actor_address": {
    "buddy_id": "dev",
    "instance_id": "inst-dev-..."
  },
  "content": "Please inspect the prototype.",
  "reply_to": "msg-..."
}
```

规则：

- 使用 `RuntimeActorAddress.from_payload()` 校验 `target_actor_address`；
- 不做 `to_buddy -> instance` 模糊解析；
- 不在 message 模块里扫描 target instance JSON；
- 不允许发送给同一个 actor；
- 是否允许同 buddy 不同 instance 互发，需要产品层明确后再开放，默认先拒绝同 buddy 自发；
- 发送前调用 `context.daemon.check_reachability(target_actor_address=...)`；
- 只有 reachability 为 `online` 才创建 message；
- 创建 message 后立即投递 `message.available` signal；
- signal delivered 后才返回 `ok: true`。

### message.list

读取当前 actor 的 inbox。

规则：

- 只返回 `to_actor_address == context.actor_address` 的成功 message；
- `buddy` filter 匹配 `from_actor_address.buddy_id`；
- 不返回 failed / pending / cleanup-only message；
- 不依赖 daemon presence。

## Message durable data

message 数据应升级为 actor-address 维度：

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
  "content": "Please inspect the prototype.",
  "reply_to": null,
  "created_at": "2026-05-30T00:00:00Z"
}
```

旧 `from_buddy` / `to_buddy` 不应继续作为主存储字段。

如果实现阶段需要兼容旧测试 fixture，应优先迁移 fixture 和上下文读取逻辑，不要保留长期双轨 message model。

## Signal shape

message 只请求 daemon 投递 reference-only signal。

信封由 runtime daemon access 构造：

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
  "created_at": "2026-05-30T00:00:00Z"
}
```

禁止在 signal 中携带：

- message body；
- full message object；
- `from_buddy`；
- `to_buddy`；
- target instance file path；
- daemon endpoint details。

## send 主链路

```text
message.send(target_actor_address, content)
  -> validate payload
  -> normalize target_actor_address through RuntimeActorAddress
  -> reject self-send
  -> context.daemon.check_reachability(target_actor_address)
  -> if not online: reject, no message created
  -> create durable message
  -> context.daemon.deliver_message_available(message_id, target_actor_address)
  -> if delivered: return success
  -> if delivery failed: cleanup created message
  -> if cleanup succeeded: return retryable failure, state_changed false
  -> if cleanup failed: return indeterminate failure, state_changed true, retryable false
```

target daemon 收到 signal 后：

```text
signal.deliver
  -> target daemon mailbox
  -> MessageAvailableHandler
  -> validate payload.message_id
  -> ActionGateway.submit_turn
  -> target buddy sees message available prompt
  -> target buddy may call message.list
```

handler prompt 继续保持 reference-only：

```text
[MESSAGE AVAILABLE]
message_id: msg-...
Use message.list to read the message when ready.
```

## Failure semantics

### invalid_target_actor_address

输入地址不满足 `RuntimeActorAddress` 契约。

结果：

- `ok: false`
- 不创建 message
- `state_changed: false`
- `durability: none`
- `retryable: true`
- `correctable_fields: ["target_actor_address"]`

### target_not_online

daemon reachability 返回：

- `registered_offline`
- `never_registered`

结果：

- `ok: false`
- 不创建 message
- `state_changed: false`
- `durability: none`
- `retryable: true`
- response 携带 `reachability_status`
- next guidance 指向 `message.contacts` 或稍后重试

### delivery_failed_cleanup_succeeded

message 已创建，但 `message.available` signal 投递失败，随后 message cleanup 成功。

结果：

- `ok: false`
- 已清理，不留下可读 message
- `state_changed: false`
- `durability: none`
- `delivery_status: delivery_failed`
- `cleanup_status: cleaned`
- `retryable: true`

这类失败可以普通重试，因为上一次没有留下成功 message。

### delivery_failed_cleanup_failed

message 已创建，signal 投递失败，cleanup 也失败。

结果：

- `ok: false`
- 状态不确定
- `state_changed: true`
- `durability: uncertain`
- `message_id` 必须返回
- `delivery_status: delivery_failed`
- `cleanup_status: failed`
- `retryable: false`

这类失败必须明确告诉 Codex-cli：

```text
Do not blindly retry.
Inspect current state through context.get or message.list before deciding.
```

## Tool response contract

`message.send` 的反馈必须遵守 env.tool 现有规范和 `docs/bitter` 的经验：

- response 要说明真实 state impact；
- 不能只靠 `ok`；
- rejected call 必须有 `permission_boundary`、`why_blocked`、`impact`、`retryable`、`retry_guidance`；
- write success 必须有 `state_changes` / `created_ids`；
- 可修正输入错误必须给 `correctable_fields`；
- next guidance 必须让 Codex-cli 能持续决策；
- 不确定状态不能被伪装成普通 retryable 失败。

成功响应建议：

```json
{
  "ok": true,
  "tool": "message",
  "action": "message.send",
  "state_changed": true,
  "durability": "durable",
  "message_id": "msg-...",
  "delivery_status": "delivered",
  "state_changes": [
    {
      "object_type": "message",
      "change": "sent",
      "message_id": "msg-..."
    }
  ],
  "created_ids": ["msg-..."],
  "allowed_next_actions": [
    "Use message.list to inspect delivered inbox messages when needed."
  ]
}
```

delivery failed but cleanup succeeded：

```json
{
  "ok": false,
  "tool": "message",
  "action": "message.send",
  "error": {
    "code": "E_MESSAGE_DELIVERY_FAILED",
    "message": "message.available signal delivery failed"
  },
  "permission_boundary": "message.delivery",
  "why_blocked": "Target daemon was online, but message.available signal delivery failed.",
  "impact": "No readable message was created; the failed send was cleaned up.",
  "state_changed": false,
  "durability": "none",
  "delivery_status": "delivery_failed",
  "cleanup_status": "cleaned",
  "retryable": true,
  "retry_guidance": "Retry message.send after rechecking message.contacts or target reachability.",
  "allowed_next_actions": [
    "Use message.contacts to refresh the target actor address.",
    "Retry message.send with the same target_actor_address if it is still online."
  ]
}
```

delivery failed and cleanup failed：

```json
{
  "ok": false,
  "tool": "message",
  "action": "message.send",
  "error": {
    "code": "E_MESSAGE_SEND_INDETERMINATE",
    "message": "signal delivery failed and message cleanup failed"
  },
  "permission_boundary": "message.delivery_cleanup",
  "why_blocked": "Signal delivery failed and cleanup of the created message also failed.",
  "impact": "A message may still exist without target notification.",
  "state_changed": true,
  "durability": "uncertain",
  "message_id": "msg-...",
  "delivery_status": "delivery_failed",
  "cleanup_status": "failed",
  "retryable": false,
  "retry_guidance": "Do not blindly retry. Use context.get or message.list to inspect current state before deciding.",
  "allowed_next_actions": [
    "Use context.get to inspect message recovery warnings.",
    "Use message.list from the target actor if available to check whether the message is visible."
  ]
}
```

## Context requirements

`context.summarize` / `context.get` must help Codex-cli decide the next action without prompt memory.

At minimum, context should expose:

- current actor address；
- current inbox cues based on actor-address message rows；
- message tool affordances with `contacts`, `send`, and `list`；
- online contact cues or a clear pointer to `message.contacts`；
- recent indeterminate message send warnings if any exist；
- source of truth text that says message data is read through `message.list` and target discovery is through `message.contacts`。

Context must not pretend that daemon delivery status is message data. It should present daemon status as decision context only.

## Current code facts to replace

Current message implementation still reflects old model:

- `scripts/env/tools/message/tool.py` exposes `send` with `to_buddy`；
- `scripts/env/domain/messages.py` validates `to_buddy`；
- `scripts/env/repos/messages.py` stores `from_buddy` / `to_buddy`；
- `scripts/env/tools/message/_impl.py` creates durable message and returns without daemon delivery；
- context message cues filter by `to_buddy == active_buddy`。

These are the main replacement points.

## Implementation risks to handle explicitly

### 1. Cleanup mechanics

The product contract is fixed:

```text
message.list cannot show a failed send.
```

Implementation may choose either:

- create visible message, then delete on delivery failure；
- create hidden/pending message, then commit visible only after delivery success。

The second shape is cleaner if it stays small, because failed delivery never creates visible inbox state. Do not introduce a broad workflow engine or message status system just to support it.

### 2. Indeterminate response contract

Existing rejection tests often assume rejected calls have:

```text
state_changed: false
durability: none
```

`delivery_failed_cleanup_failed` is a special failed write with `state_changed: true` and `durability: uncertain`。Implementation must add focused tests for this contract and adjust generic response-contract expectations only where necessary.

Do not hide indeterminate writes by returning `state_changed: false`。

### 3. Retry guidance

Ordinary delivery failure with cleanup succeeded may be retryable.

Indeterminate cleanup failure is not ordinary retryable. Response must prevent Codex-cli from blindly repeating `message.send` and creating duplicates.

### 4. Do not reintroduce fuzzy routing

`message.send` must not:

- accept `to_buddy` as main-path target；
- choose among multiple online instances；
- scan `instances/**/instance.json`；
- parse daemon registry files directly；
- inspect mailbox endpoint details。

Target selection happens before send through `message.contacts` and user/Codex decision.

## Non-goals

- No generic event bus；
- no workflow engine；
- no plugin system；
- no offline message queue in daemon；
- no daemon-owned message store；
- no multi-instance target selection policy；
- no broad compatibility layer for old `to_buddy` send；
- no message body in daemon signal。

## Verification expectations

Focused tests should prove:

- `message.contacts` returns daemon contacts with actor addresses；
- `message.send` rejects invalid `target_actor_address` without mutation；
- `message.send` rejects offline target without mutation；
- `message.send` creates durable message and returns success only when signal delivery succeeds；
- `message.send` cleans up created message when signal delivery fails；
- cleanup failure returns indeterminate response with `retryable: false`；
- `message.list` reads actor-address inbox only；
- context cues reflect actor-address messages and recovery warnings；
- message code does not parse target instance JSON or daemon registry files。

Suggested focused commands:

```bash
python3 -m pytest tests/test_message_env_tool.py -q
python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_response_contract.py -q
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_host_decision_surface_product_mode.py -q
python3 -m pytest tests/test_runtime_actor_profile.py tests/test_daemon_mailbox.py tests/test_message_available_handler.py -q
rg -n "to_buddy|from_buddy|target_actor_address|message\\.available|delivery_status|cleanup_status|durability.*uncertain|json\\.loads|glob\\(.*instances" scripts/env tools/launcher tests
```

Broad verification should follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`:

- run focused tests first；
- avoid scaling service-starting tests before lifecycle cleanup is proven；
- check for residual daemon processes after daemon-related verification。

## Audit conclusion

No product-level blocker remains.

The key semantic decision is now fixed:

```text
message.send success is atomic from the buddy perspective.
```

The implementation must be strict about response truthfulness. The main risk is not daemon capability anymore; it is letting message responses become ambiguous after partial failure. That risk is handled by explicit cleanup semantics, indeterminate failure feedback, and context cues for recovery decisions.
