# CLI/WebUI External Control Plane Forward Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `buddyswitch-cli` 重建为面向本地操作者、自动化脚本和 AI 的机器优先外部控制接口，并让 WebUI 管理能力与 CLI 共用清晰、具体、唯一的下层实现；删除 Task Sys、Side、Goal、文本输出、历史命令与公共 CLI 反向调用等残留，不保留兼容层或双轨路径。

**Architecture:** 公共 CLI 与 WebUI Management 是并列 interface adapter；两者共同依赖私有 Host Control、Actor Session 和 external-safe Task/Track Read Projection。Web Message 继续经 IM API 进入 Message 体系；Task Sys、Actor Tool Env、App Server 等内部能力保持各自所有权。现有 Host 生命周期以 Bash 为主，本次将其直接迁移到唯一的私有 Host Control 命令并由 Python facade 暴露具体操作，不引入通用 Backend Service、HTTP/RPC 服务、事件总线或全量 Python 重写。

**Tech Stack:** Bash launcher、Python 3、`argparse`、`dataclasses`、现有 App Server JSON-RPC、`pytest`、Node `node:test`、现有 WebUI HTTP/IM router。

---

## 1. 文档性质与验收结论

本文同时是：

1. 实施计划：规定目标文件、删除文件、切换顺序、测试先行步骤和提交边界。
2. 架构验收基线：规定最终允许和禁止存在的依赖方向。
3. 产品契约验收清单：规定 CLI、WebUI、IM、Task/Track projection 的对外行为。
4. 残留清除清单：用代码扫描和行为测试证明没有旧命令、旧输出或双轨路径。

实施完成后，本文所有 `Acceptance` 条目必须有自动化证据。任何未通过项都表示改造未完成，不能用兼容分支、临时 fallback、隐藏命令或文档说明代替代码清理。

## 2. 当前瓶颈

当前核心问题不是 CLI 命令数量不足，而是产品 interface 与底层模块边界不清：

- WebUI Management 通过 `LauncherCommandRunner` 反向执行公共 `buddyswitch-codex`，使公共产品入口承担了下层 API 的角色。
- `instance input` 将基础 Actor Session 输入绕入 Task Sys ingress/runtime，混淆了 Actor Session 与任务编排语义。
- CLI 仍暴露 `instance side`、`instance goal`，把 Actor Tool Env / App Server 内部能力外溢给 external user。
- CLI 同时维护 JSON、文本、颜色、确认提示等多种产品契约，不适合脚本和 AI 稳定消费。
- Web 存在未被前端使用的 Side route；Task projection 向 Web 泄漏 `execution` 等内部执行数据。
- `legacy_command_hint`、removed-command dispatch、`--json` 分支、`submit_turn.py` 等历史结构仍在主路径附近。
- CLI、Web、shell helper 对同一 Host 生命周期存在多层字符串命令和 JSON 解析，所有者不明确。

本次最短闭环是直接建立唯一的 external control plane 下层边界，同时删除旧路径；不是继续给公共 CLI 增加 wrapper，也不是把 IM、Task Sys 或全部内部能力包装成通用 API。

## 3. 任务目标重述

### 3.1 产品目标

`buddyswitch-cli` 的定位是：

> 面向 BuddySwitch 本地操作者、自动化脚本和 AI 的机器优先 external interface，完整覆盖 Host + Actor Session 外部控制面，以及明确允许的只读产品投影。

“完整”仅指该边界内完整，不表示 CLI 必须覆盖 BuddySwitch 的所有内部能力。

WebUI 的定位是：

> 面向快速管理和观察的可视化 interface；管理能力是 bounded CLI control/query plane 的高频可视化子集，Message 与 Open TUI 分别接入 IM API 和 Actor Session Attach，不通过公共 CLI 实现。

### 3.2 架构目标

最终依赖方向必须是：

```text
Public CLI --------------------------+
                                     |
WebUI Management --------------------+--> Host Control
                                     +--> Actor Session
                                     +--> Task Read Projection
                                     +--> Track Read Projection

WebUI Message --> IM HTTP Router --> External IM Session --> Message system

Actor Tool Env --> Task Sys runtime --> Actor Session Input --> App Server
IM wake handler --> Task Sys ingress/runtime --> Actor Session Input --> App Server
```

明确禁止：

```text
WebUI Management --> public buddyswitch-codex
CLI instance input --> Task Sys ingress/runtime
CLI --> Actor Side lifecycle
CLI --> Goal lifecycle
CLI --> IM identity/session emulation
Task/Track read --> raw repository row passthrough
old path + new path selected by flag/config/fallback
```

### 3.3 开发原则

- 前进式 rebuild：直接替换，完成切换后立即删除旧实现。
- 不保留历史 alias、弃用提示、removed-command 特判或隐藏兼容命令。
- 不保留 `--json` / text 双输出，也不提供 `--output text`。
- 不双写、不双读、不通过 fallback 回旧路径。
- 一个操作只有一个 owner、一个实现、一个状态写入口。
- 每个实施切片必须同时完成新路径、调用方切换、旧代码删除和测试更新。
- 不为本次目标引入通用服务层、插件系统、事件总线或推测性抽象。
- 所有新 Python 进程必须使用 `tools/launcher/env.sh` 解析出的 `$BUDDYSWITCH_PYTHON`。

## 4. 已确认的产品边界

### 4.1 CLI 保留并重建的命令面

```text
instance roles
instance start --role <role>
instance list [--role <role>]
instance status <actor-id>
instance input <actor-id> --text <text>
instance interrupt <actor-id>
instance compact <actor-id>
instance clear <actor-id>
instance attach <actor-id>
instance resume <actor-id>
instance stop <actor-id>
instance delete <actor-id> --yes
instance capabilities <actor-id> get
instance capabilities <actor-id> set --parent <level> --side <level>

task list [--actor <actor-id>]
task get <task-id>
track list [--owner <identity-id>]
track get <track-id>

data cleanup (--role <role> | --all-data) --yes
env status
env browser status [--instance <actor-id>] [--port <port>] [--profile-dir <dir>]
env browser ensure --instance <actor-id> [--port <port>] [--profile-dir <dir>]
env browser release --instance <actor-id>
env reset --yes
web [--host <host>] [--port <port>]
```

命令名继续使用 `instance`，本次不做无产品收益的 `actor` 重命名。

### 4.2 CLI 明确删除的产品能力

