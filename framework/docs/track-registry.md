# BuddySwitch Track Object Rules

This document defines active track behavior in BuddySwitch.

## Source Of Truth

- Tracks: `buddyswitch/objects/tracks/*.json`
- Tasks: `buddyswitch/objects/tasks/*.json`
- Artifacts: `buddyswitch/objects/artifacts/*.json`
- Runtime tool service: `scripts/env/services/tracks.py`
- Broker tool dispatch: `scripts/env/tools/dispatch.py`
- Skill-facing command: `python3 scripts/env/client.py track <operation>`

## Track Schema (v1)

Required fields:

- `id`
- `title`
- `status` (`active | blocked | done | archived`)
- `current_buddy`
- `next_buddy` (nullable)
- `task_ids`
- `summary`
- `updated_at`

Tracks link iteration work by `task_ids`.
Tracks do not directly own artifact ids.

## Task Schema (v1)

Required fields:

- `id`
- `buddy`
- `title`
- `status` (`active | blocked | done | archived`)
- `track_id` (nullable)
- `artifact_slots`
- `artifact_ids`
- `run_ids`
- `latest_run_id`
- `summary`
- `created_at`
- `updated_at`

A persisted run may optionally associate a task.
A task may be untracked or bound to exactly one track.

## Artifact Schema (v1)

Required fields:

- `id`
- `title`
- `task_id`
- `buddy`
- `kind`
- `revision`
- `supersedes_artifact_id`
- `is_current`
- `source_run_id`
- `summary`
- `content`
- `created_at`
- `updated_at`

Artifacts participate in track flow through `artifact.task_id -> task.track_id`.

## Permission Model

- `pm` controls track lifecycle operations (`create`, `update`, `advance`, `archive`) through broker-routed `env.tool` track commands.
- Non-PM buddies do not mutate track lifecycle fields.
- Buddies with `track.read` may inspect track summaries.
- Active buddies may attach or detach their own tasks to an existing track through the track tool.
- Track inspection should come from prepared task/track context, workspace projection, or `python3 scripts/env/client.py track get`.
- Retired top-level `track_operation` payloads are not accepted by runtime persist.

## Auto-Register Rule

Track membership changes only through explicit `track.attach_task` and `track.detach_task`.
Artifact creation updates task `artifact_ids` and per-kind `artifact_slots` revision state through artifact-tool operations.
