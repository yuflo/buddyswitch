# Native-First Env Tool Surface Cleanup Task

Date: 2026-05-31

## 任务一句话

把 BuddySwitch 产品运行时 env tools 从“CLI 是事实主路径，MCP 只是新增能力”的过渡态，收口成 Codex-native MCP-first 的统一工具面：

```text
runtime registry owns every env action contract
  -> native MCP exposes every registry action
  -> product-mode Codex can discover and call those actions natively
  -> active skills / AGENTS / role contracts / runtime tips teach native-first
  -> CLI remains only as debug fallback and test harness
```

这不是 `message` 单点修复。`message` 只是暴露问题最明显的入口。

本任务必须覆盖所有 BuddySwitch env tools，也就是当前 runtime registry 支持的 9 个 tool / 40 个 action。

## 当前核心问题

上一轮 A+ 已经把 env actions 投影成 native MCP tools，并在产品实例里注册了 `buddyswitch-env` MCP server。但真实日志仍然大量走：

```bash
python3 scripts/env/client.py ...
```

这说明当前瓶颈已经不是“有没有 MCP server”，而是：

```text
BuddySwitch 自己的提示面、skill 面、contract 面、测试约束仍在训练 Codex 走 CLI。
```

如果这次只继续修 `message` 文案，问题会重复出现在 `task`、`request`、`track`、`artifact`、`comment`、`context`、`search`、`evidence` 上。

## 已确认事实

### 1. Registry 全集

当前 registry 支持以下 env tools：

| Tool | Actions |
| --- | --- |
| `artifact` | `list`, `get`, `update_metadata`, `list_attachments`, `get_attachment`, `create_revision`, `attach_file` |
| `comment` | `list`, `add`, `resolve` |
| `context` | `list_sources`, `summarize`, `get` |
| `evidence` | `approve_downgrade`, `issue_browser` |
| `message` | `send`, `contacts`, `conversation`, `list` |
| `request` | `list`, `get`, `block`, `create`, `cancel`, `complete`, `accept` |
| `search` | `open_browser`, `status`, `request` |
| `task` | `propose`, `confirm`, `current` |
| `track` | `list`, `add_update`, `create`, `archive`, `open`, `add_proof`, `add_material`, `update_now` |

Native projection 当前返回 40 个 specs，`message__contacts`、`message__send`、`message__list`、`message__conversation` 都存在。

### 2. MCP server 和 launcher 注册已存在

当前代码已经有：

- `scripts/env/tool_runtime/native_mcp.py`
- `tools/launcher/env_tool_mcp_server.py`
- `tools/launcher/env.sh` 中的 `buddyswitch_env_mcp_ensure`
- `buddyswitch-codex` 产品实例启动时注册 `buddyswitch-env`
- `tests/test_env_native_mcp_projection.py`
- `tests/test_env_native_mcp_server.py`

实例 config 中也已经出现：

```toml
[mcp_servers.buddyswitch-env]
command = "python3"
args = [".../tools/launcher/env_tool_mcp_server.py", ...]
default_tools_approval_mode = "approve"
```

实例日志显示 Codex 能 list 到：

```text
server_name=buddyswitch-env tool_count=40
```

### 3. 但“自然 native 调用”尚未完成验收

`tools/list` 成功不等于模型已经自然调用 native tools。

真实日志中仍观察到：

- message arrival tip 提醒 native tool，但同时给出 `Fallback CLI`；
- agent 读 `message-tool` skill 后复制 CLI 示例；
- 实际调用仍是 `exec_command` 跑 `python3 scripts/env/client.py message list --payload '{}'`；
- 没有看到 `buddyswitch-env` MCP tool call 记录；
- Codex 当前可能因为 MCP tool 总量、tool_search/deferred 策略、或 MCP namespace 前缀，让裸 `message__list` 并不是实际可见调用名。

因此本任务必须把“native MCP 已注册”和“Codex 会自然发现并优先调用”分开验证。

## 已确认残留面

### Active prose 残留

只读扫描显示 active guidance 中仍有 CLI-first 残留：

