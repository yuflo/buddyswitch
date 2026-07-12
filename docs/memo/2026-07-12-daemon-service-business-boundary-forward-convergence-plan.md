# Daemon Service 业务边界前进式收敛实施计划

> **执行要求：** 实施本计划时使用 `superpowers:test-driven-development`，按任务逐项完成 RED → GREEN → 清理 → 验证；全部完成后使用 `superpowers:verification-before-completion` 做新鲜验收。本文描述一个终态架构，任务编号只代表安全的实现顺序，不代表过渡架构、灰度阶段或双轨兼容期。

**日期：** 2026-07-12

**范围：** actor instance daemon、Task Sys daemon 接入、IM/Track/Browser 入站适配、WebUI Task Sys 读取、相关 CLI/tool runtime 与架构测试

**性质：** 内部架构直接替换；不保留旧 import、旧 mailbox method、旧 status 字段、旧状态 schema 兼容或旧 service locator 入口

## 1. 任务目标重述

本次升级的目标不是把 `_task_sys_status_payload` 换一个文件存放，也不是给现有耦合再包一层薄适配器。目标是一次性把 daemon service 收敛为真正的通用宿主控制与投递基础设施，并让 Task Sys、IM、Track、Browser 各自拥有自己的业务语义和适配代码。

完成后的系统只能有一条当前路径：

1. daemon core 只拥有进程生命周期、actor/runtime 上下文、通用 mailbox 请求、通用 trigger/schedule、handler 调度和宿主运行状态。
2. Task Sys 自己拥有任务状态机、存储、读模型、runtime 指令、mailbox 命令名及其参数校验。
3. IM、Track、Browser 自己拥有各自的业务投递与 handler 语义；它们只能调用通用 daemon 能力或公开的产品服务。
4. `instance_daemon.py` 是产品模块装配到通用 daemon 的唯一 composition root。
5. Web API 直接组合 host-control facts 与 Task Sys 公共 read model；daemon status 不再充当 Task Sys 数据通道。
6. 被替换的代码、测试、字段、命令、导入和文档表述全部删除，不保留 alias、fallback、adapter-to-old-path、双写或旧 schema guard。

一句话终态：**daemon 托管业务模块，但不知道业务模块；产品模块使用 daemon 能力，但不把产品语义塞回 daemon。**

## 2. 从 `docs/bitter` 提炼出的硬约束

以下不是建议，而是本计划的验收条件：

| 原则 | 本次落地要求 |
|---|---|
| 修复 owning layer | Task 状态与命令归 Task Sys；IM/Track/Browser 语义归各自产品模块；daemon 只保留通用宿主能力。 |
| 测试资源生命周期 | 会启动 daemon、socket、thread 或 Web server 的测试必须自己清理；先跑 focused tests，再检查残留进程/端口，最后跑扩大测试集。 |
| 并行修改边界 | 把高 churn 的 `daemon_core.py`、`daemon_client.py` 拆成稳定通用合同与局部产品适配，减少所有功能都修改中心文件的结构性冲突。 |
| 语义残留清理 | 行为测试通过后仍必须扫描旧 method、旧 status 字段、旧 import、旧 handler、旧 schema 字段和旧文案；活跃代码与测试都不能继续教授旧路径。 |
| 共享边界不能持续特判 | generic mailbox 只接受不透明 command registry；不能继续在 transport 中增加 `if method == "mailbox.<product>..."`。 |
| 产品 core 拥有模型 | Task Sys domain/service 提供唯一 actor task projection；CLI、Web、tool 都是它的投影消费者。 |
| 端到端合同切片 | 每条消费者动作必须验证到可观察结果，不能只证明某个 helper 被调用。 |
| 精确当前 schema | daemon state 只接受当前字段 allowlist；删除仍记忆 retired fields 的 `pop`/guard，不以兼容名义保留历史 schema。 |

## 3. 当前架构现状与关键问题

### 3.1 已经正确的部分

- Browser UI 只调用 Web HTTP API，没有 import Task Sys 或调用 actor runtime tool handler。
- Web API 组合 domain/service read model 的方向正确；`web_management.py -> scripts.env.domain.task_sys` 本身不是违规依赖。
- Task Sys domain/runtime/tool 没有反向依赖 WebUI。
- `notification_center.py` 已采用通用 `InboundSourceRegistration`；`instance_daemon.py` 已具备 composition root 的雏形。
- `central_daemon_core.py` 主要处理 actor registry、reachability 与 signal forwarding，不应因本次改造引入 Task Sys 语义。
- 通用 trigger/schedule 是合理 daemon 能力，应该保留其通用性。

### 3.2 daemon core 直接拥有 Task Sys 语义

当前 `tools/launcher/daemon_core.py`：

- 直接 import `tools.launcher.task_sys_runtime` 和 `scripts.env.domain.task_sys`。
- `DaemonRuntime` 暴露 `execute_task_sys_instruction`、`cleanup_task_sys_side_lease` 等产品方法。
- mailbox dispatch 直接识别 Task Sys 方法。
- `_task_sys_status_payload` 直接推导 `objects/task-sys/tasks` 存储路径、读取 JSON、重复 active/recoverable 分类并塑造 DTO。
- `daemon_status()` 把 `task_sys` 作为控制面状态返回。

这破坏了 daemon service 的业务解耦：控制面知道产品存储布局、状态语义、DTO 结构和 runtime 方法。历史 Phase 3 要求“daemon 调用 Task Sys read API，不复制状态机”；`b46ce12` 首次用直接扫描存储偏离该设计，`f0d6f17` 又扩展第二套 recoverable/summary 语义。当前不是偶然的一处 import，而是一条已经扩散到 status、mailbox、CLI 和测试的错误边界。

### 3.3 generic mailbox 与 client 被产品方法污染

当前 `tools/launcher/daemon_mailbox.py`：

- constructor 接收 `task_sys_dispatcher`。
- transport 层硬编码 `mailbox.task_sys.execute_instruction` 与 `mailbox.task_sys.cleanup_side_lease`。
- transport 层负责 Task 参数校验、分支和错误语义。

当前 `scripts/env/tool_runtime/daemon_client.py`：

- 暴露 Task Sys 专用 helper 和 CLI 子命令。
- 为 Task Sys 持有特殊 timeout。
- `wake_im_actor` 同时承担 IM payload 校验、身份解析、中心 reachability 和本地 trigger 投递。

这让本应稳定的通用 client/transport 成为产品 service locator；以后每加一个产品动作都会继续修改中心模块。

### 3.4 `DaemonAccess` 模糊了依赖

当前 `scripts/env/tool_runtime/context.py` 的 `DaemonAccess` 同时提供：

- actor directory/reachability；
- generic signal delivery；
- Track comment 投递；
- Task Sys runtime 指令；
- IM actor wake。

`ToolContext.daemon` 因而把多个不同所有者的能力压成一个“什么都能做”的入口。调用方无法从依赖声明判断自己需要的是目录、信号、Task runtime 还是 IM delivery，也使 generic daemon client 很难保持产品无关。

### 3.5 Task read model 有双轨与重复扫描

当前一次 Web actor console 刷新会发生：

1. instance status 调用触发 daemon 自己扫描 Task 存储；
2. Web 调用 `active_tasks_for_actor` 再扫描一次；
3. Web 调用 `recoverable_tasks_for_actor` 再扫描一次。

