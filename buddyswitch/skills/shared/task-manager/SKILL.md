---
name: task-manager
description: Use when you need to create, inspect, update, archive, or bind the current task for the active buddy through runtime-owned env tools.
---

# task-manager

## Purpose
- Manage task lifecycle through the broker-routed env tool path.
- Keep task mutations scoped to the launcher-locked active buddy and instance.

## Command Surface
- `python3 scripts/env/client.py task create --payload <json-file>`
- `python3 scripts/env/client.py task list`
- `python3 scripts/env/client.py task get --task-id <task-id>`
- `python3 scripts/env/client.py task get-current`
- `python3 scripts/env/client.py task set-current --task-id <task-id>`
- `python3 scripts/env/client.py task update --payload <json-file>`
- `python3 scripts/env/client.py task archive --task-id <task-id>`

## Payload Hints
- `create`: `{"title":"...", "summary":"..."}`
- `update`: `{"task_id":"...", "title":"...", "summary":"...", "status":"active|blocked|done|archived"}`

## Guardrails
- Active buddy and instance identity come from runtime context, not payload fields.
- Cross-buddy named task operations are rejected by the env tool/service boundary.
- `task.archive` sets `status=archived`; it does not delete task objects.
- `task.set_current` updates both `current_task_id` and `current_track_id` from the selected task.

## Decision Source
- Runtime/tool feedback is authoritative for permission boundaries and next actions.
- Use `prepare.runtime_context.env_tools.task_manager` plus structured rejection payload fields (`permission_boundary`, `allowed_next_actions`, `command_hint`) to choose the next step.

## Shared Runtime Rules
- Contribute to one buddy-run commit.
- Do not call persist from inside the skill.
