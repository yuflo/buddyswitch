# Message 产品体验无残留修复任务备忘

Date: 2026-05-30

## 任务一句话

把 `message` 从“底层大体能跑，但 host 需要猜字段、猜方向、猜入口状态”的协作体验，修成一条无残留、无历史过渡、可一次性验证的产品主路径：

```text
message.contacts
  -> 拿到真实可发送 target_actor_address
  -> message.send 一次成功
  -> target daemon 唤醒目标 buddy
  -> target buddy 用 message.list 读取 inbox
  -> 任一 buddy 可用明确的 conversation/history 动作查看双向上下文
  -> daemon status 能真实显示普通 handler 与 mailbox handler
```

本任务不是给旧模型补兼容层，也不是用更长 prompt 教 agent 避坑。

本任务要把残留问题修在它们各自拥有的层：

- tool schema 和 response 文案；
- message domain rule；
- message read model；
- shared message skill；
- runtime entrypoint permission；
- daemon status observability；
- focused tests 和 service lifecycle verification。

## 背景证据

这次 PM 和 market 的真实运行日志说明：消息 durable data 和 signal 主链路不是完全坏的，但产品表面有多处残留不一致。

已经观察到的事实：

- PM 第一次调用 `message.contacts` 时用了错误资源名 `message.contacts`，实际 CLI 是 `message contacts`。
- PM 调用 `message.list --payload '{"box":"inbox"}'` 被拒绝，原因是 `message.list` 不接受 `box`。
- PM 第一次调用 `message.send` 时用了旧字段：

```json
{
  "actor_address": {
    "buddy_id": "market",
    "instance_id": "inst-market-ae219d1e9e24"
  },
  "message": "..."
}
```

实际字段是：

```json
{
  "target_actor_address": {
    "buddy_id": "market",
    "instance_id": "inst-market-ae219d1e9e24"
  },
  "content": "..."
}
```

- PM 通过查 tool catalog 后改成正确 payload，`message.send` 成功，返回 `delivery_status: delivered` 和 `handling_status: handled`。
- market 的主消息线程能收到 `[MESSAGE AVAILABLE]`，能 `message.list` 读到 PM 消息，能接受 request，能回复 PM。
- market 另一个 goal continuation 线程是 read-only / broker-transport blocked，调用 `context summarize` 时报 `Operation not permitted`，因此无法读 message 或回复。
- `message.contacts` 给 PM 返回过 `pm` 自己且 `sendable: true`，但 `message.send` 明确拒绝同 buddy 发送。
- `message.list {"buddy":"market"}` 只查 active actor inbox 中来自 market 的消息，不显示 PM 自己刚发出的 outbox。PM 因此只能推测“market 还没回”，看不到完整会话上下文。
- `instance daemon status` 的 handler 观测只显示 `task_checkout`，即使 `message_available` 有 persisted state，也显示 `registered: false`。原因是 status 只传入普通 notification handlers，没有传入 mailbox handlers。

因此，当前问题不是“message 文件有没有创建”这么窄。

当前核心问题是：

```text
message 的产品可用性被多个残留契约同时拖住：
工具文案、skill、domain rule、read model、entrypoint permission、daemon status 没有形成同一个真实产品契约。
```

## 已经确定不是本任务的问题

以下不要重新打开：

- 不重新设计 daemon signal envelope。
- 不把 message body 放进 daemon signal。
- 不让 daemon 拥有 message durable store。
- 不恢复 `to_buddy` 作为 `message.send` 主路径。
- 不做 buddy id 到 instance id 的模糊路由。
- 不做 offline queue。
- 不做 read receipt。
- 不做 group message / broadcast。
- 不做 workflow engine / event bus / plugin system。
- 不把 track/request/comment 的业务语义混进 message。

message 的业务主路径已经明确：

```text
direct actor-address message
```

本任务只把这条路径修到真正顺滑、可解释、可验证。

## 前进式开发原则

这次不要走历史过渡方案。

具体含义：

