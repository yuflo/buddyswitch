# BuddySwitch IM Rebuild Forward 阶段计划

日期：2026-06-28  
状态：阶段任务收束文档。  
适用范围：External IM Session 边界重建、Web/HTTP IM 投影收束、iMessage Channel Adapter MVP。

## 一句话结论

先重建一个唯一的 `External IM Session` 应用语义层，再让 `Integration External IM HTTP API` 和 `Web Console IM BFF` 都投影它，最后把 iMessage 做成只消费 `/api/im/*` 的本地 Channel Adapter。

这不是新增一条 iMessage 产品分支，也不是在 Web UI 旁边继续维护第二套 IM 语义。目标是 rebuild-forward：替换旧边界，删除残留，不保留双轨兼容。

## 任务目标

### 目标 1：清除当前 External IM 的双轨语义

当前讨论里的 `#1` 和 `#2` 分别是：

- `#1 Integration External IM HTTP API`：外部集成方通过 `/api/im/*` 创建连接、发送消息、订阅事件、读取回复。
- `#2 Web Console IM BFF`：浏览器通过 `/api/web/im/*` 使用 Web 控制台里的 IM 能力。

目标不是把两组 HTTP route 合并成一个 URL family，而是让两组 route 背后只存在一套应用语义：

```text
External IM Session
  -> Integration External IM HTTP API (/api/im/*)
  -> Web Console IM BFF (/api/web/im/*)
```

`/api/im/*` 和 `/api/web/im/*` 可以继续作为两个 consumer surface，因为它们的消费者不同：一个面向集成进程，一个面向浏览器。它们不能继续作为两个业务实现分支。

### 目标 2：把 Web Console IM 降级为纯 BFF 投影

Web Console IM 只做浏览器需要的附加工作：

- 隐藏 `connection_key`，不让浏览器持有集成凭证。
- 维护 Web 专用 external session。
- 把事件补全成浏览器渲染需要的 DTO，例如同时返回 `events` 和对应 `messages`。
- 把 Web UX 约定保持在 Web 层，例如 direct conversation 不存在时返回空列表而不是让浏览器处理底层错误。

Web Console IM 不拥有发送、事件游标、conversation、disposition、actor target resolution 的产品语义。

### 目标 3：让 iMessage 成为 Channel Adapter，而不是 Central IM 分支

iMessage 的位置是：

```text
iPhone iMessage
  -> Mac Messages.app
  -> local imsg
  -> BuddySwitch iMessage Channel Adapter
  -> Integration External IM HTTP API (/api/im/*)
  -> External IM Session
  -> Central IM Core
```

iMessage adapter 只负责协议转换、去重、allowlist、本地进度状态、健康检查和 `imsg send/watch`。它不导入 Central IM core，不读写消息 repo，不知道 actor wake 的内部实现。

### 目标 4：保留 Central IM Core 的产品所有权

Central IM Core 继续拥有：

- message / conversation / participant / event / disposition 语义。
- external connection 与 actor participant 的基础关系。
- actor wake 触发语义。
- actor 通过 message tool 回复的语义。

Central IM Core 不拥有：

- Web 浏览器 session 细节。
- iMessage Apple ID、chat_id、rowid、guid。
- `imsg` 进程生命周期。
- Channel Adapter 的 allowlist、重连、offset 状态。

### 目标 5：用端到端合同验证 MVP

MVP 的最终合同句是：

```text
iPhone 用户发送 iMessage
  -> Mac 本地 bridge 收到并投递到 BuddySwitch
  -> 目标 actor 被唤醒并用 Central IM 回复
  -> bridge 读取回复事件并通过 iMessage 发回同一个 iPhone 用户
```

阶段验收不能只看模块测试。必须至少保留一个能证明这个消费端闭环的 acceptance test 或 smoke 脚本。

## 非协商原则

这些原则来自 `docs/bitter` 和当前前进式开发规则，必须进入实现验收：

- Built-in product rule：产品语义在 core/session 层，HTTP、Web、CLI、Channel 都只是 projection。
- Residue cleanup rule：语义替换完成前，live surface 不能继续教旧语义。
- End-to-end contract rule：跨层能力必须有一个消费者可观察闭环。
- Rebuild-forward：旧结构阻碍当前目标时直接替换和删除，不叠兼容 wrapper。
- 禁止双轨兼容：不允许 old path 和 new path 长期并存；阶段内迁移只能作为同一变更的临时中间态。
- 禁止残留：旧 route、旧 helper、旧命名、旧测试断言如果还在 live surface 中表达旧语义，阶段不能验收。

## 目标架构

### 层次结构

