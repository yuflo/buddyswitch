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
- The request references approved scope, a PRD, a prototype artifact, or concrete application behavior.

## Do Not Use When
- The user wants product scoping, design specification, market research, or test-only execution.
- The request is really a track lifecycle update for PM.
- The work would require changing product direction rather than implementing an approved scope.

## Inputs
- Task request and expected behavior.
- PRD and other approved artifact context context when available.
- Target code paths and technical constraints.
- Optional track context or summary hint.

## Outputs
- Durable outputs are written explicitly through env tools.
- Durable implementation report content is written through `artifact-tool` `artifact.create_revision`.
- Reference written artifacts by explicit ids when relevant.

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

- Runtime execution uses env.tool through python3 scripts/env/client.py ... .
- Product-readable durable state is written explicitly as task or artifact objects.
- Use buddybox env tools with `logical_name` for active-buddy-private working files.
- Return after required explicit durable writes are complete.

## BuddySwitch Commit Output

Write durable outputs explicitly via env tools. Do not rely on deprecated prepare/persist flows.

Required top-level field:
- `execution_summary`

Use `artifact-tool` when this skill produces a durable artifact:
- `template`: `brief`
- `title`: concise artifact title
- `summary`: short downstream selection summary
- `body`: include `task_summary`, `changed_files`, `implementation_notes`, `verification`, `risks`, and `follow_ups` as markdown

After `artifact.create_revision` returns `ok=true`, use `track.open` and `artifact.get` to verify shared visibility when needed.
Use optional `working_notes` for concise reasoning or verification notes.
Use optional `task_id` only as association metadata for an explicitly selected task.

## Guardrails

- Do not change product scope silently.
- Do not make architecture direction changes without explicit note.
- Do not skip verification reporting.
- Do not write runtime noise into `projects/app/` source folders; write temporary private files through buddybox env tools using `logical_name`.

## Examples
- `Implement the approved P0 creator profile flow in projects/app`
- `Fix the regression in onboarding CTA behavior and report verification`
- `Build the playlist reorder interaction from the approved artifact context`

## Counterexamples
- `Define the MVP scope for creator profile`
- `Clarify the product scope for playlist reorder`
- `Run smoke checks for the onboarding CTA regression`

## Gotchas
- This skill can use track context, but it does not own track lifecycle changes.
- Implementation tasks often mention requirements artifacts; that does not make them PM tasks.
