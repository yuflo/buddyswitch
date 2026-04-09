---
name: write-prd
description: Produce an MVP PRD from research and requirements, aligned with the PM contract.
---

# write-prd

## Agent

- `pm`

## Contract And Template

- Contract: `framework/contracts/pm.md`
- Template: `framework/templates/prd.md`

## Inputs

- Research artifacts and context.
- Product requirements and constraints.
- Existing assumptions and dependencies.
- Optional output file path.

## Steps

1. Define problem and user value from available evidence.
2. Draft goals and non-goals with clear boundaries.
3. Define users and scenarios.
4. Split scope into P0 and P1.
5. Add acceptance criteria, risks, and open questions.
6. Write the PRD using the PRD template.

## Track/Object Handling

- Follow `framework/docs/track-registry.md`.
- PM can create/update/advance tracks and attach/detach artifact IDs.
- PM can create/update artifact objects and set `context_track_id`.
- Track creation/progression should stay explicit with user intent.

## Output Path

- Default: `artifacts/<artifact-id>--<slug>.md`
- If user provides a path, use it as-is.

## Required Output Fields

- `problem`
- `goals`
- `non_goals`
- `users_and_scenarios`
- `scope_p0_p1`
- `acceptance_criteria`
- `risks`
- `open_questions`

## Guardrails

- Do not produce visual design specs.
- Do not implement code.
- Do not expand scope without calling it out explicitly.
