# BuddySwitch IM Central Rebuild 审核版任务说明

## 当前结论

这次任务不是给现有 `/api/messages/send` 补回复接口，也不是继续扩展一个假的
`user-actor`。目标是把 BuddySwitch 的 message 能力 forward rebuild 成一个
中心化 IM System。

最终主路径必须是单线：

```text
external script / web / actor tool
        -> Central IM HTTP Contract
        -> IM product core: service/domain/repo store + events + participant state
        -> central daemon host bridge: registry/reachability + runtime wake
        -> actor daemon-service + app-server + innerTUI/parent-side handling
        -> actor reply through the same Central IM HTTP Contract
```

不能是：

```text
external -> HTTP gateway -> new store
actor    -> old message repo -> message.available -> mailbox
web      -> fake user actor
```

核心边界：

- IM 是产品系统，负责 address、conversation、message、reply、event cursor、participant message state。
- IM product core 必须落在 `scripts/env` 的 message service/domain/repo 这一层；它拥有模型、存储、规则和业务 contract。
- HTTP、actor tool、WebManagement、innerTUI wake 都是 IM product 的 projection/interface，不拥有 IM 语义。
- `central-daemon-service` 是 host/control plane：承接 actor registry/reachability、HTTP 挂载、runtime wake 桥接，并委托 IM product core 处理 message truth。
- HTTP 是 IM 的统一对外 contract，不是 WebManagement 的临时功能，也不是 launcher 私有业务层。
- daemon-service、app-server、innerTUI 是 actor 主动处理消息的运行体系，不能被说成“发一个 prompt”。
- mailbox 不是 message store；IM 主路径重建后不再依赖 mailbox/message.available。
- 不 build 真实 `user-actor`，也不把 external 注册进 actor registry。

## 事实核对

当前代码事实：

- [tools/launcher/web_management.py](../../tools/launcher/web_management.py) 只暴露旧 `/api/messages/send`，payload 是 `actor_id + content`，默认调用 `web_user_actor.send_web_user_message`。
- [tools/launcher/web_user_actor.py](../../tools/launcher/web_user_actor.py) 固定伪造 `{"role_id":"user","actor_id":"act-user-local"}`，启动 mailbox sink，并把这个 fake actor 注册进 central daemon actor registry。
- [scripts/env/services/messages.py](../../scripts/env/services/messages.py) 目前 send 路径是：校验 actor 地址、检查 reachability、写旧 message row、投递 `message.available` signal；如果 signal delivery 失败，会删除刚写入的 message。
- [scripts/env/repos/messages.py](../../scripts/env/repos/messages.py) 当前 message 是物理 JSON store，不是内存。它写入 `runtime_files.MESSAGES_DIR`，但单 row 同时承载 content、reply、inbox/disposition，不适合作为 open IM store。
- [tools/launcher/central_daemon_core.py](../../tools/launcher/central_daemon_core.py) 当前只做 actor registry、contacts、reachability、`signal.deliver`/`event.deliver` 到 daemon mailbox socket；目标也应是 host/control plane，不应变成 IM product core。
- [tools/launcher/daemon_mailbox.py](../../tools/launcher/daemon_mailbox.py) 是本地 socket trigger transport，不是 durable mailbox。
- [tools/launcher/message_available_handler.py](../../tools/launcher/message_available_handler.py) 把 `message.available` trigger 转成 parent prompt 或 side triage prompt。这里承载了 actor pro-active handling 经验，但事件名和 transport 需要重建。
- [scripts/env/tools/message/_impl.py](../../scripts/env/tools/message/_impl.py) 当前 actor tool 直接走旧 message service/repo/signal path。

外部架构参照：

- Matrix Client-Server API 让 client send message、control rooms、sync conversation history，并支持轻客户端从 server lazy-load state；`/sync` 支持 long-polling 和 `next_batch` cursor。
  Source: <https://spec.matrix.org/latest/client-server-api/>
- XMPP RFC 6120 中 server 负责 route stanzas；server-to-server 也是 server 间路由，不是 client/actor 之间绕过中心互写。
  Source: <https://datatracker.ietf.org/doc/html/rfc6120>
