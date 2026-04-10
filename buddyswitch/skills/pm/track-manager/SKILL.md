---
name: track-manager
description: Manage track lifecycle operations for product iteration control.
version: "2.0"
track_mode: optional
default_artifact_kind: track-event
auto_summary: true
output_schema: framework/schemas/pm/track-manager.json
side_effect_level: high
produces:
  - track-state
  - track-linkage
consumes:
  - track
  - artifact
---

# track-manager

## Purpose
- Manage the lifecycle of track objects and artifact linkage so the PM buddy remains the single authority for track state.

## Use when
- The task is explicitly about creating, listing, reading, updating, advancing, attaching, detaching, or archiving tracks.
- The user wants to change `current_buddy`, `next_buddy`, `status`, `summary`, or the artifact linkage on a track.
- The task needs a durable track-operation summary under `runs/summaries/pm/`.

## Do Not Use When
- The primary deliverable is a PRD, design spec, implementation change, research report, or test report.
- The user is asking to read track context only as background for another artifact-producing skill.
- The task is really about changing product scope rather than manipulating track state.

## Inputs
- A track-focused task in `switch pm: ...` form.
- Optional explicit `track-id`, `artifact-id`, `status`, `current_buddy`, `next_buddy`, or summary text.
- Existing track and artifact objects from the env store.

## Outputs
- Updated track objects in `buddyswitch/objects/tracks/`.
- Optional artifact linkage updates.
- An execution summary file under `runs/summaries/pm/`.

## Steps
1. Identify the intended track operation from the user task.
2. Resolve the target track or derive a new track id for creation.
3. Validate referenced buddy ids, artifact ids, and lifecycle fields.
4. Apply the track mutation or linkage change through the env store.
5. Persist a summary describing the operation and outcome.

## Verification
- Confirm the requested action is one of `create`, `read`, `list`, `update`, `advance`, `attach`, `detach`, or `archive`.
- Confirm referenced track and artifact ids exist unless the operation is `create`.
- Confirm only the PM buddy mutates track lifecycle state.

## Core Rules
- PM owns track lifecycle changes.
- Track IDs must be unique in `buddyswitch/objects/tracks/`.
- If create target collides, append incremental suffix (`-2`, `-3`, ...).
- Attach and detach only operate on existing artifact IDs.

## Examples
- `switch pm: create onboarding-rewrite track for MVP handoff`
- `switch pm: advance track onboarding-rewrite next_buddy dev status active`
- `switch pm: attach art-onboarding-prd to track onboarding-rewrite`

## Counterexamples
- `switch pm: draft the MVP PRD for onboarding rewrite`
- `switch design: continue onboarding-rewrite track and produce IA spec`
- `switch dev: implement the approved onboarding rewrite scope`

## Gotchas
- Track mutation is explicit; do not infer a lifecycle change from vague planning language.
- This skill can read track context, but it should not become the default just because a task casually mentions the word `track`.
- Artifact linkage changes must preserve object consistency between track and artifact records.