- `instance side start/send/close`
- `instance goal get/set/clear`
- 所有 IM 命令族
- 所有交互式确认 prompt
- 所有 text/table/color 输出模式
- `--json` 开关
- 所有历史命令 alias、迁移提示和 removed-command 特判
- 作为内部协议使用的公共或隐藏 `__locked-*` 命令

删除公共 Side/Goal 不等于删除内部能力：

- `actor_side_thread.start_actor_side_thread()` 继续由 Task Sys runtime 使用。
- `app_server.py` 中 Goal callable 继续作为 App Server 内部能力存在。
- 删除的是 external product adapter、shell wrapper、帮助文本、路由和外部测试。

### 4.3 Actor Session Input

`instance input` 是干净的 Actor Session primitive：

```text
CLI
  -> ActorSession.input(actor_id, text)
  -> resolve actor runtime/thread/socket/permissions/capability
  -> reconcile parent thread model/effort
  -> app_server.input_turn(...)
  -> idle: turn/start
  -> active: turn/steer
```

该路径不得创建 Task Sys task，不得接受或生成 `task_id`，不得构造 task runtime frame、side frame 或 handoff frame。

### 4.4 Actor Session Attach

不新建一个名为“Actor Session TUI”的产品或运行时。保留的抽象是 Actor Session Attach：

```text
CLI instance attach ----+
                        +--> ActorSession.resolve_attach()
WebUI Open TUI ----------+        |
                                  +--> validated attach descriptor
                                  +--> codex resume --remote ...
```

CLI attach 直接 handoff 当前终端；WebUI Open TUI 在 macOS Terminal 中执行私有 attach entry。二者使用同一个 descriptor builder，不拼接公共 CLI 命令。

### 4.5 IM

- CLI 不提供 IM 命令，也不伪造 IM 实体、会话、conversation、ack 或 event 生命周期。
- 脚本和 AI 需要 IM 行为时直接使用 IM API。
- Web Message 保持 `/api/im/* -> ImHttpRouter -> ExternalImSession -> Message system`。
- IM API 不是通用 Task 查询或 Host Control API。

### 4.6 Task/Track 外部只读投影

Task list/get 只允许：

```text
task_id
source_type
status
task_desc
actor.actor_id
actor.role_id
relation.kind
relation.target_task_id
updated_at
```

必须排除：`execution`、events、runtime instructions、context、side thread id、handoff frame、raw source payload、repository path 和内部错误堆栈。

Track list 只允许：

```text
id
title
outcome
owner_identity_id
state
now
acceptance_criteria
non_goals
updated_at
comment_summary
```

Track get 在上述字段基础上允许：

```text
materials
proofs
updates
comment_threads
```

CLI 和 WebUI 不获得 Task/Track create/update/close。所有变更继续由 Actor Tool Env 和各 domain owner 承担。

## 5. 当前代码审查结论

### 5.1 P0：必须消除的边界错误

1. [`buddyswitch-codex`](../../buddyswitch-codex) 的 `instance input` 当前调用 Task Sys ingress/runtime helper，而直接输入 primitive 已存在于 `tools/launcher/app_server.py::input_turn`。这是输入语义耦合的根因。
2. `tools/launcher/web_management.py::LauncherCommandRunner` 将公共 CLI 当作 Web 的下层 API；start/clear/interrupt/stop/resume/delete/roles/list/status 均经该路径执行。
3. Web actor console 使用 `task_sys.actor_task_projection`，当前 `task_summary()` 会包含 `execution`，违反 external-safe projection 边界。

### 5.2 P1：必须随主切换删除的产品残留

1. 公共 CLI 帮助、parser 和 dispatch 仍暴露 Side、Goal、`--json` 与文本输出。
2. `legacy_command_hint()`、`fail_removed_public_command()` 和旧命令显式 dispatch 是历史兼容残留；最终应与普通 unknown command 使用同一结构化错误。
3. `tools/launcher/submit_turn.py` 的进程入口已无生产调用，但其 callable 仍被 `parent_thread_submit.py` 使用，而后者由 Task Sys runtime 调用；两层 start/steer 实现与 `app_server.input_turn` 重复。最终应将 capability reconcile + input 收归 Actor Session，Task Sys 与 CLI 共同依赖该下层 primitive，再同时删除这两个旧 helper。
4. Web Side API route 仍存在，但前端 contract test 明确没有 `/side` 和 `/side/close` 消费者。
5. `tools/launcher/actor_side_thread.py` 的 argparse/main 只服务外部 Side shell helper；内部核心函数必须保留，外部 CLI main 应删除。
6. `tools/launcher/app_server.sh` 的 Goal shell wrapper 只服务公共 Goal 命令；wrapper 应删除，Python 内部 callable 保留。

### 5.3 P2：必须统一的输出与运行时残留

1. `buddyswitch-codex`、`instance.sh`、`cleanup.sh`、`scripts/env_manifest.py`、`scripts/env_cleanup.py` 存在 `--json` 或 human 分支。
2. `browser_runtime_manager.py` 存在 `_print_human_result`、`_emit_result` 和 `--output {json,human}`；`browser_cockpit.sh` 仍调用 `--output human`。
3. Web server 启动当前打印非结构化 readiness 文本。
4. `web_management.py` 有重复 `_list_buddies()` 赋值与重复 `raise`；这些代码应在替换相关方法时自然消失，不单独扩大清理范围。

### 5.4 已经正确、不得反向破坏的边界

- `im_wake_handler.py` 直接进入 Task Sys ingress/runtime，不依赖公共 CLI input。
- Actor Tool Env 通过 daemon mailbox / Task Sys runtime 驱动 Actor，不依赖 CLI stdin。
- `actor_side_thread.start_actor_side_thread()` 是 Task Sys 内部能力，不是 CLI 所有。
- Web `/api/im/*` 已委托 `ImHttpRouter`，该链路保持。
- `tools/launcher/app_server.py` 已提供 status/ensure/stop/thread/input/interrupt/compact 等 callable primitive。
- `track_read.py` 已有 domain read 基础；本次增加明确投影而不是另建 Track 存储读取。

## 6. 目标模块与所有权

### 6.1 新建模块

