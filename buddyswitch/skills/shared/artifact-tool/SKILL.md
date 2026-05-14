---
name: artifact-tool
description: Use when you need track-scoped artifact summaries, direct artifact-id full reads, revision writes for owned tasks, or metadata updates through runtime-owned env tools.
---

# artifact-tool

## Purpose
- Manage artifact reads and revision writes through the broker-routed env tool path.
- Use `artifact get --artifact-id` as the full-body read entrypoint.
- Keep mutation scoped to launcher-locked active buddy tasks, allowed artifact kinds, and reserved source run.
- Use revision creation for content changes; do not overwrite artifact content in place.

## Use when
- The active buddy needs track-level summary rows: `artifact list --track-id <track-id>`.
- The active buddy needs a full artifact body by id: `artifact get --artifact-id <artifact-id>`.
- A new artifact revision should be created for the active buddy's task.
- Runtime/tool feedback asks for an artifact env tool command.

## Do Not Use When
- You need to delete artifacts; cleanup remains an admin/runtime maintenance concern.
- You are committing the full run result; use the runtime persist path for the run audit.

## Runtime Contract
- CLI: `python3 scripts/env/client.py artifact <operation>`
- Broker contract: method `env.tool` with envelope `{"tool":"artifact","action":"<action>","args":{...}}`
- Runtime injects the active instance and active buddy. Payload-authored identity fields do not grant authority.
- Follow structured feedback fields: `permission_boundary`, `allowed_next_actions`, `stop_condition`, and `command_hint`.

## Common Operations
- `list --track-id <track-id>`
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

If `artifact.get` is rejected, read `why/relation/missing_preconditions/next_actions/command_hint`. The normal recovery path is `track.join --track-id <track-id>` then retry `artifact.get`.
