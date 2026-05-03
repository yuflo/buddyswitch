---
name: track-manager
description: Use when the task is managing track lifecycle operations such as create, update, advance, or archive.
---

# track-manager

## Purpose
- Manage the lifecycle of track objects and task linkage so the PM buddy remains the single authority for track state.

## Use when
- The demand is explicitly about creating, listing, reading, updating, advancing, or archiving tracks.
- The user wants to change `current_buddy`, `next_buddy`, `status`, `summary`, or task linkage on a track.
- The task needs a durable track-operation audit in BuddySwitch state.

## Do Not Use When
- The primary deliverable is a PRD, design artifact, implementation change, research report, or test report.
- The user is asking to read track context only as background for another artifact-producing skill.
- The task is really about changing product scope rather than manipulating track state.

## Inputs
- A track-focused demand in ordinary product-mode request text.
- Optional explicit `track-id`, `task-id`, `status`, `current_buddy`, `next_buddy`, or summary text.
- Existing track and task objects from the env store.

## Outputs
- Updated track objects in `buddyswitch/objects/tracks/`.
- Optional task linkage updates through the resolved task.
- A run audit under `buddyswitch/content/runs/`.

## Steps
1. Identify the intended track operation from the user task.
2. Resolve the target track or derive a new track id for creation.
3. Validate referenced buddy ids, task ids, and lifecycle fields.
4. Apply the track mutation or task linkage change through the env store.
5. Persist a run audit describing the operation and outcome.

## Verification
- Confirm the requested action is one of `create`, `read`, `list`, `update`, `advance`, or `archive`.
- Confirm referenced track and task ids exist unless the operation is `create`.
- Confirm only the PM buddy mutates track lifecycle state.

## Core Rules
- PM owns track lifecycle changes.
- Track IDs must be unique in `buddyswitch/objects/tracks/`.
- If create target collides, append incremental suffix (`-2`, `-3`, ...).
- Track linkage is task-centric: tracks store `task_ids`, and artifacts flow through their owning tasks.

## Examples
- `create onboarding-rewrite track for MVP handoff`
- `advance next_buddy dev status active`
- `update summary for handoff readiness`

## Counterexamples
- `draft the MVP PRD for onboarding rewrite`
- `continue onboarding-rewrite track and refine the prototype flow`
- `implement the approved onboarding rewrite scope`

## Gotchas
- Track mutation is explicit; do not infer a lifecycle change from vague planning language.
- This skill can read track context, but it should not become the default just because a task casually mentions the word `track`.
- Task linkage changes must preserve object consistency between track and task records.