| 文件 | 唯一责任 | 禁止责任 |
|---|---|---|
| `tools/launcher/cli_contract.py` | 公共 CLI JSON envelope、错误码、exit code 映射 | 业务操作、Web DTO、日志格式 |
| `tools/launcher/host_control.py` | Python-facing Host Control、输入校验、typed result/error、私有 Host command invocation | CLI parser、Web HTTP、IM、Task mutation |
| `tools/launcher/host_control.sh` | 唯一 Host lifecycle/workspace/runtime shell mechanics，JSON-only | 公共帮助、文本输出、兼容命令、Web 语义 |
| `tools/launcher/actor_session.py` | parent capability reconcile、input 与 attach descriptor/handoff；供 CLI 和 Task Sys runtime 共同调用 | Task record/编排、Side、Goal、IM |
| `tools/launcher/cli.py` | 公共参数解析、调用 operation、输出 contract | Host 生命周期实现、Web adapter、domain mutation |
| `scripts/env/domain/task_read.py` | external-safe Task list/get projection | Task mutation、raw passthrough |
| `tests/test_cli_contract.py` | JSON/错误/exit contract | Host runtime 行为 |
| `tests/test_host_control.py` | Host operation 与私有命令边界 | 公共 CLI 文案 |
| `tests/test_actor_session.py` | input/attach 行为与 Task Sys 隔离 | Task Sys runtime 业务测试 |
| `tests/test_external_query.py` | Task/Track allowlist 与只读边界 | repository 实现细节断言 |
| `tests/test_external_control_architecture.py` | 禁止依赖与残留扫描 | 重复行为测试 |

### 6.2 修改模块

| 文件 | 改造结果 |
|---|---|
| `buddyswitch-codex` | 仅加载 `env.sh`、执行 `buddyswitch_env_init`、用 `$BUDDYSWITCH_PYTHON` `exec tools/launcher/cli.py` |
| `tools/launcher/web_management.py` | 注入 Host Control / Actor Session / projections；删除公共 CLI runner 和 Side routes |
| `tools/launcher/app_server.py` | 保留 Goal callable，删除无内部消费者的 Goal CLI subcommands |
| `tools/launcher/app_server.sh` | 保留 Host Control 所需 app-server shell mechanics；删除 Goal wrappers |
| `tools/launcher/actor_side_thread.py` | 保留内部 callable；删除外部 argparse/main |
| `tools/launcher/env.sh` | 保留唯一 Python resolver；删除 public Side、submit helper 和旧 CLI 专用函数 |
| `tools/launcher/browser_runtime_manager.py` | JSON-only；删除 human formatter/output selector |
| `tools/launcher/browser_cockpit.sh` | 只消费 JSON；所有 Python 子进程用 `$BUDDYSWITCH_PYTHON` |
| `scripts/env_manifest.py` | `list-roles` 固定输出 JSON；删除 human 输出和 `--json` 参数，供 private Host Control 调用 |
| `scripts/env_cleanup.py` | 保留 cleanup plan/execute callable；删除 human printer 和输出分叉 |
| `tools/launcher/cleanup.sh` | 仅作为私有 env/data mechanics；JSON-only，无 prompt |
| `scripts/env/domain/track_read.py` | 增加 exact-allowlist external list/get projection |
| `docs/arch/web-interface-call-architecture.md` | 将公共 CLI 从 lower API 改为 peer adapter，记录 IM/Actor Session/Task/Track 边界 |

### 6.3 删除模块与代码块

以下删除是计划内确定项，不设兼容保留期：

- `tools/launcher/instance.sh`
- `tools/launcher/submit_turn.py`
- `tools/launcher/parent_thread_submit.py`
- `tools/launcher/actor_capability_cli.py`
- `tests/test_submit_turn.py`
- `tests/test_parent_thread_submit.py`
- `buddyswitch-codex` 现有函数式 parser、human formatter、Side、Goal、Task Sys input、legacy dispatch、`__locked-*` 实现
- `web_management.py::LauncherCommandRunner`
- Web Side methods/routes/tests
- `actor_side_thread.py` 外部 CLI parser/main
- `app_server.sh` Goal shell functions
- `app_server.py` Goal CLI parser branches
- browser/env/cleanup 的 human output code 和对应测试

`actor_capability_cli.py` 删除后，Host Control 直接调用 `actor_capability.py` 的 core callable；不得复制 capability 读写逻辑。`parent_thread_submit.py` 删除后，Task Sys runtime 直接调用 Actor Session Input，不得保留本地 submit wrapper。

## 7. 公共契约

### 7.1 JSON 输出

除 `--help`、`instance attach` 成功 handoff 和 `web` 持续运行外，每个公共命令只向 stdout 写一行 UTF-8 JSON。

成功：

```json
{"ok":true,"kind":"instance.status","data":{"actor_id":"reviewer-1","state":"running"}}
```

失败：

```json
{"ok":false,"error":{"code":"NOT_FOUND","message":"actor not found","details":{"actor_id":"reviewer-1"}}}
```

约束：

- key 使用 snake_case。
- JSON 使用单行，`ensure_ascii=False`，不输出 ANSI color。
- stdout 只放产品 contract；diagnostic/log 放 stderr。
- `message` 稳定、简短，不承载解析所需信息；机器字段放 `details`。
- 不在成功 payload 中重复 `ok` 或 `kind`。

### 7.2 Exit code

| Exit | Error code | 语义 |
|---:|---|---|
| `0` | - | 成功 |
| `1` | `INTERNAL_ERROR` / `EXECUTION_FAILED` | 未分类内部或下层执行失败 |
| `2` | `INVALID_ARGUMENT` / `UNKNOWN_COMMAND` | 参数或命令错误 |
| `3` | `NOT_FOUND` | actor/task/track/role 不存在 |
| `4` | `CONFLICT` / `PRECONDITION_FAILED` / `CONFIRMATION_REQUIRED` | 状态冲突或缺少显式确认 |
| `5` | `RUNTIME_UNAVAILABLE` / `TIMEOUT` | App Server/daemon/browser runtime 不可用或超时 |

不允许 operation 自行选择其它 exit code。

### 7.3 特殊命令

- `--help`：保持 argparse 文本；不承诺机器稳定契约。
- `instance attach`：校验成功后使用 `os.execvpe()` handoff 给 Codex TUI，不打印成功 JSON；handoff 前失败仍输出一行结构化错误。
- `web`：server ready 后 stdout 输出一次 `{"ok":true,"kind":"web.ready","data":{"url":"..."}}`；运行日志全部写 stderr。
- destructive command：必须显式 `--yes`；缺失时返回 `CONFIRMATION_REQUIRED`，不弹 prompt、不打印人类预览。

## 8. 实施约束

### 8.1 无双轨切片规则

每项任务的 GREEN 阶段必须在同一个提交中完成：

1. 新 owner operation 可运行。
2. CLI 和/或 Web 调用方切换到新 owner。
3. 被替换的旧路径和旧测试删除。
4. focused test 与 residue test 同时通过。

禁止提交以下中间结构：

