---
name: track-manager
description: Use when you need to inspect tracks, attach or detach active-buddy tasks, or ask PM to mutate track lifecycle through runtime-owned env tools.
---

# track-manager

## Purpose
- Manage track coordination through the broker-routed env tool path.
- Read track context from any buddy with runtime `track.read` authority.
- Mutate lifecycle state only when the runtime accepts the active buddy as PM.

## Use when
- The demand is explicitly about creating, updating, advancing, archiving, or inspecting tracks.
- The active buddy needs to attach or detach one of its own tasks from an existing track.
- Runtime/tool feedback asks for a track-manager command.

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
- `get-current`
- `create --payload <json>`
- `update --payload <json>`
- `advance --payload <json>`
- `archive --track-id <track-id>`
- `attach-task --track-id <track-id> --task-id <task-id>`
- `detach-task --track-id <track-id> --task-id <task-id>`

## Verification
- Contribute to one buddy-run commit.
- Do not call persist from inside the skill.
- Confirm the command response is JSON with `ok=true` before relying on changed state.
- For rejected operations, follow `allowed_next_actions` instead of retrying with guessed payloads.
- Do not edit state files directly.