前端约每三秒刷新，因此重复逻辑也是持续 I/O 和语义漂移风险。Task tool list 也分别调用 active/recoverable。系统没有一个由 Task Sys 拥有的一次扫描 actor projection。

这里还要区分 identity 与 Task target：稳定身份是 `IdentityRef(id="act-...", type="actor")`；`role_id` 是 `ActorIdentityProfile` 上的角色属性。Task 记录里的 `actor_target={"actor_id": ..., "role_id": ...}` 是任务执行目标绑定，不是另一套复合身份。公共 read API 应接收 typed `ActorIdentityProfile`，由 Task Sys 转换并校验自己的存储投影，不能要求每个调用方手拼两个可能漂移的字段。

### 3.6 Browser 跨越 daemon 内部状态边界

`tools/launcher/browser_runtime_manager.py` 为取消 Browser 自己的 pending schedules，直接 import `daemon_core`、计算 daemon state path 并实例化 `DaemonState`。Browser 因此知道 daemon 状态文件和内部类，而不是调用一个稳定的通用 schedule-state API。

### 3.7 活跃的死代码与历史兼容知识

- `task_checkout_handler.py` 的 `record_completed_turn` 已是 no-op，却仍被 `instance_daemon.py` import 和注册。
- `DaemonRuntime.submit_parent_prompt`、daemon origin-turn/runtime-call 记录及其 status projection 没有生产调用者，只剩测试维护。
- `DaemonState.load` 仍显式 `pop` retired fields 和旧 daemon action 字段，活跃 runtime 因而继续认识历史 schema。
- 业务 handlers 直接 import `daemon_core.HandlerResult`，把稳定合同绑在巨大实现模块上。

这些都必须随主改造删除；只搬走 Task Sys status 而保留它们，不符合“无残留”。

### 3.8 测试正在保护错误架构

- `test_daemon_core_decoupling.py` 只禁止旧 `task_management`/`task_tui`，没有禁止当前 `task_sys`。
- 部分 mailbox generic 测试没有检查 Task Sys token/import。
- `test_daemon_status_includes_task_sys_active_projection` 明确要求 daemon status 包含 Task Sys。
- tests 锁定了 `DaemonRuntime` 的 Task 方法、mailbox Task 方法和 generic daemon client 的 Task helpers。

因此当前测试全绿只能证明旧行为稳定，不能证明边界正确。实施必须先把架构意图改写为会失败的新测试，再移动代码。

## 4. 目标架构

```text
Browser UI
  -> Web Management API
       -> host control API -----------------------------> generic daemon status
       -> Task Sys actor_task_projection() ------------> Task Sys repo

Actor Task tool / CLI Task ingress
  -> TaskSysRuntimeClient
       -> generic daemon mailbox request
            -> opaque application command registry
                 -> TaskSysDaemonAdapter
                      -> Task Sys runtime/domain/repo

IM post-write
  -> ImActorDelivery
       -> central actor directory/reachability
       -> generic local trigger
            -> IM handler
                 -> TaskSysDaemonAdapter when task lifecycle work is required

Track comment
  -> generic signal delivery
       -> Track handler
            -> TaskSysDaemonAdapter when task lifecycle work is required

Browser schedule
  -> generic daemon schedule API
       -> Browser handler/runtime manager
            -> public daemon schedule-state cancellation API

instance_daemon.py
  -> registers Task/IM/Track/Browser handlers and application commands
  -> is the only product-to-daemon composition root
```

### 4.1 依赖方向

允许：

- product adapter -> generic daemon contracts/client
- product adapter -> its own domain/runtime/repo
- instance composition root -> generic daemon + product adapters
- Web API -> host-control API + product read model

禁止：

- generic daemon core/mailbox/client/state/runtime -> Task Sys、IM、Track、Browser
- generic daemon status -> product projection
- Browser/Track/IM -> daemon state file or daemon implementation class
- product tool -> `ToolContext.daemon` service locator
- transport -> hardcoded product method name、product payload schema、product timeout 或 product error
- 新路径 -> 旧路径 fallback/alias/双写

### 4.2 模块职责与落点

| 模块 | 终态职责 |
|---|---|
| `tools/launcher/daemon_contracts.py` | `HandlerResult`、`DaemonContext`、daemon handler typing、generic application command 合同；零产品 import/token。 |
| `tools/launcher/daemon_state.py` | 当前 daemon state schema、原子读写、schedule 查询/取消公共 API；精确当前 allowlist。 |
| `tools/launcher/daemon_runtime.py` | handler 可用的宿主 runtime facts，例如 `parent_activity`；不含 Task/IM/Track/Browser 方法。 |
| `tools/launcher/daemon_core.py` | 生命周期、通用 trigger/schedule/dispatch/status orchestration；不塑造产品 DTO。 |
| `tools/launcher/daemon_mailbox.py` | 通用控制方法 + 不透明 application command registry；不知道 registry key 的业务含义。 |
| `scripts/env/tool_runtime/daemon_client.py` | 通用 mailbox、trigger、schedule、actor directory/signal primitive；没有产品 helper/CLI。 |
| `tools/launcher/task_sys_daemon_adapter.py` | Task Sys daemon 内调用、server-side payload 校验、runtime 委托与业务错误映射。 |
| `scripts/env/tool_runtime/task_sys_runtime_protocol.py` | Task Sys client/adapter 共享的当前 command keys 与 wire shape；不包含 transport 实现。 |
| `scripts/env/tool_runtime/task_sys_runtime_client.py` | Task Sys 外部 runtime client/CLI；通过 generic mailbox 请求 Task adapter。 |
| `scripts/env/tool_runtime/im_actor_delivery.py` | IM actor 目标校验、身份/reachability、local trigger 投递。 |
| `tools/launcher/instance_daemon.py` | 唯一 composition root，装配 product handlers 与 application commands。 |
| `scripts/env/domain/task_sys.py` | 唯一一次扫描的 actor task projection 与 Task 状态语义。 |
| `tools/launcher/web_management.py` | 将 host facts 与 Task projection 组合为 Web DTO；不通过 daemon 读 Task。 |

### 4.3 最小稳定合同，不建设通用框架

generic mailbox 只需要一个小合同，不引入 plugin system、event bus、规则引擎或 workflow DSL：

```python
ApplicationCommand = Callable[[Mapping[str, object]], Mapping[str, object]]
ApplicationCommandFactory = Callable[
    [DaemonContext], Mapping[str, ApplicationCommand]
]
```

`DaemonMailbox` 对 application command 只做三件事：查 key、调用 callable、把 generic success/error envelope 写回响应。key 与 payload 的含义完全由注册方拥有。

Task Sys runtime protocol 定义当前且唯一的 keys，client 与 adapter 共同 import，不能各自复制字符串：

```python
EXECUTE_INSTRUCTION = "task_sys.execute_instruction"
CLEANUP_SIDE_LEASE = "task_sys.cleanup_side_lease"
```

旧 `mailbox.task_sys.*` 名字直接删除，不注册 alias，也不在 client 失败后重试旧方法。

### 4.4 Task Sys 唯一读模型

`scripts/env/domain/task_sys.py` 新增一个公开函数：

```python
def actor_task_projection(*, actor_profile: ActorIdentityProfile) -> dict[str, object]:
    """Read Task records once and return canonical actor-visible summaries."""
```