- 新旧 parser 同时由 flag 选择。
- Web 优先新 operation、失败后 fallback 公共 CLI。
- `instance input` 同时支持 direct 与 Task Sys mode。
- 新 JSON contract 外包一层旧 JSON/text formatter。
- 旧命令保留为 hidden alias。
- 新 projection 失败时回传 raw domain object。

### 8.2 Host Control 的实现取舍

现有 Host lifecycle 横跨 `env.sh`、workspace、browser cockpit、App Server 与 daemon shell mechanics。一次性将约三千行成熟 shell mechanics 全量翻译成 Python 会扩大风险，但不解决当前 interface owner 瓶颈。

因此最终目标采用：

```text
CLI/Web -> HostControl (Python concrete facade)
                    -> private host_control.sh (single shell owner)
```

这是最终唯一实现，不是迁移 adapter：

- `host_control.sh` 不公开给 external user，不承载产品 help。
- `host_control.py` 是 CLI/Web 共用的具体 operation boundary。
- Web 不知道脚本路径、命令名、`--json` 或 stdout parsing 细节。
- 不启动新 daemon、HTTP/RPC server 或常驻协调进程。
- 原 `instance.sh` 直接删除，Host 逻辑只能存在于 `host_control.sh`。

## 9. 测试运行前提

每个 Python 测试命令使用：

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest <targets> -q
```

不得使用 `python`、`python3`、Python shebang 或 `sys.executable` 启动仓库 Python 进程。

本文制定时的相关基线已验证：

```text
377 passed, 102 subtests passed in 430.25s
```

基线覆盖：launcher、Web management、App Server client、submit turn、Actor Side、Task Sys runtime、external IM session、IM HTTP router。实施者必须先复跑受影响 focused tests；若基线已经在分支上失败，先记录并区分既有失败，不能用本次改造掩盖。

## 10. 实施任务

### Task 1: 冻结机器优先 CLI contract

**Files:**
- Create: `tools/launcher/cli_contract.py`
- Create: `tests/test_cli_contract.py`

- [ ] **Step 1: 写失败测试**

测试覆盖：成功 envelope、错误 envelope、Unicode、单行 JSON、稳定 key、error-to-exit mapping、未知异常归一为 `INTERNAL_ERROR`，以及 stdout 不含 ANSI。

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest tests/test_cli_contract.py -q
```

Expected: FAIL，因为 `tools.launcher.cli_contract` 尚不存在。

- [ ] **Step 2: 实现最小 contract**

核心类型固定为：

```python
@dataclass(frozen=True)
class CliError(Exception):
    code: str
    message: str
    details: Mapping[str, object] = field(default_factory=dict)

def success(kind: str, data: object) -> dict[str, object]: ...
def failure(error: CliError) -> dict[str, object]: ...
def exit_code(error: CliError) -> int: ...
def emit(payload: Mapping[str, object], stream: TextIO) -> None: ...
```

禁止在该模块添加业务 exception 子类树或 serializer plugin。

- [ ] **Step 3: 运行 focused test**

Expected: `tests/test_cli_contract.py` 全部 PASS。

- [ ] **Step 4: 提交**

```bash
git add tools/launcher/cli_contract.py tests/test_cli_contract.py
git commit -m "test(cli): define machine-first output contract"
```

**Acceptance:** contract 只有 JSON 一种产品输出；error code 与 exit code 有唯一映射。

### Task 2: 原子抽取并切换 Host Control

**Files:**
- Create: `tools/launcher/host_control.py`
- Create: `tools/launcher/host_control.sh`
- Create: `tests/test_host_control.py`
- Modify: `tools/launcher/web_management.py`
- Modify: `tests/test_web_management.py`
- Modify: `buddyswitch-codex`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tools/launcher/app_server.sh`
- Delete: `tools/launcher/instance.sh`
- Delete: `tools/launcher/actor_capability_cli.py`

- [ ] **Step 1: 写 Host operation 与 Web dependency 失败测试**

测试固定以下 interface：

```python
class HostControl:
    def roles(self) -> list[dict[str, object]]: ...
    def start(self, role_id: str) -> dict[str, object]: ...
    def list_instances(self, role_id: str | None = None) -> list[dict[str, object]]: ...
    def status(self, actor_id: str) -> dict[str, object]: ...
    def clear(self, actor_id: str) -> dict[str, object]: ...
    def resume(self, actor_id: str) -> dict[str, object]: ...
    def stop(self, actor_id: str) -> dict[str, object]: ...
    def delete(self, actor_id: str) -> dict[str, object]: ...
    def interrupt(self, actor_id: str) -> dict[str, object]: ...
    def compact(self, actor_id: str) -> dict[str, object]: ...
    def capabilities_get(self, actor_id: str) -> dict[str, object]: ...
    def capabilities_set(self, actor_id: str, parent: str, side: str) -> dict[str, object]: ...
```

同时断言：

- `WebManagementService` 接收 `HostControl` dependency。
- Web lifecycle route 调用 injected operation，不构造 shell command。
- `web_management.py` 不出现 `LauncherCommandRunner`、`buddyswitch-codex` 或 `--json`。
- private runner 只允许执行固定 `host_control.sh`，不接受任意 argv executable。

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest tests/test_host_control.py tests/test_web_management.py -q
```

Expected: 新测试 FAIL，既有 Web tests 仍提供回归基线。

- [ ] **Step 2: 移动 Host mechanics，不复制**

将 `buddyswitch-codex` 与 `instance.sh` 中 roles/start/list/status/clear/resume/stop/delete/interrupt/compact mechanics 移入 `host_control.sh`。capabilities 由 `host_control.py` 直接调用 `actor_capability.py` core。每移动一个 operation，原函数立即删除；最终删除整个 `instance.sh` 与 `actor_capability_cli.py`。

`host_control.sh`：

- 只接受固定 private operation 名。
- 只输出 canonical JSON data/error。
- 不含 public help、颜色、prompt、Side、Goal、legacy alias。
- 内部锁在该 owner 内完成，不经公共 `__locked-*` dispatch。
- 所有 Python child 使用 `$BUDDYSWITCH_PYTHON`。

- [ ] **Step 3: 实现 Python facade 并切换两个 adapter**

`HostControl` 负责 actor/role 参数校验、私有命令执行、JSON schema 校验和稳定异常归一。`WebManagementService` 直接接收 facade；改造中的公共 Bash parser 通过 `"$BUDDYSWITCH_PYTHON" -m tools.launcher.host_control` 调用同一个 facade，直至 Task 5 被 Python parser 整体替换。该 private module entry 只桥接当前 Bash parser，不提供第二套 Host 实现，也不允许 fallback 原函数。

