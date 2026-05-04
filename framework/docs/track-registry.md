# BuddySwitch Track Object Rules

This document defines active track behavior in BuddySwitch.

## Source Of Truth

- Tracks: `buddyswitch/objects/tracks/*.json`
- Tasks: `buddyswitch/objects/tasks/*.json`
- Artifacts: `buddyswitch/objects/artifacts/*.json`
- Runtime (primary): `scripts/turn_runtime.py`
- Manual/debug object APIs: `scripts/env_tracks.py`, `scripts/env_tasks.py`, `scripts/env_artifacts.py`

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

Every persisted run belongs to a task.
A task may be untracked or bound to exactly one track.

## Artifact Schema (v1)

Required fields:

- `id`
- `title`
- `task_id`
- `buddy`
- `skill_id`
- `source_run_id`
- `summary`
- `content`
- `created_at`
- `updated_at`

Artifacts participate in track flow through `artifact.task_id -> task.track_id`.

## Permission Model

- `pm` controls track lifecycle operations (`create`, `update`, `advance`, `archive`) through PM skill outputs using `state_effects.track_operation`.
- Non-PM buddies do not directly mutate track lifecycle fields.
- Track inspection should come from prepared task/track context and workspace projection.
- Retired top-level `track_operation` payloads are not accepted by runtime persist.

## Auto-Register Rule

When a task is bound to a track, runtime registers the task id in that track's `task_ids`.
Artifact creation updates task `artifact_ids` and per-slot `artifact_slots` revision state.