返回结构由 Task Sys 拥有，至少包含：

- `tasks`
- `active_tasks`
- `recoverable_tasks`
- `active_count`
- `recoverable_count`

`tasks`、`active_tasks`、`recoverable_tasks` 都使用同一个公开 task summary shape。Web 可以再塑造浏览器 DTO，但不能重新判断 Task 状态；task tool/context 也从该 projection 读取，不能再各自扫描和分类。

identity core 继续唯一拥有“谁”：`IdentityRef` 与 `ActorIdentityProfile`。Task Sys 只拥有“任务指向该 actor，并按其 profile role 执行”的语义。本次保留 Task 记录当前 `actor_target` 存储 shape，由 domain 内部从 profile 规范化；不把 daemon 解耦扩张成 Task 持久化 schema 重建。

## 5. 明确解决的关键问题

### 5.1 前面 WebUI 与 Task Sys 耦合问题是否自然解决

会，而且按正确边界解决：

- Browser 仍然只依赖 Web DTO，不增加任何 Task Sys 知识。
- Web API 保留对 Task Sys 公共 read model 的单向依赖，这是正确的 product-view composition，不需要为了“零 import”绕到 daemon。
- daemon status 的 `task_sys` 字段、存储扫描和重复 projection 全部删除。
- Web actor console 改为一次读取 Task Sys projection；不再借 host-control status 夹带产品状态。

因此解决的不是“Web 永远不能 import Task Sys”，而是消除错误的 `Web -> daemon status -> Task storage` 隐性路径，并让唯一的显式依赖落在 owner 提供的 read API 上。

### 5.2 daemon service 的业务解耦是否已被破坏

当前确实已被破坏，破坏面包括 read、command、client、context、status、state 与 tests。终态验收不是检查某一个 helper 是否搬走，而是要求 generic daemon 模块对 `task_sys`、`im`、`track`、`browser` 的产品 token 与 import 都为零；composition root 是唯一允许看见双方的地方。

### 5.3 为什么直接面向终态

这是内部架构且没有已声明的外部 mailbox/status 合同或不可逆数据迁移。本仓库的 sharp-forward 原则要求直接替换。分任务只用于让测试红绿节奏清晰；合并时不会存在：

- old/new mailbox method 并存；
- daemon status 新旧字段并存；
- `DaemonAccess` 与新显式 accessors 并存；
- old state fields 与 current schema 并存；
- old Task projection 与 canonical projection 并存。

### 5.4 host-control status 删除 Task 后，Task 可观测性在哪里

- Web actor console：Task Sys projection。
- actor runtime/tool：`task_sys.list/get/...`。
- CLI actor input 与 Task runtime：Task Sys client/adapter。

daemon status 只回答 daemon 是否 ready、handler/schedule/runtime host facts，不再回答产品 Task 状态。若未来需要独立运维 Task CLI，应作为 Task Sys 产品入口设计，不把字段塞回 daemon status；该能力不在本次范围内。

## 6. 不在本次范围内

- 不重写 Task Sys 状态机、side-thread lease 业务语义或 parent/side capability 模型。
- 不重写 Task Sys `actor_target` 持久化 schema；公共边界改用现有 identity core 类型并在 domain 内校验当前存储投影。
- 不改变 Central daemon 的 actor registry/reachability 协议。
- 不改变 IM message 持久化与 post-write 业务语义。
- 不改变 Track comment 产品语义。
- 不改变 Browser TTL、页面生命周期或 WebUI 视觉交互。
- 不建设 generic plugin/event/workflow/rule framework。
- 不为旧内部 JSON、mailbox method、import path、status 字段或 service locator 提供迁移兼容。

## 7. 实施计划

### Task 1：建立终态架构文档与稳定 handler 合同

**Files:**

- Create: `docs/arch/daemon-service-architecture.md`
- Create: `tools/launcher/daemon_contracts.py`
- Modify: `tools/launcher/daemon_core.py`
- Modify: `tools/launcher/daemon_triggers.py`
- Modify: `tools/launcher/im_wake_handler.py`
- Modify: `tools/launcher/track_comment_added_handler.py`
- Modify: `tools/launcher/browser_page_expired_handler.py`
- Modify: `tools/launcher/browser_release_handler.py`
- Modify: `tests/test_daemon_core_decoupling.py`
- Modify: `tests/test_daemon_communication_boundary.py`
- Create: `tests/test_daemon_contracts.py`

**Step 1: 写稳定架构文档**

`docs/arch/daemon-service-architecture.md` 只描述终态稳定合同：generic daemon 职责、product adapter 职责、composition root、status 边界、mailbox application command 合同和禁止依赖。它不是本文的执行步骤镜像，也不记录历史迁移路径。

**Step 2: 为稳定合同写 RED tests**

先只锁定本任务能够完成并保持绿色的合同边界：

```python
from daemon_contracts import DaemonContext, DaemonHandler, HandlerResult
```

补充行为断言：

- `HandlerResult.handled/ignored/failed` 保持当前可观察 shape。
- `DaemonContext` 只承载稳定宿主身份、路径、role、socket 与 permission facts。
- handler protocol 能表达 `handles(trigger)` 与 `handle(context, state, runtime, trigger)`。
- 所有业务 handler 的合同 import 来自 `daemon_contracts`，不再从 `daemon_core` 取得 `HandlerResult`。
- `daemon_contracts.py` 不 import `daemon_core` 或任何产品模块。

完整的 generic-daemon 产品零知识 source boundary test 在 Task 7 加入；不能在 Task 1 先提交一个要等 Task 3–6 才能变绿的总断言。

**Step 3: 运行 RED**

Run:

```bash
python -m unittest -q \
  tests.test_daemon_core_decoupling \
  tests.test_daemon_communication_boundary \
  tests.test_daemon_contracts
```

Expected: FAIL，原因是 `daemon_contracts.py` 尚不存在，且 handlers 仍从 `daemon_core` 取得合同；不能因无关 fixture 失败。

**Step 4: 实现合同并切换 imports**

创建 `daemon_contracts.py`，移动而非复制 `HandlerResult` 与 `DaemonContext`，定义最小 handler protocol。`load_daemon_context()` 仍由 core 负责 I/O，但返回稳定合同对象。切换 core、trigger router 与全部业务 handlers 后，从 `daemon_core.py` 删除原合同定义。不得保留 re-export alias。

**Step 5: 运行 GREEN**

Run:

```bash
python -m unittest -q \
  tests.test_daemon_contracts \
  tests.test_daemon_core_decoupling \
  tests.test_daemon_communication_boundary \
  tests.test_daemon_trigger_router \
  tests.test_im_wake_handler \
  tests.test_track_comment_added_handler \
  tests.test_browser_page_expired_handler
```

Expected: PASS；业务 handlers 不再依赖 daemon implementation module 来取得合同。

**Step 6: Commit**

```bash
git add docs/arch/daemon-service-architecture.md \
  tools/launcher/daemon_contracts.py \
  tools/launcher/daemon_core.py \
  tools/launcher/daemon_triggers.py \
  tools/launcher/im_wake_handler.py \
  tools/launcher/track_comment_added_handler.py \
  tools/launcher/browser_page_expired_handler.py \
  tools/launcher/browser_release_handler.py \
  tests/test_daemon_core_decoupling.py \
  tests/test_daemon_communication_boundary.py \
  tests/test_daemon_contracts.py
git commit -m "refactor: establish stable daemon handler contracts"
```