- XMPP MUC 的 groupchat message 发送到 room service，再由 room/service reflect 给 occupants。这支持“群发/房间 fanout 归中心服务”的判断。
  Source: <https://xmpp.org/extensions/xep-0045.html>
- MQTT 5.0 是 client/server publish/subscribe messaging transport，broker/server 是订阅和分发中心。
  Source: <https://groups.oasis-open.org/communities/community-home/digestviewer/viewthread?CommunityKey=99c86e3a-593c-4448-b7c5-018dc7d3f2f6&GroupId=2737&MessageKey=0dd8db83-269c-4d0a-864c-8146d7d41167>

这些资料不是要求照搬外部协议，而是支持一个底线：轻量 IM 采用中心 message service；P2P actor 直连不适合当前目标。

## 质疑点表

| # | 质疑点 | 触发内容 | 重新审核结论 |
|---|---|---|---|
| 1 | 不能把 `interface/name` 临时当 external address | 之前口头把 external 注册说成 name/interface 生成 address | external address 必须由 IM product core 签发，客户端只能拿 token/cursor 使用；display/name 只是展示标签 |
| 2 | 外部到底怎么拿 actor 回复 | 旧 `/api/messages/send` 只返回 send 结果，没有 reply 获取路径 | 外部通过 `events` subscription 拿到 reply event，再用 message/replies API 读取 reply；send 不同步等待 actor 回复 |
| 3 | 异步订阅回调是否是基础能力 | actor reply 是异步的，用户脚本需要收到回复 | 基础能力是 event cursor + long-poll/stream；SDK/脚本在客户端执行 callback。server-side webhook 不进入本次闭环 |
| 4 | 是否变成 actor P2P | 之前表达让人误解 actor 消息绕开 central | 否。所有 send 都进入 Central IM HTTP Contract。actor daemon 只处理 wake 和运行，不持有 message truth |
| 5 | central daemon contract 是否要调整 | 当前 central daemon 只做 registry/reachability/signal | 要调整。central-daemon-service 扩展为中心控制面，新增 HTTP host/wake bridge contract；store/events 由 IM product core 拥有 |
| 6 | actor side/parent 处理能不能不破坏 | 现有 `message_available_handler` 已经处理 idle/running parent/side | 处理策略继承，入口事件和数据源重建；actor 仍通过 innerTUI/runtime 主动处理，不重写心智模型 |
| 7 | innerTUI 是不是只是 prompt | 用户明确反复强调 innerTUI 是体系 | 文档必须把 innerTUI 定义成 human-facing runtime client surface + actor attention 体系的一部分，不再把它降级为 prompt |
| 8 | message store 是内存还是物理存储 | 用户问 `message__get/conversation` 是否从内存取 | 当前是物理 JSON store；新 IM store 也必须是中心 durable store，不是 per-actor private store |
| 9 | mailbox 是物理消息存储吗 | 用户问 mailbox 是否基础抽象 | mailbox 不是物理消息存储，是 runtime trigger transport。IM rebuild 后 mailbox 不参与 IM 主路径 |
| 10 | `message.available` 是否还保留 | 旧路径核心依赖 `message.available` | IM 主路径不保留。可以把现有 handler 经验迁移成 `im.message.created` wake adapter，但不能继续作为 message delivery contract |
| 11 | HTTP rebuild 到底改哪些部分 | 之前说得像只加 HTTP API | rebuild 包括 HTTP contract、IM product core/store/events、web/external path、actor tool client、runtime wake replacement、old path deletion |
| 12 | 外部大批量接入是否清晰 | 用户要求外部大量接入 actor communication | external client 先注册中心签发 participant/session，再通过同一 HTTP contract send/subscribe；不为每个外部接入创建 actor daemon |
| 13 | 群发会不会暴露架构问题 | P2P 很难做群发、离线、状态 | 中心化 conversation/fanout 才能自然支持 group/broadcast；Phase 1 只做 direct，但 store/event 模型不阻断 group |
| 14 | actor-to-actor 是否和 external-to-actor 同路 | 旧 actor tool 仍可能走 repo/signal | 必须同路：`message__send` 也调用 Central IM HTTP Contract，不直接写 repo，不直接 deliver signal |
| 15 | 不做双轨兼容如何落地 | 用户要求 rebuild forward，no left | 删除 fake user actor、旧 `/api/messages/send`、`send_from_web_user`、actor send 里的 direct repo+signal 主路径；非 IM runtime trigger 可独立保留 |