- [ ] **Step 4: 删除旧 Web runner 与旧 Host path**

删除 `LauncherCommandRunner`、所有 public CLI argv builder、`--json` parse 和对应 mock。删除 `instance.sh` 及 repo-consistency 中对其存在性的断言。

- [ ] **Step 5: 运行 focused tests**

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest \
  tests/test_host_control.py \
  tests/test_web_management.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_app_server_client.py -q
```

Expected: PASS；Web lifecycle 与 CLI lifecycle 共享同一 Host operation fake/contract。

- [ ] **Step 6: 提交**

```bash
git add -A tools/launcher/host_control.py tools/launcher/host_control.sh tools/launcher/instance.sh tools/launcher/actor_capability_cli.py tools/launcher/web_management.py tools/launcher/app_server.sh buddyswitch-codex tests
git commit -m "refactor(control): establish single host control owner"
```

**Acceptance:** Web 不再调用 public CLI；Host lifecycle shell mechanics 只存在于 `host_control.sh`；`instance.sh` 与 `actor_capability_cli.py` 不存在。

### Task 3: 重建 Actor Session Input 与 Attach，删除 Side/Goal 外溢

**Files:**
- Create: `tools/launcher/actor_session.py`
- Create: `tests/test_actor_session.py`
- Modify: `tools/launcher/app_server.py`
- Modify: `tools/launcher/app_server.sh`
- Modify: `tools/launcher/actor_side_thread.py`
- Modify: `tools/launcher/task_sys_runtime.py`
- Modify: `tools/launcher/env.sh`
- Modify: `tools/launcher/web_management.py`
- Modify: `tests/test_app_server_client.py`
- Modify: `tests/test_actor_side_thread.py`
- Modify: `tests/test_task_sys_runtime_executor.py`
- Modify: `tests/test_web_management.py`
- Modify: `tests/test_buddyswitch_launcher.py`
- Delete: `tools/launcher/submit_turn.py`
- Delete: `tools/launcher/parent_thread_submit.py`
- Delete: `tests/test_submit_turn.py`
- Delete: `tests/test_parent_thread_submit.py`

- [ ] **Step 1: 写 Actor Session 失败测试**

测试覆盖：

- idle thread 调用 `app_server.input_turn()` 并得到 `turn/start` 结果。
- active thread 调用相同 primitive 并得到 `turn/steer` 结果。
- 每次 input 先按当前 actor capability 调用 `thread_settings_update`，再调用 `app_server.input_turn()`。
- 空 text、actor 不存在、runtime 不可用返回稳定 error。
- input 前后 Task Sys task repository 数量和内容不变。
- input 模块 source 不 import `task_sys`、`task_sys_ingress`、`task_sys_runtime_client`。
- Task Sys runtime 调用 Actor Session Input callable，不 import CLI 或自行实现 start/steer。
- attach descriptor 包含已校验 actor/thread/cwd/argv/env。
- CLI attach 使用 `os.execvpe()`；Web Open TUI 使用同一 descriptor，不包含 `buddyswitch-codex`。

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest tests/test_actor_session.py -q
```

Expected: FAIL，因为新 module 尚不存在。

- [ ] **Step 2: 实现唯一 Actor Session operation**

```python
@dataclass(frozen=True)
class AttachDescriptor:
    actor_id: str
    thread_id: str
    cwd: Path
    argv: tuple[str, ...]
    env: Mapping[str, str]

def input_actor_turn(
    *, socket_path: Path, instance_json: Path, thread_id: str,
    text: str, permissions: str,
) -> dict[str, object]: ...

class ActorSession:
    def input(self, actor_id: str, text: str) -> dict[str, object]: ...
    def resolve_attach(self, actor_id: str) -> AttachDescriptor: ...
    def exec_attach(self, actor_id: str) -> NoReturn: ...
```

`input_actor_turn()` 先用 `actor_capability.resolve_parent_capability()` 同步 thread model/effort，再直接调用 `app_server.input_turn()`；`ActorSession.input()` 只负责从 actor id 解析 context 并委托该 callable。Task Sys runtime 也直接调用 `input_actor_turn()`，因此共享下层发送语义但不依赖 CLI。attach descriptor 的 build 逻辑只存在一处。

- [ ] **Step 3: 同切片删除 Side/Goal public surface**

- 从 CLI parser/help/dispatch 删除 Side、Goal。
- 从 Web 删除 Side route、handler、service method 和测试。
- 从 `env.sh` 删除 `buddyswitch_actor_side_thread_start` 等 public helper。
- 从 `actor_side_thread.py` 删除 argparse/main，保留 Task Sys 使用的 core callable。
- 从 `app_server.sh` 删除 Goal wrappers。
- 从 `app_server.py` 删除 Goal CLI subcommands，保留 `goal_get/set/clear` callable 与内部测试。
- 将 `parent_thread_submit.py` 的 capability reconcile 行为移入 `actor_session.py`，切换 Task Sys runtime 后删除 `parent_thread_submit.py` 和对应测试。
- 删除 `submit_turn.py` 和对应测试；将 start/steer RPC 断言迁入 `test_app_server_client.py`，将 actor-level 输入断言放入 `test_actor_session.py`。

- [ ] **Step 4: 回归内部 Task Sys/Side/Goal**

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest \
  tests/test_actor_session.py \
  tests/test_app_server_client.py \
  tests/test_actor_side_thread.py \
  tests/test_task_sys_runtime_executor.py \
  tests/test_web_management.py \
  tests/test_buddyswitch_launcher.py -q
```

Expected: PASS；Task Sys 仍可创建内部 side thread，App Server Goal callable tests 仍通过，external adapters 不再暴露 Side/Goal。

- [ ] **Step 5: 提交**

```bash
git add -A tools/launcher tests
git commit -m "refactor(session): restore direct actor input and attach"
```

**Acceptance:** CLI 与 Task Sys 共同依赖 Actor Session Input，Actor Session 不反向依赖 Task Sys；Side/Goal 只留内部 owner；`parent_thread_submit.py` 与 `submit_turn.py` 均不存在。

### Task 4: 建立 Task/Track external-safe read projection

**Files:**
- Create: `scripts/env/domain/task_read.py`
- Create: `tests/test_external_query.py`
- Modify: `scripts/env/domain/track_read.py`
- Modify: `tools/launcher/web_management.py`
- Modify: `tests/test_web_management.py`

- [ ] **Step 1: 写 exact-allowlist 失败测试**

fixture 应包含所有允许字段与敏感字段，测试必须使用 key equality 而非 `assertNotIn` 零散黑名单：

```python
assert set(projected_task) == {
    "task_id", "source_type", "status", "task_desc",
    "actor", "relation", "updated_at",
}
```

同时测试：list filter、get not-found、稳定排序、空列表、Track list/get 的不同 allowlist、projection 不修改输入对象。

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest tests/test_external_query.py -q
```