### Task 2：抽出通用 state，并删除 checkout/parent-submit 死路径

**Files:**

- Create: `tools/launcher/daemon_state.py`
- Modify: `tools/launcher/daemon_core.py`
- Modify: `tools/launcher/instance_daemon.py`
- Delete: `tools/launcher/task_checkout_handler.py`
- Create: `tests/test_daemon_state.py`
- Modify: `tests/test_daemon_core.py`
- Modify: `tests/test_daemon_trigger_router.py`
- Modify: `tests/test_im_wake_handler.py`
- Modify: `tests/test_track_comment_added_handler.py`
- Modify: `tests/test_browser_page_expired_handler.py`
- Modify: `tests/test_daemon_service_contract.py`
- Delete: `tests/test_task_checkout_handler.py`

**Step 1: 为 current state schema 写 RED tests**

断言持久化 schema 只有当前字段：

```python
CURRENT_STATE_KEYS = {
    "actor_id",
    "main_thread_id",
    "ready",
    "last_error",
    "handlers",
    "scheduled_trigger_ids",
    "scheduled_triggers",
}
```

测试 unknown/retired key 时必须走统一 invalid-state 错误，不能按名字静默 `pop`。同时写 schedule cancellation 公共 API 的行为测试：只删除匹配 actor/thread/source-owner 的 pending schedule，保留其他 owner 的 schedule，并原子保存。

Run RED:

```bash
python -m unittest -q tests.test_daemon_state tests.test_daemon_core
```

Expected: FAIL，原因是 state 仍位于 core、仍接受 retired fields，且新 current-schema tests 尚未满足；不能因临时目录或 daemon fixture 泄漏失败。

**Step 2: 抽出 contracts**

把 `HandlerResult`、handler protocol/context typing 移到 `daemon_contracts.py`。所有业务 handler 只 import 该稳定合同；`daemon_core.py` 负责执行合同，不再是合同定义者。

**Step 3: 抽出 current-only state**

把 `DaemonState`、state file 解析/原子保存和 schedule-state 操作移到 `daemon_state.py`。删除：

- `LEGACY_STATE_FIELDS`；
- retired field 的定向 `pop`；
- daemon origin-turn state；
- daemon runtime-call state；
- 旧 daemon action 字段知识。

加载时先验证 object，再用 `unknown = set(payload) - CURRENT_STATE_KEYS` 做精确拒绝。这里不保留“先清洗再读”的兼容行为。

**Step 4: 删除没有生产调用者的 runtime 路径**

从当前 `DaemonRuntime` 与 state 删除没有生产调用者的 parent-submit/provenance 路径：

- `submit_parent_prompt`；
- `record_daemon_origin_turn`；
- `record_runtime_call`；
- 相应 id/state/status projection；
- 因死路径而存在的 `parent_thread_submit` import。

本任务暂不复制或移动仍被 IM/Track 使用的 Task methods；它们在 Task 3 与 adapter 同一 RED/GREEN 切片中被直接替换，随后把只剩 `parent_activity` 的 host runtime 移到 `daemon_runtime.py`。

**Step 5: 删除 no-op checkout residue**

删除 `task_checkout_handler.py` 与测试，从 `instance_daemon.py` 移除 import/registration。若没有可观察产品行为，就不保留一个永远返回 ignored 的 handler 来象征历史设计。

**Step 6: 运行 GREEN 与回归**

Run:

```bash
python -m unittest -q \
  tests.test_daemon_contracts \
  tests.test_daemon_state \
  tests.test_daemon_core \
  tests.test_daemon_trigger_router \
  tests.test_im_wake_handler \
  tests.test_track_comment_added_handler \
  tests.test_browser_page_expired_handler \
  tests.test_daemon_service_contract \
  tests.test_instance_daemon_entrypoint
```

Expected: PASS；state 文件未知字段被精确拒绝，现有 trigger/handler 行为不变，测试集不再 import 已删除 checkout handler。

**Step 7: Commit**

```bash
git add -A -- \
  tools/launcher/daemon_state.py \
  tools/launcher/daemon_core.py \
  tools/launcher/instance_daemon.py \
  tools/launcher/task_checkout_handler.py \
  tests/test_daemon_state.py \
  tests/test_daemon_core.py \
  tests/test_daemon_trigger_router.py \
  tests/test_im_wake_handler.py \
  tests/test_track_comment_added_handler.py \
  tests/test_browser_page_expired_handler.py \
  tests/test_daemon_service_contract.py \
  tests/test_task_checkout_handler.py
git commit -m "refactor: isolate daemon state and remove dead runtime paths"
```

### Task 3：用不透明 application commands 替换 Task-specific mailbox

**Files:**

- Create: `tools/launcher/task_sys_daemon_adapter.py`
- Create: `tools/launcher/daemon_runtime.py`
- Create: `scripts/env/tool_runtime/task_sys_runtime_protocol.py`
- Create: `scripts/env/tool_runtime/task_sys_runtime_client.py`
- Modify: `tools/launcher/daemon_contracts.py`
- Modify: `tools/launcher/daemon_mailbox.py`
- Modify: `tools/launcher/daemon_core.py`
- Modify: `tools/launcher/instance_daemon.py`
- Modify: `tools/launcher/im_wake_handler.py`
- Modify: `tools/launcher/track_comment_added_handler.py`
- Modify: `scripts/env/tool_runtime/daemon_client.py`
- Modify: `scripts/env/tool_runtime/context.py`
- Modify: `scripts/env/tools/task_sys/_impl.py`
- Modify: `buddyswitch-codex`
- Create: `tests/test_task_sys_daemon_adapter.py`
- Create: `tests/test_task_sys_runtime_client.py`
- Modify: `tests/test_daemon_mailbox.py`
- Modify: `tests/test_daemon_service_contract.py`
- Modify: `tests/test_task_sys_runtime_executor.py`
- Modify: `tests/test_daemon_core.py`
- Modify: `tests/test_im_wake_handler.py`
- Modify: `tests/test_track_comment_added_handler.py`
- Modify: `tests/test_prepare_runtime_context.py`
- Modify: `tests/test_env_tool_response_contract.py`

**Step 1: 为 generic dispatch 和 Task adapter 写 RED tests**

覆盖：

- mailbox 可 dispatch 注册的任意 command key 并返回统一 envelope；
- 未注册 key 返回 generic unknown-method error；
- duplicate command key 在 daemon 启动时立即失败；
- registry key 为空或 handler 非 callable 时启动失败；
- Task payload validation、Task error mapping、65 秒 execution timeout policy 全部由 Task client/adapter 测试持有；
- generic mailbox/client 测试不出现 Task Sys 方法名。

Run RED:

```bash
python -m unittest -q \
  tests.test_daemon_mailbox \
  tests.test_task_sys_daemon_adapter \
  tests.test_task_sys_runtime_client
```

Expected: FAIL，原因是 product adapter/client/protocol 尚不存在，mailbox 仍硬编码 Task methods；不能靠调整旧断言获得通过。

**Step 2: 实现 generic registry**

