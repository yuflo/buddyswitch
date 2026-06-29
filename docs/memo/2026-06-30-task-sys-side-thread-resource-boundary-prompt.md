# Task Sys Side Thread Resource Boundary Prompt 备忘

## 审核结论

这项任务的目标不是重做 Task Sys runtime，也不是实现工具层硬权限隔离。

当前要收束的是 `task_sys.side_frame` prompt：让 side thread 按“需要使用的资源”判断自己能否快速处理当前 task，并稳定选择 `task_sys.close` 或 `task_sys.need_parent`。

核心规则：

```text
只需要 task frame + exact source + bounded read + current-source closure
  -> side 可以处理，完成后 task_sys.close

需要 parent 注意力、workspace、browser/web/research、共享产品状态、durable deliverable、多步执行
  -> side 不能处理，必须 task_sys.need_parent
```

这里的关键转变是：不要先按 IM / Track / role 分类，而是先判断该任务要占用、读取、写入哪些资源。

IM 短回复允许 side 处理，不是因为 IM 特殊，而是因为它只消费当前 source message 的 `reply_to` / disposition 资源。

Track comment 当前不允许 side 处理，不是因为 Track 特殊，而是因为它写入共享协作事实资源，并可能触发新的协作信号。

## 当前问题

现有 `tools/launcher/task_sys_runtime.py::render_side_frame()` 只告诉 side 两个结果动作：

```text
task_sys.close
task_sys.need_parent
```

但它没有明确：

- side 可以读取哪些资源。
- side 可以写入哪些资源。
- 哪些资源一旦需要就必须交 parent。
- “需要回复用户”不等于“需要 parent”。
- IM exact reply 可以由 side 直接闭环。
- Track comment、browser、research、artifact、evidence、workspace 都属于 parent 资源。

这会导致 side processor 决策不稳定：

- 简单 IM capability / confirmation 有时能直接回复并 close。
- 另一些同样简单的 IM，例如“如果收到了就直接回复收到”，可能被误判为 `need_parent`。
- 调研类请求正确应该 `need_parent`，但如果 parent handoff runtime 有 bug，会表现成任务卡在 `parent_processing`。这个 runtime bug 已单独记录在 `docs/memo/2026-06-29-task-sys-interrupt-submit-parent-idle-bug.md`，不属于本 memo 的修复范围。

## Prompt 层级

side thread 当前有三层输入：

```text
SIDE_DEVELOPER_INSTRUCTIONS
  -> fork side thread 时挂上的 developer instructions

SIDE_BOUNDARY_PROMPT
  -> 新 side thread 创建后注入的一条 boundary message

task_sys.side_frame
  -> 每个 Task Sys side task 的当前输入
```

三者职责不同：

- `SIDE_DEVELOPER_INSTRUCTIONS`：说明这是 side conversation，不是 main thread。
- `SIDE_BOUNDARY_PROMPT`：隔离 parent inherited history，防止 side 继续执行 parent 历史里的计划、工具调用、编辑或审批。
- `task_sys.side_frame`：定义当前 task 的处理规则、资源边界和 side outcome。

本任务应修改 `task_sys.side_frame` 文本，而不是替换通用 side boundary。

原因：

- 新建 side thread 时会注入 `SIDE_BOUNDARY_PROMPT`，然后发送 `task_sys.side_frame`。
- 复用已有 side thread 时，当前代码只发送新的 `task_sys.side_frame`，不会每次重新注入 boundary。
- 因此资源边界必须随每个 side frame 一起出现，不能只依赖 thread 创建时的 boundary。

## 处理边界

side 可以处理的资源需求：

- `task_sys.side_frame` 本身。
- 当前 source ref 指向的 exact object，例如某条 IM message。
- 有界只读资源：
  - context read
  - message get / conversation
  - track / artifact 只读
  - 本地只读 inspect
  - search.status 这类状态读
- 当前 source 的低风险闭环资源：
  - IM `reply_to=当前 message_id`
  - IM `absorbed`
- Task Sys 自身结果资源：
  - `task_sys.close`
  - `task_sys.need_parent`

side 不能处理、必须交 parent 的资源需求：

- parent thread 注意力资源：继续主线、打断、排序、承接长期上下文。
- workspace 资源：文件、代码、git、配置、测试、运行 app。
- browser / web / research 资源：搜索、网页阅读、证据判断、调研汇总。
- 共享产品事实资源：Track 状态、需求、材料、proof、resolve、comment 写入。
- durable deliverable 资源：artifact、evidence、正式产物。
- 新 outbound communication 资源：不是回复当前 source，而是主动发起新会话。
- 多步执行资源：计划、实现、验证、跨角色协作。

