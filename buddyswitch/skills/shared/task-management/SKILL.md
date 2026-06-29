---
name: task-management
description: Use when processing Task Sys side frames, parent-thread decisions, or checkpoint frames through BuddySwitch env tools.
---

# task-management

## Principles
- Task state is owned by Task Sys, not by actor-private files.
- Primary route: use native BuddySwitch env MCP tools through `env.tool`.
- Use `task_sys.close` when a `task_sys.side_frame` is handled without parent work.
- Use `task_sys.need_parent` when a `task_sys.side_frame` needs parent-thread work; `interrupt` is only a parameter.
- Use `task_sys.checkpoint_update` when a `task_sys.checkpoint` frame asks for the actor's checkpoint outcome.
- Exact payload schemas, effects, rejection meanings, and recovery guidance come from native tool schemas and `context.get.tool_catalog['task_sys']`.
- Diagnostic fallback: `python3 scripts/turn_runtime.py status`.
- Broker method remains `env.tool`; do not edit runtime task objects or private runtime files directly.

## Judge The Frame
- If the frame kind is `task_sys.side_frame`, finish with exactly one Task Sys side result: `close` or `need_parent`.
- If the frame kind is `task_sys.parent_frame`, process the parent task context in the frame before using other product tools.
- If the frame kind is `task_sys.checkpoint`, choose a legal `checkpoint_update` outcome from the frame; do not rely on a recommendation.
- Use `context.get` only when exact schemas or runtime source descriptions are needed.

## Runtime Boundary
- Task Sys frames carry source refs and task context; do not reconstruct raw inbound prompts.
- Product tools such as track, artifact, message, and search remain the source of truth for their own product data.
- Rejections leave Task Sys and sibling runtime state unchanged unless the response explicitly says otherwise.
