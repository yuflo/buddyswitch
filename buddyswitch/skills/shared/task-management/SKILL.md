---
name: task-management
description: Use when current user input may continue, create, switch, confirm, finish, or block a persistent BuddySwitch task.
---

# task-management

## Principles
- Task state is active-buddy private state stored in the instance-local taskbox.
- Use native BuddySwitch env MCP tools for task state when available; fallback CLI still routes through env.tool.
- Do not edit taskbox files or runtime state files directly.
- Use `context.get.tool_catalog['task']`, `context.summarize`, or `python3 scripts/turn_runtime.py status` for exact payload and response details.
- `--payload` takes one JSON object string.
- Runtime response fields are authoritative for effects, rejection reasons, and recovery.

## Continue Current Task
- If the user input naturally continues the current task, keep working without task mutation.
- Read `task.current` when you need the current TaskSnapshot, pending confirmation, or recent task history.

```bash
python3 scripts/env/client.py task current --payload '{"history_limit":8}'
```

## Create New Task
- Use this only when there is no active or blocked current task.
- Use `task.propose` with `type` set to `start`, a clear title, and a detailed body.
- If active work would be replaced, use the switch flow instead.

```bash
python3 scripts/env/client.py task propose --payload '{"type":"start","task":{"title":"Clean runtime environment","summary":"Refine task input context.","body":"Detailed body for the task.","priority":"normal","refs":[]},"reason":"User introduced a new task.","evidence":"User asked for task input context."}'
```

## Switch Task
- Use this when the user clearly wants to leave the current task for another task.
- Use `task.propose` with `type` set to `switch`; this creates a pending confirmation and does not change the current task yet.
- Existing targets use a task id. New targets include a task title and body.

```bash
python3 scripts/env/client.py task propose --payload '{"type":"switch","target":{"mode":"existing","task_id":"task-0002-next-task"},"reason":"User asked to switch tasks.","evidence":"User named the next task."}'
```

## Confirm Pending Switch
- Use this only when the current TaskSnapshot shows a pending switch and the user answers it.
- Accepting changes the current task. Rejecting keeps the current task.

```bash
python3 scripts/env/client.py task confirm --payload '{"confirmation_id":"confirm-0001","decision":"accept","reason":"User confirmed the switch."}'
```

## Mark Done / Blocked
- Use `task.propose` when the user clearly marks the current task done or blocked.
- The task id must match the current task from `task.current`.

```bash
python3 scripts/env/client.py task propose --payload '{"type":"finish","task_id":"task-0001-clean-runtime-environment","reason":"Task completed.","evidence":"Verification passed."}'
python3 scripts/env/client.py task propose --payload '{"type":"block","task_id":"task-0001-clean-runtime-environment","reason":"External input needed.","evidence":"User decision is required."}'
```

## Tool Reference
- Read: `task.current`
- Propose: `task.propose`
- Confirm: `task.confirm`
- Inspect exact tool details with `context.get.tool_catalog['task']` or `python3 scripts/turn_runtime.py status`.