- 删除旧 `to_buddy/from_buddy` message 心智模型在 message skill 里的残留。
- 不给 `message.send` 增加 `to_buddy`、`actor_address`、`message` 等旧字段 alias。
- 不新增“兼容旧 payload 然后内部转换”的 adapter。
- 不保留双套 message read model。
- 不靠 AGENTS 或 prompt 长篇解释来掩盖 tool contract 不一致。
- 不因为已有测试 fixture 使用旧字段就保留旧行为；测试 fixture 应迁移到 actor-address 模型。
- 不手改 `buddyswitch/objects/**` 或 running instance runtime object 来绕过问题。

一次成功不是“不测试就直接上”。

一次成功的含义是：

```text
先把契约和验证口径写准，
再按同一产品语义一次性替换残留，
最后用 focused tests + 真实 PM/market 主路径验证，
确认没有 stale skill、残留进程、残留 socket、旧 payload 入口。
```

## docs/bitter 约束

本任务必须遵守以下 bitter 经验。

### 1. Tool / Skill / Prompt 分层

参考：`docs/bitter/2026-05-18-tool-skill-layering-principles.md`

执行规则：

- tool catalog 拥有 payload 字段、行为语义、读写影响、失败反馈。
- tool response 必须让 host 知道真实 state impact、correctable fields、next action。
- skill 只负责短的工作流判断，不复制完整 schema。
- AGENTS 不变成 message payload 手册。
- 如果 host 要读 `_impl.py` 才知道怎么发消息，就是 tool contract 失败。

本任务中对应要求：

- 修 `message.contacts` 的 next action 文案。
- 修 `message-tool` skill 中旧 payload 示例。
- 修 `message.contacts` 与 `message.send` 的 sendable 一致性。
- 为 `message.conversation` / `message.history` 建立工具契约，而不是让 agent 用 inbox-only list 猜会话。

### 2. Test Resource Lifecycle

参考：`docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`

执行规则：

- 会启动 daemon、app-server、runtime broker、fake Codex、browser 的验证，必须有生命周期归属。
- broad suite 前先跑 focused service-starting test。
- focused test 后检查残留 process / socket / marker。
- broad suite 后再次检查残留。
- 不能用“测试断言通过”替代“宿主机资源回到 baseline”。

本任务中对应要求：

- 先跑纯 env tool / domain / schema tests。
- 再跑 daemon status / launcher focused tests。
- 最后才跑真实 PM/market instance 主路径。
- 真实实例验证后必须 stop/delete 测试实例或确认它们是本次手动验证保留对象。

### 3. Parallel Change Boundary

参考：`docs/bitter/2026-05-28-parallel-change-boundary-principles.md`

执行规则：

- 本任务集中在 `message` 产品切片和 daemon observability 的必要边界。
- 不顺手重构 request、track、artifact、comment。
- 不做大范围格式化、移动文件、机械 rename。
- shared hotspot 必须显式列出并用 focused tests 守住。

本任务会触碰的 shared hotspot：

- `scripts/env/tool_runtime/role_auth.py`
- `scripts/env/tools/context/_impl.py`
- `tools/launcher/daemon_core.py`
- `tools/launcher/instance_daemon.py`

这些文件只能为 message 产品体验闭环做必要改动。

## 目标产品体验

PM 想找 market 讨论一个话题时，理想路径应当是：

```bash
python3 scripts/env/client.py message contacts --payload '{"buddy":"market"}'
```

返回中明确区分：

```json
{
  "contacts": [
    {
      "buddy_id": "market",
      "actor_address": {
        "buddy_id": "market",
        "instance_id": "inst-market-ae219d1e9e24"
      },
      "contact_status": "online",
      "sendable": true
    }
  ],
  "sendable_count": 1
}
```

然后发送：

```bash
python3 scripts/env/client.py message send --payload '{"target_actor_address":{"buddy_id":"market","instance_id":"inst-market-ae219d1e9e24"},"content":"先聊目标用户和替代方案。"}'
```

