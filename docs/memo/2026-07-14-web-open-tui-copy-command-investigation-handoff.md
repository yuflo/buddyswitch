# Web Open TUI / Copy command 调查交接备忘

**日期：** 2026-07-14

**目标 worktree：** `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`

**文档性质：** 基于 live WebUI、进程、源码和 Git 历史的调查交接；不是最终设计，也不是实施计划。

## 1. 阅读边界

本文记录已经验证的事实、当前分析框架、工作假设、替代解释和待确认问题，帮助 `fea-daemon` 接手后避免重新做一遍基础排查。

本文不预先决定以下事项：

- 不判定 CLI/WebUI 解耦方向错误。
- 不判定 Copy command 必须恢复为 `buddyswitch-codex instance attach`。
- 不判定完整 direct attach 命令必须从 API 或 UI 删除。
- 不判定问题只能在前端、后端或环境初始化中的某一层修复。
- 不把当前最有证据支持的解释写成不可推翻的架构结论。

接手者应先确认产品语义，再决定代码和测试如何变化。原因是 Open TUI 同时跨越 Actor Session、Terminal 执行、Web API 和可见 UI；过早在其中一层做局部缩短，可能反向破坏已经完成的 owner 收敛、actor 隔离或 runtime provenance。

## 2. 用户发现的问题

在 `http://127.0.0.1:8765/` 的 Team room 中选中 PM actor 后，右侧 `Tools` 区域最初显示 `Open TUI`。触发一次 Open TUI 后：

- 页面显示 `Terminal opened.`；
- `open-tui-fallback` 区域变为可见；
- 页面展示一条很长的 shell command；
- 下方出现 `Copy command` 按钮。

用户的直接观察是：Copy command 对应的内容异常长，看起来像经过了多次追加。用户随后提出的架构疑问是：这是否受到 `fea-daemon` 中 CLI/WebUI 解耦改造影响；如果改造方向本身正确，是否存在新 attach contract 到 Web 展示面的适配缺口。

## 3. Live 调查快照

### 3.1 服务归属

调查时 `127.0.0.1:8765` 的监听进程为：

```text
PID 12000
/Users/chen/miniconda3/bin/python
/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon/tools/launcher/web_management.py
cwd=/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon
started=2026-07-14 18:57:19 +0800
```

Live `/static/app.js` 的 SHA-256 为：

```text
294d2805a291b3bd78524db1045554a770c03e7d38de619df9327f5645d55e02
```

该值与 `fea-daemon/tools/launcher/assets/web-management/app.js` 一致，与 `fea-webui` 中的文件不一致。因此本次可见行为应以 `fea-daemon` 为调查对象，不能用 `fea-webui` 当前的短命令实现解释 live 8765。

### 3.2 实际命令形态

本次 PM actor 的 live command 长度为 2,190 个字符，结构可以归纳为：

```text
cd <actor-workspace>
&& env
  PATH=<inherited-path>
  <actor isolation and runtime environment assignments>
  <recorded Codex executable>
  resume --remote unix://<actor-app-server-socket> <thread-id>
```

统计结果：

| 项目 | Live 值 |
|---|---:|
| command 字符数 | 2,190 |
| 环境变量赋值数 | 22 |
| PATH 分段数 | 21 |
| PATH 唯一分段数 | 18 |
| `/Users/chen/.local/bin` 出现次数 | 4 |

22 个环境变量主要分为：

- actor 隔离：`HOME`、`CODEX_HOME`、`XDG_CONFIG_HOME`；
- actor/runtime 定位：`BUDDYSWITCH_ACTOR_ID`、`BUDDYSWITCH_ROLE_ID`、`BUDDYSWITCH_INSTANCE_JSON`、`BUDDYSWITCH_REPO_ROOT`、`BUDDYSWITCH_SHARED_ROOT`；
- workspace/private/temp：`BUDDYSWITCH_ACTOR_PRIVATE_DIR`、`BUDDYSWITCH_INSTANCE_TMP`、`BUDDYSWITCH_PROJECT_WORKSPACE_DIR`、`TMPDIR`、`TMP`、`TEMP`、`TMPPREFIX`；
- 终端与进程环境：`PATH`、`TERM`、`COLORTERM`、`LANG`、`LC_TERMINAL`、`LC_TERMINAL_VERSION`、`BUDDYSWITCH_PYTHON`。

本次捕获没有发现 token、credential 或任意未过滤的完整服务环境被带入 command；可见内容主要是本机路径、actor 标识和终端 locale。这个观察不能代替对 `_attach_env()` allowlist 的长期安全审查。

