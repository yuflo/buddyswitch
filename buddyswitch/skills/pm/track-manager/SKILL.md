---
name: track-manager
description: Manage track lifecycle operations for product iteration control.
track_mode: optional
default_artifact_kind: track-event
auto_summary: true
triggers:
  - track
  - tracks
  - create track
  - update track
  - read track
  - list tracks
  - show track
  - advance
  - attach
  - detach
  - archive
---

# track-manager

## Agent

- `pm`

## Purpose

- Manage track lifecycle and linkage operations:
  - `create`
  - `read`
  - `list`
  - `update`
  - `advance`
  - `attach`
  - `detach`
  - `archive`

## Core Rules

- PM owns track lifecycle changes.
- Track IDs must be unique in `buddyswitch/objects/tracks/`.
- If create target collides, append incremental suffix (`-2`, `-3`, ...).
- Attach and detach only operate on existing artifact IDs.

## Output

- Track operations should return structured execution summary.
- Summary path defaults to `runs/summaries/pm/<operation-id>.md`.
