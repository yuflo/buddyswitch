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
- Optional track context or summary hint.

## Outputs
- Code changes primarily under `projects/app/`.
- Runtime-only temporary outputs under `projects/app/.runtime/`.
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

## Execution Summary Rule

- `execution_summary` persists as `artifact.summary`.
- Keep it selection-ready for downstream buddies:
  - artifact role
  - key resolved outcome
  - downstream relevance

## Track/Object Handling

- Follow `framework/docs/track-registry.md`.
- This buddy may read tracks and create/update artifact objects through the resolved task.
- Do not mutate track lifecycle fields directly.
- If output belongs to a track, rely on the explicit switch track target or existing task binding; artifacts do not store direct track references.

## Output Path

- Code changes: primarily `projects/app/`
- Project runtime-only temporary outputs: `projects/app/.runtime/`
- Durable BuddySwitch state: task objects under `buddyswitch/objects/tasks/`, artifact objects under `buddyswitch/objects/artifacts/`, and run audits under `buddyswitch/content/runs/`
- Do not request or rely on `artifacts/*.md` or `runs/summaries/**`.

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
