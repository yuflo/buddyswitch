# iMessage Channel Product Logic Rebuild Memo

日期：2026-06-28

状态：目标与任务收束文档。本文覆盖下一次实现任务，不是历史回顾文。

## 明确目标

只启动 `./buddyswitch-codex web`，iMessage 自动成为可用入口；每个 Apple ID 独立接入 identity/connection 体系，独立选择在线 actor，并在同一个 iMessage 对话里用极简数字交互持续沟通。

这次不是继续打磨旧 bridge MVP，而是 rebuild-forward：删除旧入口、旧参数、旧全局状态和旧测试假设，用 iMessage 模块内的产品逻辑替换它。

## 当前事实

当前 MVP 已经证明 iMessage 通道能走通，但它仍是粗糙的单 actor bridge：

- 用户需要单独启动 `buddyswitch-codex imessage bridge`，不符合产品体验目标。
- 旧命令依赖固定目标 actor 和 sender allowlist，导致一个 bridge 进程只有一个目标 actor。
- iMessage 本地状态是全局状态，不能表达不同 Apple ID 各自独立的 connection、active actor、pending choices 和路由。
- 普通 iMessage 内容会被直接投递到固定 actor，没有 iMessage 层的 actor 选择产品逻辑。
- actor 回复直接发回原文，没有 iMessage channel 要求的 `[Message From act-xxxx]` 包装。

已有底座已经具备这次重建需要的关键能力：

- `POST /api/im/connections` 会创建 external identity 和 connection key。
- `/api/im/*` authenticated routes 使用 `Authorization: Bearer <connection_key>`。
- `ExternalImSession` 已经是 `/api/im/*` 与 Central IM Core 之间的应用语义边界。
- Web 服务已经承载 `/api/im/*` router，并会确保 central daemon 存在。
- actor wake 通过 central daemon 触达 actor runtime。

因此目标不是新建一套 IM core，也不是让 iMessage 直接读写 Central IM repo。目标是在 iMessage 模块内补齐 channel-specific 产品交互，同时继续把业务消息投递给现有 `/api/im/*`。

## 非协商原则

来自 `docs/bitter` 和 BuddySwitch forward rules 的硬约束：

- Rebuild-forward：旧结构阻碍当前目标时直接替换、删除，不保留双轨兼容。
- No residue：live surface 不能继续教旧语义；旧命令、旧参数、旧 runbook、旧测试断言都要清掉或改成新语义。
- End-to-end contract：验收必须证明真实 iMessage 用户闭环，不允许只用分层单测宣称完成。
- Built-in product boundary：Central IM 的产品语义仍在 core/session；iMessage 的 channel 交互策略只属于 iMessage 模块。
- Wrong-boundary guard：不要把 `/actors`、数字选择、Apple ID 私有状态塞进 Web、HTTP router、ExternalImSession 或 Central IM。
- Test resource lifecycle：涉及 Web 服务、worker、`imsg watch`、后台进程的测试必须有明确 start/stop/cleanup 和残留检查。

## 产品体验

用户只需要一个入口：

```bash
./buddyswitch-codex web
```

iMessage 侧只有一个显式系统指令：

```text
/actors
```

`/actors` 返回当前在线 actor 列表，格式固定为三个字段：

```text
[1] role_id actor_id
[2] role_id actor_id
[3] role_id actor_id
```

用户回复数字选择 actor。选择成功后，同一个 Apple ID 后续普通消息都发给该 actor，直到用户再次用 `/actors` 选择新的 actor。

actor 回复由 iMessage channel 包装，格式固定：

```text
[Message From act-xxxx]

xxxx
xxxx
```

如果某个 Apple ID 尚未选择 actor，普通消息不得投给默认 actor。iMessage channel 只回复一个最小提示：发送 `/actors` 选择 actor。

## 架构边界

目标依赖方向：

```text
iMessage user
  -> Messages.app / imsg
  -> BuddySwitch iMessage module
  -> Integration External IM HTTP API (/api/im/*)
  -> ExternalImSession
  -> Central IM Core
  -> actor runtime
```

Web 的定位：

```text
./buddyswitch-codex web
  -> starts Web Management service
  -> ensures central daemon
  -> starts/stops iMessage channel worker lifecycle
```

Web 只负责生命周期，不负责 iMessage 产品语义。

