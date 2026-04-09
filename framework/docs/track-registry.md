# BuddySwitch Track Object Rules

This document defines track behavior in env-centric BuddySwitch.

## Source Of Truth

- Tracks: `buddyswitch/objects/tracks/*.json`
- Artifacts: `buddyswitch/objects/artifacts/*.json`
- APIs: `scripts/env_tracks.py`, `scripts/env_artifacts.py`

## Track Schema (v1)

Required fields:

- `id`
- `title`
- `status` (`active | blocked | done | archived`)
- `current_buddy`
- `next_buddy` (nullable)
- `artifact_ids`
- `summary`
- `updated_at`

## Artifact Schema (v1)

Required fields:

- `id`
- `title`
- `kind`
- `path` (`artifacts/<artifact-id>--<slug>.md`)
- `producer_buddy`
- `source_skill`
- `context_track_id` (nullable)
- `created_at`
- `updated_at`

## Permission Model

- `pm` can create/update/advance tracks and attach/detach artifacts.
- Other buddies can read tracks and create/update artifacts.
- Non-PM buddies must not directly mutate track `status/current_buddy/next_buddy/artifact_ids`.

## Auto-Register Rule

When an artifact is created or updated with `context_track_id`, the system auto-attaches its `id` into the target track's `artifact_ids`.

## Explicitness Rule

Tracks should still be explicit user-intent objects. If a task is only artifact generation, creating a track is optional and should be PM-driven.
