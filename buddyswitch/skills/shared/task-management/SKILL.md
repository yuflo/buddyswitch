---
name: task-management
description: Use when current user input may continue, create, switch, confirm, finish, or block a persistent BuddySwitch task.
---

# task-management

## Principles
- Task state is active actor private state stored in the instance-local taskbox.
- Primary: use native BuddySwitch env MCP tools such as `task__current`, `task__propose`, and `task__confirm`.
- Exact payload schemas, allowed task proposal types, effects, and response meanings come from native tool schemas and `context.get.tool_catalog['task']`.
- Diagnostic fallback: `python3 scripts/turn_runtime.py status`.
- Broker method remains `env.tool`; do not edit taskbox files or runtime state files directly.
- Runtime response fields are authoritative for effects, rejection reasons, and recovery.

## Continue Current Task
- If the user input naturally continues the current task, keep working without task mutation.
- Read `task__current` when you need the current TaskSnapshot, pending confirmation, or recent task history.

## Create New Task
- Use this only when there is no active or blocked current task.
- Use `task__propose` with a start proposal, a clear title, and a detailed body.
- If active work would be replaced, use the switch flow instead.

## Switch Task
- Use this when the user clearly wants to leave the current task for another task.
- Use `task__propose` with a switch proposal. This creates a pending confirmation and does not change the current task yet.
- Existing targets use a task id. New targets include a task title and body.

## Confirm Pending Switch
- Use this only when the current TaskSnapshot shows a pending switch and the user answers it.
- `task__confirm` accepting changes the current task. Rejecting keeps the current task.

## Mark Done / Blocked
- Use `task__propose` when the user clearly marks the current task done or blocked.
- The task id must match the current task from `task__current`.

## Tool Reference
- Read: `task__current`.
- Propose: `task__propose`.
- Confirm: `task__confirm`.
- Inspect exact tool details with `context.get.tool_catalog['task']` or `python3 scripts/turn_runtime.py status`.