Expected: FAIL，因为 Task external projection 尚不存在且现有 summary 泄漏字段。

- [ ] **Step 2: 实现 owner-local projection**

- `task_read.py` 从 Task domain read API 获取对象并构造新 dict；不返回原对象引用。
- `track_read.py` 增加 `list_external_tracks()` / `get_external_track()`，复用现有 read owner。
- 不在 CLI/Web 内各写一次字段过滤。
- 不增加 mutation、permission framework 或通用 serializer。

- [ ] **Step 3: 切换 Web actor console**

Web 从 `task_sys.actor_task_projection` 切到 `task_read` external projection。删除 Web DTO 中 `execution` 读取和测试快照中的内部字段。

- [ ] **Step 4: 运行 focused tests**

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest \
  tests/test_external_query.py \
  tests/test_web_management.py \
  tests/test_task_sys_runtime_executor.py -q
```

Expected: PASS；Task Sys 内部 summary 可继续服务内部 runtime，但 external adapter 不再直接使用它。

- [ ] **Step 5: 提交**

```bash
git add scripts/env/domain/task_read.py scripts/env/domain/track_read.py tools/launcher/web_management.py tests/test_external_query.py tests/test_web_management.py
git commit -m "feat(query): add external-safe task and track projections"
```

**Acceptance:** CLI/Web 可共享明确只读投影；敏感 execution/runtime 字段无法穿透。

### Task 5: 原子重建公共 CLI adapter

**Files:**
- Create: `tools/launcher/cli.py`
- Modify: `buddyswitch-codex`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: 写目标 command surface 失败测试**

测试通过实际 `buddyswitch-codex` 进程验证：

- 第 4.1 节命令可解析。
- task/track list/get 调用 external projection。
- 所有非特殊成功/失败只输出一行 JSON。
- 无 `--json`、`--output text`、颜色和 prompt。
- destructive command 缺 `--yes` 返回 exit 4 + `CONFIRMATION_REQUIRED`。
- Side、Goal、IM、旧命令和 `__locked-*` 均返回普通 `UNKNOWN_COMMAND`，没有迁移提示。
- `--help` 不出现被删除命令。

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest tests/test_buddyswitch_launcher.py -q
```

Expected: FAIL，证明当前 parser/output 与目标不同。

- [ ] **Step 2: 实现 Python parser 与 operation dispatch**

`cli.py` 只负责：解析参数、构造 dependency、调用 HostControl/ActorSession/projection、用 `cli_contract` 输出。每个 command handler 不得直接读写 actor/task/track repository。

- [ ] **Step 3: 将公共 shell 入口缩成 bootstrap**

`buddyswitch-codex` 最终只允许：定位 repo、source `tools/launcher/env.sh`、`buddyswitch_env_init`、`exec "$BUDDYSWITCH_PYTHON" tools/launcher/cli.py "$@"`。删除旧 Bash parser 和全部 formatter。

- [ ] **Step 4: 删除 legacy dispatch**

旧命令不保留专用函数、提示、alias 或特殊 exit path。Task 2 已删除 capability process wrapper，CLI 只调用 HostControl capability operation。

- [ ] **Step 5: 运行 focused tests 与 shell syntax**

```bash
bash -n buddyswitch-codex tools/launcher/host_control.sh tools/launcher/app_server.sh
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest \
  tests/test_cli_contract.py \
  tests/test_host_control.py \
  tests/test_actor_session.py \
  tests/test_external_query.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_repo_consistency.py -q
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add -A buddyswitch-codex tools/launcher/cli.py tests
git commit -m "refactor(cli): rebuild as machine-first external adapter"
```

**Acceptance:** 公共 CLI 不含业务 mechanics；命令契约单一；旧命令无任何历史识别逻辑。

### Task 6: 清除 admin/browser/data 输出双轨

**Files:**
- Modify: `tools/launcher/browser_runtime_manager.py`
- Modify: `tools/launcher/browser_cockpit.sh`
- Modify: `tools/launcher/cleanup.sh`
- Modify: `scripts/env_manifest.py`
- Modify: `scripts/env_cleanup.py`
- Modify: `tools/launcher/cli.py`
- Modify: `tests/test_cdp_browser_session.py`
- Modify: `tests/test_browser_lazy_release_integration.py`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: 写 JSON-only 失败测试**

断言 browser/env/data helpers：

- parser 不接受 `--output human` 或 `--json`。
- stdout 仅 canonical JSON。
- `browser_cockpit.sh` source 不出现 `--output human`。
- cleanup 不读取 stdin、不弹确认。
- CLI `web` readiness 为单行 JSON，日志走 stderr。

- [ ] **Step 2: 删除 formatter 和分叉**

删除 `_print_human_result`、human `_emit_result`、text cleanup plan、manifest text role list。保留已有 Python callable 和 JSON data path，不新加兼容 wrapper。

- [ ] **Step 3: 运行 focused tests**

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest \
  tests/test_cdp_browser_session.py \
  tests/test_browser_lazy_release_integration.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_repo_consistency.py -q
```

Expected: PASS。

- [ ] **Step 4: 提交**

```bash
git add tools/launcher/browser_runtime_manager.py tools/launcher/browser_cockpit.sh tools/launcher/cleanup.sh scripts/env_manifest.py scripts/env_cleanup.py tools/launcher/cli.py tests
git commit -m "refactor(cli): remove human output tracks"
```

**Acceptance:** 产品命令和其直接 helper 没有 text/JSON 双轨；`--help` 是唯一保留的普通文本信息面。

### Task 7: 完成 WebUI adapter 切换与 IM 回归

**Files:**
- Modify: `tools/launcher/web_management.py`
- Modify: `tests/test_web_management.py`
- Modify: `tests/web_management_ui_contract.test.js`
- Modify: `tests/web_management_ui_state.test.js`

- [ ] **Step 1: 增加 Web route-to-owner contract tests**

覆盖：

- lifecycle routes 只调用 HostControl。
- Open TUI 只调用 ActorSession descriptor。
- actor console 只使用 external Task projection。
- `/api/im/*` 仍只委托 ImHttpRouter。
- `/api/instances/*/side` 与 `/side/close` 返回 404/unknown route。
- Web 无 Task/Track mutation routes。

- [ ] **Step 2: 删除残余 adapter-level duplication**

删除 command output parsing、重复 actor validation、重复 `_list_buddies()`、Side DTO 与 dead branch。保持现有 HTTP response shape，除已确认删除/收紧的 Side 和 Task execution 字段外不扩大前端改版。

- [ ] **Step 3: 运行 Python 与前端 contract tests**

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest \
  tests/test_web_management.py \
  tests/test_external_im_session.py \
  tests/test_im_http_router.py -q

node --test \
  tests/web_management_markdown_renderer.test.js \
  tests/web_management_ui_contract.test.js \
  tests/web_management_ui_state.test.js
```