| Area | CLI mentions | Files |
| --- | ---: | ---: |
| `buddyswitch/skills/shared` | 28 | 6 |
| `buddyswitch/skills/market` | 30 | 15 |
| `buddyswitch/skills/dev` | 1 | 1 |
| `buddyswitch/skills/design` | 1 | 1 |
| `buddyswitch/skills/test` | 1 | 1 |
| `framework/contracts` | 15 | 5 |

其中最影响行为的是：

- `buddyswitch/skills/shared/message-tool/SKILL.md`
- `buddyswitch/skills/shared/task-management/SKILL.md`
- `buddyswitch/skills/shared/request-tool/SKILL.md`
- `buddyswitch/skills/shared/track-tool/SKILL.md`
- `buddyswitch/skills/shared/artifact-tool/SKILL.md`
- `buddyswitch/skills/shared/comment-tool/SKILL.md`
- `framework/contracts/{pm,market,design,dev,test}.md`
- `buddyswitch/skills/market/*/SKILL.md` 中的 `search open-browser` CLI 调用
- `tools/launcher/message_available_handler.py`

### 测试残留

部分测试当前不是防止 CLI-first，而是在固定 CLI-first 或过渡态。例如：

- 要求 AGENTS 包含 `context summarize --payload '{}'`
- 要求 message available prompt 包含 `message list --payload '{}'`
- 要求 shared message skill 包含 `message contacts --payload`
- 只限制 CLI 次数，而不是限制 active guidance 的主路径

这些测试需要改成 native-first governance tests。

## 正确架构边界

### Registry 是唯一 action contract source

`scripts/env/tools/<tool>/tool.py` 和 `ActionDefinition` 继续拥有：

- action name；
- payload schema；
- response schema；
- permission；
- mutation/read/write/durability/visibility；
- use_when / do_not_use_when；
- success effect；
- failure guarantee；
- risk hints。

不要在 skill、AGENTS、role contract 中复制完整 schema。

### Native MCP 是产品会话主路径

产品模式下，Codex 应通过 native BuddySwitch env MCP tools 调用 runtime state：

```text
context__summarize
message__list
message__conversation
message__contacts
message__send
task__current
task__propose
request__get
track__open
artifact__get
search__open_browser
...
```

实际 model-visible 名称可能带 MCP namespace，例如 `mcp__buddyswitch_env`。文案不能假设裸 `message__list` 一定是唯一可见名字。实施时必须用当前 Codex 版本验证实际可见名和调用路径。

### CLI 只保留为 debug fallback

`scripts/env/client.py` 不删除，因为它仍然有价值：

- 本地 debug；
- tests；
- broker 诊断；
- MCP server 故障时的人工 fallback；
- 运行时 contract smoke。

但它不能再是 active product guidance 的默认路径。

CLI 示例只允许出现在明确标注的 debug/fallback 文档、CLI tests、历史 memo 中。Active skill / AGENTS / role contract / runtime tips 不应把 CLI 当主路径教给 agent。

### Skill 只保留 workflow note

Skill 应回答：

- 什么时候用这个 tool；
- 常见工作流顺序；
- 哪些状态要先读；
- 哪些行为不要做；
- 如何从 runtime response 继续。

Skill 不应提供 CLI payload 教程，也不应成为第二份 tool catalog。

### Runtime tip 不教 fallback

`MESSAGE AVAILABLE` 这类 runtime tip 应短、准、单路径：

```text
[MESSAGE AVAILABLE]
A direct message is available for this actor.
Use the BuddySwitch env message inbox/conversation native tool to read it.
```

不要同时给 native 和 CLI 两条同级路径。否则模型会抓住更熟悉的 shell 路径。

## 本任务覆盖范围

### 必须覆盖

1. All env tools in registry: 9 tools / 40 actions.
2. Native MCP projection and server coverage tests.
3. Product-mode launcher MCP registration and Codex config.
4. Codex model-visible discovery behavior, including direct vs deferred exposure.
5. Runtime signal tips, especially message available.
6. Shared runtime tool skills.
7. Role contracts.
8. Buddy AGENTS templates.
9. Market/search skills and other role skills with runtime CLI calls.
10. Tests that currently force CLI-first prose.
11. Residual scans for active guidance.

### 不覆盖