### 3.3 PATH 重复的来源

监听进程 PID 12000 及其父 CLI 进程 PID 11985 已经具有与 command 相同的 PATH，其中 `/Users/chen/.local/bin` 已重复 4 次。

当前 `_attach_env()` 会从 `os.environ` 复制 PATH，未发现它在每次 Open TUI 时继续拼接 PATH。因而现有证据支持：PATH 的重复至少在 Web 进程启动时已经存在，Actor Session 将其原样投影进 attach descriptor。

这只解释了 command 中一部分视觉膨胀。即使 PATH 完全去重，actor 隔离变量、完整 executable、socket 和 thread id 仍会使 direct attach command 显著长于旧的 CLI wrapper command。

## 4. 已验证的数据流

### 4.1 前端没有表现出逐次累加

`tools/launcher/assets/web-management/app.js` 当前行为为：

1. 切换 actor 时，`clearOpenTuiFeedback()` 将 `state.openTuiCommand` 设为空字符串。
2. 点击 Open TUI 时，再次先将 `state.openTuiCommand` 设为空字符串。
3. 请求 `/api/instances/{actor_id}/open-tui`。
4. 成功时用 `payload.command` 整体替换 `state.openTuiCommand`；失败时用 error details 中的 command 整体替换。
5. `Copy command` 调用 `navigator.clipboard.writeText(command)`；fallback 路径也只是把当前 command 写入临时 textarea 后执行一次 copy。

相关位置：

- `clearOpenTuiFeedback()`：`app.js:555-558`
- `renderOpenTui()`：`app.js:2060-2073`
- `openTui()`：`app.js:3121-3166`
- `copyOpenTuiCommand()`：`app.js:3184-3211`

因此，“多次点击导致前端对同一字符串执行 `+=` 追加”目前没有源码或 live 状态证据支持。仍应由接手者用针对重复点击、actor 快速切换和 stale response 的行为测试复核，而不是仅凭静态阅读永久排除所有竞态。

### 4.2 后端生成单个完整执行字符串

`tools/launcher/web_management.py::_open_tui()` 当前流程为：

```text
ActorSession.resolve_attach(actor_id)
  -> AttachDescriptor(cwd, argv, env)
  -> build_open_tui_attach_command(descriptor)
  -> actor_session.terminal_command_from_descriptor(descriptor)
  -> Terminal opener(command)
  -> HTTP success payload { command, terminal }
```

`tools/launcher/actor_session.py` 的关键行为为：

- `resolve_attach()` 校验 actor、runtime、thread 和 socket，并调用 App Server `thread/resume`；
- `_attach_env()` 构造 actor 隔离和运行环境；
- argv 使用 recorded Codex executable，执行 `resume --remote unix://... <thread-id>`；
- `terminal_command_from_descriptor()` 将 cwd、env 和 argv 序列化为一条 shell command。

该字符串同时被用于 macOS Terminal 执行，也被放进 Web API 的 success/error payload。

### 4.3 成功状态也显示 fallback 区域

HTML 将长命令容器命名为 `open-tui-fallback`：

```html
<div id="open-tui-fallback" class="command-fallback" hidden>
  <code id="open-tui-command" class="mono-value long-value"></code>
  <button id="copy-tui-command-button">Copy command</button>
</div>
```

但当前前端的显示条件不是“Terminal 打开失败”，而是：

```text
state.openTuiCommand 非空，并且当前 actor 仍允许 Open TUI
```

后端成功响应始终包含 `command`。因此 `Terminal opened.` 与完整 fallback command 同时出现，是当前代码的确定行为，而不是浏览器偶发渲染。

## 5. 相关改造背景

### 5.1 原始架构目标

`docs/memo/2026-07-13-cli-webui-external-control-forward-rebuild-implementation-acceptance-plan.md` 将 Public CLI 与 WebUI Management 定义为并列 interface adapter：

```text
Public CLI --------+
                   +--> Host Control
WebUI Management --+--> Actor Session
                   +--> external-safe read projections
```

计划明确禁止 `WebUI Management -> public buddyswitch-codex`，并规定：

- lifecycle 属于 private Host Control；
- direct input/attach 属于 Actor Session；
- CLI attach 与 Web Open TUI 使用同一个 descriptor builder；
- Web Open TUI 不拼接 public CLI command。

当前 `docs/arch/web-interface-call-architecture.md` 仍表达同一边界：Web 和 CLI 是 peers；Open TUI 与 public CLI 都调用 Actor Session。

### 5.2 与问题相关的提交顺序