Expected: 全部 PASS；IM send/events/ack/conversation 行为未改变。

- [ ] **Step 4: 提交**

```bash
git add tools/launcher/web_management.py tests/test_web_management.py tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
git commit -m "refactor(web): use shared external control operations"
```

**Acceptance:** Web Management、Web Message、Open TUI 三条链路分别归属 Host/Projection、IM、Actor Session，不交叉借道。

### Task 8: 更新架构文档并建立永久残留门禁

**Files:**
- Create: `tests/test_external_control_architecture.py`
- Modify: `tests/test_repo_consistency.py`
- Modify: `docs/arch/web-interface-call-architecture.md`

- [ ] **Step 1: 写 source-level architecture gates**

测试必须验证：

1. `web_management.py` 不包含 `LauncherCommandRunner`、`buddyswitch-codex`、`--json`、Side route。
2. `actor_session.py` 不 import Task Sys，不出现 `task_id`、side/handoff runtime frame。
3. `buddyswitch-codex` 只做 canonical Python bootstrap。
4. `instance.sh`、`submit_turn.py`、`parent_thread_submit.py`、`actor_capability_cli.py` 及其专用测试文件不存在。
5. public CLI/help 不含 Side、Goal、IM command family、human formatter、legacy command hint、`__locked-*`。
6. external Task/Track projection 使用 exact allowlist，Web 不直接用 `task_sys.actor_task_projection`。
7. repo Python single-entrypoint invariant 继续通过。

- [ ] **Step 2: 更新 durable architecture 文档**

`docs/arch/web-interface-call-architecture.md` 应明确：

- 公共 CLI 是 peer adapter，不是 Web 的 lower API。
- private Host Control 是 Host lifecycle owner。
- Actor Session Input/Attach 不属于 Task Sys。
- Web Message 属于 IM API。
- Task/Track 只开放 external-safe read projection。
- Side/Goal mutations 不对 external interface 开放。

不得记录临时迁移状态、兼容说明或两阶段路线。

- [ ] **Step 3: 执行精确残留扫描并清除所有命中**

```bash
rg -n "LauncherCommandRunner|legacy_command_hint|fail_removed_public_command|__locked-|--output[ =]human|_print_human_result" \
  buddyswitch-codex tools scripts tests docs/arch

rg -n "instance (side|goal)|/side(/close)?|SUBMIT_TURN_HELPER|parent_thread_submit|actor_capability_cli|tools/launcher/instance\.sh" \
  buddyswitch-codex tools scripts tests docs/arch

rg -n "buddyswitch-codex|--json" tools/launcher/web_management.py

rg -n "task_sys|task_id|side_frame|task_sys_ingress|task_sys_runtime_client" \
  tools/launcher/actor_session.py
```

Expected:

- 前三组无命中。
- Actor Session 组无命中。
- 测试中的 forbidden string 使用分段 literal 或 AST/path assertion，避免扫描测试自身造成假阳性。
- 内部 `side` capability level、Task Sys side runtime 与 App Server Goal callable 不属于禁用命中，应通过精确 pattern 保留。