iMessage 模块拥有：

- `imsg status/watch/send`。
- Apple ID sender key 解析与归一化。
- sender key 到 connection key 的私有映射。
- sender key 到 active actor 的私有映射。
- sender key 到 pending actor choices 的临时快照。
- inbound 去重。
- outbound event 去重。
- message id 到 iMessage route 的回复路由。
- `/actors` 控制消息。
- 数字选择控制消息。
- actor 回复前缀包装。

iMessage 模块不得拥有：

- Central IM message/conversation/event 存储。
- actor wake 内部实现。
- actor runtime message tool 语义。
- Web browser session 语义。
- `/api/im/*` route 业务语义。

Web 模块不得拥有：

- `/actors` 解析。
- 数字选择解析。
- Apple ID active actor 状态。
- pending actor choices 状态。
- iMessage outbound 文案包装。

Central IM / ExternalImSession 不得拥有：

- Apple ID、chat_id、guid、rowid、sender handle。
- iMessage control message。
- iMessage active actor。
- iMessage pending choices。
- `[Message From ...]` 包装。

## iMessage 私有状态

状态必须是 iMessage channel 私有状态，必须替换旧路径为：

```text
runtime_files.LOCAL_ROOT / "imessage-channel" / "state.json"
```

目标 schema：

```json
{
  "schema_version": 2,
  "contacts": {
    "sender:yuflo2024@126.com": {
      "connection_key": "imck-...",
      "active_actor_id": "act-dev-xxx",
      "pending_actor_choices": {
        "1": "act-pm-xxx",
        "2": "act-dev-xxx"
      },
      "seen_inbound_keys": ["guid:..."],
      "sent_outbound_event_ids": ["imev-..."],
      "routes": {
        "msg-xxx": {
          "chat_id": "6",
          "sender": "yuflo2024@126.com"
        }
      }
    }
  }
}
```

状态规则：

- `contacts` 以 Apple ID / sender key 为隔离边界。
- 同一个 Apple ID 首次发消息时创建 `/api/im/connections`，保存 connection key；后续复用。
- 不同 Apple ID 不能共享 connection key、active actor、pending choices、seen inbound keys、sent event ids 或 route。
- `pending_actor_choices` 必须存储最近一次 `/actors` 返回的快照；数字回复解析这份快照，不能实时重新查 actor 列表，否则序号会漂移。
- `active_actor_id` 是 iMessage channel 状态，不写入 Central IM。
- `routes` 用于把 actor 回复路由回原 iMessage chat/sender，不写入 Central IM。

## 数据流边界

### `/actors` 数据流

```text
用户 iMessage: /actors
  -> imsg watch
  -> iMessage module 识别为控制消息
  -> 按 sender key ensure contact connection
  -> GET /api/im/actors with that connection key
  -> 过滤在线 actor
  -> 写入 contacts[sender_key].pending_actor_choices
  -> imsg send 回同一个 chat:
       [1] role_id actor_id
       [2] role_id actor_id
```

边界要求：

- 不调用 `POST /api/im/messages`。
- 不创建 Central IM message。
- 不唤醒 actor。
- 不进入 Web BFF。
- 不把 `/actors` 存入 actor conversation。

### 数字选择数据流

```text
用户 iMessage: 2
  -> imsg watch
  -> iMessage module 识别为数字控制消息
  -> 查 contacts[sender_key].pending_actor_choices["2"]
  -> 写入 contacts[sender_key].active_actor_id
  -> 清理或保留 pending choices 由实现决定，但必须不影响 Apple ID 隔离
  -> imsg send 回同一个 chat:
       act-dev-xxx
```

边界要求：

- 数字只在存在 pending choices 时作为控制消息。
- 没有 pending choices 时，数字按普通消息处理；如果尚未选择 active actor，则返回 `/actors` 提示。
- 数字选择不调用 `POST /api/im/messages`。
- 数字选择不唤醒 actor。

### 普通消息数据流

```text
用户 iMessage: 正常内容
  -> imsg watch
  -> iMessage module 查 contacts[sender_key].active_actor_id
  -> POST /api/im/messages with:
       target_identity_id = active_actor_id
       content = 原始用户内容
  -> ExternalImSession
  -> Central IM Core
  -> central daemon wake actor
  -> actor runtime processes message
```

