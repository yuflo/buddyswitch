---
name: task-tool
description: Use when you need to create, list, read, update, or archive explicit buddy-owned tasks through runtime env tools.
---

# task-tool

## Purpose
- Manage explicit task ids used by artifacts and handoffs.
- Keep task writes within active-buddy ownership boundaries.

## Runtime Contract
- CLI: `python3 scripts/env/client.py task <operation>`
- Broker method: `env.tool`
- Operations: `create`, `list`, `get`, `update`, `archive`

## Notes
- `task.create` can attach an existing `track_id` explicitly.
- There is no current-task binding surface in runless mode.
- Use runtime/tool feedback, not prompt text, as authority.

## Verification
- Confirm response JSON has `ok=true` and returned task fields.
- For failures, follow `permission_boundary`, `why_blocked`, and `allowed_next_actions`.
- Do not edit runtime state files directly.