成功响应必须包含：

```json
{
  "ok": true,
  "state_changed": true,
  "durability": "durable",
  "message_id": "msg-...",
  "delivery_status": "delivered",
  "handling_status": "handled"
}
```

PM 如果想看双方刚刚聊到哪里，不应该误用 inbox-only list，而应该使用明确的双向会话读取动作：

```bash
python3 scripts/env/client.py message conversation --payload '{"buddy":"market","limit":20}'
```

或者在已经有精确 actor address 时：

```bash
python3 scripts/env/client.py message conversation --payload '{"target_actor_address":{"buddy_id":"market","instance_id":"inst-market-ae219d1e9e24"},"limit":20}'
```

返回必须只包含 active actor 可见的双向消息：

```text
active actor -> market actor
market actor -> active actor
```

不能包含第三方对话，不能包含与 active actor 无关的消息。

## 任务边界

### In scope

- 修 shared message skill。
- 修 message.contacts 的 sendable 语义和文案。
- 新增明确的 message conversation/history 读取动作。
- 更新 context message cues，让 host 能看到 inbox 和 conversation 的不同 source of truth。
- 修 role auth，让新 read action 被所有 manifest roles 授权。
- 修 daemon status，让 mailbox handlers 成为可观测注册对象。
- 找到并修复 product-mode goal continuation 的 runtime permission 入口，或者明确禁止该入口承载 env.tool 消息协作。
- 更新 focused tests。
- 做真实 PM/market 主路径验证和残留资源检查。

### Out of scope

- 不改变 request lifecycle。
- 不改变 track publication 语义。
- 不改变 artifact/comment 的数据模型。
- 不做 generic conversation store。
- 不做 message unread/read status。
- 不做离线投递。
- 不做多 recipient。
- 不做旧 payload 兼容期。

## 代码触点

### Message tool surface

- Modify: `scripts/env/tools/message/tool.py`
- Modify: `scripts/env/tools/message/_impl.py`
- Modify: `scripts/env/domain/messages.py`
- Modify: `scripts/env/tool_runtime/role_auth.py`

职责：

- 定义 `message.conversation` / `message.history` 动作。
- 修正 `message.contacts` 输出和 next action。
- 保证 self / same-buddy contact 不会被标成可发送。
- 保证 unsupported field rejection 指向正确字段。
- 保持 `message.send` 不接受旧字段。

### Message skill

- Modify: `buddyswitch/skills/shared/message-tool/SKILL.md`

职责：

- 删除 `to_buddy` 示例。
- 删除 `from_buddy/to_buddy` 主模型描述。
- 保留短工作流：先 contacts，复制 `contact.actor_address` 到 `target_actor_address`，再 send。
- 明确 `message.list` 是 active actor inbox。
- 明确双向上下文用 `message.conversation` / `message.history`。
- 指向 `context.get.tool_catalog['message']` 和 `turn_runtime.py status` 作为 schema source of truth。

### Context discovery

- Modify: `scripts/env/tools/context/_impl.py`
- Modify if needed: `scripts/env/tools/context/tool.py`

职责：

- `message_cues.source_of_truth` 不再只写 `message.list`。
- 区分 inbox cues 和 conversation lookup guidance。
- 仍不把 message content 放进 compact context summary。

建议形态：

```json
{
  "message_cues": {
    "inbox_source_of_truth": "message.list",
    "conversation_source_of_truth": "message.conversation",
    "target_discovery": "Use message.contacts to discover online target actor addresses.",
    "latest_inbox": []
  }
}
```

### Daemon status observability

- Modify: `tools/launcher/daemon_core.py`
- Modify: `tools/launcher/instance_daemon.py`

职责：

- `run` 已经传入 `mailbox_handlers=default_mailbox_handlers()`，status 也必须知道 mailbox handlers。
- status payload 必须能显示 `message_available` 已注册，而不是只显示 persisted but unregistered。
- 不把 mailbox handler 合并成假的 notification handler 语义；可以在 status 中明确分组。