```text
Central IM Core
  env.services.messages
  repos/messages
  message tool
  im wake handler

External IM Session
  external identity/session
  connection authentication
  actor identity resolution
  send/read events/conversation/disposition
  common error contract

HTTP Projections
  Integration External IM HTTP API: /api/im/*
  Web Console IM BFF: /api/web/im/*

Channel Adapters
  iMessage bridge
```

### 依赖方向

```text
iMessage bridge
  -> /api/im/*
  -> External IM Session
  -> Central IM Core
  -> repo
```

```text
Browser UI
  -> /api/web/im/*
  -> External IM Session
  -> Central IM Core
  -> repo
```

```text
Actor runtime message tool
  -> Central IM Core
  -> repo
```

禁止方向：

- iMessage bridge -> `env.services.messages`
- iMessage bridge -> message repo
- Browser UI -> `/api/im/*`
- Web Console IM BFF -> duplicated send/events/conversation semantics
- Central IM Core -> Web/iMessage/HTTP projection
- Central IM Core -> Apple ID / chat_id / imsg state

### 唯一语义边界：External IM Session

`External IM Session` 是 external consumer 与 Central IM Core 之间的唯一应用语义层。它的职责是：

- `create_connection(display_name)`：创建 external session，返回集成方需要的认证材料。
- `authenticate(connection_key)`：把 credential 解析成 external participant 和 connection。
- `list_actors(role_id?)`：返回可投递 actor identity。
- `send_message(connection, target_identity_id, content, reply_to?)`：投递 external -> actor 消息并触发 wake。
- `read_events(connection, limit, wait_ms)`：读取 external 可见事件，不暴露内部 cursor。
- `get_direct_conversation(connection, identity_id, limit)`：读取 external 与目标 actor 的 direct conversation。
- `get_message(connection, message_id)`：读取 external 可见消息。
- `list_replies(connection, message_id)`：读取回复关系。
- `update_disposition(connection, message_id, disposition, reason?)`：更新 external 侧消息状态。

Web BFF 可以在它之上做 DTO shaping，但不能旁路它重新调用 Central IM Core。

### 两个 HTTP projection 的分工

`Integration External IM HTTP API (/api/im/*)`：

- 面向本地 bridge、CLI、headless client。
- 使用 `Authorization: Bearer <connection_key>`。
- 返回集成 API contract，不关心浏览器渲染便利。
- iMessage bridge 只使用这个 surface。

`Web Console IM BFF (/api/web/im/*)`：

- 面向 browser。
- 不把 `connection_key` 暴露给 browser。
- 通过 server-owned Web external session 调用 `External IM Session`。
- 返回 browser DTO。

结论：两个 route family 是两个 projection，不是两个 IM 分支。

### iMessage Channel Adapter 的边界

Channel Adapter 是 `Integration External IM HTTP API (/api/im/*)` 的外部消费者 / headless client，不是和 `Integration External IM HTTP API`、`Web Console IM BFF` 并列的第三套 IM 应用语义。

iMessage adapter 拥有：

- Mac 本地 `imsg` 调用。
- Messages.app 权限和健康检查。
- inbound row/guid 去重。
- `is_from_me=true` 过滤。
- sender allowlist。
- chat_id / sender handle / target actor identity 的本地映射。
- event polling 后通过 `imsg send` 发回原 sender。

iMessage adapter 不拥有：

- BuddySwitch message id 生成。
- conversation 存储。
- actor wake。
- actor reply 语义。
- Web UI session。
- Central IM repo。

## 阶段任务

### 阶段 0：事实基线与入口冻结

核心问题：实现前先锁定真实当前状态，防止文档和代码分叉。

任务：

- 记录 `imsg` 已验证能力：`status`、`chats/history`、`send`、`watch` 均可用。
- 记录当前 BuddySwitch 已有 Central IM 测试基线。
- 锁定当前 live surfaces：`/api/im/*`、`/api/web/im/*`、actor message tool、wake handler、Web UI JS。
- 明确启动目标：MVP 用户只启动 Web 服务和 iMessage bridge 两个用户可见进程。

验收：

- `docs/memo/2026-06-28-imessage-interface-brief.html` 保留为可行性证据。
- 本阶段文档明确 `#1`、`#2` 的真实名称和关系。
- 没有开始写 iMessage adapter 代码。

### 阶段 1：Rebuild External IM Session

核心问题：当前 `/api/im/*` 和 `/api/web/im/*` 都直接含有 IM session/send/events/conversation 语义，形成事实双轨。

方案：

- 新建唯一应用语义边界：`External IM Session`。
- 将 actor target resolution、connection authentication、send、events、conversation、message fetch、replies、disposition 都收束到这个边界。
- `im_http_router.py` 改成薄 HTTP projection：解析 HTTP、认证 header、调用 `External IM Session`、返回 HTTP response。
- `web_management.py` 改成 Web BFF：确保 Web session、解析 browser query/body、调用 `External IM Session`、做 browser DTO shaping。
- `web_im_identity.py` 只保留 Web server-owned session 持久化职责，不再被理解为 Web IM 业务语义层。