## 三个核心目标和观察

### 目标 A: HTTP rebuild 的范围必须明确

HTTP rebuild 的对象不是一个 route，而是 IM 的统一 contract。

要重建：

- Central IM HTTP API projection：participant/session、addresses、messages、replies、conversation、events、disposition。
- IM product core：participant/session、conversation、message、participant message state、event cursor、send/read/reply/disposition/fanout rules。
- IM store：中心 durable JSON store，由 IM repo/service 写入，不由 launcher/web/tool 直接写入。
- Web/external/actor tool client：都调用同一 IM contract。
- Runtime wake adapter：IM product core durable accepted 后，由 central daemon host bridge 唤醒目标 actor。
- 旧路径删除：`web_user_actor.py`、`/api/messages/send`、`send_from_web_user`、actor send direct repo+signal、`message.available` delivery contract。

不重建：

- actor parent/side handling 策略。
- app-server thread execution。
- innerTUI 作为 runtime client surface 的地位。
- Track/Task/Artifact/Comment 协作系统。
- `track.comment.added` 这类非 IM 轻量 notification。

### 目标 B: 外部使用路径必须闭环

外部脚本不是 actor，不拥有 daemon，不被注册进 actor registry。

外部路径：

```text
1. Start BuddySwitch central runtime / web surface.
2. POST /api/im/external-participants
   -> IM product core issues external participant id, token, first event cursor.
3. GET /api/im/actors?role_id=market
   -> central returns reachable actor addresses from actor registry.
4. POST /api/im/messages
   -> IM product core stores message, appends event, requests target actor wake.
5. Subscribe:
   GET /api/im/events?cursor=...&wait_ms=25000
   -> central returns message/reply events visible to this participant.
6. On reply event:
   GET /api/im/messages/{reply_message_id}
   Optional correlation check:
   GET /api/im/messages/{original_message_id}/replies
7. PATCH /api/im/messages/{reply_message_id}/disposition
   -> optional external ack/absorbed state.
```

脚本视角的 callback 是 client-side callback：

```text
while running:
  events = GET /api/im/events(cursor, wait_ms)
  cursor = events.next_cursor
  for event in events:
    on_im_event(event)
```

这满足异步订阅回调，不要求 build `user-actor`，也不要求本次闭环实现 server-side webhook。中心只保存 durable IM state、participant session/token、event cursor 所需数据；客户端可以只保存 token/cursor。

### 目标 C: actor-to-actor 必须和 external-to-actor 同路

actor 之间也不直接写对方 runtime，不直接投递 old mailbox message。

actor-to-actor 路径：

```text
actor A message__send
  -> Central IM HTTP Contract
  -> IM product store creates message/event/state
  -> central daemon wake bridge checks actor B reachability
  -> actor B daemon-service/app-server/innerTUI parent-side handling
  -> actor B message__get/conversation reads IM product store
  -> actor B message__send(reply_to=original)
  -> Central IM HTTP Contract
  -> actor A receives reply through same wake/event path
```

这里的统一点是 IM contract 和中心 truth，不是每个 actor 自己有一套本地 inbox。

## 重新设计

### 1. IM product core and central host control plane

这次 rebuild 必须遵守 built-in product 边界：

```text
IM product core
  scripts/env/services/messages.py
  scripts/env/domain/messages.py
  scripts/env/repos/messages.py
  owns model, storage, rules, business contract

Interface projections
  /api/im/* HTTP route
  scripts/env/tools/message/*
  WebManagement UI
  innerTUI wake prompt surface

Host/control plane
  central-daemon-service
  actor registry / reachability
  HTTP mounting
  runtime wake bridge
```

