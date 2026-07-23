---
name: task-management
description: Use when an actor is executing a current Task Sys side frame, parent frame, or TASK PROGRESS CHECK.
---

# task-management

## Ownership

Task Sys owns execution of one current Task. This skill does not triage inbound
information, reconcile Demand outcomes, or select new work. Use native BuddySwitch env MCP tools through `env.tool`; never edit runtime objects directly.
Exact contracts come from `context.get.tool_catalog['task_sys']` and runtime
response fields. Diagnostic fallback:
`"$BUDDYSWITCH_PYTHON" scripts/turn_runtime.py status`.

Task `status` is the only lifecycle truth:
`in_progress.side_processing`, `in_progress.awaiting_parent`,
`in_progress.parent_processing`, `completed`, or `canceled`.

## Task frames

- On `task_sys.side_frame`, call `task_sys.close` when side completes the frame, `task_sys.need_parent` when parent resources are required, or `task_sys.cancel` when work must stop.
- On `task_sys.parent_frame`, complete the requested parent work and call `task_sys.close`; cancel only when work must stop without completion.
- Use `task_sys.list` or `task_sys.get` to read ongoing Task Sys task state.
- Use `task_sys.cancel` when the actor decides an active Task must stop without completion.

## [TASK PROGRESS CHECK]

Turn completion alone never completes a Task.

- For side work: close, cancel, request parent work, or continue side work without changing status.
- For parent work: close, cancel, or continue parent work without changing status.
- Continue only when concrete Task work remains. Close immediately when the frame goal and its evidence are complete.