建议 shape：

```json
{
  "handlers": {
    "registered": ["task_checkout"],
    "items": {}
  },
  "mailbox_handlers": {
    "registered": ["message_available"],
    "items": {}
  }
}
```

如果选择一个统一 `handlers` list，也必须保留 handler source/type，避免之后排障时分不清 notification handler 与 mailbox handler。

### Runtime entrypoint permission

Likely touchpoints:

- Inspect: `tools/launcher/app_server.py`
- Inspect: `tools/launcher/app_server.sh`
- Inspect: `tools/launcher/instance.sh`
- Inspect tests around `thread/goal/set`, `thread/start`, `thread/resume`, side fork, daemon submit.

职责：

- 找到 market read-only goal continuation 是哪条入口创建的。
- 如果这是 BuddySwitch product-mode continuation，应统一使用 `buddyswitch-runtime`。
- 如果这是外部 Codex manual goal thread，不能让 BuddySwitch runtime instructions 要求它调用 env tools；要把产品协作路由回 instance main / daemon-triggered thread。
- 不能靠“让 agent 下次注意”解决。

## Implementation Tasks

### Task 1: 写失败测试，锁定 message skill 不再暴露旧契约

Files:

- Modify: `tests/test_runtime_skills.py`
- Modify later: `buddyswitch/skills/shared/message-tool/SKILL.md`

新增或扩展测试：

- shared message skill 不包含 `to_buddy`。
- shared message skill 不包含 `from_buddy`。
- shared message skill 不展示 `message send` 的旧 payload。
- shared message skill 包含 `target_actor_address`。
- shared message skill 包含 `message contacts`。
- shared message skill 包含 `message conversation` 或最终选定的 `message history`。
- shared message skill 仍保留 `message list --payload '{}'`。
- shared message skill 明确 `message.list` 不接受 `box`。
- shared message skill 指向 `context.get.tool_catalog['message']`。

Focused command:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTest::test_shared_message_skill_prevents_observed_invalid_calls -q
```

Expected before implementation:

```text
FAIL
```

Failure should prove当前 skill 仍包含旧 `to_buddy/from_buddy` 模型。

### Task 2: 修 shared message skill

Files:

- Modify: `buddyswitch/skills/shared/message-tool/SKILL.md`

要求：

- skill 是 workflow note，不是 schema mirror。
- 示例必须使用当前 CLI 形态：

```bash
python3 scripts/env/client.py message contacts --payload '{"buddy":"market"}'
python3 scripts/env/client.py message send --payload '{"target_actor_address":{"buddy_id":"market","instance_id":"inst-market-ae219d1e9e24"},"content":"Please review track-alpha."}'
python3 scripts/env/client.py message list --payload '{}'
python3 scripts/env/client.py message conversation --payload '{"buddy":"market","limit":20}'
```

- 文案必须说明：

```text
message.contacts 返回 contact.actor_address。
message.send 需要把 contact.actor_address 放进 target_actor_address。
message.list 只读 active actor inbox。
message.conversation 读 active actor 与目标 buddy/actor 的双向可见消息。
```

- 禁止继续说：

```text
Messages have exactly from_buddy and to_buddy.
Send with to_buddy.
```

Verification:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTest::test_shared_message_skill_prevents_observed_invalid_calls -q
```

Expected after implementation:

```text
PASS
```

### Task 3: 写失败测试，锁定 contacts 与 send 的一致性

Files:

- Modify: `tests/test_message_env_tool.py`

新增测试：

```text
test_message_contacts_marks_active_buddy_rows_not_sendable
```

场景：

- active actor 是 `pm / inst-pm-contacts-self`。
- central daemon contacts 返回：
  - `pm / inst-pm-contacts-self`
  - `pm / inst-pm-other`
  - `market / inst-market-contacts`
- `message.contacts` 不得把任何 `buddy_id == "pm"` 的 row 标成 `sendable: true`。
- `market` row 必须 `sendable: true`。
- response 需要有 `sendable_count` 或同等明确字段。
- `allowed_next_actions` 必须出现 `target_actor_address`，不能只说 `actor_address`。