`central-daemon-service` 从“runtime registry + signal delivery”升级成 host/control plane，但不能成为 IM product core：

```text
central-daemon-service
  actor registry / reachability
  HTTP host for IM route
  runtime wake adapter
  delegates IM message truth to scripts/env product core
```

这不是新建大平台，也不是 service split。现阶段仍是本地 monolith-first：一个 IM product core 拥有 IM truth；HTTP 是它暴露出来的 contract。WebManagement 挂载这个 router，但不能拥有 IM 语义。launcher 可以有很薄的 host adapter，但 adapter 不拥有 message model/store/rules。

IM product core 的职责：

- 签发 external participant identity 和 local token。
- 映射 actor participant 到现有 `role_id + actor_id`。
- 创建/复用 direct conversation。
- 持久化 message。
- 为每个 participant 维护 message state。
- 追加 participant-visible event。
- 提供 cursor read/long-poll。
- 对群发/多方 conversation 做中心 fanout 的结构预留。

central host/control plane 的职责：

- 维护 actor registry 和 reachability。
- 挂载或转发 `/api/im/*` HTTP contract。
- 在 durable accepted 后请求 actor wake。
- 把 wake 送入 daemon-service/app-server/innerTUI parent-side handling。

IM product core 不做：

- 不把 external 注册到 actor registry。
- 不启动 external daemon。
- 不把 comment/track/artifact 混进 IM。
- 不做通用 event bus。
- 不保留旧 message 主路径。

central host/control plane 不做：

- 不直接写 IM store。
- 不拥有 message/conversation/participant state 规则。
- 不让 `signal.deliver` 继续成为 message business delivery。

废弃旧的误导性分层：

```text
central-daemon-service
  actor registry / reachability
  IM participant registry
  IM conversation/message/state/event store
  IM HTTP contract
  runtime wake adapter
```

这会把 product semantics 塞进 launcher，违反 built-in product 原则。

### 2. Participant 和 address

Actor participant：

```json
{
  "kind": "actor",
  "actor_address": {
    "role_id": "market",
    "actor_id": "act-market-607eca23170c"
  }
}
```

External participant 由 central 签发：

```json
{
  "kind": "external",
  "external_id": "ext-01j...",
  "client_kind": "script",
  "display_name": "local curl script"
}
```

`client_kind` 只能用于观察和 UI，不参与路由真相。路由真相是 `external_id` 和 central-issued token。

注册 API：

```text
POST /api/im/external-participants
Authorization: optional local admin/session auth
Content-Type: application/json
```

Request：

```json
{
  "client_kind": "script",
  "display_name": "local smoke script"
}
```

Response：

```json
{
  "ok": true,
  "participant": {
    "kind": "external",
    "external_id": "ext-01j...",
    "client_kind": "script",
    "display_name": "local smoke script"
  },
  "participant_token": "impt_...",
  "event_cursor": "imev-000000"
}
```

客户端之后的请求使用 token。客户端不能提交任意 `from_actor_address` 或伪装成 `role_id=user`。

### 3. HTTP API contract

最小闭环 API：

```text
POST /api/im/external-participants
GET  /api/im/actors?role_id=market
POST /api/im/messages
GET  /api/im/messages/{message_id}
GET  /api/im/messages/{message_id}/replies
GET  /api/im/conversations/{conversation_id}
GET  /api/im/conversations/direct?kind=actor&role_id=market&actor_id=act-market-...
GET  /api/im/events?cursor=...&limit=...&wait_ms=25000
PATCH /api/im/messages/{message_id}/disposition
```

Authentication:

- external requests use `Authorization: Bearer <participant_token>`.
- actor tool requests use runtime-issued actor identity from active actor context.
- web/innerTUI human client uses local session identity and receives central-issued external participant identity when sending IM as a human.

`POST /api/im/messages` external-to-actor:

```json
{
  "to": {
    "kind": "actor",
    "actor_address": {
      "role_id": "market",
      "actor_id": "act-market-607eca23170c"
    }
  },
  "content": "你好，收到后请回复 pong",
  "reply_to": null
}
```

Response：