在 `daemon_contracts.py` 增加 `ApplicationCommand` / `ApplicationCommandFactory` 最小类型合同。`run_daemon` 接收 `application_command_factories`；daemon context 构造完成后解析 factories 并生成一个只读 key → callable map，再交给 `DaemonMailbox`。transport 不 introspect key 前缀，不按产品类型分支。

控制面自有方法仍可由 mailbox 明确处理，例如 readiness/status/shutdown；产品命令统一经 registry。两者 key 冲突必须 fail fast。

**Step 3: 实现 Task Sys adapter**

`task_sys_daemon_adapter.py`：

- import Task Sys runtime protocol 的唯一 current command keys；
- 校验 `instruction`、`task_id`、`reason` 等 Task payload；
- 调用 `task_sys_runtime.execute_instruction` / cleanup service；
- 把业务失败转换为 Task client 能理解的当前错误合同；
- 提供 `command_handlers(context)` 给 composition root；
- 提供 daemon 内 handler 直接调用的 typed functions，避免 handler 绕一圈 socket 调自己。

**Step 4: 实现 Task Sys runtime client/CLI**

`task_sys_runtime_client.py` 使用 `daemon_client.request_mailbox()` 这个 generic primitive，并与 adapter 共同 import `task_sys_runtime_protocol.py`。Task command keys/wire shape 只在 protocol 出现；timeout 与 client-side error mapping 只在 client 出现。CLI 直接提供当前 `execute`/`cleanup-side-lease` 命令，供 `buddyswitch-codex instance_input` 使用。

**Step 5: 切换所有生产调用方并删除旧路**

- `instance_daemon.py` 注册 Task adapter factory。
- IM/Track handlers 直接调用 Task adapter typed function。
- `context.py` 增加显式 `TaskSysRuntimeAccess` / `ToolContext.task_sys_runtime`，其实现委托 Task Sys runtime client；同时从 `DaemonAccess` 删除两个 Task methods。
- `scripts/env/tools/task_sys/_impl.py` 只调用 `context.task_sys_runtime`。
- `buddyswitch-codex` 从 generic daemon-client CLI 切到 Task client CLI。
- 从 `daemon_mailbox.py` 删除 `task_sys_dispatcher` 及所有 Task-specific branches。
- 从 `daemon_client.py` 删除 Task helpers、Task CLI parser/dispatch 和 Task-specific timeout。
- 从 `daemon_core.py` 删除 Task mailbox dispatch 与 Task runtime methods；把此时只剩宿主 `parent_activity` 的 `DaemonRuntime` 移到 `daemon_runtime.py`。

没有调用方留在旧路后才允许 GREEN；不能保留旧函数作为 forwarding wrapper。

**Step 6: 运行 GREEN 与端到端 Task 切片**

Run:

```bash
python -m unittest -q \
  tests.test_daemon_mailbox \
  tests.test_task_sys_daemon_adapter \
  tests.test_task_sys_runtime_client \
  tests.test_task_sys_runtime_executor \
  tests.test_daemon_core \
  tests.test_daemon_service_contract \
  tests.test_im_wake_handler \
  tests.test_track_comment_added_handler \
  tests.test_context_binding_env_tool \
  tests.test_prepare_runtime_context \
  tests.test_env_tool_response_contract
```

Expected: PASS，并证明两条完整链路：

1. CLI actor input → Task ingress → Task client → generic mailbox → Task adapter → actor runtime result。
2. actor `task_sys` tool → Task client → generic mailbox → Task adapter → Task lifecycle observable result。

**Step 7: Commit**

```bash
git add -A -- \
  tools/launcher/task_sys_daemon_adapter.py \
  tools/launcher/daemon_runtime.py \
  scripts/env/tool_runtime/task_sys_runtime_protocol.py \
  scripts/env/tool_runtime/task_sys_runtime_client.py \
  tools/launcher/daemon_contracts.py \
  tools/launcher/daemon_mailbox.py \
  tools/launcher/daemon_core.py \
  tools/launcher/instance_daemon.py \
  tools/launcher/im_wake_handler.py \
  tools/launcher/track_comment_added_handler.py \
  scripts/env/tool_runtime/daemon_client.py \
  scripts/env/tool_runtime/context.py \
  scripts/env/tools/task_sys/_impl.py \
  buddyswitch-codex \
  tests/test_task_sys_daemon_adapter.py \
  tests/test_task_sys_runtime_client.py \
  tests/test_daemon_mailbox.py \
  tests/test_daemon_service_contract.py \
  tests/test_task_sys_runtime_executor.py \
  tests/test_daemon_core.py \
  tests/test_im_wake_handler.py \
  tests/test_track_comment_added_handler.py \
  tests/test_prepare_runtime_context.py \
  tests/test_env_tool_response_contract.py
git commit -m "refactor: move task runtime commands behind product adapter"
```

### Task 4：拆除 `DaemonAccess` service locator，归还 IM/Track/Task 能力

**Files:**

- Create: `scripts/env/tool_runtime/im_actor_delivery.py`
- Modify: `scripts/env/tool_runtime/context.py`
- Modify: `scripts/env/tool_runtime/daemon_client.py`
- Modify: `scripts/env/tool_runtime/im_client.py`
- Modify: `scripts/env/tools/track/_impl.py`
- Create: `tests/test_im_actor_delivery.py`
- Modify: `tests/test_prepare_runtime_context.py`
- Modify: `tests/test_context_binding_env_tool.py`
- Modify: `tests/test_track_comment_env_tool.py`
- Modify: `tests/test_daemon_communication_boundary.py`
- Modify: `tests/test_env_tool_response_contract.py`
- Modify: `tests/test_runtime_actor_profile.py`
- Modify: `tests/test_communication_identity_cutover.py`

**Step 1: 为显式 capability dependencies 写 RED tests**

`ToolContext` 的公开字段必须表达实际能力，而不是公开 `.daemon`：

```python
actor_directory: ActorDirectoryAccess
signal_delivery: SignalDeliveryAccess
task_sys_runtime: TaskSysRuntimeAccess
im_actor_delivery: ImActorDeliveryAccess
```

测试以下调用边界：

- IM client 只依赖 actor directory 与 IM actor delivery；
- Track tool 只依赖 actor directory 与 signal delivery；
- Task tool 只依赖 Task Sys runtime；
- generic `daemon_client.py` 不再包含 `wake_im_actor`、Track-specific function 或 Task function；
- `DaemonAccess` 和 `context.daemon` 不存在。

Run RED:

```bash
python -m unittest -q \
  tests.test_im_actor_delivery \
  tests.test_prepare_runtime_context \
  tests.test_daemon_communication_boundary
```

Expected: FAIL，原因是 IM delivery 仍在 generic client，`DaemonAccess`/`.daemon` 仍存在，显式 accessors 合同尚未满足。

**Step 2: 移动 IM delivery 业务流程**

把 `wake_im_actor` 中的 IM payload validation、actor identity resolution、reachability check、本地 trigger orchestration 移到 `im_actor_delivery.py`。它可以组合 generic actor directory 与 local trigger primitives，但 generic daemon client 不再认识 IM envelope。

**Step 3: 建立小而明确的 accessors**

在 `context.py` 只负责构造依赖；实现代码委托到各 owner client。不要重新创造一个包含所有 accessor 的 facade，也不要给 accessors 添加未被现有消费者使用的通用 extension hook。