Focused command:

```bash
python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTest::test_message_contacts_marks_active_buddy_rows_not_sendable -q
```

Expected before implementation:

```text
FAIL
```

当前 `normalize_contact_rows()` 只按 online status 判断 `sendable`，会把 self 标成 sendable。

### Task 4: 修 contacts normalization 和 response 文案

Files:

- Modify: `scripts/env/domain/messages.py`
- Modify: `scripts/env/tools/message/_impl.py`
- Modify if needed: `tests/test_message_env_tool.py`

实现要求：

- `normalize_contact_rows()` 必须接收 active/source actor 信息。
- same buddy rows 的 `sendable` 必须为 `false`。
- same buddy rows 应携带清晰原因，例如：

```json
{
  "sendable": false,
  "why_not_sendable": "message.send rejects targets with the same buddy_id as the active actor"
}
```

- 不要在 contacts 层删除数据后让 host 不知道为什么少了自己；质量优先的做法是显式区分 online 和 sendable。
- `message.contacts` success response 的 allowed next action 必须类似：

```text
Use message.send with contact.actor_address copied into target_actor_address.
```

- response 建议增加：

```json
{
  "count": 3,
  "sendable_count": 1
}
```

Verification:

```bash
python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTest::test_message_contacts_marks_active_buddy_rows_not_sendable -q
python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTest::test_message_send_rejects_self_buddy_actor_address_without_state_change -q
```

Expected after implementation:

```text
PASS
```

### Task 5: 写失败测试，锁定 message.conversation read model

Files:

- Modify: `tests/test_env_tool_schema_contract.py`
- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_role_action_auth.py`
- Modify: `tests/test_message_env_tool.py`
- Modify later: `scripts/env/tools/message/tool.py`
- Modify later: `scripts/env/domain/messages.py`
- Modify later: `scripts/env/tools/message/_impl.py`
- Modify later: `scripts/env/tool_runtime/role_auth.py`

Schema tests:

- message tool action list 包含 `conversation`。
- `message.conversation` 是 read action。
- required permission 是 `message.conversation`。
- payload 支持：
  - `target_actor_address`
  - `buddy`
  - `q`
  - `limit`
- payload 不支持 `box`、`to_buddy`、`from_buddy`。

Domain/service behavior tests:

- `target_actor_address` selector 返回 active actor 与该 target actor 的双向消息。
- `buddy` selector 返回 active actor 与该 buddy 所有 actor-address 的双向消息。
- 没有 selector 时拒绝。
- 同时给 `target_actor_address` 和 `buddy` 时拒绝。
- 返回中不包含 active actor 不参与的消息。
- 返回中不包含 message content 以外的 forbidden fields。
- order 明确：按 `created_at` 从旧到新，若 limit 裁剪，则取最新 limit 后再从旧到新展示，方便阅读上下文。

Focused commands:

```bash
python3 -m pytest tests/test_env_tool_schema_contract.py::EnvToolSchemaContractTest::test_message_tool_schema_uses_actor_address_send_contract -q
python3 -m pytest tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTest::test_registry_semantics_cover_every_registered_tool_and_action -q
python3 -m pytest tests/test_role_action_auth.py -q
python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTest::test_message_conversation_returns_visible_bidirectional_actor_messages -q
```

Expected before implementation:

```text
FAIL
```

### Task 6: 实现 message.conversation

Files:

- Modify: `scripts/env/tools/message/tool.py`
- Modify: `scripts/env/domain/messages.py`
- Modify: `scripts/env/tools/message/_impl.py`
- Modify: `scripts/env/tool_runtime/role_auth.py`

Tool contract:

```text
message.conversation = read active actor's visible two-party message history.
```

Input contract:

```json
{
  "target_actor_address": {
    "buddy_id": "market",
    "instance_id": "inst-market-ae219d1e9e24"
  },
  "limit": 20
}
```

or:

```json
{
  "buddy": "market",
  "limit": 20
}
```

Selector rule:

```text
Exactly one of target_actor_address or buddy is required.
```

Visibility rule:

```text
active actor must be one participant in every returned message.
target selector must match the other participant.
```

Sorting rule:

```text
select visible rows
sort newest first for limiting
take limit
return chronological old -> new
```

Response fields:

```json
{
  "ok": true,
  "state_changed": false,
  "durability": "none",
  "read_scope": "active actor visible direct conversation messages",
  "messages": [],
  "count": 0,
  "selector": {
    "buddy": "market"
  }
}
```

Non-goal:

- Do not change `message.list` into conversation mode.
- Do not add `direction: inbox|outbox|all` to `message.list` and overload the old action.
- Do not make send target selection fuzzy.

Verification:

```bash
python3 -m pytest tests/test_message_env_tool.py -q
python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_role_action_auth.py -q
```

Expected after implementation:

```text
PASS
```

### Task 7: 更新 context message cues

Files:

- Modify: `scripts/env/tools/context/_impl.py`
- Modify if schema snapshot requires: `scripts/env/tools/context/tool.py`
- Modify: `tests/test_context_binding_env_tool.py`

要求：

- compact context summary 仍只展示 inbox cues，不展示 full content。
- cues 必须显式告诉 host：

```text
message.list = active actor inbox
message.conversation = active actor visible bidirectional conversation
message.contacts = target actor discovery
```

Regression test:

- 更新 `test_context_summarize_includes_compact_active_inbox_message_cues`。
- 断言旧 `source_of_truth: "message.list"` 不再独占全部 message reading 语义。
- 断言存在 `conversation_source_of_truth` 或等价字段。

Focused command:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py::ContextBindingEnvToolTest::test_context_summarize_includes_compact_active_inbox_message_cues -q
```

