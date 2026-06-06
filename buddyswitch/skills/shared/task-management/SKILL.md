---
name: task-management
description: Use when current user input may continue, capture, select, switch, progress, checkout, or review a persistent BuddySwitch task.
---

# task-management

## Principles
- Task state is active actor private state stored in the instance-local taskbox.
- Primary route: use native BuddySwitch env MCP tools through `env.tool`.
- Task tools expose Task Operations: `current`, `capture`, `select`, `switch_request`, `switch_confirm`, `progress`, `checkout`, and `review`.
- Exact payload schemas, effects, rejection meanings, and recovery guidance come from native tool schemas and `context.get.tool_catalog['task']`.
- Diagnostic fallback: `python3 scripts/turn_runtime.py status`.
- Broker method remains `env.tool`; do not edit taskbox files or runtime state files directly.
- Runtime response fields and TaskViewModel are authoritative for current anchor, shelf, pending switch, evidence, checkout cue, warnings, and next legal operations.

## Judge The Input
- If the user input naturally continues the current task, keep working without task mutation.
- Read task `current` when current anchor, shelf, pending switch, recent evidence, or available actions matter.
- Use task `capture` when a new work demand should be saved for later and must not replace active work.
- Use task `select` when captured shelf work or blocked work should become current and no active current anchor exists.
- Use task `switch_request` when the actor should leave active current work for another captured, blocked, or new target task.
- Use task `switch_confirm` only when TaskViewModel shows a pending switch and the user answers that pending switch.
- Use task `progress` to append evidence, refs, or progress summary to the active current task.
- Use task `checkout` to end a work block as `continue`, `finish`, or `block`.
- Use task `review` to inspect captured, blocked, pending, or stale task cues.

## Runtime Boundary
- Task refs are private context links; task operations do not publish or mutate track, artifact, message, comment, request, browser, or actor private file contents.
- Capture stores work on the shelf; it does not auto-select.
- Switching is two-step: request first, then confirm accept or reject.
- Finish requires evidence. Block requires a reason.
- Rejections leave taskbox and sibling runtime state unchanged unless the response explicitly says otherwise.
