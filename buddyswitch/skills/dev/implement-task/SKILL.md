---
name: implement-task
description: Use when the task is implementing scoped product changes, bug fixes, or refactors in project code.
---

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
- A contribution to the current compact buddy-run commit.
- Durable implementation report content is written before persist through `artifact-tool` `artifact.create_revision`.
- The final run commit references already-written artifacts with optional `artifact_ids` metadata.

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
- This native skill contributes content to the current buddy run.
- Do not call persist from the skill perspective.
- The locked buddy session persists one buddy run commit after all needed native skill work is integrated.

## BuddySwitch Commit Output

Contribute to one buddy-run commit. Do not call persist from inside the skill.

Required top-level field:
- `execution_summary`

Use `artifact-tool` before persist when this skill produces a durable artifact:
- `kind`: `implementation-report`
- `title`: concise artifact title
- `summary`: short downstream selection summary
- `content`: include `task_summary`, `changed_files`, `implementation_notes`, `verification`, `risks`, and `follow_ups`

After `artifact.create_revision` returns `ok=true`, include the returned artifact id in optional `artifact_ids`.
Use optional `working_notes` for concise reasoning or verification notes.
Use optional `task_id` only as association metadata for an explicitly selected task.
Use optional `handoff` when another manifest buddy should continue.

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
