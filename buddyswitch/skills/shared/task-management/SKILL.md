---
name: task-management
description: Use when processing Task Sys side frames, parent-thread decisions, or ongoing Task Sys task state through BuddySwitch env tools.
---

# task-management

## Principles
- Task state is owned by Task Sys, not by actor-private files.
- Task `status` is the only lifecycle truth: `in_progress.side_processing`, `in_progress.awaiting_parent`, `in_progress.parent_processing`, `completed`, or `canceled`.
- Primary route: use native BuddySwitch env MCP tools through `env.tool`.
- Use `task_sys.list` or `task_sys.get` to read ongoing Task Sys task state.
- Use `task_sys.close` when a `task_sys.side_frame` is completed in side.
- Use `task_sys.need_parent` when a `task_sys.side_frame` needs parent-thread work; `interrupt` is only a parameter.
- Use `task_sys.cancel` when the actor decides an active Task must stop without completion.
- When a `task_sys.parent_frame` completes required frame work, call `task_sys.close`.
- For IM source frames, use message tools for required message reads and sends; Task Sys status owns processing lifecycle.
- Use `message.send(target_identity_id=...)` when the IM task requires a new explicit actor or external target.
- Use `message.send(reply_to=...)` when replying to an IM message addressed to the active actor; the runtime resolves the original sender through the normal target-identity path.
- If a reply is required, send it before closing the Task.
- If no reply is required and the source work is complete, call `task_sys.close` directly.
- Exact payload schemas, effects, rejection meanings, and recovery guidance come from native tool schemas and `context.get.tool_catalog['task_sys']`.
- Diagnostic fallback: `"$BUDDYSWITCH_PYTHON" scripts/turn_runtime.py status`.
- Broker method remains `env.tool`; do not edit runtime task objects or private runtime files directly.

## Judge The Frame
- If the frame kind is `task_sys.side_frame`, use `task_sys.close` when side completes the frame, `task_sys.need_parent` when parent resources are required, or `task_sys.cancel` when work must stop.
- If the frame kind is `task_sys.parent_frame`, complete the required frame work and call `task_sys.close`; call `task_sys.cancel` only when work must stop without completion.
- On a parent Progress Check, close, cancel, or continue parent work without changing status; turn completion alone never completes a Task.
- Use `context.get` only when exact schemas or runtime source descriptions are needed.

## Runtime Boundary
- Task Sys frames carry source refs and task context; do not reconstruct raw inbound prompts.
- Product tools such as track, artifact, message, and search remain the source of truth for their own product data.
- Rejections leave Task Sys and sibling runtime state unchanged unless the response explicitly says otherwise.
