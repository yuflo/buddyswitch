# BuddySwitch Track Object Rules

This document defines track behavior in env-centric BuddySwitch.

## Source Of Truth

- Tracks: `buddyswitch/objects/tracks/*.json`
- Tasks: `buddyswitch/objects/tasks/*.json`
- Artifacts: `buddyswitch/objects/artifacts/*.json`
- Runtime (primary): `scripts/switch_runtime.py`
- APIs (manual/debug): `scripts/env_tracks.py`, `scripts/env_tasks.py`, `scripts/env_artifacts.py`

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

Tracks link product iteration work by `task_ids`. They do not directly own artifact ids.

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

Every persisted run must belong to a task. A task may be untracked or bound to exactly one track.

## Artifact Schema (v1)

Required fields:

- `id`
- `title`
- `task_id`
- `buddy`
- `skill_id`
- `source_run_id`
- `summary`
- `content` (structured artifact payload)
- `created_at`
- `updated_at`

Artifacts participate in track flow through `artifact.task_id -> task.track_id`. Artifact objects do not store `track_id`.

## Permission Model

- `pm` `track-manager` skill controls track lifecycle core operations:
  - `create`, `read`, `list`, `update`, `advance`, `archive`
- Other buddies can read tracks and create/update artifacts through their resolved task.
- Non-PM buddies must not directly mutate track `status/current_buddy/next_buddy/task_ids`.

## Auto-Register Rule

When a task is bound to a track, the system registers its id in the target track's `task_ids`. Artifact creation updates the owning task's `artifact_ids` and `artifact_slots[slot]` state.

## Explicitness Rule

Tracks should still be explicit user-intent objects. If a demand is only a single buddy task, creating or binding a track is optional and should be explicit in the invocation or PM-driven through track-manager.