边界要求：

- iMessage module 只传业务内容，不把 `/actors`、数字选择、前缀包装传给 actor。
- target actor 由 iMessage 私有状态决定。
- Central IM 只看到 external identity 到 actor identity 的 direct message。
- actor runtime 不知道用户来自 iMessage，也不需要理解 Apple ID。

### actor 回复数据流

```text
actor replies through Central IM
  -> /api/im/events visible to that sender connection
  -> iMessage module polls per contact connection
  -> GET /api/im/messages/{message_id}
  -> 用 reply_to / route 找回原 iMessage chat
  -> imsg send:
       [Message From act-xxxx]

       actor reply content
```

边界要求：

- event polling 必须按 contact/connection 分开，不能继续用全局 connection。
- actor id 来自消息 envelope / participant metadata，不从正文猜。
- 前缀包装由 iMessage module 做，不污染 Central IM message content。
- outbound 去重按 contact 隔离。

## 实施任务

### 1. 重建测试合同

先写失败测试，再改实现。

需要覆盖：

- `./buddyswitch-codex web` 是唯一用户启动入口。
- 根 launcher 不再暴露 `imessage bridge` 用户命令。
- Web 只启动/停止 iMessage worker 生命周期，不解析 iMessage 控制消息。
- 首个 Apple ID 消息会创建独立 `/api/im/connections`。
- 同一 Apple ID 后续消息复用同一 connection key。
- 两个 Apple ID 的 connection key、active actor、pending choices 完全隔离。
- `/actors` 返回 `[n] role_id actor_id`，并写入 pending choices 快照。
- 数字选择只改 active actor，不发 Central IM message。
- 普通消息发给 active actor。
- 没有 active actor 的普通消息只提示 `/actors`。
- actor 回复通过 `[Message From act-xxxx]` 包装后回到原 iMessage route。
- iMessage module 不导入 Central IM repo/service 私有实现。

### 2. 删除旧公开入口和旧参数

目标：

- 删除 root launcher 中的旧 iMessage bridge help 文案。
- 删除 root launcher 中的旧 iMessage top-level command dispatch。
- 删除固定 target actor 参数。
- 删除 sender allowlist 参数。
- 删除全局 `target_identity_id`、`allowed_senders` 状态。

不做兼容：

- 不保留旧命令作为 alias。
- 不保留旧参数为 deprecated。
- 不做新旧 state schema 双轨读取。
- 不保留旧测试断言。

### 3. 替换 iMessage bridge 为 iMessage channel module

目标文件边界：

- `tools/launcher/imessage_bridge.py`：删除或替换旧 bridge 语义。
- `tools/launcher/imessage_channel.py`：建议作为新 iMessage module 落点。
- `tests/test_imessage_bridge.py`：删除或改名为 `tests/test_imessage_channel.py`，测试新语义。

模块职责：

- `ImessageChannelWorker`：负责 watch inbound、poll outbound、start/stop 生命周期。
- `ImessageChannelController`：负责 `/actors`、数字选择、普通消息投递、回复包装。
- `ImessageChannelStateStore`：负责 iMessage 私有状态读写。
- `BuddySwitchImApi`：继续只消费 `/api/im/*`。
- `CommandImsgClient`：继续封装 `imsg` 命令。

这几个类可以在同一文件内先实现，不要为了第一版拆出框架。

### 4. 把 iMessage lifecycle 接入 Web

目标：

- 用户启动 `./buddyswitch-codex web` 后，Web Management service 启动 iMessage channel worker。
- Web 只传入 server/base URL、state path、logger、stop signal 这类生命周期参数。
- Web 不读写 iMessage state。
- Web 不解析 iMessage message content。
- Web shutdown 时必须停止 worker 和 `imsg watch` 子进程。

实现约束：

- 如果本机没有 `imsg` 或 Messages.app 权限不可用，Web 主服务不应被 iMessage worker 崩掉；iMessage channel 状态应可通过日志或健康状态观察。
- 测试 worker lifecycle 时必须做 cleanup 和残留检查。

### 5. 对齐 actor 在线列表

目标：

- `/api/im/actors` 返回可投递 actor。
- iMessage `/actors` 只展示在线/可达 actor。
- 展示字段固定为 `role_id actor_id`。

