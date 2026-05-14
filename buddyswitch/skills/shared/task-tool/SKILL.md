---
name: task-tool
description: Use when you need to create/update/archive active-buddy tasks, inspect visible task ids for orientation, or bind current task through runtime-owned env tools.
---

# task-tool

## Purpose
- Manage task lifecycle through the broker-routed env tool path.
- Keep task mutations scoped to the launcher-locked active buddy and instance.
- Use `task.get --task-id` as orientation for task metadata and artifact summaries.
- Use `artifact.get --artifact-id` for full artifact bodies.

## Command Surface
- `python3 scripts/env/client.py task create --payload <json-file>`
- `python3 scripts/env/client.py task list`
- `python3 scripts/env/client.py task get --task-id <task-id>`
- `python3 scripts/env/client.py task get-current`
- `python3 scripts/env/client.py task set-current --task-id <task-id>`
- `python3 scripts/env/client.py task update --payload <json-file>`
- `python3 scripts/env/client.py task archive --task-id <task-id>`
- Broker contract: method `env.tool` with envelope `{"tool":"task","action":"<action>","args":{...}}`

## Payload Hints
- Envelope fields:
  - `tool`: `task`
  - `action`: one of `create|list|get|get_current|set_current|update|archive`
  - `args`: object payload for the selected action
- `create`: `{"title":"...", "summary":"..."}`
- `update`: `{"task_id":"...", "title":"...", "summary":"...", "status":"active|blocked|done|archived"}`

`task.get` returns artifact summary rows, not foreign full artifact content.

## Guardrails
- Active buddy and instance identity come from runtime context, not payload fields.
- Cross-buddy named task operations are rejected by the env tool/service boundary.
- `task.archive` sets `status=archived`; it does not delete task objects.
- `task.set_current` updates both `current_task_id` and `current_track_id` from the selected task.

## Decision Source
- Runtime/tool feedback is authoritative for permission boundaries and next actions.
- Use `prepare.runtime_context.env_tools.task` plus structured rejection payload fields (`permission_boundary`, `allowed_next_actions`, `command_hint`) to choose the next step.

## Direct Id Rule
- If you see a `task_id`, use `task get --task-id <task-id>`.
- If task summary includes artifact ids you need to read fully, use `artifact get --artifact-id <artifact-id>`.

## Shared Runtime Rules
- Contribute to one buddy-run commit.
- Do not call persist from inside the skill.
