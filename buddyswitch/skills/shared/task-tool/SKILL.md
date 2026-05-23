---
name: task-tool
description: Use when you need to create, list, read, update, archive, or review history for explicit active-buddy-owned tasks through runtime env tools.
---

# task-tool

## Purpose
- Manage active-buddy private task work items inside the instance-local taskbox.

## Runtime Route
- CLI: `python3 scripts/env/client.py task create --payload '{"task_id":"task-alpha","title":"Review design direction","priority":"high","summary":"Review shared material."}'`
- Broker method: `env.tool`
- Discover current operations, payload keys, effects, and recovery guidance with `context.get.tool_catalog['task']` or `python3 scripts/turn_runtime.py status`.

## CLI Payload Rule
- `--payload` takes one JSON object string.
- Do not pass a filesystem path to `--payload`.
- For long markdown bodies, generate JSON with `python3 - <<'PY'` and pass it via command substitution.

```bash
python3 scripts/env/client.py task create --payload '{"task_id":"task-alpha","title":"Review design direction","priority":"high","summary":"Review shared material."}'
python3 scripts/env/client.py task history --payload '{"limit":10}'
```

## Workflow Notes
- Use explicit `task_id` values from runtime responses; there is no hidden current-task binding in runless mode.
- Task state is instance-local and private to the active buddy taskbox; there is no shared task queue and no fallback to shared task objects.
- `task.track_id` is an optional private organization hint and does not grant cross-buddy artifact access.
- Use `priority` and `refs` to keep private task triage and provenance inside the taskbox.
- Use `task.history` when you need recent lifecycle lines from `history.md`.
- For action payloads and return meanings, inspect `context.get.tool_catalog['task']` or `python3 scripts/turn_runtime.py status`; runtime response fields are authoritative for effects and recovery.

## Verification
- Confirm `ok=true` and returned ids/rows match expected scope.
- On rejection, trust `permission_boundary`, `why_blocked`, `state_changed`, `durability`, `correctable_fields`, and `alternative_capabilities`.
- Do not edit taskbox files or runtime state files directly.