需要审核当前来源：

- 现状 actor list 来自 Web instance rows。
- wake path 使用 central daemon reachability。

实施要求：

- actor list 与 wake reachability 不能长期分叉。
- 若保留 Web instance rows 作为来源，必须证明状态与 central daemon reachability 一致。
- 若改用 central daemon contacts/reachability，保持 `ExternalImSession.list_actors` contract 不变。

### 6. 更新 live docs 和 smoke runbook

目标：

- 所有面向执行的 live docs 必须只描述 `./buddyswitch-codex web` 入口。
- smoke runbook 必须以 `/actors -> 数字选择 -> 普通消息 -> actor prefixed reply` 为主路径。
- 旧 bridge 命令只能留在明确标记为历史证据的文档中；不能留在当前执行说明、测试计划或 help 输出中。

## 验收合同

端到端合同句：

```text
用户只启动 ./buddyswitch-codex web
  -> Apple ID A 在 iMessage 发送 /actors 并回复数字选择 actor
  -> Apple ID A 的普通消息投递给该 actor
  -> actor 回复以 [Message From act-xxxx] 前缀回到 Apple ID A 的原 iMessage 对话
  -> Apple ID B 走同样流程时拥有独立 connection 和 active actor
```

自动化验证建议：

```bash
python -m pytest tests/test_imessage_channel.py -q
python -m pytest tests/test_buddyswitch_launcher.py tests/test_web_management.py -q
python -m pytest tests/test_external_im_projection_contract.py tests/test_im_external_reply_loop.py -q
python -m py_compile tools/launcher/imessage_channel.py tools/launcher/web_management.py tools/launcher/im_http_router.py scripts/env/services/external_im_session.py
```

残留扫描建议：

```bash
rg -n "target-identity-id|allow-sender|allowed_senders|target_identity_id|buddyswitch-codex imessage bridge|imessage-bridge" \
  buddyswitch-codex tools/launcher tests docs/spec docs/memo
```

期望：

- live runtime/help/test/spec/smoke surfaces 无旧入口、旧参数、旧全局状态命中。
- 如历史 memo 保留旧内容，必须明确标记为 historical/superseded，不能作为当前执行路径引用。

手工 smoke 主路径：

```text
1. 启动 ./buddyswitch-codex web
2. 确认至少一个 actor 在线
3. 从 Apple ID A 发送 /actors
4. 收到 [1] role_id actor_id 列表
5. 回复 1
6. 收到 act-xxxx 确认
7. 发送普通消息
8. actor 回复后，iMessage 收到：
   [Message From act-xxxx]

   ...
9. 从 Apple ID B 重复 3-8，确认选择和回复互不串线
```

## 架构审核

本方案的收束点：

- iMessage 产品交互收束在 iMessage module。
- Web 只做生命周期投影。
- `/api/im/*` 继续作为 Integration External IM HTTP API。
- `ExternalImSession` 继续作为 external identity/connection 到 Central IM 的唯一应用语义层。
- Central IM Core 继续只拥有 message/conversation/event/wake 语义。

主要外溢风险与处理：

- 风险：把 `/actors` 放到 `/api/im/*` router。处理：禁止，`/actors` 是 iMessage control message，不是 Integration External IM API。
- 风险：Web Management 直接保存 active actor。处理：禁止，Web 只能启动/停止 worker。
- 风险：为了方便在 Central IM message content 里加 `[Message From ...]`。处理：禁止，前缀只属于 iMessage outbound projection。
- 风险：不同 Apple ID 共用一个 connection key。处理：状态 schema 以 sender key 隔离，测试必须覆盖双 Apple ID。
- 风险：actor list 和 wake reachability 分叉。处理：本任务必须对齐来源或加测试证明一致。
- 风险：保留旧命令作为兼容。处理：禁止，旧入口直接删除。
- 风险：为了 state migration 保留旧 schema 双轨。处理：禁止，本阶段按 rebuild-forward，不承诺旧 MVP state 迁移。

审核结论：

该任务的产品逻辑边界是干净的：iMessage 只拥有 iMessage channel 的交互和私有状态；Central IM 只拥有通用 IM 业务语义；Web 只拥有服务生命周期。只要实施时按上述禁止项删除旧入口和全局状态，就不会形成模块外溢或双轨兼容。