| 提交 | 时间 | 已验证的相关变化 | 与长 command 的关系判断 |
|---|---|---|---|
| `0e8b3f5` `refactor(control): establish single host control owner` | 2026-07-13 22:54 | 建立单一 Host Control owner | 提供解耦背景；不是 direct command 展开的直接证据 |
| `c31ecb4` `refactor(session): restore direct actor input and attach` | 2026-07-14 00:36 | 新增 Actor Session / AttachDescriptor；Web Open TUI 从短 public CLI wrapper 切换为 descriptor 序列化 | 是命令形态从短 wrapper 变成长 direct attach 的主要已知变化 |
| `9973e71` `refactor(cli): rebuild as machine-first external adapter` | 2026-07-14 02:28 | 重建 public CLI adapter | 强化 peer adapter 背景；不是 Web command 序列化 owner |
| `aa15385` `refactor(web): use shared external control operations` | 2026-07-14 04:18 | Web 改用共享 owner operations | 进一步清理 Web -> CLI 依赖 |
| `0593c68` `test(arch): enforce external control boundaries` | 2026-07-14 04:51 | 用架构测试固定 peer/owner 边界 | 使“Web command 不含 public CLI”成为测试约束 |
| `6e4a2c3` `Add Codex runtime provenance` | 2026-07-14 14:14 | descriptor 使用 recorded executable，并增加 shared-root provenance | 增加了 command 中的显式路径和 provenance 信息，但不是完整展开的起点 |

在 `c31ecb4` 之前，Open TUI command 为：

```text
cd <repo-root> && ./buddyswitch-codex instance attach <actor-id>
```

之后变为基于 descriptor 的 direct `codex resume --remote`。这是可由 Git diff 直接确认的历史事实。

“该改造是否遗漏了 Web 展示适配”属于基于事实的解释，不是 Git 历史直接陈述的作者意图。

## 6. 当前分析框架

为避免把一个可见症状错误归因到整个解耦方向，建议把问题拆成五个独立判断层：

| 层 | 当前职责 | 本次需要回答的问题 |
|---|---|---|
| Owner / dependency | Web、CLI 直接调用 Host Control / Actor Session | peer adapter 边界是否仍应保持 |
| Attach execution | 校验 actor/runtime/thread，构造 cwd/env/argv，连接 remote session | 哪些环境对正确 attach 是必要的 |
| Web API contract | `/open-tui` 返回执行结果和 command | success 与 failure 各自需要返回什么 |
| UI presentation | 展示状态、fallback 和 Copy command | 用户何时需要看到多少内容 |
| Process environment | Web/CLI 启动时继承 PATH/locale | PATH 重复应在哪个 owner 处理，或是否处理 |

这五层相关，但不应在没有产品决定时合并成一个“大命令太长，所以恢复旧 CLI command”的修复。

## 7. 工作假设与替代解释

以下按当前证据支持程度排列，但都不是最终结论。

### 7.1 工作假设 A：执行载体与展示载体复用了同一 command

支持证据：

- 后端只生成一个 `command`；
- 同一字符串既交给 Terminal opener，又放入 HTTP payload；
- 前端只要拿到非空 command 就展示 fallback；
- direct descriptor 包含运行正确性所需的内部细节，但 UI 以完整文本直接呈现。

可能解释：CLI/Web owner 解耦和 direct attach 本身可以成立，但旧的 `{command}` Web DTO / UI fallback 假设没有随着 command 从短 wrapper 变为完整 descriptor serialization 而重新定义。

尚未确认：产品是否本来就要求 Copy command 与 Terminal 实际执行内容逐字相同。如果答案是“必须相同”，则这种复用可能是有意契约，而不是遗漏。

### 7.2 替代解释 B：完整 command 是有意的可复现恢复载体

完整 cwd/env/argv 可以让用户在 Terminal 自动打开失败时复制并执行与自动路径等价的命令。若产品目标优先保证可复现恢复，后端返回完整 command 可能完全正确，问题可能只在：

- 成功时仍展开显示；
- 默认视觉层级过高；
- 标签没有说明它是 exact recovery command；
- command 没有折叠或按需展开。

这一解释需要产品语义和失败恢复场景验证。

### 7.3 替代解释 C：success/failure 可见性条件是主要缺口

HTML 明确使用 `fallback` 命名，而渲染条件只检查 command 是否非空。若 Copy command 仅用于 Terminal 打开失败，则后端可以继续生成完整 direct command，问题可能主要位于 success UI 状态和 payload 消费方式。

这一解释不能仅凭元素命名成立；需要确认 `Copy command` 是否也被设计为成功后的高级工具。