**Step 4: 一次切换全部消费者并删除 service locator**

Task Sys capability 已在 Task 3 切到显式入口。本任务切换 `im_client.py`、Track tool 和其余 context consumers 后，直接删除 `DaemonAccess` 类型、`.daemon` 字段与旧 helper。禁止保留 deprecated property 或 `__getattr__` fallback。

**Step 5: 运行 GREEN 与产品链路测试**

Run:

```bash
python -m unittest -q \
  tests.test_im_actor_delivery \
  tests.test_prepare_runtime_context \
  tests.test_context_binding_env_tool \
  tests.test_track_comment_env_tool \
  tests.test_daemon_communication_boundary \
  tests.test_env_tool_response_contract \
  tests.test_runtime_actor_profile \
  tests.test_communication_identity_cutover \
  tests.test_im_wake_handler \
  tests.test_track_comment_added_handler
```

Expected: PASS，并证明：

- IM post-write → IM delivery → central reachability → local trigger → IM handler → Task adapter。
- Track comment → generic signal → Track handler → Task adapter。

**Step 6: Commit**

```bash
git add -A -- \
  scripts/env/tool_runtime/im_actor_delivery.py \
  scripts/env/tool_runtime/context.py \
  scripts/env/tool_runtime/daemon_client.py \
  scripts/env/tool_runtime/im_client.py \
  scripts/env/tools/track/_impl.py \
  tests/test_im_actor_delivery.py \
  tests/test_prepare_runtime_context.py \
  tests/test_context_binding_env_tool.py \
  tests/test_track_comment_env_tool.py \
  tests/test_daemon_communication_boundary.py \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_actor_profile.py \
  tests/test_communication_identity_cutover.py
git commit -m "refactor: replace daemon service locator with explicit capabilities"
```

### Task 5：建立 Task Sys 唯一 actor projection，并从 daemon status 删除 Task

**Files:**

- Modify: `scripts/env/domain/task_sys.py`
- Modify: `scripts/env/tools/task_sys/_impl.py`
- Modify: `scripts/env/tools/context/_impl.py`
- Modify: `scripts/env/tool_runtime/registry.py`
- Modify: `tools/launcher/web_management.py`
- Modify: `tools/launcher/daemon_core.py`
- Modify: `buddyswitch-codex`
- Modify: `tests/test_task_sys_substrate.py`
- Modify: `tests/test_web_management.py`
- Modify: `tests/test_daemon_service_contract.py`
- Modify: `tests/test_daemon_core.py`
- Modify: `tests/test_env_tool_active_task_gate.py`
- Modify: `tests/web_management_ui_contract.test.js`

**Step 1: 写一次扫描与分类语义 RED tests**

在 `test_task_sys_substrate.py` 用受控 repo fixture/spy 证明 `actor_task_projection(actor_profile=ActorIdentityProfile(...))` 每次调用只读取 Task records 一次，并从同一记录集合生成 `tasks`、`active_tasks`、`recoverable_tasks` 与 counts。覆盖：

- active 状态；
- recoverable 状态；
- 非目标 actor；
- execution/relation 影响；
- profile identity/role 与存储 target 一致；
- 同 identity 的不同 role 不匹配当前 Task target；
- summary 字段一致性；
- 空集合。

测试禁止 Web、tool、daemon 各自复制 active/recoverable 状态集合。

Run RED:

```bash
python -m unittest -q \
  tests.test_task_sys_substrate \
  tests.test_web_management \
  tests.test_daemon_service_contract \
  tests.test_env_tool_active_task_gate
```

Expected: FAIL，原因是 canonical profile-based projection 尚不存在、调用方仍多次扫描、daemon status 仍包含 Task projection。

**Step 2: 实现 canonical projection**

在 Task Sys domain 中接收 `ActorIdentityProfile`，把 `profile.identity.id` / `profile.role_id` 转成并校验当前 Task target 投影；随后复用唯一状态判定和公开 summary builder，一次获取 records 后完成 actor filter 与分组。现有 `active_tasks_for_actor`、`recoverable_tasks_for_actor`、`has_active_task_for_actor` 及 tool-local `_task_summary` 在全部调用方切换后同一提交删除，不能留下 wrapper。

**Step 3: 切换 Web 与 tools**

- `_actor_console` 从已验证的 actor id 与 instance role 构造 `ActorIdentityProfile`，调一次 projection，再塑造 Web DTO。
- `task_sys.list` 从 projection 选择 `tasks`/`active_tasks`/`recoverable_tasks`。
- Task tool 使用 `ToolContext.current_actor_identity_profile`；context summary 从当前 identity/active role 构造同一 profile 并使用 projection。
- runtime active-task gate 使用已经构造的 runtime actor profile 调用同一 projection，不再调用独立 boolean scan helper。
- Browser JS 继续只消费 `/api/actors/{id}/console`，不新增 Task 子路由。

**Step 4: 删除 daemon Task projection 和 status 字段**

从 `daemon_core.py` 删除 `_task_sys_status_payload`、Task storage path 推导、Task JSON 读取和 `status["task_sys"]`。从 `buddyswitch-codex instance status` 删除 Task-specific 输出。删除/重写保护旧字段的 tests。

`/api/instances/{id}/status` 继续原样表达 host-control status；它不再包含 Task。`/api/actors/{id}/console` 是 Web Task view 的唯一当前 route。

**Step 5: 运行 GREEN、Web 合同与性能语义验证**

Run:

```bash
python -m unittest -q \
  tests.test_task_sys_substrate \
  tests.test_web_management \
  tests.test_daemon_service_contract \
  tests.test_daemon_core \
  tests.test_context_binding_env_tool \
  tests.test_env_tool_active_task_gate
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
```

Expected: PASS；console 返回 active/recoverable Task DTO，daemon status 无 `task_sys`，一次 console Task 读取只触发一次 canonical projection/repo read，前端仍不调用拆分 Task 子路由。

**Step 6: Commit**

```bash
git add -A -- \
  scripts/env/domain/task_sys.py \
  scripts/env/tools/task_sys/_impl.py \
  scripts/env/tools/context/_impl.py \
  scripts/env/tool_runtime/registry.py \
  tools/launcher/web_management.py \
  tools/launcher/daemon_core.py \
  buddyswitch-codex \
  tests/test_task_sys_substrate.py \
  tests/test_web_management.py \
  tests/test_daemon_service_contract.py \
  tests/test_daemon_core.py \
  tests/test_env_tool_active_task_gate.py \
  tests/web_management_ui_contract.test.js
git commit -m "refactor: make task sys the sole owner of actor projection"
```

### Task 6：让 Browser 只使用公开 schedule-state API

**Files:**

- Modify: `tools/launcher/daemon_state.py`
- Modify: `tools/launcher/browser_runtime_manager.py`
- Modify: `tests/test_daemon_state.py`
- Modify: `tests/test_browser_runtime_manager.py`
- Modify: `tests/test_daemon_core_decoupling.py`

**Step 1: 写 RED tests**

测试 Browser release 清理只通过公开函数完成，并验证：

- 删除同 actor/main-thread、Browser owner 的 pending schedules；
- 不删除其他 source owner 或其他 actor/thread 的 schedules；
- state 不存在时返回当前明确结果；
- 保存失败时错误可观察；
- `browser_runtime_manager.py` 不 import `daemon_core`、`DaemonState` 或自行拼 daemon state path。