```json
{
  "ok": true,
  "message": {
    "id": "msg-01j...",
    "conversation_id": "conv-01j...",
    "reply_to": null
  },
  "event_id": "imev-01j...",
  "delivery_status": "accepted",
  "wake_status": "submitted",
  "next_cursor": "imev-01j..."
}
```

语义：

- `delivery_status=accepted` 表示 IM product store 已持久化 message。
- `wake_status=submitted|target_not_online|wake_failed` 表示 runtime wake 结果。
- wake failure 不删除 durable message。
- actor reply 不从 send response 返回；reply 通过之后的 event 返回。

`GET /api/im/events`：

```json
{
  "events": [
    {
      "event_id": "imev-01j...",
      "type": "message.created",
      "message_id": "msg-02j...",
      "conversation_id": "conv-01j...",
      "from": {
        "kind": "actor",
        "actor_address": {
          "role_id": "market",
          "actor_id": "act-market-607eca23170c"
        }
      },
      "to": {
        "kind": "external",
        "external_id": "ext-01j..."
      },
      "reply_to": "msg-01j..."
    }
  ],
  "next_cursor": "imev-02j..."
}
```

### 4. IM store

Current `messages/*.json` 单 row store 替换为中心 IM store：

```text
state/im/participants/*.json
state/im/conversations/*.json
state/im/messages/*.json
state/im/message_states/*.json
state/im/events/*.json
state/im/cursors/*.json
```

Message 不保存 per-recipient disposition：

```json
{
  "id": "msg-01j...",
  "conversation_id": "conv-01j...",
  "from": {"kind": "external", "external_id": "ext-01j..."},
  "to": [{"kind": "actor", "actor_address": {"role_id": "market", "actor_id": "act-market-607eca23170c"}}],
  "content": "hello",
  "reply_to": null,
  "created_at": "2026-06-24T00:00:00Z"
}
```

Participant message state 独立：

```json
{
  "message_id": "msg-01j...",
  "participant": {
    "kind": "actor",
    "actor_address": {
      "role_id": "market",
      "actor_id": "act-market-607eca23170c"
    }
  },
  "disposition": "unseen",
  "reason": null,
  "updated_at": "2026-06-24T00:00:01Z",
  "processed_by": null
}
```

Event 是 participant-visible cursor item：

```json
{
  "event_id": "imev-01j...",
  "participant": {"kind": "external", "external_id": "ext-01j..."},
  "type": "message.created",
  "message_id": "msg-02j...",
  "conversation_id": "conv-01j...",
  "created_at": "2026-06-24T00:00:02Z"
}
```

Phase 1 只实现 direct conversation。Store 命名保留 `to` 为数组，是为了不在 Phase 2 群发/group fanout 时再次拆 message model；Phase 1 validation 仍要求 `to` 只有一个 target。

### 5. Runtime wake 和 innerTUI

actor pro-active handling 不重建心智模型，只替换入口和数据源。

当前：

```text
message.available trigger
  -> message_available_handler
  -> render parent/side prompt
  -> actor calls message__get/message__conversation
```

重建后：

```text
Central IM message accepted
  -> runtime wake adapter with message_id/conversation_id/event_id
  -> actor daemon-service checks parent activity
  -> idle: parent handling
  -> running: side triage
  -> actor calls message__get/message__conversation
  -> tools read IM product store through IM contract
```

需要继承：

- idle parent handling。
- running parent side triage。
- `needs_parent` disposition。
- actor 用 `message__get` 精确读取 message。
- actor 用 `message__conversation` 获取上下文。
- actor 用 `message__send(reply_to=...)` 回复。
- actor 用 `message__mark` 标记 absorbed/replied/needs_parent。

需要删除/替换：

- `message.available` 作为 IM delivery contract。
- `deliver_message_available`。
- `message_inbound` 作为默认 IM source。
- `message_available_handler` 的事件名和旧 payload 语义。

innerTUI 在这套设计里是 actor runtime client surface。它支撑 actor 被唤醒、观察、接管、side/parent 处理等体验；它不是 fake user actor，也不是 message store。

### 6. Actor tool migration

