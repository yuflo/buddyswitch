# Identity 体系重构备忘

## 任务目标

建立一套全局 Identity 底层体系。

系统里所有表达“谁”的地方，都统一使用同一个身份结构：

```ts
IdentityRef = {
  id: string,
  type: "actor" | "external"
}
```

这是底层身份体系重构，不是 IM 层局部改造。

IM、runtime、daemon、auth、web、track、task、artifact、comment 都应该消费这套 Identity 体系，不再各自定义目标、归属、通信对象的定位方式。

## 核心规则

- `id` 是全局唯一身份 ID。
- `type` 表示身份类型，用于业务分支。
- `role_id` 是权限和能力属性，不是身份主键。
- `actor_address` 是 daemon 路由投影，不是业务身份。
- `connection_key` 是 external 认证凭证，不是业务身份。
- `display_name` 是展示信息，不是身份主键。
- 业务关系持久化时，只存 identity id。
- 展示、权限、路由、session 信息都通过 identity projection 解析。

不引入新的公共身份概念。

## 执行门禁

本重构按阶段推进，但阶段是执行门禁，不是长期兼容边界。

每个阶段必须先形成该阶段的测试计划，再实施代码改造。阶段结束时必须记录：

- 本阶段解决的核心问题。
- 本阶段改动范围。
- 本阶段删除的旧路径。
- 本阶段新增或更新的测试。
- 实际执行的测试命令和结果。
- 是否满足阶段验收。

未满足阶段验收，不进入下一阶段。

阶段验收至少需要证明：

- 新写入路径只写 identity 字段。
- actor-facing / web-facing contract 没有暴露 routing address。
- 没有新增并行公共定位方式。
- 被替换的旧路径已经删除，或明确记录为一次性迁移输入。
- 相关自动化测试通过。

最终阶段必须执行全局残留搜索，确认没有旧公共定位方式和旧写入路径继续存在。

## 阶段 1：Identity Core

### 核心问题

当前系统没有统一表达“谁”的底层入口。

### 要点

- 定义统一的 `IdentityRef`。
- 现有 `actor_id` 作为 actor identity id。
- 现有 `external_id` 作为 external identity id。
- 业务引用统一存储 `identity_id`。
- 提供 resolver / hydrator：
  - 当前 runtime actor -> identity
  - connection key -> identity
  - identity -> actor routing projection
  - identity -> auth / display / session projection

### 注意事项

- 不用 `role_id` 识别 identity。
- 不用 `display_name` 识别 identity。
- 不靠解析 id 前缀做业务判断。
- 不设计庞大的 profile 抽象；调用方需要什么投影，就解析什么投影。

## 阶段 2：Runtime / Auth / Routing

### 核心问题

identity 统一后，权限和路由仍然要和身份分层，不能混成一个概念。

### 要点

- runtime 提供可信当前身份：

```ts
current_identity = {
  id: actor_id,
  type: "actor"
}
```

- auth 继续使用可信 runtime `role_id`。
- daemon / mailbox 内部可以继续使用路由结构。
- service 层在需要投递时，通过 identity resolver 查出路由数据。
- actor-facing / web-facing contract 只接受 identity id。

### 注意事项

- actor-facing tool 不暴露 `actor_address`。
- web / public API 不要求 `role_id + actor_id`。
- payload 里的 role 不可信。
- external identity 没有 actor runtime，也没有 daemon route。

## 阶段 3：Message / Conversation

### 核心问题

消息系统应该表达“我和目标 identity 的对话”，而不是暴露路由结构或旧存储形态。

### 目标形态

```ts
conversation.identity_ids
message.from_identity_id
message.to_identity_id
message_state.owner_identity_id
event.visible_to_identity_id
connection.identity_id
```

### 工具语义

```ts
message__send(target_identity_id, content)
message__conversation(target_identity_id, limit?)
message__get(message_id)
message__contacts()
```

### 要点

- actor 查询历史基于 `current_identity_id + target_identity_id`。
- actor 不通过 `message_id` 主动发现对话历史。
- `message_id` 只用于读取某条具体消息。
- conversation 记录直接保存相关 identity ids。
- message state 归属到 identity，不归属到 role 或 routing address。

### 注意事项

- 不设计新的对话身份模型。
- 不设计多种公共 conversation 定位方式。
- 不让 actor 传 routing address。
- 不保留没有实现语义的 schema 字段。
- 当前代码里的旧命名只作为迁移对象，不进入新设计语言。

## 阶段 4：Web / External Identity

### 核心问题

external user 需要进入 Identity 体系，但不能被做成 actor。

### 目标方向

```ts
GET  /api/web/im/session -> identity
POST /api/web/im/messages -> target_identity_id
GET  /api/web/im/conversations/direct?identity_id=...
```

### 要点

- web session 认证后解析为 external identity。
- `connection_key` 只负责认证，不是业务身份。
- web 发消息使用 `target_identity_id`。
- web 查 direct conversation 使用 `identity_id`。
- response 可以 hydrate 展示信息。

### 注意事项

- external identity 没有 `role_id`。
- external identity 没有 daemon route。
- external identity 不参与 actor runtime。
- external 只是 identity 的一种 `type`。

## 阶段 5：Product Ownership

### 核心问题

track、task、artifact、comment 的归属也应该使用统一 Identity。

### 目标方向

```ts
track.owner_identity_id
task.owner_identity_id
artifact.created_by_identity_id
artifact.author_identity_ids
comment.by_identity_id
comment.mentioned_identity_ids
comment.resolved_by_identity_id
```

### 要点

- ownership 判断比较 identity id。
- 如果某类对象只允许 actor 拥有，用 `type == "actor"` 做业务约束。
- 展示信息通过 identity projection hydrate。
- 历史展示快照只有在产品明确需要不可变历史展示时才增加。

### 注意事项

- 不用 routing address 表达 owner。
- 不用 role id 表达 owner。
- 不让 ownership 层依赖 daemon routing 结构。
- 不把 message / conversation 结构搬到 product ownership。

## 阶段 6：Contract 替换与验证

### 核心问题

identity 成为系统 contract 后，不能留下并行公共定位方式。

### 要点

- tool schema、HTTP API、repo、tests 全部以 identity 字段为准。
- 旧字段只允许作为一次性迁移输入。
- 新写入路径只写 identity 字段。
- 测试重新锁定新语义。

### 验证路径

- actor 给 actor 发消息。
- external 给 actor 发消息。
- actor 查询与目标 identity 的 conversation。
- external 查询与目标 identity 的 conversation。
- message state 归属到正确 identity。
- daemon delivery 通过 identity resolver 完成路由解析。
- auth 仍然只信 runtime role。
- track / task / artifact / comment ownership 使用 identity id。

## 红线

- 不设计双公共定位路径。
- 不让 `actor_address` 出现在 actor-facing 或 web-facing contract。
- 不让 `role_id + actor_id` 和 `identity_id` 并存为公共 locator。
- 不把 credential、routing address、role、display metadata 当 identity。
- 不保留旧字段作为新写入路径。
- 不引入未批准的新身份概念。

## 一句话总结

全系统只用 `IdentityRef { id, type }` 表达“谁”；auth、routing、display、session 都是按需解析的 projection；actor 和 external 进入同一套 Identity 底层，但 external 不变成 actor。