### 7.4 替代解释 D：环境膨胀是主要体验来源

PATH 的 21 个分段和重复路径确实增加了长度，且来自父进程环境。可能需要检查 CLI/bootstrap 为什么产生重复 PATH。

但即使 PATH 去重，剩余 actor isolation/runtime assignments 仍然很多。因此仅清理 PATH 很可能改善噪声，却不能独立回答 Copy command 产品契约。

### 7.5 当前证据不支持的解释：前端持续 append

前端源码是 clear + replace，Copy handler 是单次 write。现阶段没有证据证明多次点击会线性累积历史 command。

接手者仍可用自动化测试复核重复点击、快速 actor 切换、旧请求晚返回和 Copy promise 晚完成；这些场景已有 selection request ownership 逻辑，不应只靠肉眼判断。

## 8. 过早下定论的连锁风险

### 8.1 直接恢复 public CLI wrapper

如果 Web 内部重新通过 `buddyswitch-codex instance attach` 执行，可能重新形成 adapter 依赖 adapter，违反现有架构文档和测试约束。

需要区分：

- Web 内部 Terminal execution path；
- 返回给用户手工执行的 copy/recovery surface。

二者是否允许使用不同表达，必须先由产品和架构共同决定，不能从“短命令更好看”直接推导。

### 8.2 直接删减 env

删掉 `HOME`、`CODEX_HOME`、workspace/private/tmp、runtime executable 或 socket/thread 信息，可能让 attach 进入错误的 Codex home、错误 cwd、错误 runtime 或错误临时目录。没有最小必要环境测试前，不应从字符串长度推导可删除字段。

### 8.3 只隐藏 UI

只在成功状态隐藏 command 可能已经满足产品体验，也可能只是遮住 API contract 仍不清晰的问题。是否需要进一步区分 execution descriptor 与 user-facing recovery command，应由接手者根据预期外部契约决定。

### 8.4 先做 PATH 去重

PATH 去重是相对独立的环境卫生问题。若在 attach serializer 内做，可能把 bootstrap/environment owner 的问题隐藏在消费端；若在启动层做，又会影响 CLI、Web 和子进程。应先确认 owner 和验证范围。

### 8.5 直接修改现有架构测试

当前测试明确断言 Open TUI command 包含 direct `codex resume`，且不包含 `buddyswitch-codex` / `instance attach`。这些断言中既有 owner 边界，也可能混入具体展示形态。删除或反转断言前，应先区分哪些保护架构、哪些只是当前序列化实现。

## 9. 建议由 fea-daemon 先确认的决策

接手者在实施前应给出明确答案：

1. `Copy command` 的产品角色是什么：失败恢复、成功后的高级工具、诊断信息，还是 exact executable command？
2. Terminal 成功打开后是否仍应显示 Copy command？
3. 自动执行 command 与用户复制 command 是否必须逐字相同？
4. `/open-tui` success payload 是否承诺返回 command，还是只承诺 terminal/result 状态？
5. failure payload 是否必须携带可独立执行的恢复命令？
6. user-facing command 可以暴露哪些 actor 本地路径、runtime provenance 和 locale？
7. PATH 重复属于本任务、独立 bootstrap hygiene，还是接受的 inherited environment？
8. “Web 不通过 public CLI”约束仅保护内部调用方向，还是也要求任何用户可见 copy command 都不得引用 public CLI？
9. live acceptance 应覆盖成功、Terminal opener 失败、非 macOS、actor unhealthy、actor 切换和重复点击中的哪些场景？

## 10. 可供评估的方向，不作为预定方案

### 方向 1：保持 exact command，只调整可见性和信息层级

保留后端和 Terminal execution，不改变 descriptor；重新定义成功/失败状态下 Copy command 的显示与标签。

优点是最小化 attach/runtime 风险。局限是 API 仍用一个 command 同时表达执行与恢复语义。

### 方向 2：区分内部 execution command 与 user-facing recovery contract

Actor Session descriptor 继续作为唯一 attach owner；Web/Terminal 内部执行仍走 direct descriptor。API/UI 另行定义用户可见恢复信息。

优点是职责更清楚。风险是容易引入第二套命令构造或形成隐性双轨，必须证明二者共享同一 attach 语义而不是各自维护。

### 方向 3：保留完整 command，并将其明确定位为高级诊断/恢复信息

不把 command 当普通 Tools 内容常驻展示，而把它作为可展开的 exact execution detail。

优点是保留可复现性且不改变后端。局限是如果用户真正需要简洁的手工入口，这只改善视觉层级，没有解决交互目标。