Expected after implementation:

```text
PASS
```

### Task 8: 修 daemon status 的 mailbox handler 观测

Files:

- Modify: `tools/launcher/daemon_core.py`
- Modify: `tools/launcher/instance_daemon.py`
- Modify: `tests/test_daemon_core.py`
- Modify: `tests/test_instance_daemon_entrypoint.py`
- Modify: `tests/test_buddyswitch_launcher.py`

当前残留：

```text
run path:
  handlers=[TaskCheckoutHandler()]
  mailbox_handlers=[MessageAvailableHandler()]

status path:
  handlers=[TaskCheckoutHandler()]
  mailbox_handlers omitted
```

修复要求：

- `daemon_status()` 支持 mailbox handler status。
- `instance_daemon status` 必须传入 `default_mailbox_handlers()`。
- persisted `message_available` state 不能再显示为 unregistered when the mailbox handler is actually wired.

建议 status shape：

```json
{
  "handlers": {
    "registered": ["task_checkout"],
    "items": {
      "task_checkout": {
        "registered": true
      }
    }
  },
  "mailbox_handlers": {
    "registered": ["message_available"],
    "items": {
      "message_available": {
        "registered": true
      }
    }
  }
}
```

测试更新：

- `tests/test_daemon_core.py::test_daemon_status_reports_registered_handler_observability`
- `tests/test_daemon_core.py::test_daemon_status_includes_persisted_unregistered_handler_state`
- `tests/test_instance_daemon_entrypoint.py::test_status_prints_json_from_daemon_core`
- launcher status tests currently expecting only `["task_checkout"]` must be updated to assert mailbox status separately.

Focused commands:

```bash
python3 -m pytest tests/test_daemon_core.py::DaemonCoreTest::test_daemon_status_reports_registered_handler_observability -q
python3 -m pytest tests/test_daemon_core.py::DaemonCoreTest::test_daemon_status_includes_persisted_unregistered_handler_state -q
python3 -m pytest tests/test_instance_daemon_entrypoint.py::InstanceDaemonEntrypointTest::test_status_prints_json_from_daemon_core -q
```

Expected after implementation:

```text
PASS
```

