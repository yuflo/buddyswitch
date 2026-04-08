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

## Registry Handling

- Follow `framework/docs/track-registry.md`.
- If the user explicitly references Track/registry/register/promote intent, use `scripts/registry.py` to register the PRD artifact with `role: "pm"` and `type: "prd"`.
- If the user does not explicitly reference Track/registry/register/promote intent, leave the artifact untracked and optionally suggest a registration switch.
- Do not create or associate Tracks based only on PM judgment.

## Output Path

- Default: `artifacts/prd/<slug>.md`
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