必须删除：

- `im_http_router.py` 里直接调用 `message_service.send_external_connection_message`、`read_external_connection_events`、`get_im_direct_conversation` 等产品语义的路径。
- `web_management.py` 里直接调用同类 Central IM Core 方法的路径。
- 任何为了兼容旧 Web/Integration 分支而保留的 parallel helper。

阶段验收：

- 只有 `External IM Session` 能从 HTTP/Web projection 调用 Central IM Core 的 external-session 方法。
- `/api/im/*` contract 不变，因为它是 iMessage bridge 要消费的 integration surface。
- `/api/web/im/*` contract 不变，因为它是 browser UI 要消费的 BFF surface。
- route family 可以保留两个，语义实现只能保留一个。
- residue scan 显示 HTTP/Web route 文件不再直接持有 external IM 产品语义。

建议验证：

```bash
python -m pytest tests/test_im_http_router.py tests/test_web_management.py tests/test_im_web_management_projection.py tests/test_im_external_reply_loop.py -q
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

### 阶段 2：Projection Contract 收紧

核心问题：重建 session 层后，要防止 route family 又长回业务语义。

方案：

- 给 `Integration External IM HTTP API` 增加 projection contract 测试：router 只做 auth/body/query/status mapping。
- 给 `Web Console IM BFF` 增加 projection contract 测试：Web route 只做 session ownership、actor scope requirement、browser DTO shaping。
- 给 residue scan 增加活面检查：HTTP/Web projection 不得直接调用被收束的 Central IM Core external-session 方法。
- 保留现有 Web UI contract：browser 只能调用 `/api/web/im/*`，不能直接调用 `/api/im/*`。

阶段验收：

- Integration API 和 Web BFF 的差异被写进测试，而不是散落在实现注释里。
- Web BFF 的“额外一点事情”被明确限制为 browser session 和 DTO shaping。
- 没有旧 route 被复活，例如 `/api/messages/send` 或 `/api/im/external-participants`。
- 文档、测试、实现对 `#1`、`#2` 的命名一致。

### 阶段 3：iMessage Channel Adapter MVP

核心问题：在干净 External IM Session 边界之后，接入 iMessage，不污染 Central IM Core。

方案：

- 新增本地 bridge 命令，目标形态：

```bash
./buddyswitch-codex imessage bridge \
  --server http://127.0.0.1:8765 \
  --target-identity-id <actor_identity_id> \
  --allow-sender <iphone_apple_id_or_phone>
```

- bridge 启动时调用 `/api/im/connections` 创建或恢复 external connection。
- bridge 启动时调用 `/api/im/actors` 验证 `target_identity_id` 可投递；不可投递时 fail fast。
- inbound：`imsg watch` 监听消息，过滤 `is_from_me=true`，校验 allowlist，按 rowid/guid 去重，调用 `POST /api/im/messages`。
- outbound：bridge 长轮询 `GET /api/im/events`，读取 actor 回复事件，拉取消息内容后用 `imsg send` 发回对应 sender/chat。
- 本地保存 bridge 状态：connection_key、target_identity_id、allowed sender、chat identifier、last inbound row/guid、已发送 outbound event id。
- bridge 状态只属于 adapter，不进入 Central IM Core。

用户启动目标：

```bash
./buddyswitch-codex web --port 8765
./buddyswitch-codex imessage bridge --server http://127.0.0.1:8765 --target-identity-id <actor_identity_id> --allow-sender <sender>
```

不把 `./buddyswitch-codex instance start --role pm` 设计成用户必须记住的第三个 iMessage 启动步骤。若目标 actor 在 `/api/im/actors` 中不可达，bridge 必须给出明确错误并退出。

阶段验收：

- iMessage adapter 代码不导入 `env.services.messages` 或 message repo。
- Central IM Core 不出现 Apple ID、chat_id、rowid、guid、imsg 字段。
- 重复 inbound row/guid 不会重复投递到 BuddySwitch。
- bridge 重启后不会重复发送已处理 outbound event。
- allowlist 外 sender 不会进入 Central IM。

建议验证：

```bash
python -m pytest tests/test_im_http_router.py tests/test_im_external_reply_loop.py tests/test_im_product_core.py -q
```

另需新增 bridge 级测试覆盖：

- inbound row/guid 去重。
- `is_from_me=true` 过滤。
- allowlist 拒绝。
- `/api/im/actors` 目标不可达 fail fast。
- outbound event 一次性发送。

### 阶段 4：端到端 Smoke

核心问题：模块都通过不代表用户能完成 iMessage 对话。

方案：

- 保留 automated acceptance test 覆盖 external -> actor -> external reply loop。
- 增加本地 smoke runbook，覆盖真实 Mac `imsg` 主路径。
- smoke 只验证 MVP：一对一文本、一个 allowlisted sender、一个 target actor、同一 chat 回复。

手动 smoke：

```text
1. Mac 登录 BuddySwitch 专用 Apple ID。
2. Messages.app 可收发 iMessage。
3. imsg status/chats/send/watch 已通过。
4. 启动 ./buddyswitch-codex web --port 8765。
5. 启动 ./buddyswitch-codex imessage bridge ...。
6. iPhone 从 allowlisted Apple ID 发送文本消息。
7. actor 回复后，iPhone 在同一 iMessage 会话收到回复。
```

阶段验收：

- 记录一次真实 smoke 的命令、输入、输出和观察结果。
- 若真实 iMessage 环境失败，必须区分是 Apple/Messages/imsg 权限问题，还是 BuddySwitch adapter 问题。
- 不用 mock smoke 替代真实 smoke，但 automated tests 可以覆盖重复逻辑。

### 阶段 5：残留清理与文档收口

核心问题：语义替换后，活面不能继续教旧架构。

方案：

- 更新 `docs/arch/web-interface-call-architecture.md` 中 IM API family 的描述：Web IM 与 Integration IM 是 projection，External IM Session 才是共享语义边界。
- 保留 `docs/memo/2026-06-28-imessage-interface-brief.html` 作为可行性调研，不把它当最终架构规范。
- 新增或更新短原则文档时，只记录 durable lesson，不写执行日记。
- 对 live surfaces 做 scoped residue scan。

必须扫描的活面：

- `tools/launcher/im_http_router.py`
- `tools/launcher/web_management.py`
- `tools/launcher/web_im_identity.py`
- `tools/launcher/assets/web-management/app.js`
- `tests/test_im_http_router.py`
- `tests/test_web_management.py`
- `tests/test_im_web_management_projection.py`
- `tests/web_management_ui_contract.test.js`
- `docs/arch/web-interface-call-architecture.md`

阶段验收：

- 没有 live surface 把 `/api/im/*` 和 `/api/web/im/*` 描述成两套 IM 产品实现。
- 没有 live surface 建议 iMessage 直接接 Central IM Core。
- 没有 live surface 建议为 iMessage 新建 Central IM branch。
- 文档中的启动方式与实际命令一致。

## 风险与应对

### 风险 1：把 projection 差异误判成业务分支

应对：保留两个 HTTP surface，但将共享语义下沉到 `External IM Session`。验收看调用路径，不看 route 数量。

### 风险 2：Web BFF 又开始长业务语义

应对：Web BFF 只允许持有 browser session、DTO shaping、UI-specific status mapping。send/events/conversation/disposition 必须走 `External IM Session`。

### 风险 3：iMessage 状态污染 Central IM Core

应对：Apple handle、chat_id、rowid、guid、allowlist、imsg 健康状态只存在 adapter 本地状态和 adapter 日志中。

### 风险 4：Mac 权限导致非代码失败

应对：bridge 启动健康检查必须先验证 `imsg status`、Messages.app 可访问、目标 sender 可发送；失败时在 adapter 层退出并给出可操作错误。

### 风险 5：重复投递或重复回复

应对：inbound 用 rowid/guid 去重；outbound 用 event id 去重；状态落 adapter 本地；重启后继续从最后处理点恢复。

### 风险 6：阶段推进留下旧语义残留

应对：每阶段结束做 scoped residue scan。旧路径命中必须被删除，除非它是历史 memo 或一次性迁移输入，并且不在 live surface。

## 不做范围

MVP 不做：

- 群聊。
- 附件。
- tapback / reaction。
- typing indicator。
- 已读回执。
- 多 sender 路由。
- 第三方 relay。
- 通用 Channel plugin framework。
- 远程 Mac / SSH bridge。
- iMessage 专属 actor runtime。

这些不是被遗忘，而是当前 bottleneck 不需要。先验证一对一文本闭环。

## 完成定义

本任务阶段整体完成需要同时满足：

- `External IM Session` 成为唯一 external IM 应用语义层。
- `/api/im/*` 和 `/api/web/im/*` 都只是 projection。
- iMessage adapter 只消费 `/api/im/*`。
- Central IM Core 不出现 iMessage 专属状态。
- 旧 helper、旧 route、旧测试语义被删除或明确不在 live surface。
- 端到端合同被 automated acceptance test 或真实 smoke 证明。
- 文档、代码、测试用同一套命名描述架构。

## 当前立即下一步

下一步不是先写 iMessage bridge。

下一步是执行阶段 1：rebuild `External IM Session`，先清掉 `Integration External IM HTTP API` 与 `Web Console IM BFF` 的语义双轨。完成并验证后，再进入 iMessage Channel Adapter。
