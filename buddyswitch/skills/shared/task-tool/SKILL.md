---
name: task-tool
description: Use when you need to create, list, read, update, or archive explicit buddy-owned tasks through runtime env tools.
---

# task-tool

## Purpose
- Manage active-buddy task work items and task ids used by artifacts and handoffs.

## Runtime Route
- CLI: `python3 scripts/env/client.py task <operation>`
- Broker method: `env.tool`
- Operations: `create`, `list`, `get`, `update`, `archive`

## Workflow Notes
- Use explicit `task_id` values from runtime responses; there is no hidden current-task binding in runless mode.
- For action payloads and return meanings, inspect `context.get.tool_catalog['task']` or `python3 scripts/turn_runtime.py status`; runtime response fields are authoritative for effects and recovery.

## Verification
- Confirm `ok=true` and returned ids/rows match expected scope.
- On rejection, trust `permission_boundary`, `why_blocked`, `state_changed`, `durability`, `correctable_fields`, and `alternative_capabilities`.
- Do not edit runtime state files directly.