- [ ] **Step 4: 运行 architecture tests**

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest \
  tests/test_external_control_architecture.py \
  tests/test_repo_consistency.py -q
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add tests/test_external_control_architecture.py tests/test_repo_consistency.py docs/arch/web-interface-call-architecture.md
git commit -m "test(arch): enforce external control boundaries"
```

**Acceptance:** 关键架构边界由自动化门禁保护，而不是只存在于本计划。

### Task 9: 全量验证与验收证据

**Files:**
- Modify only files required to fix failures caused by Tasks 1-8

- [ ] **Step 1: Shell syntax 与 diff hygiene**

```bash
bash -n buddyswitch-codex tools/launcher/*.sh
git diff --check
```

Expected: 全部 exit 0，无 whitespace error。

- [ ] **Step 2: 全量 Python tests**

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest tests -q
```

Expected: 全部 PASS，无 skip 用于规避本次行为。

- [ ] **Step 3: 全量 Node tests**

```bash
node --test tests/*.test.js
```

Expected: 全部 PASS。

- [ ] **Step 4: 公共 CLI smoke**

在 tests 提供的隔离 shared root/fake Codex 环境执行：

```bash
./buddyswitch-codex instance roles
./buddyswitch-codex instance list
./buddyswitch-codex task list
./buddyswitch-codex track list
./buddyswitch-codex env status
./buddyswitch-codex instance side
./buddyswitch-codex instance goal
./buddyswitch-codex instance delete missing-actor
```

Expected:

- 前五项各输出一行 success JSON。
- Side/Goal 各输出 `UNKNOWN_COMMAND`，exit 2，无迁移提示。
- missing actor 输出 `NOT_FOUND`，exit 3。
- 无命令读取 stdin 或等待 prompt。

- [ ] **Step 5: Web/IM/Open TUI integration smoke**

启动 `./buddyswitch-codex web`，验证：

- stdout 首行是 `web.ready` JSON。
- instance list/status/start/stop 走 injected Host Control integration test path。
- Web Message send/events/ack/conversation 回归通过。
- Open TUI 生成的命令不包含 public CLI，并能 handoff 到 Codex remote session。
- Side endpoint 返回 404。
- actor console payload 不含 `execution`。

浏览器 smoke 只检查既有 UI 主路径无回归；本次不改视觉设计，不新建视觉验收范围。

- [ ] **Step 6: Python single-entrypoint 验收**

运行现有 Python consistency test，并扫描新文件：

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest tests/test_repo_consistency.py -q

rg -n "(^|[[:space:]])python3?([[:space:]]|$)|#!/usr/bin/env python|sys\.executable" \
  buddyswitch-codex tools/launcher/cli.py tools/launcher/host_control.py \
  tools/launcher/host_control.sh tools/launcher/actor_session.py
```

Expected: test PASS；scan 无命中。

- [ ] **Step 7: 工作树与删除验收**

```bash
git status --short
git diff --stat
git diff --name-status
```

人工核对：变更只服务本计划；所有预定删除文件显示 `D`；无生成缓存、runtime object、private state 或无关文档改动。

- [ ] **Step 8: 最终提交**

```bash
git add -A
git commit -m "test(control): verify forward external interface rebuild"
```

**Acceptance:** 全量测试、集成 smoke、残留扫描和工作树审计均有可复核输出。

## 11. 验收矩阵

| ID | 验收目标 | 自动化证据 | 通过标准 |
|---|---|---|---|
| A01 | CLI 机器优先 | `test_cli_contract.py`, launcher tests | 除特殊命令外 stdout 单行 JSON |
| A02 | 无文本双轨 | repo consistency + `rg` | 无 `--json`、human formatter/output selector |
| A03 | Web/CLI 共用 Host owner | host/web tests | Web 不执行 public CLI，二者调用 HostControl |
| A04 | Actor input 干净 | actor session/Task Sys tests | CLI/Task Sys 共用 Actor Session，direct `input_turn`，Task repository 不变 |
| A05 | Attach 共用 descriptor | actor/web tests | CLI/Web 同一 builder，无 public CLI 拼接 |
| A06 | Side 不外溢 | launcher/web/architecture tests | public command/route/helper 均不存在 |
| A07 | Internal Side 保留 | Task Sys/actor side tests | Task Sys side runtime 行为通过 |
| A08 | Goal 不外溢 | launcher/architecture tests | public Goal 命令/wrapper 不存在 |
| A09 | Internal Goal 保留 | App Server tests | Python Goal callable 仍通过 |
| A10 | Task read 安全 | external query tests | exact allowlist，无 execution/runtime fields |
| A11 | Track read 安全 | external query tests | list/get exact allowlist，只读 |
| A12 | 无 Task/Track mutation | parser/route tests | CLI/Web 无 create/update/close |
| A13 | IM 边界不变 | IM router/session tests | Web IM 全链路通过，CLI 无 IM family |
| A14 | 无历史残留 | architecture gates + `rg` | alias/hint/removed dispatch/旧文件均不存在 |
| A15 | 无双轨 | source gates + review | 无 fallback、mode flag、old/new dispatch |
| A16 | Python 入口统一 | repo consistency | 新 Python child 全用 `$BUDDYSWITCH_PYTHON` |
| A17 | Web readiness 稳定 | launcher/web integration | `web.ready` JSON，日志 stderr |
| A18 | 破坏性操作非交互 | CLI tests | 缺 `--yes` 为 exit 4 JSON，不读 stdin |
| A19 | 全量无回归 | full pytest/node | 全部 PASS |
| A20 | 架构文档一致 | doc review + source gates | 文档只描述最终单轨形态 |

## 12. 关键问题与实施判断

### 12.1 为什么不让 Web 直接调用公共 CLI？

公共 CLI 是 external product adapter，其参数、输出和进程 handoff 都是产品契约。Web 复用它会使 adapter 依赖 adapter，并把命令字符串、stdout parser 和 CLI 迁移成本泄漏到 Web。共同依赖 Host Control operation 才能形成并列 interface。

### 12.2 为什么保留 private shell Host Control？

Host lifecycle 当前天然包含 workspace、process、lock、browser、App Server 等 shell mechanics。将所有 mechanics 翻译成 Python 不会改善本次产品边界，反而扩大验证面。将代码“移动而不是复制”到唯一 private owner，已能消除公共 CLI 反向依赖和多 owner 问题。

### 12.3 为什么 CLI 不覆盖 IM？

IM 链路要求 external entity/session/conversation/ack 等完整语义。CLI 不是 IM 实体；为追求“CLI 功能完备”而伪造身份会反向污染 IM 架构。需要 IM 行为的脚本和 AI 直接消费 IM API。

### 12.4 为什么保留 `instance input`？

它是对现有 actor session 发送一轮输入的基础外部控制 primitive，适合操作者、脚本和 AI 调试。错误来自当前实现借道 Task Sys，而非能力本身。正确处理是恢复 direct App Server path。

### 12.5 为什么 Side/Goal 不能因为可调试就继续暴露？

Side lifecycle 属于 Task Sys / Actor Tool Env，Goal 属于 App Server 内部 session state。external user 观察或调试内部状态不构成产品 mutation contract；代码、测试、日志和明确的 read projection 才是对应调试面。

### 12.6 “CLI 完备”如何防止再次膨胀？

新增 CLI 命令必须同时满足：

1. 属于 Host 或 Actor Session external control，或属于批准的 external-safe read projection。
2. 有明确 owner operation，不要求 CLI 创建内部身份或编排状态。
3. Web 若需要同一管理能力，可直接复用 owner operation。
4. 具有稳定 JSON schema、error code、exit code 和行为测试。

任一条件不满足，则不进入 CLI 产品面。

## 13. 非目标

- 不把 BuddySwitch 全部 launcher shell 重写为 Python。
- 不新建通用 Backend Data Service、HTTP/RPC control server 或 event bus。
- 不给 external user 开放 Task/Track mutation。
- 不为 CLI 创建 IM identity 或 conversation lifecycle。
- 不重做 WebUI 视觉设计。
- 不重命名 `instance` command family。
- 不保留旧 CLI contract 的迁移期、warning 或兼容 adapter。
- 不修改 Task Sys、Message、IM 的内部业务语义，除非测试证明本次边界切换暴露了直接缺陷。

## 14. 完成定义

本计划完成必须同时满足：

- Task 1-9 全部勾选并有对应 commit/test output。
- A01-A20 全部通过。
- 公共 CLI、WebUI Management、Web Message、Actor Session、Task Sys 的 owner 与依赖方向符合第 3 节。
- 所有预定旧文件、旧命令、旧 route、旧 formatter 和旧测试已删除。
- 没有兼容 flag、fallback、alias、hidden command、dual read/write 或旧命令提示。
- 全量 Python/Node tests、shell syntax、diff check、residue scan 全部通过。
- 架构文档描述的是最终单轨实现，不记录临时过渡路径。
- 最终 review 未发现 public adapter 直接读写 domain/runtime state。

失败时只修复新单轨实现；不允许通过恢复旧路径、增加兼容 mode 或降低测试断言来获得绿色结果。