### Task 9: 修 product-mode goal continuation 权限残留

Files to inspect first:

- `tools/launcher/app_server.py`
- `tools/launcher/app_server.sh`
- `tools/launcher/instance.sh`
- `tools/launcher/daemon_core.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/helpers/fake_codex.py`

Observed failure:

```text
market goal continuation thread:
  sandbox_policy: read-only
  network: restricted
  context summarize -> E_RUNTIME_BROKER_PROTOCOL
  permission_boundary: broker-transport
```

Required conclusion before coding:

```text
Is this thread created by BuddySwitch product-mode launcher, or by external/manual Codex goal continuation?
```

If it is BuddySwitch-owned:

- the turn must be created/resumed with `permissions: "buddyswitch-runtime"`；
- add launcher regression test around the exact RPC path；
- test must inspect RPC params, not only output text。

If it is external/manual:

- BuddySwitch must not instruct that thread to call env tools；
- handoff/goal UX must route product runtime work back into instance main thread or daemon-triggered message thread；
- add a contract test around the launcher-facing behavior that prevents pretending env tools are available in read-only continuation。

Do not add a fallback that reads runtime object files directly.

Do not edit old buddybox or `buddyswitch/objects/**` directly.

Focused commands after identifying owner:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "goal or permissions or resume or side" -q
python3 -m pytest tests/test_app_server_client.py -k "permissions or goal or resume" -q
```

These tests may touch service-starting helpers. Follow resource lifecycle checks before expanding.

### Task 10: Refresh running-instance skill materialization, not runtime objects

Reason:

Existing PM/market instances may already contain copied stale skills under their instance workspace. Source skill fixes alone do not prove the currently running daemons will stop reading old examples.

Required behavior:

- Do not manually edit runtime object files.
- Do not manually patch `.agents/skills` in one instance as the product fix.
- Use launcher-supported restart/rematerialization path.
- If no supported sync path exists, add or document the product-supported path as part of the fix.

Verification target:

```text
freshly started pm/market instances read the corrected shared message skill.
currently running test instances are restarted or explicitly excluded from verification.
```

Suggested checks:

```bash
rg -n "to_buddy|from_buddy|message send --payload.*actor_address|message send --payload.*message" \
  buddyswitch/skills/shared/message-tool/SKILL.md \
  ~/.codex-buddyswitch/instances/*/workspace/.agents/skills/message-tool/SKILL.md
```

Expected after remediation:

```text
No stale message send examples in source or verified fresh runtime skill copies.
```

## Final Verification Plan

### Phase 1: Pure contract tests

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTest::test_shared_message_skill_prevents_observed_invalid_calls -q
python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_role_action_auth.py -q
python3 -m pytest tests/test_message_env_tool.py -q
python3 -m pytest tests/test_context_binding_env_tool.py::ContextBindingEnvToolTest::test_context_summarize_includes_compact_active_inbox_message_cues -q
```

Expected:

```text
All pass.
```

No daemon/app-server should be left running by these tests.

### Phase 2: Daemon observability focused tests

Run:

```bash
python3 -m pytest tests/test_daemon_core.py -q
python3 -m pytest tests/test_instance_daemon_entrypoint.py -q
```

Expected:

```text
All pass.
daemon status payload includes mailbox_handlers.message_available as registered when wired.
```

Residual check:

```bash
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex" || true
```

Expected:

```text
No unexpected test-owned processes remain.
```

### Phase 3: Launcher permission focused tests

Run only after confirming lifecycle cleanup:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "message or daemon or status or permissions or goal or resume or side" -q
python3 -m pytest tests/test_app_server_client.py -k "permissions or goal or resume or side" -q
```

Expected:

```text
All selected tests pass.
No stale app-server, daemon, runtime broker, fake Codex, or browser processes remain.
```

Residual check:

```bash
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex" || true
```

### Phase 4: Real PM/market product path

Use fresh or intentionally restarted instances.

Main path:

```bash
./buddyswitch-codex instance start --buddy pm
./buddyswitch-codex instance start --buddy market
```

From PM:

```bash
python3 scripts/env/client.py message contacts --payload '{"buddy":"market"}'
python3 scripts/env/client.py message send --payload '{"target_actor_address":{"buddy_id":"market","instance_id":"<market-instance>"},"content":"请先从目标用户和替代方案聊起。"}'
python3 scripts/env/client.py message conversation --payload '{"buddy":"market","limit":20}'
```

From market after daemon wake:

```bash
python3 scripts/env/client.py message list --payload '{"buddy":"pm","limit":20}'
python3 scripts/env/client.py message send --payload '{"target_actor_address":{"buddy_id":"pm","instance_id":"<pm-instance>"},"content":"先看项目制/客户制人群。"}'
```

Back from PM:

```bash
python3 scripts/env/client.py message list --payload '{"buddy":"market","limit":20}'
python3 scripts/env/client.py message conversation --payload '{"buddy":"market","limit":20}'
./buddyswitch-codex instance status <pm-instance> --json
./buddyswitch-codex instance status <market-instance> --json
```

Expected:

- contacts returns market as `sendable: true`。
- contacts does not mark PM itself as sendable。
- PM send succeeds first try with `target_actor_address`。
- market reads PM message through inbox list。
- market reply succeeds first try。
- PM inbox list shows market reply。
- PM conversation shows both PM outbound and market inbound messages。
- status shows `task_checkout` and `message_available` observability without false unregistered state。

Cleanup:

```bash
./buddyswitch-codex instance stop <pm-instance>
./buddyswitch-codex instance stop <market-instance>
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex" || true
```

If instances are intentionally kept for manual inspection, record that explicitly in the final report. Otherwise no residual processes should remain.

## Acceptance Criteria

本任务完成时必须同时满足：

- `message-tool` skill 不再包含旧 `to_buddy/from_buddy` message send 模型。
- `message.contacts` 不再把 active buddy 或同 buddy actor 标成 `sendable: true`。
- `message.contacts` 的 next action 明确教 host 把 `contact.actor_address` 放到 `target_actor_address`。
- `message.send` 仍只接受 `target_actor_address + content`，不添加旧字段兼容。
- `message.list` 保持 inbox-only，语义不被混淆。
- 新增 `message.conversation` / `message.history`，用于双向可见消息读取。
- context cues 区分 inbox source 和 conversation source。
- role auth 覆盖新增 read action。
- daemon status 能真实显示 mailbox handler 注册状态。
- product-mode runtime continuation 的权限边界被修正或被明确路由，不再让 read-only 线程假装可用 env tools。
- focused tests 全部通过。
- 真实 PM/market 主路径验证通过。
- 验证后没有未登记的 daemon / app-server / broker / fake Codex 残留进程或 socket。

## 禁止验收的伪完成

以下情况不能算完成：

- 只更新了 prompt 或 AGENTS，没有修 tool contract。
- 只让 PM 这次“知道怎么发”，但 skill 仍保留旧示例。
- `message.contacts` 仍把 self 标成 sendable。
- `message.list` 继续被用来猜 outbox 状态。
- 新增了旧 payload alias，导致两个发送入口长期并存。
- market read-only continuation 仍会被指引调用 env tools。
- daemon status 仍显示 `message_available` unregistered，靠日志证明它其实能跑。
- tests pass 但留下 app-server / daemon / broker 残留。

## 最终判断

这次要修的不是单个 bug，而是一次 message 产品契约收敛。

正确方向是：

```text
actor-address send remains strict
contacts becomes truthful about sendability
list remains inbox-only
conversation becomes explicit bidirectional read
skill stops copying stale schema
runtime entrypoints stop creating fake env.tool availability
daemon status reports the handlers actually wired
tests prove behavior and resource cleanup
```

只要按这个备忘执行，后续 PM 与 market 的 message 协作就不需要靠猜字段、查源码、读日志拼接状态，也不需要保留任何历史过渡入口。