actor-facing tool 名称保留，降低 role prompt 和 native MCP surface 震荡：

```text
message__contacts
message__send
message__get
message__list
message__conversation
message__mark
```

实现改为 Central IM HTTP client：

```text
message__send
  -> POST /api/im/messages as active actor participant

message__get
  -> GET /api/im/messages/{id} as active actor participant

message__conversation
  -> GET /api/im/conversations/direct?kind=actor&role_id=...&actor_id=...

message__mark
  -> PATCH /api/im/messages/{id}/disposition
```

禁止：

- actor tool direct repo write。
- actor tool direct `signal.deliver`。
- actor tool accepting `role_id=user` as an actor address。

### 7. WebManagement 和 quick experience

`./buddyswitch-codex web` 可以继续作为快速体验入口，但 WebManagement 不拥有 IM 语义。

目标关系：

```text
web_management HTTP server
  -> mounts/proxies Central IM HTTP router
  -> serves static UI
  -> does not construct message rows
  -> does not construct daemon signals
  -> does not start WebUserActorRuntime
```

快速体验应是：

```text
./buddyswitch-codex web
curl POST /api/im/external-participants
curl POST /api/im/messages
curl GET  /api/im/events
```

不需要 delete 旧 actor instance；需要的是目标 actor daemon 在线。如果目标 actor 不在线，send 仍可以 durable accepted，但 `wake_status=target_not_online`。

## 场景模拟

### 模拟 1: 外部脚本发送并获取 reply

```text
script registers external participant
script finds market actor
script sends message M1 to market
IM product core stores M1 and event E1
central host bridge wakes market actor
market actor parent/side reads M1
market actor sends M2 reply_to=M1
IM product core stores M2 and event E2 visible to script
script long-poll receives E2
script fetches M2 or M1 replies
```

通过条件：

- script 不需要 actor daemon。
- send response 不假装同步返回 reply。
- reply 通过 event/replies 可取。
- fake `act-user-local` 不存在。

### 模拟 2: target actor idle

```text
central accepts M1
wake adapter sees actor parent idle
submit parent handling workflow
actor uses message__get(M1)
actor replies or marks absorbed
```

通过条件：

- actor 主动处理路径保留。
- old `message.available` 不出现。
- message truth 在 IM product store。

### 模拟 3: target actor busy

```text
central accepts M1
wake adapter sees parent running
submit side triage workflow
side decides lightweight reply / needs_parent / absorbed
if needs_parent, parent later handles through existing runtime pattern
```

通过条件：

- side/parent 机制不破坏。
- `needs_parent` 是 actor processing disposition，不是通用 read receipt。

### 模拟 4: actor-to-actor

```text
actor A message__send to actor B
message__send calls Central IM HTTP Contract
IM product core stores message; central host bridge wakes actor B
actor B replies through same message__send(reply_to=...)
IM product core appends reply event; central host bridge wakes actor A when reachable
```

通过条件：

- actor A 不写 actor B 的本地文件。
- actor A 不直接 deliver mailbox signal。
- actor-to-actor 和 external-to-actor 同 store、同 event、同 wake adapter。

### 模拟 5: target offline / wake failed

```text
script sends M1
IM product core stores M1
reachability says target_not_online or wake failed
response returns delivery_status=accepted, wake_status=target_not_online|wake_failed
later actor comes online and can be woken by pending unseen message scan
```

通过条件：

- durable message 不因 wake failure 被删除。
- delivery 和 wake 状态分离。

### 模拟 6: group/fanout 压力校验

```text
sender sends to conversation C with participants P1/P2/P3
IM product core stores one message
IM product core appends participant-visible events/states for each recipient
central host bridge wakes online actor participants
external participants receive via event cursor
```

通过条件：

- 群发不需要 sender 逐个 p2p 写 receiver。
- fanout、offline、read/disposition 都在中心可解释。
- Phase 1 direct model keeps conversation/message/state split, so group fanout changes recipient cardinality instead of replacing the main path。

## Rebuild 模块清单

### 1. IM product core

Primary files:

