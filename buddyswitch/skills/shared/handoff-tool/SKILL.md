---
name: handoff-tool
description: Use when you need to inspect recent handoffs, validate a handoff payload, or create an explicit handoff record through runtime-owned env tools.
---

# handoff-tool

## Purpose
- Keep handoffs explicit and auditable.
- Validate source ownership, ids, and lifecycle boundaries before handoff creation.
- Use list/validate/create instead of hidden lifecycle mutation.

## Command Surface
- `python3 scripts/env/client.py handoff list [--track-id <track-id>]`
- `python3 scripts/env/client.py handoff validate --payload <json-file>`
- `python3 scripts/env/client.py handoff create --payload <json-file>`

## Payload Hints
- Required fields: `track_id`, `source_task_id`, `source_run_id`, `target_buddy`, `artifact_ids`, `reason`, `context`.
- Optional fields: `historical_artifact_ids`, `next_buddy`.
- Forbidden fields: lifecycle mutation fields such as `track_status`, `current_buddy`, `state_effects`.

## Verification
- Contribute to one buddy-run commit.
- Do not call persist from inside the skill.
- Run `handoff validate` first, then `handoff create`.
- Confirm JSON response is `ok=true` before relying on handoff visibility.
- Do not edit raw state files directly.
