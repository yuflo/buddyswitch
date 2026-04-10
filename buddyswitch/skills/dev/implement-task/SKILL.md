---
name: implement-task
description: Implement scoped product changes in project code and report verified outcomes.
version: "2.0"
track_mode: optional
default_artifact_kind: implementation-report
auto_summary: true
output_schema: framework/schemas/dev/implement-task.json
side_effect_level: high
produces:
  - code-change
  - implementation-report
consumes:
  - prd
  - design-spec
  - task
---

# implement-task

## Purpose
- Implement scoped product changes in code and produce a verified implementation report that downstream testing or review can use.

## Use when
- The task is about building, coding, fixing, integrating, refactoring within scope, or changing behavior in `projects/app/`.
- The user wants code changes plus verification results.
- The request references approved scope, PRD, design contract, or concrete application behavior.

## Do Not Use When
- The user wants product scoping, design specification, market research, or test-only execution.
- The request is really a track lifecycle update for PM.
- The work would require changing product direction rather than implementing an approved scope.

## Inputs
- Task request and expected behavior.
- PRD and design context when available.
- Target code paths and technical constraints.
- Optional summary or artifact output path.

## Outputs
- Code changes primarily under `projects/app/`.
- Runtime-only temporary outputs under `projects/app/.runtime/`.
- A durable implementation artifact and optional summary scaffold from the default runtime.

## Steps

1. Restate the requested task and affected area.
2. Implement scoped changes in `projects/app/`.
3. Keep refactors localized and justified.
4. Run relevant local verification commands.
5. Summarize changed files, implementation notes, verification, and limitations.
6. Write durable implementation summary when requested.

## Verification
- Run the most relevant local checks for the changed behavior.
- Confirm the implementation stays within the approved scope.
- Report known limitations or blocked validation explicitly.

## Track/Object Handling

- Follow `framework/docs/track-registry.md`.
- This buddy may read tracks and create/update artifact objects.
- Do not mutate track lifecycle fields directly.
- If output belongs to a track, set `context_track_id` on artifact creation/update.

## Output Path

- Code changes: primarily `projects/app/`
- Project runtime-only temporary outputs: `projects/app/.runtime/`
- Durable summary default: `artifacts/<artifact-id>--<slug>.md`
- If user provides a path, use it as-is.

## Required Output Fields

- `task_summary`
- `changed_files`
- `implementation_notes`
- `verification_runs`
- `known_limitations`

## Guardrails

- Do not change product scope silently.
- Do not make architecture direction changes without explicit note.
- Do not skip verification reporting.
- Do not write runtime noise into `projects/app/` source folders; use `projects/app/.runtime/`.

## Examples
- `switch dev: Implement the approved P0 creator profile flow in projects/app`
- `switch dev: Fix the regression in onboarding CTA behavior and report verification`
- `switch dev: Build the playlist reorder interaction from the design spec`

## Counterexamples
- `switch pm: Define the MVP scope for creator profile`
- `switch design: Produce the IA spec for playlist reorder`
- `switch test: Run smoke checks for the onboarding CTA regression`

## Gotchas
- This skill can use track context, but it does not own track lifecycle changes.
- Implementation tasks often mention requirements artifacts; that does not make them PM tasks.
