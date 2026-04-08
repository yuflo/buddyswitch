---
name: implement-task
description: Implement scoped product changes in project code and report verified outcomes.
---

# implement-task

## Agent

- `dev`

## Contract And Template

- Contract: `framework/contracts/dev.md`
- Template: `framework/templates/impl-report.md`

## Inputs

- Task request and expected behavior.
- PRD and design context.
- Target code paths and constraints.
- Optional summary output path.

## Steps

1. Restate the requested task and affected area.
2. Implement scoped changes in `projects/app/`.
3. Keep refactors localized and justified.
4. Run relevant local verification commands.
5. Summarize changed files, implementation notes, verification, and limitations.
6. Write durable implementation summary when requested.

## Registry Handling

- Follow `framework/docs/track-registry.md`.
- If the user explicitly references Track/registry/register/promote intent, register the implementation report with `role: "dev"` and `type: "implementation-report"`.
- If the user does not explicitly reference Track/registry/register/promote intent, leave the implementation report untracked and optionally suggest a registration switch.
- Do not create or associate Tracks based only on dev judgment.

## Output Path

- Code changes: primarily `projects/app/`
- Project runtime-only temporary outputs: `projects/app/.runtime/`
- Durable summary default: `artifacts/build/<slug>.md`
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
