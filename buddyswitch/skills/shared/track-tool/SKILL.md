---
name: track-tool
description: Use when you need to discover tracks, inspect one track by id, join a track for active-buddy work, or execute PM-owned lifecycle updates through runtime-owned env tools.
---

# track-tool

## Purpose
- Manage track coordination through broker-routed env tools.
- Use direct-id commands as the default source-intake path: `track list -> track get -> artifact get`.
- Use `track join` to create/reuse/select active-buddy task linkage without mutating PM lifecycle fields.

## Use when
- The demand is explicitly about creating, updating, advancing, archiving, joining, or inspecting tracks.
- The active buddy sees a `track_id` and needs current artifact ids and relation status.
- Runtime/tool feedback asks for a track env tool command.

## Do Not Use When
- The primary deliverable is a PRD, research report, design artifact, implementation change, or smoke-test report.
- The request only needs existing track context from `prepare.runtime_context`.

## Runtime Contract
- CLI: `python3 scripts/env/client.py track <operation>`
- Broker contract: method `env.tool` with envelope `{"tool":"track","action":"<action>","args":{...}}`
- Runtime injects the active instance and active buddy. Payload-authored identity fields do not grant authority.
- Follow structured feedback fields: `permission_boundary`, `allowed_next_actions`, `stop_condition`, and `command_hint`.

## Common Operations
- `list`
- `get --track-id <track-id>`
- `join --track-id <track-id> [--task-id <task-id>]`
- `python3 scripts/env/client.py track join --track-id <track-id> [--task-id <task-id>]`
- `get-current`
- `create --payload <json>`
- `update --payload <json>`
- `advance --payload <json>`
- `archive --track-id <track-id>`
- `attach-task --track-id <track-id> --task-id <task-id>` (maintenance)
- `detach-task --track-id <track-id> --task-id <task-id>` (maintenance)

`attach-task` and `detach-task` are maintenance operations, not the normal source-intake path.

## Verification
- Contribute to one buddy-run commit.
- Do not call persist from inside the skill.
- Confirm the command response is JSON with `ok=true` before relying on changed state.
- For rejected operations, follow `allowed_next_actions` instead of retrying with guessed payloads.
- Do not edit state files directly.