以下不是本任务目标：

- 不删除 `scripts/env/client.py`。
- 不重写 runtime broker。
- 不重写 tool registry。
- 不新增 generic workflow engine、plugin layer、adapter layer。
- 不为旧 CLI payload 加 alias。
- 不改外部 Codex、GitHub、Gmail、Chrome DevTools 工具行为。
- 不把历史 memo 全部重写。历史 memo 可以保留过去证据，但不能作为 active guidance 被测试或安装。

## 实施任务建议

### Task 1: Native exposure audit

目标：先证明当前 native exposure 到底是什么状态。

检查点：

- `native_mcp.list_native_tool_specs()` 覆盖所有 `registry.supported_tools()` / `supported_actions()`。
- MCP server `tools/list` 返回 40 个 tool。
- 产品实例 config 正确注册 `buddyswitch-env`。
- Codex turn logs 里能看到 `buddyswitch-env tool_count=40`。
- 进一步确认 model-visible tool 是直接暴露，还是被 tool_search/deferred 机制隐藏。
- 确认当前可调用名是否带 `mcp__buddyswitch_env` namespace。

验收不是只看 `tools/list`，而是要证明 agent 在产品 turn 中有 native discovery/call path。

### Task 2: Message available tip cleanup

目标：清掉最明显的 CLI fallback 诱导。

修改点：

- `tools/launcher/message_available_handler.py`
- `tests/test_message_available_handler.py`

要求：

- prompt 不出现 `python3 scripts/env/client.py`。
- prompt 不出现 `Fallback CLI`。
- prompt 不出现不被 schema 接受的 `message_id` 读法。
- prompt 指向 native inbox/conversation action，但不硬编码错误的 model-visible namespace。

### Task 3: Shared tool skill cleanup

目标：6 个 shared runtime tool skills 都改成 native-first workflow notes。

修改点：

- `buddyswitch/skills/shared/artifact-tool/SKILL.md`
- `buddyswitch/skills/shared/comment-tool/SKILL.md`
- `buddyswitch/skills/shared/message-tool/SKILL.md`
- `buddyswitch/skills/shared/request-tool/SKILL.md`
- `buddyswitch/skills/shared/task-management/SKILL.md`
- `buddyswitch/skills/shared/track-tool/SKILL.md`

要求：

- 删除 CLI command blocks。
- 删除 `CLI Payload Rule` 主体。
- 保留 workflow order 和 boundary rules。
- 指向 native BuddySwitch env MCP tools。
- 精确 schema 只指向 runtime registry/native tool schema，不复制 payload blocks。
- 如果保留 fallback，必须是 debug-only 一句话，不给完整命令吸引模型复制。

### Task 4: Context/search/evidence coverage

目标：补齐非 shared skill 的 env tools。

重点：

- `context` 是启动入口，不能继续教 `context summarize` CLI-first。
- `search` 在 market skills 中大量 CLI-first，必须改成 native `search__open_browser` / browser cockpit workflow。
- `evidence` 当前残留少，但必须纳入 registry-wide test，避免没有 shared skill 就被漏掉。

修改点：

- `framework/contracts/*`
- `buddyswitch/skills/market/*/SKILL.md`
- `buddyswitch/skills/dev/enter-dev-workspace/SKILL.md`
- `buddyswitch/skills/design/shape-prototype/SKILL.md`
- `buddyswitch/skills/test/smoke-test/SKILL.md`

### Task 5: Role contracts and buddy AGENTS cleanup

目标：产品 buddy 启动指导不再 CLI-first。

修改点：

- `framework/contracts/{pm,market,design,dev,test}.md`
- `tools/launcher/assets/buddies/{pm,market,design,dev,test}/AGENTS.md`

要求：

- 不再写 “Start with `python3 scripts/env/client.py context summarize`”。
- 改为 “Start with native BuddySwitch env context summary tool when runtime context is needed.”
- 不再提供一串 CLI examples。
- 保留关键 runtime boundary：不要直接编辑 `buddyswitch/objects/**`，durable state 通过 env tools。

### Task 6: Tests become governance, not transition lock-in

目标：测试不再要求 CLI prose 存在。

修改点：

- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py`
- `tests/test_message_available_handler.py`
- `tests/test_host_decision_surface_product_mode.py`
- `tests/test_buddyswitch_launcher.py` 中和 AGENTS/MCP config 相关断言

新增或调整检查：

- Every registry action has a native MCP spec.
- Active product guidance must not contain CLI-first env tool examples.
- Active guidance may mention CLI only in explicit debug fallback sections, preferably without copyable commands.
- Message available prompt must not contain CLI fallback.
- Role contracts and AGENTS must prefer native BuddySwitch env MCP tools.
- No active guidance references unsupported actions such as stale `task get`.
- Search skills must reference native search action, not CLI command.

### Task 7: End-to-end behavior validation

目标：证明真实产品路径真的变了。

最小验证：

1. Start fresh PM and Market instances.
2. Confirm `buddyswitch-env` MCP registered in both.
3. Trigger a message.available signal.
4. Inspect session logs:
   - expected: first read path uses native BuddySwitch env message action, or native discovery path if tools are deferred;
   - forbidden: first read path is shell `python3 scripts/env/client.py message list`.
5. Send reply and confirm state through native path.
6. Stop/delete test instances or record why they are intentionally retained.

## Residual scan policy

After implementation, run scans against active guidance:

```bash
rg -n "python3 scripts/env/client.py" \
  buddyswitch/skills \
  framework/contracts \
  tools/launcher/assets/buddies \
  tools/launcher/*handler*.py
```

Expected:

- zero CLI-first references in active guidance; or
- only allowlisted debug fallback references with tests proving they are not primary workflow instructions.

Also scan for stale names:

```bash
rg -n "message\\.list|message\\.send|task get|context list_sources|Fallback CLI|CLI Payload Rule" \
  buddyswitch/skills \
  framework/contracts \
  tools/launcher/assets/buddies \
  tools/launcher/*handler*.py \
  tests
```

Expected:

- no stale product guidance;
- tests assert native-first behavior instead of preserving old CLI-first behavior.

## Verification commands

Focused pure tests:

```bash
python3 -m pytest \
  tests/test_env_native_mcp_projection.py \
  tests/test_env_native_mcp_server.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  tests/test_message_available_handler.py \
  tests/test_host_decision_surface_product_mode.py \
  -q
```

Focused launcher tests:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "mcp or codex_config or product_instance" -q
```

Residual process check after launcher or instance tests:

```bash
pgrep -fl "instance_daemon.py|central_daemon.py|runtime_broker|app_server.py|fake_codex|chrome_devtools_cockpit_proxy.py" || true
```

Manual product validation:

```bash
./buddyswitch-codex instance start --buddy pm
./buddyswitch-codex instance start --buddy market
```

Then trigger/observe a real message flow and inspect session logs for native MCP tool usage.

## Definition of Done

This task is done only when all of the following are true:

1. All 9 env tools / 40 actions are covered by native MCP projection tests.
2. Product-mode launcher registers `buddyswitch-env` correctly.
3. Actual Codex model-visible native discovery path is verified, including direct vs deferred behavior.
4. Active runtime tips do not provide CLI fallback as primary or co-primary instruction.
5. Shared tool skills are native-first and do not contain copyable CLI workflow examples.
6. Role contracts and buddy AGENTS are native-first.
7. Market/search skills no longer teach CLI-first `search open-browser`.
8. Tests no longer require CLI-first prose.
9. Residual scans pass against active guidance.
10. A real PM/Market message flow is validated without the first env action going through shell CLI.

## Key risk

The main risk is confusing three different states:

```text
MCP server registered
  != MCP tools model-visible
  != Codex naturally chooses native env tools first
```

This task must verify the third state. If the tools are registered but deferred behind tool search or hidden by namespace mismatch, the fix belongs in launcher/config/discovery guidance, not in another layer of CLI prompt instructions.

## Recommended implementation posture

Follow SHARP:

- do not add compatibility wrappers;
- do not preserve CLI-first examples in active guidance;
- do not expand into a generic tool platform redesign;
- replace the active guidance directly;
- keep CLI as debug harness, not product behavior;
- prove the behavior with tests and a real product message flow.