Run RED:

```bash
python -m unittest -q \
  tests.test_daemon_state \
  tests.test_browser_runtime_manager \
  tests.test_daemon_core_decoupling
```

Expected: FAIL，原因是 Browser 仍直接 import daemon implementation/state internals，公开 owner-scoped cancellation 合同尚未满足。

**Step 2: 实现并切换**

公开 API 放在 `daemon_state.py`，语义是通用的 owner-scoped schedule cancellation，不出现 Browser product token。Browser runtime manager 调用该 API并传自己的 owner 值。

**Step 3: 删除内部越界代码并运行 GREEN**

Run:

```bash
python -m unittest -q \
  tests.test_daemon_state \
  tests.test_browser_runtime_manager \
  tests.test_browser_page_expired_handler \
  tests.test_daemon_core_decoupling
```

Expected: PASS；Browser lifecycle 行为不变，Browser 模块不再认识 daemon state internals。

**Step 4: Commit**

```bash
git add -A -- \
  tools/launcher/daemon_state.py \
  tools/launcher/browser_runtime_manager.py \
  tests/test_daemon_state.py \
  tests/test_browser_runtime_manager.py \
  tests/test_daemon_core_decoupling.py
git commit -m "refactor: expose generic daemon schedule state boundary"
```

### Task 7：全链路验收、残留清理与架构文档复核

**Files:**

- Modify: `docs/arch/daemon-service-architecture.md`
- Modify: `docs/arch/web-interface-call-architecture.md`
- Modify: `tests/test_repo_consistency.py`

若 residue scan 发现旧路径，回到拥有该路径的前述任务修正并重跑该任务 GREEN；不在验收阶段创建泛化 cleanup layer。

**Step 1: 将关键 residue rules 固化为 repo consistency tests**

检查范围仅覆盖活跃 source/tests/stable architecture docs，不修改历史 memo 对历史事实的记录。至少固化：

```text
generic daemon modules must not contain product imports/tokens
DaemonAccess and context.daemon must not exist
mailbox.task_sys.* must not exist
daemon status task_sys projection must not exist
task_checkout_handler must not exist
LEGACY_STATE_FIELDS and retired-state targeted pops must not exist
active_tasks_for_actor/recoverable_tasks_for_actor/has_active_task_for_actor wrappers must not exist
browser_runtime_manager must not import daemon_core/DaemonState
```

source tests 优先用 Python AST/import graph；只对方法名、字段名与命令 key 使用 scoped text scan，避免靠脆弱的整仓字符串禁令误伤历史 memo。

**Step 2: 执行人工 residue scans**

Run:

```bash
rg -n \
  'mailbox\.task_sys|_task_sys_status_payload|task_sys_dispatcher|execute_task_sys_instruction|cleanup_task_sys_side_lease|DaemonAccess|context\.daemon|task_checkout_handler|LEGACY_STATE_FIELDS|daemon_origin_turn|daemon_runtime_call|submit_parent_prompt' \
  tools/launcher scripts/env tests buddyswitch-codex docs/arch
```

Expected: no matches。若新 Task client/adapter 的 typed method 名与旧 generic method 名相同，应改为 owner-local 清晰命名并通过 import-boundary test 判断；不能为了让 scan 绿而降低边界测试。

Run:

```bash
rg -n \
  'active_tasks_for_actor|recoverable_tasks_for_actor|has_active_task_for_actor' \
  tools/launcher scripts/env tests docs/arch
```

Expected: no matches；唯一读入口是 `actor_task_projection`。

Run:

```bash
rg -n \
  'from tools\.launcher\.daemon_core import (HandlerResult|DaemonState)|import tools\.launcher\.daemon_core|from daemon_core import (HandlerResult|DaemonState)|(^|[[:space:]])import daemon_core' \
  tools/launcher scripts/env tests
```

Expected: no production matches；tests 如需验证 core 可直接 import module，但不能从 core 取得已抽离合同/state。

**Step 3: 运行 focused architecture acceptance**

Run:

```bash
python -m unittest -q \
  tests.test_daemon_contracts \
  tests.test_daemon_state \
  tests.test_daemon_core_decoupling \
  tests.test_daemon_communication_boundary \
  tests.test_daemon_mailbox \
  tests.test_task_sys_daemon_adapter \
  tests.test_task_sys_runtime_client \
  tests.test_instance_daemon_entrypoint \
  tests.test_repo_consistency
```

Expected: PASS。

**Step 4: 运行六条端到端合同切片**

Run:

```bash
python -m unittest -q \
  tests.test_task_sys_runtime_executor \
  tests.test_context_binding_env_tool \
  tests.test_im_actor_delivery \
  tests.test_im_wake_handler \
  tests.test_track_comment_env_tool \
  tests.test_track_comment_added_handler \
  tests.test_web_management \
  tests.test_browser_runtime_manager \
  tests.test_browser_page_expired_handler
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
```

Expected: PASS，并覆盖：

1. CLI input 到 Task runtime 结果；
2. actor Task tool 到 Task lifecycle；
3. IM post-write 到 handler/Task adapter；
4. Track comment 到 handler/Task adapter；
5. Web console 到可见 Task panel DTO；
6. Browser schedule 到 lifecycle 与 owner-scoped cancellation。

**Step 5: 检查测试资源生命周期后再扩大验证**

运行测试前记录 BuddySwitch 相关进程与监听 socket；运行后再次记录并比较。所有测试创建的 daemon、server、thread、socket 和临时目录必须在 test cleanup 中回收。不能用手工 kill 掩盖 fixture 泄漏。

Run before the expanded test command:

```bash
snapshot_dir="$(mktemp -d)"
ps -axo pid=,command= | rg 'buddyswitch|instance_daemon|central_daemon|web_management' | sort > "$snapshot_dir/processes.before"
lsof -nP -iTCP -sTCP:LISTEN | rg 'buddyswitch|Python|node' | sort > "$snapshot_dir/listeners.before"
```

Run:

```bash
python -m unittest -q \
  tests.test_daemon_core \
  tests.test_daemon_core_decoupling \
  tests.test_daemon_communication_boundary \
  tests.test_daemon_trigger_router \
  tests.test_daemon_mailbox \
  tests.test_instance_daemon_entrypoint \
  tests.test_notification_center \
  tests.test_im_wake_handler \
  tests.test_track_comment_added_handler \
  tests.test_browser_page_expired_handler \
  tests.test_browser_runtime_manager \
  tests.test_task_sys_runtime_executor \
  tests.test_repo_consistency
```

Expected: PASS，且测试前后没有新增存活的 BuddySwitch test daemon 或 listener。

Run immediately after the expanded test command:

```bash
ps -axo pid=,command= | rg 'buddyswitch|instance_daemon|central_daemon|web_management' | sort > "$snapshot_dir/processes.after"
lsof -nP -iTCP -sTCP:LISTEN | rg 'buddyswitch|Python|node' | sort > "$snapshot_dir/listeners.after"
diff -u "$snapshot_dir/processes.before" "$snapshot_dir/processes.after"
diff -u "$snapshot_dir/listeners.before" "$snapshot_dir/listeners.after"
rm -rf "$snapshot_dir"
```