接手者可以选择其中一种、组合其中部分，或基于新的产品证据提出不同方向。本文不推荐排序，以免在产品语义未确认前锁死实现。

## 11. 建议的实施前验证边界

在写修复测试或修改 contract 前，建议先完成以下短验证：

1. 用当前 `./buddyswitch-test` 入口定位 Open TUI 的 unit/integration/system tests，标注每个断言保护的是 owner architecture、attach correctness、HTTP contract 还是 UI presentation。
2. 在不改变代码的前提下复现一次 Terminal opener success 和一次 fake opener failure，比较 payload 与 UI 状态。
3. 统计 command 长度时分开计算 PATH、actor isolation env、runtime provenance、argv 四部分，避免把全部噪声归因于 PATH。
4. 确认 current dirty worktree 与 live Python process 启动时加载的源码版本；Python module 可能在进程启动后与磁盘继续变化。
5. 记录最终产品决定，再写最小失败测试；不要先修改现有架构断言来让候选实现通过。

## 12. 建议的验收关注点

以下是验收关注点，不是已经批准的目标行为：

- Web 与 CLI 仍是 peer adapters，不出现 Web 内部 shell-through public CLI，除非架构决定被明确重开并重新论证。
- Actor Session 仍是 direct input/attach owner；attach 不反向进入 Task Sys。
- recorded Codex runtime、actor cwd、home/private/tmp 和 remote socket/thread 的正确性有自动化证明。
- success 与 failure 的 Copy command 可见性符合明确产品决定。
- 重复点击、快速切换 actor、stale response 和 copy completion 不会把旧 actor command 写入新选择。
- live WebUI 不再给用户造成“历史命令不断追加”的误解，或能够清楚解释展示的是 exact recovery detail。
- PATH hygiene 若纳入本任务，应有独立 owner、行为测试和不改变可执行解析顺序的证明。
- 相关测试通过 `./buddyswitch-test focused ...` 执行；最终范围是否需要 `./buddyswitch-test full` 由 `fea-daemon` 接手方按变更风险决定。

## 13. 证据索引

### Live

- URL：`http://127.0.0.1:8765/`
- actor：`act-pm-91c4d57dd98e`
- visible status：`Terminal opened.`
- command length：2,190
- env assignments：22
- PATH：21 entries / 18 unique / `.local/bin` × 4
- live owner：`fea-daemon/tools/launcher/web_management.py`

### Source

- `tools/launcher/actor_session.py`
  - `ActorSession.resolve_attach()`
  - `terminal_command_from_descriptor()`
  - `_attach_env()`
- `tools/launcher/web_management.py`
  - `WebManagementService._open_tui()`
  - `build_open_tui_attach_command()`
- `tools/launcher/assets/web-management/app.js`
  - `clearOpenTuiFeedback()`
  - `renderOpenTui()`
  - `openTui()`
  - `copyOpenTuiCommand()`
- `tools/launcher/assets/web-management/index.html`
  - `#open-tui-fallback`
- `tests/integration/web/management_harness.py`
  - `assert_open_tui_command_uses_descriptor()`
- `tests/integration/web/test_management_http.py`
  - Open TUI success/failure/owner tests
- `docs/arch/web-interface-call-architecture.md`
- `docs/memo/2026-07-13-cli-webui-external-control-forward-rebuild-implementation-acceptance-plan.md`

### Git

- `0e8b3f5 refactor(control): establish single host control owner`
- `c31ecb4 refactor(session): restore direct actor input and attach`
- `9973e71 refactor(cli): rebuild as machine-first external adapter`
- `aa15385 refactor(web): use shared external control operations`
- `0593c68 test(arch): enforce external control boundaries`
- `6e4a2c3 Add Codex runtime provenance`

## 14. 交接摘要

当前可以可靠交接的不是一个最终修复结论，而是一组边界清楚的事实：

- live 8765 属于 `fea-daemon`；
- command 的长度来自完整 descriptor serialization，而非已发现的前端字符串累加；
- PATH 重复来自 Web/CLI 父进程环境，attach 路径当前原样继承；
- direct attach 是 CLI/WebUI external control 重建中的明确设计；
- success payload 返回完整 command，前端因此在成功状态也展示 fallback；
- 现有测试同时保护 owner 边界和具体 command 形态，需要在改动前拆分理解。

最需要 `fea-daemon` 接手方重新判断的是：内部 exact execution、失败恢复入口和用户可见 Copy command 是否应继续共享同一个 contract。这个问题的答案将决定修复应落在 UI 可见性、Web DTO、command projection、process environment，还是其中多个明确分工的层；本文不替接手者预先作答。