- [scripts/env/domain/messages.py](../../scripts/env/domain/messages.py)
- [scripts/env/repos/messages.py](../../scripts/env/repos/messages.py)
- [scripts/env/services/messages.py](../../scripts/env/services/messages.py)

Changes:

- add IM participant/session methods。
- add IM send/read/events/disposition methods。
- replace actor-only message row model with IM participant/conversation/message/state/event model。
- own all writes to `state/im/*`。
- remove `EXTERNAL_MESSAGE_ROLE_IDS = {"user"}` as actor role compatibility。
- remove `send_from_web_user`。
- remove send failure cleanup semantics tied to signal delivery。
- keep actor-facing validation semantics where they still match IM。

### 2. Central host/control plane

Primary files:

- [tools/launcher/central_daemon_core.py](../../tools/launcher/central_daemon_core.py)
- create `tools/launcher/im_http_router.py` for `/api/im/*` request parsing and response shaping
- optional thin launcher host adapter only if needed; it must delegate to `scripts/env` IM product core

Changes:

- keep actor registry/reachability。
- add HTTP host/mounting for IM contract。
- add runtime wake adapter entry。
- delegate IM store and business operations to IM product core。
- stop using `signal.deliver` as message business delivery。
- assert launcher does not write IM store directly。

### 3. HTTP contract

Primary files:

- [tools/launcher/web_management.py](../../tools/launcher/web_management.py)
- [tools/launcher/assets/web-management/app.js](../../tools/launcher/assets/web-management/app.js)

Changes:

- remove old `/api/messages/send` public path。
- mount/proxy central `/api/im/*` contract。
- ensure WebManagement does not directly construct message rows/signals or implement IM business rules。
- UI can start minimal: register external participant, send, poll events, show replies。

### 4. Actor runtime wake

Primary files:

- [tools/launcher/message_inbound.py](../../tools/launcher/message_inbound.py)
- [tools/launcher/message_available_handler.py](../../tools/launcher/message_available_handler.py)
- [tools/launcher/instance_daemon.py](../../tools/launcher/instance_daemon.py)
- [scripts/env/tool_runtime/context.py](../../scripts/env/tool_runtime/context.py)

Changes:

- replace message.available handler with IM wake adapter/handler。
- keep parent/side runtime behavior。
- update default handler/subscription list。
- keep Track comment notification independent。

### 5. Actor message tool

Primary files:

- [scripts/env/tools/message/_impl.py](../../scripts/env/tools/message/_impl.py)
- [scripts/env/tools/message/tool.py](../../scripts/env/tools/message/tool.py)
- create `scripts/env/tool_runtime/im_client.py` for actor-side Central IM HTTP calls

Changes:

- implement Central IM HTTP client as actor-tool projection。
- move `send/get/list/conversation/mark` to IM contract。
- keep tool names and high-level results stable where possible。
- assert no direct repo write/signal delivery in actor send。
- update `tool.py` semantics from direct actor inbox rows to IM participant/conversation/message/event model。

### 6. Remove fake user actor

Primary files:

- [tools/launcher/web_user_actor.py](../../tools/launcher/web_user_actor.py)
- [tests/test_web_user_actor.py](../../tests/test_web_user_actor.py)

Changes:

- delete fake user actor runtime。
- delete fake mailbox sink。
- delete central actor registry entry for `act-user-local`。
- replace tests with external participant/session tests。

## Phase plan

### Phase 1: IM product truth and HTTP contract

Goal:

```text
external participant can register, send message, read events/replies from IM product store through the Central IM HTTP Contract.
```

Tests first:

- external participant registration returns central-issued id/token/cursor。
- `POST /api/im/messages` persists message/state/event。
- `GET /api/im/events` returns cursor-ordered events and supports wait。
- `GET /api/im/messages/{id}/replies` returns reply messages。
- wake failure does not delete durable message。
- `/api/messages/send` is removed; route-level test expects 404。

### Phase 2: Runtime wake replacement

Goal:

```text
Central IM accepted message wakes actor through daemon-service/app-server/innerTUI flow without message.available.
```

Tests first:

