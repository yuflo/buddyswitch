---
name: task-management
description: Use when processing Task Sys side frames, parent-thread decisions, or ongoing Task Sys task state through BuddySwitch env tools.
---

# task-management

## Principles
- Task state is owned by Task Sys, not by actor-private files.
- Primary route: use native BuddySwitch env MCP tools through `env.tool`.
- Use `task_sys.list` or `task_sys.get` to read ongoing Task Sys task state.
- Use `task_sys.update_task_analysis` to record `task_desc` and `task_relation` before side close or parent handoff.
- Use `task_sys.close` when a `task_sys.side_frame` is completed in side.
- Use `task_sys.need_parent` when a `task_sys.side_frame` needs parent-thread work; `interrupt` is only a parameter.
- When a `task_sys.parent_frame` completes required frame work, call `task_sys.close`.
- For IM source frames, use message tools for required message reads, sends, and disposition work.
- Use `message.send(target_identity_id=...)` when the IM task requires a new explicit actor or external target.
- Use `message.send(reply_to=...)` when replying to a processable inbound IM message; the runtime resolves the original sender through the normal target-identity path.
- Use `message.mark(..., disposition=absorbed)` only when no reply is needed.
- Exact payload schemas, effects, rejection meanings, and recovery guidance come from native tool schemas and `context.get.tool_catalog['task_sys']`.
- Diagnostic fallback: `"$BUDDYSWITCH_PYTHON" scripts/turn_runtime.py status`.
- Broker method remains `env.tool`; do not edit runtime task objects or private runtime files directly.

## Judge The Frame
- If the frame kind is `task_sys.side_frame`: Generate `task_desc`, read relation context, call `task_sys.update_task_analysis`, then close or hand off.
- Use `task_sys.close` when side completes the frame after analysis; use `task_sys.need_parent` when parent resources outside the frame's allowed tools are required.
- If the frame kind is `task_sys.parent_frame`, complete the required frame work, perform required message actions first when this is an IM source frame, then call `task_sys.close`.
- Use `context.get` only when exact schemas or runtime source descriptions are needed.

## Runtime Boundary
- Task Sys frames carry source refs and task context; do not reconstruct raw inbound prompts.
- Product tools such as track, artifact, message, and search remain the source of truth for their own product data.
- Rejections leave Task Sys and sibling runtime state unchanged unless the response explicitly says otherwise.