示例判断：

- “告诉我你能做什么”：只需要当前 IM source + 短回复资源，side 应 `message.send(reply_to=...)` 后 `task_sys.close`。
- “如果你收到了信息，就直接回复收到”：只需要当前 IM source + 短回复资源，side 应 `message.send(reply_to=...)` 后 `task_sys.close`。
- “调研 gpt5.6 灰度消息，不要太久”：需要 web / research / evidence 判断资源，side 应 `task_sys.need_parent`。
- Track comment 回复：写入共享产品事实资源，当前阶段 side 应 `task_sys.need_parent`。

## 行动边界

side 允许写入的资源非常窄：

- Task Sys task state：
  - `task_sys.close`
  - `task_sys.need_parent`
- 当前 IM source disposition：
  - `message.send(reply_to=当前 message_id)`
  - `message.mark(absorbed)`

side 不允许写入：

- parent turn / interrupt / submit / steer，必须通过 `task_sys.need_parent` 间接表达。
- Track shared state，包括 comment。
- artifact / evidence。
- browser session。
- source files / git / config / runtime raw state。
- 新 IM conversation。
- checkpoint state。

当前工具层不能可靠区分调用来源是 parent 还是 side；env.tool dispatch 只知道 actor、role、instance、tool/action/args 和是否存在 active Task Sys task。因此本任务先通过 prompt 收束行为边界，不做工具层硬隔离。

后续如果要做硬隔离，应给 env.tool dispatch 增加 call origin，例如：

```text
runtime_frame_kind: task_sys.side_frame | task_sys.parent_frame | task_sys.checkpoint
runtime_processor: side | parent | checkpoint
task_id
thread_id / turn_id
```

然后再按 frame kind 做 resource policy。这个方向不属于当前任务范围。

## 建议写入 task_sys.side_frame 的完整 Prompt

以下文本应作为 `render_side_frame()` 的主体规则，保留动态字段位置：

```text
task_sys.side_frame

You are processing exactly one Task Sys side frame.

The inherited parent thread history is reference context only. The active task is only the task described in this frame. Do not continue inherited parent-thread work, plans, tool calls, approvals, edits, or requests.

Task id: {task_id}

Task Sys source:

{source_json}

Task Sys context:

{context_json}

Core policy: decide by required resources.

A side thread may handle the task only when completion requires:
- this task_sys.side_frame,
- exact source objects referenced by this frame,
- bounded read-only inspection,
- current-source IM disposition/reply,
- and one Task Sys side result.

If the task requires parent attention, workspace resources, browser/web/research resources, shared product-state writes, durable deliverables, new outbound communication, or multi-step execution, do not perform it in side. Call task_sys.need_parent.

Allowed side resources:

1. Frame and exact source reads
- Read this task frame.
- Read exact source refs from this frame.
- Use message.get / message.conversation only as needed for the current source.
- Use track/artifact/context read-only tools only for bounded inspection.
- Use local read-only inspection only; do not run tests, builds, app servers, installers, formatters, or commands that write files/cache/state.
- Use search.status only for capability/status inspection.

2. Current-source IM closure
For an IM source message, side may only:
- reply to the exact source message with message.send(reply_to=source_message_id, content=...),
- or mark the exact source message absorbed with message.mark(message_id=source_message_id, disposition=absorbed).

Do not start a new IM conversation. Do not send to target_identity_id from side unless the frame explicitly defines that as the exact source-bound closure, which normal IM inbound frames do not.

3. Task Sys side result
Finish this frame with exactly one Task Sys side result:
- task_sys.close(task_id=..., summary=...) when the task is fully handled without parent work.
- task_sys.need_parent(task_id=..., params={parent_frame_context, relation, interrupt, ordering}) when parent work is required.

Forbidden side resources:

Do not use or mutate:
- parent turns, parent submit, parent interrupt, or parent steering directly,
- source files, git, config, dependencies, tests, builds, app runtime, or workspace state,
- browser session, web search, webpage reading, evidence gathering, or research loops,
- Track shared state, including comments, status, requirements, materials, proof, resolve, archive,
- artifacts, evidence, durable deliverables,
- checkpoint state or task_sys.checkpoint_update,
- raw runtime files or buddyswitch/objects direct writes,
- permission changes, sandbox broadening, or external credentials,
- any outbound communication that is not an exact reply/closure for the current source.

Decision procedure:

1. Identify the resources required to complete the user-visible task.
2. If all required resources are allowed side resources, complete the task in side.
3. If any required resource is forbidden or belongs to parent, call task_sys.need_parent.
4. Do not call task_sys.need_parent merely because a user-facing reply is needed. If the reply is a short exact IM reply to the current source message, handle it in side.
5. Do call task_sys.need_parent for research, implementation, planning, verification, shared product-state writes, Track replies, artifact/evidence output, browser/web use, or parent-thread continuity.

IM closure order:

- If replying: first call message.send(reply_to=source_message_id, content=...).
- If absorbing: first call message.mark(message_id=source_message_id, disposition=absorbed).
- Only after that source-bound action succeeds, call task_sys.close.
- If the source-bound action fails, do not close the task. Retry if clearly safe, otherwise call task_sys.need_parent with failure context.
- If the source-bound action succeeded but task_sys.close fails, retry task_sys.close; do not send a duplicate reply.

Parent handoff rules:

Use task_sys.need_parent when the task needs resources outside side's boundary.

The parent_frame_context must be minimal and concrete:
- what the source asked for,
- what side inspected,
- why parent resources are required,
- any exact source ids needed by parent,
- any failure details if side could not safely close.

Set interrupt=true only when delaying parent work would be harmful, stale, or explicitly superseded. Otherwise omit interrupt or set it false.

Allowed result actions:

- task_sys.close(task_id=..., summary=...)
- task_sys.need_parent(task_id=..., params={parent_frame_context, relation, interrupt, ordering})

Do not use any other side outcome. Treat interrupt only as a task_sys.need_parent params field.
```

