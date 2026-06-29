# Task Sys interrupt_submit_parent Idle Parent Bug 备忘

## 审核结论

这是一个真实 bug，不是 WebUI 观察误差。

用户通过 WebUI 向 `act-market-5a72d50492b7` 发送 IM：

```text
适当调研一下关于 gpt5.6 的灰度消息，控制一下调研时间，不要太久，
```

Task Sys side processor 已经正确判断该任务需要 parent 介入，并调用了 `task_sys.need_parent`。问题发生在 Task Sys runtime 执行 parent handoff 时：

```text
task_sys.need_parent
  -> parent_handoff_instruction()
  -> task status = parent_processing
  -> runtime instruction = interrupt_submit_parent
  -> task_sys_runtime._execute_submit_parent(interrupt=True)
  -> app_server.interrupt_turn(parent_thread)
  -> parent thread idle, no active turn
  -> interrupt raises
  -> submit parent frame never runs
```

结果是 task 被推进到 `parent_processing`，但 parent 主线程没有收到 parent frame，也没有 started turn，于是任务悬挂。

## 现场证据

### 实例状态

Actor:

```text
act-market-5a72d50492b7
role: market
main thread: 019f1380-da25-7fc3-b94a-d81f25d7695a
side thread: 019f1384-6184-76e1-9330-259c1dc68553
```

Web console 当前显示：

```json
{
  "thread_status": "idle",
  "task_sys": {
    "active_count": 1,
    "active_tasks": [
      {
        "task_id": "task-im-message-created-fe3cdc161363",
        "status": "parent_processing",
        "active_processor": "parent"
      }
    ]
  }
}
```

主线程 `thread/read --include-turns` 显示：

```json
{
  "status": {"type": "idle"},
  "turns": []
}
```

### Task Sys record

任务：

```text
state/buddyswitch/objects/task-sys/tasks/task-im-message-created-fe3cdc161363.json
```

关键字段：

```json
{
  "status": "parent_processing",
  "active_processor": "parent",
  "side_result": {
    "outcome": "need_parent"
  },
  "parent_handoff_params": {
    "relation": "direct_message_requests_parent_research",
    "interrupt": true,
    "ordering": {
      "priority": "normal",
      "timebox": "short"
    }
  }
}
```

这证明 side 并不是自主关闭，也不是漏判 parent。它已经明确 requested parent handoff。

### IM message state

原消息：

```text
msg-040444f14c70
```

message state:

```json
{
  "disposition": "unseen"
}
```

没有 reply message 指向 `msg-040444f14c70`。这符合 parent frame 没有真正提交的结果。

## 代码路径

### 1. side 工具调用 parent handoff

文件：

```text
scripts/env/tools/task_sys/_impl.py
```

`need_parent()` 先记录 side result，再生成 parent instruction，最后执行 runtime instruction：

```python
result = task_sys.record_side_result(...)
instruction = task_sys.parent_handoff_instruction(...)
parent_runtime = _execute_parent_instruction(context, instruction)
```

### 2. parent_handoff_instruction 提前推进状态

文件：

```text
scripts/env/domain/task_sys.py
```

`parent_handoff_instruction()` 根据 params 决定 instruction type：

```python
instruction_type = "interrupt_submit_parent" if params.get("interrupt") is True else "submit_parent"
```

随后立刻持久化：

```python
record.update({
  "status": "parent_processing",
  "active_processor": "parent",
})
```

这发生在 runtime actuation 成功之前。

### 3. interrupt_submit_parent 强制先 interrupt

文件：

```text
tools/launcher/task_sys_runtime.py
```

`_execute_submit_parent(..., interrupt=True)` 当前实现：

```python
if interrupt:
    interrupted = app_server.interrupt_turn(...)
    ...
result = launcher_submit_turn.submit_turn(...)
```

如果 interrupt 失败，`submit_turn()` 不会执行。

### 4. idle parent 无法 interrupt

文件：

```text
tools/launcher/app_server.py
```

`interrupt_turn()` 在没有 active in-progress turn 时直接失败：

```python
turn_id = active_turn_id(socket_path, thread_id)
if not turn_id:
    raise AppServerUnavailableError(
        f"thread {thread_id} has no active in-progress turn"
    )
```

本次 parent thread 正是 idle，因此没有 active turn 可 interrupt。

## 根因

`interrupt_submit_parent` 把 `interrupt=true` 理解为“必须成功 interrupt 后才能 submit parent”，但 Task Sys 语义更接近“如果 parent 正在运行，则先打断；如果 parent idle，则直接提交 parent frame”。

当前实现没有处理 parent idle / no active turn 场景，导致：

1. Task 状态先被推进到 `parent_processing`。
2. Runtime interrupt 在 idle parent 上失败。
3. Parent submit 没有执行。
4. Task 没有回滚到 `needs_parent`，也没有进入显式 failure 状态。
5. Web console 只看到一个悬挂的 `parent_processing` active task。

## 对照：旧 daemon runtime 已有正确行为

旧 `DaemonRuntime.submit_parent_prompt(..., interrupt_policy="ensure_stopped")` 已覆盖类似语义：

- parent idle: 不 interrupt，直接 submit。
- parent running: interrupt，等待 idle，再 submit。
- active but no active turn race: 记录 interrupt failed，但等待 idle 后继续 submit。

