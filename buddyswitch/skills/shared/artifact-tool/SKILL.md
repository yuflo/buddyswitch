---
name: artifact-tool
description: Use when you need to inspect active-task artifacts, validate artifact payloads, create new artifact revisions, or update artifact metadata through runtime-owned env tools.
---

# artifact-tool

## Purpose
- Manage artifact reads and revision writes through the broker-routed env tool path.
- Keep artifact mutation scoped to the launcher-locked active buddy, active-buddy tasks, allowed artifact kinds, and reserved source run.
- Use revision creation for content changes; do not overwrite artifact content in place.

## Use when
- The active buddy needs to list or inspect artifacts for its current task.
- A new artifact revision should be created for the active buddy's task.
- Runtime/tool feedback asks for an artifact env tool command.

## Do Not Use When
- You only need upstream artifacts already included in `prepare.runtime_context`.
- You need to delete artifacts; cleanup remains an admin/runtime maintenance concern.
- You are committing the full run result; use the runtime persist path for the run audit.

## Runtime Contract
- CLI: `python3 scripts/env/client.py artifact <operation>`
- Broker contract: method `env.tool` with envelope `{"tool":"artifact","action":"<action>","args":{...}}`
- Runtime injects the active instance and active buddy. Payload-authored identity fields do not grant authority.
- Follow structured feedback fields: `permission_boundary`, `allowed_next_actions`, `stop_condition`, and `command_hint`.

## Common Operations
- `list`
- `get --artifact-id <artifact-id>`
- `get-current [--kind <artifact-kind>]`
- `validate-payload --payload <json>`
- `create-revision --payload <json>`
- `update-metadata --payload <json>`

## Payload Hints
- `validate_payload` and `create_revision`: `{"task_id":"...", "kind":"...", "title":"...", "summary":"...", "content":{}, "source_run_id":"..."}`
- `artifact_id` is optional for `create_revision`; runtime generates one when omitted.
- `source_run_id` must come from the active prepare context's reserved run.
- `update_metadata` accepts only `artifact_id`, `title`, `summary`, and `source_run_id`.

## Verification
- Contribute to one buddy-run commit.
- Confirm the command response is JSON with `ok=true` before relying on changed state.
- For rejected operations, follow `allowed_next_actions` instead of retrying with guessed payloads.
- Do not edit state files directly.
- Do not call persist from inside the skill.