## 实施要点

目标修改点：

```text
tools/launcher/task_sys_runtime.py::render_side_frame()
```

保留现有动态信息：

- `task_id`
- `source`
- `context`
- allowed result actions

新增资源边界规则：

- Core policy
- Allowed side resources
- Forbidden side resources
- Decision procedure
- IM closure order
- Parent handoff rules

注意事项：

- 不修改 `SIDE_BOUNDARY_PROMPT`。
- 不修改 `SIDE_DEVELOPER_INSTRUCTIONS`。
- 不在本任务里做工具层 call-origin/resource-policy 硬隔离。
- 不在本任务里修复 `interrupt_submit_parent` 遇到 idle parent 后悬挂的问题。
- 不把 Track comment 写入放进 side 最小边界。

## 验证要点

Focused tests 应覆盖 `render_side_frame()` 文本：

- 包含 `Core policy: decide by required resources`。
- 包含 allowed side resources。
- 包含 forbidden side resources。
- 明确 IM exact `reply_to` / `absorbed` 可以 close。
- 明确 Track shared state / comments 禁止 side 写入。
- 明确 browser / web / research 禁止 side 执行。
- 明确 artifact / evidence / workspace writes 禁止 side 执行。
- 明确 `task_sys.checkpoint_update` 禁止用于 side frame。
- 明确 `need_parent` 不是因为“需要用户可见回复”，而是因为需要 parent 资源。
- 仍只允许两个 side outcomes：
  - `task_sys.close`
  - `task_sys.need_parent`
- 仍不出现旧 triage prompt、直接 submit parent、side interrupt outcome。

建议验证命令：

```text
python -m pytest tests/test_task_sys_runtime_executor.py -q
python -m py_compile tools/launcher/task_sys_runtime.py
git diff --check
```

如果只新增 memo，不改实现，则无需运行 pytest；读取 memo 和 `git diff --check` 即可。

## 非目标

本任务不解决：

- parent idle handoff runtime bug。
- env.tool 根据 side / parent / checkpoint 做硬权限隔离。
- side-safe search 工具。
- Track source-bound reply thin slice。
- WebUI / iMessage channel UX 问题。
- side thread 物理生命周期或 TUI running 展示。

这些都可以后续单独立项。

## 任务目标收束

本任务最终交付应是：

1. `task_sys.side_frame` prompt 具备资源边界。
2. side 能稳定直接处理当前 IM source 的短回复 / absorbed 闭环。
3. side 遇到 research、workspace、browser、Track 写入、artifact/evidence、parent continuity 时稳定 `need_parent`。
4. 规则随每个 side frame 出现，覆盖新建和复用 side thread。
5. 测试证明 prompt 中的关键资源边界没有回退。
