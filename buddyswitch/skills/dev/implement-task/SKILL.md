# implement-task

## Purpose
- Implement scoped product changes in code and produce a verified implementation report that downstream testing or review can use.

## Use when
- The task is about building, coding, fixing, integrating, refactoring within scope, or changing behavior in `projects/app/`.
- The user wants code changes plus verification results.
- The request references approved scope, a PRD, a prototype handoff, or concrete application behavior.

## Do Not Use When
- The user wants product scoping, design specification, market research, or test-only execution.
- The request is really a track lifecycle update for PM.
- The work would require changing product direction rather than implementing an approved scope.

## Inputs
- Task request and expected behavior.
- PRD and other approved handoff context when available.
- Target code paths and technical constraints.
- Optional track context or summary hint.

## Outputs
- Code changes primarily under `projects/app/`.
- Runtime-only temporary outputs under `runs/raw/`.
- A durable implementation artifact object plus run audit from the default runtime.

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

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.

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
- Do not write runtime noise into `projects/app/` source folders; use `runs/raw/`.

## Examples
- `Implement the approved P0 creator profile flow in projects/app`
- `Fix the regression in onboarding CTA behavior and report verification`
- `Build the playlist reorder interaction from the approved handoff`

## Counterexamples
- `Define the MVP scope for creator profile`
- `Clarify the product scope for playlist reorder`
- `Run smoke checks for the onboarding CTA regression`

## Gotchas
- This skill can use track context, but it does not own track lifecycle changes.
- Implementation tasks often mention requirements artifacts; that does not make them PM tasks.