Expected: 两个 `diff` 无新增测试进程/listener。若有环境本来就在变化，必须用 PID、command、socket path 回溯到具体 fixture 并修复 cleanup，不能直接修改过滤条件隐藏泄漏。

**Step 6: 文档与 diff 验收**

- `daemon-service-architecture.md` 只描述最终边界，不包含 migration/temporary/fallback 方案。
- `web-interface-call-architecture.md` 明确 daemon status 只提供 host facts、Task view 直接使用 Task Sys projection。
- 检查所有被删除测试已被终态行为测试替代，而不是只删除断言。

Run:

```bash
git diff --check
git status --short
```

Expected: `git diff --check` 无输出；status 只包含本计划范围内的 source/tests/docs 变更。

**Step 7: Commit**

```bash
git add -- \
  docs/arch/daemon-service-architecture.md \
  docs/arch/web-interface-call-architecture.md \
  tests/test_repo_consistency.py
git commit -m "docs: lock the daemon product boundary"
```

## 8. 旧路径删除清单

实现完成时以下项目必须是“删除”，不能是 deprecated、转发或保留未调用：

| 旧路径/结构 | 终态 |
|---|---|
| `daemon_core._task_sys_status_payload` | 删除 |
| daemon status `task_sys` | 删除 |
| daemon 直接 Task storage path/JSON scan | 删除 |
| `DaemonRuntime.execute_task_sys_instruction` | 删除 |
| `DaemonRuntime.cleanup_task_sys_side_lease` | 删除 |
| `daemon_mailbox.task_sys_dispatcher` | 删除 |
| `mailbox.task_sys.execute_instruction` | 删除且无 alias |
| `mailbox.task_sys.cleanup_side_lease` | 删除且无 alias |
| generic `daemon_client` Task helpers/CLI | 删除 |
| generic `daemon_client.wake_im_actor` | 删除 |
| `ToolContext.daemon` / `DaemonAccess` | 删除 |
| `task_checkout_handler.py` | 文件与注册、测试一起删除 |
| daemon origin-turn/runtime-call records | 状态、方法、status、测试一起删除 |
| `DaemonRuntime.submit_parent_prompt` | 删除 |
| `LEGACY_STATE_FIELDS` 与 retired field pops | 删除 |
| handler 从 `daemon_core` import contract | 删除 |
| Browser 直接读取 `DaemonState` | 删除 |
| `active_tasks_for_actor` / `recoverable_tasks_for_actor` / `has_active_task_for_actor` | 调用方切换后删除 |
| CLI `instance status` Task-specific 输出 | 删除 |
| 保护上述旧行为的 tests | 用终态合同测试替换 |

## 9. 验收矩阵

| 目标 | 自动化证据 | 通过条件 |
|---|---|---|
| generic daemon 零产品语义 | source-boundary + AST import tests | generic contracts/state/runtime/core/mailbox/client 无 Task/IM/Track/Browser product import/token/branch。 |
| 唯一 composition root | entrypoint test | 只有 `instance_daemon.py` 同时装配 generic daemon 与产品 adapters。 |
| mailbox 通用 | mailbox behavior tests | 任意 registry key 可工作；transport 不知道 Task key；duplicate/invalid registration fail fast。 |
| Task runtime 单路 | adapter/client E2E tests + residue scan | 只有 Task client → generic mailbox → Task adapter；旧 method/key/helper 为零。 |
| Task read 单路 | projection read-count test | 一次 actor projection 一次 repo read；Web/tool/context 不复制分类。 |
| daemon status 纯 host facts | status contract tests | 无 `task_sys`，无产品 DTO 或存储扫描。 |
| capability 依赖明确 | context/tool tests | 无 `DaemonAccess`/`.daemon`；每个 consumer 只取得需要的 accessor。 |
| current-only state | state schema tests | 精确 allowlist；unknown key 失败；无 retired field knowledge。 |
| Browser 边界清晰 | Browser/state tests | Browser 不 import core/state internals，只调公开 owner-scoped API。 |
| dead path 清零 | repo consistency + `rg` | checkout、origin-turn、runtime-call、parent-submit 等生产无调用路径全部删除。 |
| 产品行为不回退 | 六条 E2E slices | CLI、tool、IM、Track、Web、Browser 可观察结果全部通过。 |
| 测试环境干净 | process/socket before-after check | 没有测试创建的残留 daemon/listener。 |

## 10. 完成定义

本次优化只有同时满足以下条件才算完成：

1. 目标依赖图已经成为唯一生产路径。
2. generic daemon 的源代码、公共合同和状态中不存在产品语义。
3. Task Sys command 与 read projection 都只有一个 owner 和一条调用路径。
4. WebUI 前述 coupling 问题通过“正确的单向 read-model 依赖 + 删除 daemon 投影”被完整解决。
5. `DaemonAccess`、旧 mailbox methods、旧 status 字段、旧 state schema guards、死 handler/runtime paths 全部物理删除。
6. 新边界测试先红后绿，现有关键产品行为由端到端切片证明。
7. focused、expanded relevant、Node Web contract tests 全绿，测试没有遗留进程/socket。
8. residue scans、`git diff --check` 和文档复核通过。
9. 任何未完成项都必须作为明确 blocker 报告；不能以 temporary、compatibility、future cleanup 或“测试已绿”替代完成。

## 11. 实施风险与控制

| 风险 | 控制 |
|---|---|
| 抽文件时无意改变 runtime 行为 | 先锁定现有 handler/trigger 行为测试，再机械移动 contracts/state/runtime。 |
| mailbox 切换造成 CLI/tool 丢调用 | 同一任务内切换全部生产调用方，并以两条 Task E2E 切片验收，不保留旧 key。 |
| Task projection 字段造成 WebUI 回归 | 以现有 console DTO 与 Node UI contract 为外层合同，domain projection 负责语义，Web 只负责 DTO shaping。 |
| source scan 误伤历史文档 | 自动 guard 只覆盖活跃 source/tests/stable arch docs；历史 memo 可保留历史事实。 |
| daemon test 泄漏资源导致假失败/假通过 | focused-first；fixture 自清理；扩大验证前后比较进程/socket。 |
| 为解耦引入过度框架 | registry 只是一张 key → callable 映射；没有 discovery、plugin lifecycle、priority、middleware 或 DSL。 |
| 分步提交形成可长期存在的中间态 | 每个提交保持测试可运行，但整项工作只以 Task 7 终态验收为交付；不发布、不合并任何含双轨的中间提交。 |

## 12. 计划文档自验收清单

- [x] 已完整阅读 `docs/bitter` 当前全部原则文档，并逐项转化为硬约束。
- [x] 已明确一个终态架构，而不是提供临时/兼容/双轨选项。
- [x] 已区分正确的 Web → Task read-model 依赖与错误的 daemon → Task storage/projection 依赖。
- [x] 已覆盖 read、command、client、context、state、status、handler、Browser 与 tests，不只处理 `_task_sys_status_payload`。
- [x] 已列出要创建、修改和删除的具体文件。
- [x] 每个实施任务都有 RED、GREEN、清理、验证和 commit 边界。
- [x] 已定义六条端到端合同切片和测试资源生命周期检查。
- [x] 已给出旧路径物理删除清单、自动 residue guards 和人工 scans。
- [x] 已明确非目标，避免借架构优化扩张为状态机或通用框架重写。
- [x] 已定义完成条件、风险和阻断报告规则。
