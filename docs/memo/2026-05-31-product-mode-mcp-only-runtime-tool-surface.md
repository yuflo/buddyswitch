# Product-Mode MCP-Only Runtime Tool Surface

Date: 2026-05-31

## 任务目标

把 BuddySwitch product-mode runtime 工具面从“native-first 但仍可能被 CLI hint 诱导”收敛为：

```text
Codex 默认只通过原生 BuddySwitch env MCP tools 使用 product runtime 能力。
CLI 不再作为 product-mode runtime action 的默认入口、提示入口、失败恢复入口或 tool feedback 推荐入口。
```

这不是删除所有诊断能力，也不是把工具调用写成硬流程。

目标是让 Codex 最大化使用原生工具：

- 正常 runtime action 走 `buddyswitch-env` MCP 暴露的原子工具，例如 `message__list`、`message__send`、`search__open_browser`、`task__current`、`track__open`。
- 当 MCP 不可见或不可用时，Codex 应被引导去诊断和恢复 MCP/runtime 注册，而不是绕过 MCP 直接执行 env CLI。
- Tool catalog 和 tool feedback 应提供足够语义，让 Codex 能自己判断下一步使用哪个原生工具。

## 当前问题

Native MCP 基础已经存在：

- `scripts/env/tool_runtime/native_mcp.py` 从 registry 投影 native MCP tool specs。
- `tools/launcher/env_tool_mcp_server.py` 把 MCP `tools/call` 转发到 broker `env.tool`。
- product instance 启动流程会注册 `buddyswitch-env` MCP server。

但仍有残留面会训练 Codex 回退 CLI：

- runtime tool catalog 可能暴露 `python3 scripts/env/client.py ...` command metadata；
- tool definition 仍包含 CLI command 字段；
- `search` 的 rejection/status feedback 中仍有 CLI `command_hint`；
- launcher 拒绝 native Codex web search 时仍提示 env CLI；
- `scripts/env/client.py` 仍可被 Codex 通过 shell 发现并作为 runtime action 入口执行。

因此，问题不是“有没有 MCP server”，而是：

```text
product-mode host-visible surface 仍有 CLI action affordance。
```

## 设计原则

本任务必须遵循 `docs/bitter` 的分层原则。

### Tool catalog

Tool catalog 描述原子能力语义：

- capability 是什么；
- 何时适用、何时不适用；
- 输入字段含义；
- reads / writes / durability / visibility / permission boundary；
- 成功和失败分别意味着什么。

Tool catalog 不应提供 copyable env CLI command，也不应编码业务 workflow。

### Tool response

Tool response 关闭一次调用后的反馈循环。

它应解释：

- `state_changed`；
- changed object ids；
- `durability`；
- content level；
- rejection reason；
- correctable fields；
- relevant alternative atomic capabilities。

它不应把 next action 写成强制脚本。

### Skill

Skill 可以组合多个原子工具形成重复业务 workflow。

Skill 不应复制 payload schema，也不应覆盖 runtime feedback。

### AGENTS

AGENTS 保持短，只提供 role orientation、runtime boundary、context discovery 入口和安全规则。

AGENTS 不应成为 tool encyclopedia 或 CLI recipe 集合。

## 非目标

这次不做以下事情：

- 不删除所有本地诊断入口。
- 不把 `python3 scripts/turn_runtime.py status` 这类只读诊断能力移除。
- 不把每个 tool package 改成判断“调用方是否 MCP”。
- 不把业务 workflow 写进 tool feedback。
- 不把 app-server WebSocket close 当作 MCP-only 工具面的一部分；若同批修复，必须作为独立 lifecycle 子项验证。

## 收敛后的方案

### 1. Product-mode runtime action MCP-only

Product-mode 正常 runtime action 只通过 native BuddySwitch env MCP tools 执行。

允许的主路径：

```text
Codex native MCP tool
  -> tools/launcher/env_tool_mcp_server.py
  -> runtime broker admission
  -> env.tool registry
  -> owning tool service
```

不再作为 product-mode 主路径：

```text
Codex shell
  -> python3 scripts/env/client.py ...
  -> runtime broker env.tool
```

CLI 可以保留为 human/admin/debug 工具，但不能进入默认 Codex product-mode surface。

### 2. 保留诊断面，不保留 action fallback

MCP 不可见或不可用时，反馈应引导：

```text
inspect runtime status
  -> repair or restart MCP/runtime registration
  -> retry native MCP tool
```

不应引导：

```text
run scripts/env/client.py message send ...
```

允许保留的诊断入口示例：

- `python3 scripts/turn_runtime.py status`
- `./buddyswitch-codex instance attach <instance-id>`
- launcher-managed restart or repair commands when they do not mutate runtime objects directly

### 3. Runtime catalog 输出 native affordance

`context.summarize` 应给 compact first-pass native tool affordances。

