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

Run linkage rules:

- `run_ids` may be empty only when `latest_run_id` is `null`.
- When `latest_run_id` is non-null, it must be included in `run_ids`.
- Create-mode resolve materializes the task immediately with zero runs (`run_ids: []`, `latest_run_id: null`); persist then attaches the first run id.

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
  - `create`, `update`, `advance`, `archive`
- Track inspection now comes from resolve-time context (`track_context`, `task_context`, selected inputs), not online `track-manager` `read` / `list` actions.
- Other buddies can read tracks and create/update artifacts through their resolved task.
- Non-PM buddies must not directly mutate track `status/current_buddy/next_buddy/task_ids`.

## Auto-Register Rule

When a task is bound to a track, the system registers its id in the target track's `task_ids`. `track-manager` create-mode persists both sides together: the task receives `track_id`, and the track records the task in `task_ids`. Artifact creation updates the owning task's `artifact_ids` and `artifact_slots[slot]` state.

## Explicitness Rule

Tracks should still be explicit user-intent objects. If a demand is only a single buddy task, creating or binding a track is optional and should be explicit in the invocation or PM-driven through track-manager.
