# Web Management Input 残留清扫备忘

## 背景

Task Sys proactive rebuild 后，Web 管理台面向 actor 的用户消息入口应走 IM 路径：

```text
WebUI message composer
  -> POST /api/web/im/messages
  -> IM message.created
  -> daemon im_message_created handler
  -> task_sys.ingest(source_type=im.message.created)
  -> side processing
  -> message.send(reply_to=...)
  -> task_sys.close
```

这条路径已经在产品体验中跑通。用户从 WebUI 向 `act-dev-e4336a29750f` 发送“告诉我你能做些什么事”后，系统生成：

- inbound message: `msg-176fafb02a86`
- Task Sys task: `task-im-message-created-bb9036243fd7`
- reply message: `msg-257854a0ec14`
- task status: `closed`
- side result: `outcome=close`
- parent handoff: `null`

主线程 attach TUI 没有看到 running 是符合当前实现的：WebUI 消息经 IM wake 进入 Task Sys side thread，能本地解决时不会提交到 parent 主线程。

## 当前确认

### 可见 WebUI 已走 IM

前端 Send 按钮调用 `sendImDraft()`，请求目标是：

```text
POST /api/web/im/messages
```

相关位置：

- `tools/launcher/assets/web-management/app.js`
  - `sendImDraft()`
  - Send button click handler

HTML 文案也已经是消息语义：

- `Message`
- `Send a direct message to the selected actor.`

这部分不是旧 actor input 入口。

### 后端仍有 input API 残留

Web management 后端仍暴露旧路由：

```text
POST /api/instances/<actor-id>/input
```

当前代码路径：

```text
tools/launcher/web_management.py
  handle_api()
    action == "input" -> self._send_input(actor_id, body)

  _parse_instance_action_path()
    path.endswith("/input") -> "input"

  _send_input()
    parses {"text": ...}
    calls _send_input_under_lock()

  _send_input_under_lock()
    calls _run_input_command()

  _run_input_command()
    runs:
      ./buddyswitch-codex instance input <actor-id> --text <text> --json
```

测试里也还有该 Web API 的覆盖：

```text
tests/test_web_management.py
  /api/instances/act-pm-demo/input
```

这说明“WebUI 可见操作已迁移到 IM”与“Web management 后端 input API 完全清干净”不是同一件事。后者尚未完成。

## Fix 目标

清除 Web management 层面的旧 actor input API 残留，让 Web 管理台只保留 IM 消息入口，不再提供 `/api/instances/<actor>/input` 作为可调用 Web API。

目标完成后：

- WebUI Send 仍走 `/api/web/im/messages`。
- Web management 后端不再解析 `/api/instances/<actor>/input`。
- `web_management.py` 不再有 `_send_input*` 和 `_run_input_command()`。
- `tests/test_web_management.py` 不再测试 Web API input 路由。
- 旧 URL `POST /api/instances/<actor>/input` 应返回 404。
- Task Sys 的 CLI/product ingress 不受影响。

## 非目标

本清扫不删除 CLI：

```text
./buddyswitch-codex instance input <actor-id> --text ...
```

CLI `instance input` 仍是 Task Sys `source_type=user.input` 的产品体验入口，可用于命令行快速投递任务。它不是 Web management UI 残留。

本清扫也不删除：

- `/api/web/im/messages`
- IM domain state
- `im_message_created` daemon handler
- `task_sys.ingest()` user.input / im.message.created 支持
- `instance side` 调试入口
- TUI attach 主线程能力

## 建议改动范围

### 1. 删除 Web input route

文件：

```text
tools/launcher/web_management.py
```

删除：

- `if method == "POST" and action == "input": ...`
- `_parse_instance_action_path()` 中 `/input` 分支
- `_send_input()`
- `_send_input_under_lock()`
- `_run_input_command()`

删除后，`POST /api/instances/<actor>/input` 应落到现有 404 分支。

### 2. 更新 Web management 测试

文件：

```text
tests/test_web_management.py
```

处理原则：

- 删除验证 `/api/instances/<actor>/input` 成功调用的测试。
- 如有必要，新增或调整一个 404 覆盖，证明旧 input route 不再存在。
- 保留 `/api/web/im/messages` 的测试，并确认它是 WebUI 消息发送唯一后端路径。

### 3. 更新 UI contract 测试

文件：

```text
tests/web_management_ui_contract.test.js
```

当前已覆盖 `/api/web/im/messages`。清扫时确认没有任何 contract 仍期待 `/api/instances/<actor>/input`。

### 4. 残留搜索

清扫完成后执行：

```bash
rg -n "/api/instances/.*/input|action == \"input\"|_send_input|_run_input_command|instance input for" tools/launcher tests -S
```

预期：

- `tools/launcher/web_management.py` 和 Web UI 测试中不再有 Web API input 残留。
- `tools/launcher/instance.sh`、`buddyswitch-codex`、launcher CLI 测试中仍可出现 `instance input`，因为 CLI 入口不属于本次删除目标。

## 验收标准

1. WebUI 发送消息仍成功创建 IM message，并能触发 actor 回复。
2. Web console 显示 Task Sys active count 能正常刷新。
3. `POST /api/instances/<actor>/input` 返回 404。
4. `POST /api/web/im/messages` 测试仍通过。
5. `tests/test_web_management.py` 中没有成功路径依赖 `/api/instances/<actor>/input`。
6. 残留搜索确认 Web management input API 已删除。
7. 不影响 CLI `./buddyswitch-codex instance input`。

## 建议验证命令

Focused verification:

```bash
python -m pytest -q tests/test_web_management.py
node --test tests/web_management_ui_contract.test.js
```

Product smoke:

```bash
./buddyswitch-codex web --host 127.0.0.1 --port 8765
```

在 WebUI 选择一个 active actor，发送消息，确认：

- `state/im/messages/*.json` 出现 inbound 和 reply。
- `state/buddyswitch/objects/task-sys/tasks/*.json` 出现 `source_type=im.message.created` 任务。
- 任务最终 `status=closed` 或按需要进入 parent handoff。
- Web console `task_sys.active_count` 回到 `0`。

Route removal check:

```bash
curl -i -X POST \
  http://127.0.0.1:8765/api/instances/<actor-id>/input \
  -H 'Content-Type: application/json' \
  --data '{"text":"should be gone"}'
```

预期 HTTP status: `404`。

Residue check:

```bash
rg -n "/api/instances/.*/input|action == \"input\"|_send_input|_run_input_command|instance input for" tools/launcher tests -S
```

## 风险和注意事项

- 不要因为删除 Web API input route 而删除 CLI `instance input`。CLI 仍是 `user.input` -> Task Sys 的直接体验入口。
- 不要把 WebUI message composer 改回 actor input。WebUI 应保持 IM message 语义。
- 如果测试中有 mock 依赖 `_run_input_command()`，应删除对应测试，而不是给旧路径补兼容。
- 如果外部脚本已经调用 `/api/instances/<actor>/input`，本阶段按 SHARP 原则默认不保留兼容，除非明确发现真实外部契约。

## 一句话结论

WebUI 可见发送入口已经迁移到 IM，但 Web management 后端还残留 `/api/instances/<actor>/input` 旧 API；下一步 fix 应删除该 Web API 和对应测试残留，同时保留 CLI `instance input` 作为 Task Sys user.input 体验入口。