`context.get` / `tool_catalog` 应给完整原子能力语义。

Product-mode catalog 默认不输出 copyable env CLI command。

需要表达可调用能力时，输出 native tool name 和 schema，例如：

```json
{
  "native_tool": "message__list",
  "tool": "message",
  "action": "list",
  "input_schema": {
    "type": "object"
  }
}
```

### 4. Tool feedback 改为语义化 next action options

删除面向 agent 的 CLI `command_hint`。

用结构化候选能力替代：

```json
{
  "allowed_next_actions": [
    "Retry with a non-empty query.",
    "Inspect search status before choosing a backend."
  ],
  "allowed_next_action_options": [
    {
      "tool": "search",
      "action": "open_browser",
      "native_tool": "search__open_browser",
      "reason": "Browser backend is available and search API is blocked.",
      "arguments_hint": {
        "query": "<non-empty query>",
        "engine": "google"
      }
    }
  ],
  "correctable_fields": ["query"],
  "state_changed": false,
  "durability": "none"
}
```

这个 next action 只是候选原子能力，不是 workflow 脚本。

Codex 仍然负责判断：

- 是否先看上下文；
- 是否修 payload；
- 是否问用户；
- 是否采用某个候选工具。

### 5. Transport/admission 逻辑不下沉到 tool package

不要让 `message/tool.py`、`track/tool.py`、`search/_impl.py` 等 tool package 判断调用者是不是 MCP。

Transport/admission 只能放在：

- launcher；
- MCP server；
- broker admission。

Tool package 继续只负责：

- action semantics；
- input validation；
- product state transition；
- response feedback；
- role/action policy result。

### 6. Product-mode MCP registration fail-closed

Product instance 启动时必须确保：

- `buddyswitch-env` MCP server 已注册；
- registered server 指向当前 instance；
- broker socket 匹配当前 instance；
- native MCP tools/list 能覆盖 registry action set；
- MCP registration 失败时不要靠 env CLI fallback 掩盖。

如果 MCP 不可用，应启动失败或给清晰的 runtime repair feedback。

### 7. CLI/debug 能力要显式隔离

如果需要保留 env CLI：

- 默认 product-mode agent 不可用；
- 必须有显式 admin/debug 开关；
- 不进入 AGENTS、skills、tool catalog、tool response；
- 不作为 tool rejection 的 recovery suggestion。

如果进一步做强边界，不能只让 CLI 传普通字段冒充 MCP。需要不可伪造的 admission 机制，例如：

- launcher 注入给 MCP server 的私有 capability token；
- product MCP broker socket 和 admin/debug broker socket 分离；
- broker 根据不可伪造来源区分 product action 与 admin/debug action。

否则 `caller_interface=native_mcp` 这类普通参数只是伪边界。

### 8. WebSocket close 单独修复

`Connection reset without closing handshake` 是 app-server WebSocket 收尾协议问题。

它应单独作为 lifecycle/transport cleanup 修复：

- client 发 close frame；
- 等待 server close frame 或短 timeout；
- 再关闭 socket。

它不改变 MCP-only runtime tool surface。若同批执行，必须保持为独立 lifecycle/transport 子项，并用独立测试验证。

## 架构形态

目标架构：

```text
Skill
  -> Tool Contract
  -> Native MCP Projection
  -> MCP Server
  -> Broker Admission
  -> Service
  -> Domain Ops
  -> Object Repo
  -> Runtime Objects / Files
```

关键边界：

- skills own workflow judgment；
- tool contracts own action semantics；
- native MCP projection owns model-visible tool affordance；
- MCP server owns stdio MCP protocol adaptation；
- broker admission owns product-mode access boundary；
- services adapt requests and responses；
- domain ops own cross-object rules；
- repos own one object family。

## 验证标准

完成后必须证明：

1. Native MCP projection/server tests pass.
2. Product-mode `context.summarize` and `context.get tool_catalog` do not output copyable env CLI action commands.
3. Active AGENTS, skills, role contracts, message available prompt contain no env CLI action examples.
4. Search and other tool rejection/status feedback contain no CLI `command_hint`.
5. Tool feedback exposes semantic native next action options with state-change and durability fields.
6. Product-mode env CLI cannot be used as the normal runtime action path.
7. MCP registration failure is visible and fail-closed, not silently bypassed by CLI.
8. Tool package code does not import or reason about MCP transport identity.
9. App-server close handshake fix is tested separately.

## Success Definition

The task succeeds when a product-mode Codex session naturally uses native BuddySwitch env MCP tools for runtime work, and no host-visible product-mode guidance or tool feedback trains it to call env CLI for normal runtime actions.

The task fails if the CLI path remains visible as a normal recovery path, or if the fix forces workflow scripts into tool feedback and reduces Codex's own ability to reason from atomic tool semantics.