相关测试：

```text
tests/test_daemon_service_contract.py
  test_submit_parent_prompt_ensure_stopped_idle_submits_without_interrupt
  test_submit_parent_prompt_ensure_stopped_running_interrupts_waits_then_submits
  test_submit_parent_prompt_ensure_stopped_no_active_turn_race_waits_then_submits
```

Task Sys runtime 新路径没有复用这些保护，只测了 interrupt 成功的 happy path：

```text
tests/test_task_sys_runtime_executor.py
  test_execute_interrupt_submit_parent_interrupts_before_submit
```

缺失覆盖：

```text
interrupt_submit_parent + parent idle -> should still submit parent frame
```

## 产品影响

受影响路径：

```text
WebUI IM message
  -> im_message_created handler
  -> task_sys side frame
  -> task_sys.need_parent(params.interrupt=true)
  -> interrupt_submit_parent
  -> parent idle
```

用户表现：

- WebUI 发送需要调研、实现、复杂分析等需要 parent 的消息后，看起来没有 parent 主线程介入。
- Task Sys active count 不归零。
- Task 卡在 `parent_processing`。
- 原 IM message 保持 `unseen`，没有 reply。
- attach TUI 看不到 parent running，因为 parent turn 从未启动。

## 修复方向

首选短路径修复：在 `tools/launcher/task_sys_runtime.py` 内修正 `interrupt_submit_parent` 的执行语义。

建议语义：

```text
interrupt_submit_parent:
  if parent has active in-progress turn:
    interrupt it
    optionally wait/submit through existing app_server input semantics
  if parent is idle or no active turn:
    treat interrupt as no-op
    submit parent frame
```

实现可选路径：

1. 在 `_execute_submit_parent(interrupt=True)` 中捕获 `AppServerUnavailableError`，如果错误是 `has no active in-progress turn`，继续执行 `submit_turn()`。
2. 或在 interrupt 前读取 parent activity / active turn，只有存在 active turn 时才调用 `interrupt_turn()`。
3. 更完整地复用 `DaemonRuntime.submit_parent_prompt(..., interrupt_policy="ensure_stopped")` 的语义，但要避免重新引入旧 raw prompt 边界或 daemon 业务耦合。

同时需要处理状态推进问题：

- 当前 `parent_handoff_instruction()` 在 runtime actuation 成功前就把 task 持久化为 `parent_processing`。
- 如果后续 runtime 失败，任务会缺少恢复路径。
- 最小修复可以先保证 idle interrupt 不再失败。
- 更稳妥的后续修复是为 parent submit failure 增加可见状态或回滚到 `needs_parent`，避免任何 runtime error 都造成悬挂。

## 必补测试

### Task Sys runtime executor

新增测试：

```text
tests/test_task_sys_runtime_executor.py
```

场景：

```text
execute interrupt_submit_parent
  app_server.interrupt_turn raises AppServerUnavailableError(
    "thread thr-main has no active in-progress turn"
  )
  launcher_submit_turn.submit_turn returns turn-parent-1
expect:
  result.action == "interrupt_submit_parent"
  result.turn_id == "turn-parent-1"
  no interrupted_turn_id
  submit_turn was called
```

### Task Sys tool side processing

新增或扩展测试：

```text
tests/test_task_sys_side_processing.py
```

场景：

```text
task_sys.need_parent(params.interrupt=true)
  daemon execute_task_sys_instruction handles idle parent as no-op interrupt
expect:
  tool result ok
  parent_runtime.turn_id exists
  task status parent_processing only after parent submission succeeds
```

如果引入 failure recovery，还应新增：

```text
parent runtime execution raises
expect:
  task does not remain silently stuck in parent_processing
```

### 产品 smoke

复测本次场景：

1. WebUI 向 active market actor 发送需要调研的 IM。
2. Task Sys task 进入 parent handoff。
3. Parent main thread 从 idle 变为 running 或产生 parent turn。
4. Web console active task 不再长期卡在 `parent_processing`。
5. 原 IM message 后续由 parent 或 checkpoint 流程明确处理。

## 验收标准

1. `interrupt_submit_parent` 在 parent idle 时仍会 submit parent frame。
2. `interrupt_submit_parent` 在 parent running 时仍会先 interrupt 再 submit。
3. `task_sys.need_parent(params.interrupt=true)` 不会因为 parent idle 悬挂。
4. 相关 unit tests 覆盖 idle、running、no-active-turn race。
5. WebUI IM 调研请求能触发 parent thread 可观察的 turn。
6. 不恢复旧 raw inbound -> parent prompt 路径。

## 当前悬挂任务

当前运行时已有一个受影响任务：

```text
task-im-message-created-fe3cdc161363
status: parent_processing
active_processor: parent
message_id: msg-040444f14c70
```

不要手动编辑 `state/buddyswitch/objects/**` 修复它。应先修代码路径，再通过产品命令或后续恢复机制处理悬挂任务。

## 一句话结论

Task Sys 已经正确请求 parent，但 `interrupt_submit_parent` 在 parent idle 时先 interrupt 失败、没有继续 submit，且 task 状态已提前写成 `parent_processing`；这是 Task Sys runtime parent handoff 的边界 bug，缺少 idle/no-active-turn 覆盖。
