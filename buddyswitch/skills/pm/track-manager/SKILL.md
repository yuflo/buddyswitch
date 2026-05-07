---
name: track-manager
description: Use when the task is managing track lifecycle operations such as create, update, advance, or archive.
---

# track-manager

## Purpose
- Produce PM artifact output for explicit track lifecycle requests.
- Persist lifecycle mutations only through `state_effects.track`.

## Use when
- The demand is explicitly about creating, updating, advancing, or archiving tracks.
- The user wants to change `current_buddy`, `next_buddy`, `status`, `summary`, or task linkage on a track.

## Do Not Use When
- The primary deliverable is a PRD, design artifact, implementation change, research report, or test report.
- The request only needs track context as background.

## Outputs
- A PM artifact object in `buddyswitch/objects/artifacts/` (`kind = track-note` or `pm-decision`).
- PM result JSON matching `framework/schemas/pm/pm-result.json`.
- Explicit `state_effects.track` for lifecycle mutation.
- A run audit in `buddyswitch/content/runs/`.

## Steps
1. Identify the target lifecycle action (`create|update|advance|archive`).
2. Populate `state_effects.track` with the requested change.
3. Add optional artifact content only when a durable PM note is needed.
4. Keep mutation intent explicit; do not rely on implied track changes.

## Verification
- Confirm output includes `execution_summary` and a valid `state_effects.track` payload.
- Confirm `state_effects.track.action` is valid.
- Confirm non-create actions reference an existing `track_id`.

## Shared Runtime Rules
- Follow `framework/docs/skill-runtime-shared-rules.md`.
- This native skill contributes content to the current buddy run.
- Do not call persist from the skill perspective.
- The locked buddy session persists one buddy run commit after all needed native skill work is integrated.

## BuddySwitch Commit Output

Contribute to one buddy-run commit. Do not call persist from inside the skill.

Required top-level field:
- `execution_summary`

Use `state_effects.track`, not an artifact-only placeholder, when the requested outcome is a track lifecycle change.

Use optional `artifacts` only when a durable PM note (`track-note` or `pm-decision`) is needed.
Use optional `working_notes` for concise reasoning or verification notes.
Use optional `handoff` when another manifest buddy should continue.

## Example
- `create onboarding-rewrite track for MVP handoff`
- `advance onboarding-rewrite next_buddy dev`

## Counterexamples
- `draft the MVP PRD for onboarding rewrite`
- `implement the approved onboarding rewrite scope`