- idle actor receives parent handling workflow。
- busy actor receives side triage workflow。
- wake payload only includes ids, not full message body。
- `message.available` no longer appears in IM main path。
- `track.comment.added` still works。

### Phase 3: Actor tool migration

Goal:

```text
actor-to-actor uses same Central IM HTTP Contract.
```

Tests first:

- `message__send` calls central IM client。
- `message__get/list/conversation/mark` reads/writes through central IM client。
- actor send does not direct repo write。
- actor send does not call `deliver_message_available`。
- `role_id=user` is rejected as actor participant。

### Phase 4: Delete old path and tighten gates

Goal:

```text
no dual-track message system remains.
```

Delete:

- `tools/launcher/web_user_actor.py`
- `send_from_web_user`
- `deliver_message_available`
- old `/api/messages/send` tests
- default `message.available` registration for IM

Required searches:

```bash
rg "act-user-local|web-user|send_from_web_user|WebUserActorRuntime|deliver_message_available|/api/messages/send" tools scripts tests
rg "message.available" tools scripts tests
```

Any remaining hit must be non-IM legacy test being deleted in the same phase, or a non-IM runtime trigger with a clear reason. Final IM main path must have no hit.

## Verification map

Focused Python tests to rebuild/migrate:

- [tests/test_message_service.py](../../tests/test_message_service.py)
- [tests/test_message_env_tool.py](../../tests/test_message_env_tool.py)
- [tests/test_web_management.py](../../tests/test_web_management.py)
- [tests/test_message_available_handler.py](../../tests/test_message_available_handler.py)
- [tests/test_notification_center.py](../../tests/test_notification_center.py)
- [tests/test_instance_daemon_entrypoint.py](../../tests/test_instance_daemon_entrypoint.py)
- [tests/test_daemon_communication_boundary.py](../../tests/test_daemon_communication_boundary.py)
- [tests/test_track_comment_env_tool.py](../../tests/test_track_comment_env_tool.py)
- [tests/test_track_comment_added_handler.py](../../tests/test_track_comment_added_handler.py)

Focused JS tests if UI changes:

- [tests/web_management_ui_contract.test.js](../../tests/web_management_ui_contract.test.js)
- [tests/web_management_ui_state.test.js](../../tests/web_management_ui_state.test.js)

Manual smoke target:

```bash
./buddyswitch-codex web

curl -sS -X POST http://127.0.0.1:8765/api/im/external-participants \
  -H 'Content-Type: application/json' \
  -d '{"client_kind":"script","display_name":"local smoke"}'

curl -sS -X POST http://127.0.0.1:8765/api/im/messages \
  -H 'Authorization: Bearer <participant_token>' \
  -H 'Content-Type: application/json' \
  -d '{"to":{"kind":"actor","actor_address":{"role_id":"market","actor_id":"act-market-607eca23170c"}},"content":"你好，收到后请回复 pong"}'

curl -sS 'http://127.0.0.1:8765/api/im/events?cursor=<cursor>&wait_ms=25000' \
  -H 'Authorization: Bearer <participant_token>'
```

## Review checklist

这份方案可信必须同时满足：

- HTTP rebuild 的范围明确，不是只加 route。
- 外部用户从 send 到 reply fetch 有完整闭环。
- actor-to-actor 明确走 Central IM HTTP Contract，不是 P2P。
- actor 处理体系保留 parent/side/innerTUI 主动处理能力。
- 开发者能明确辨认：IM product core 在 `scripts/env`，HTTP/tool/web/innerTUI 是 projection，central daemon 是 host/control plane。
- mailbox 不再作为 IM 基础抽象。
- message store 是中心 durable store。
- external participant 不伪装成 actor。
- central daemon contract 是本次重点改造对象。
- 旧 message 主路径最终删除，不留双轨。

## 当前推荐

先不要写实现。

下一步应先让这份 memo 通过 review。通过后再写 implementation plan，第一批只做可验证闭环：

```text
external register
external send
central durable store
central event cursor
runtime wake
actor reply
external fetch reply
old fake user actor path removed
```

这个闭环跑通，IM rebuild 才算找对线头。
