---
name: write-prd
description: Use when the task is drafting a PRD, defining MVP scope, or turning validated requirements into product requirements.
---

# write-prd

## Purpose
- Produce a scoped MVP PRD that turns explicit market evidence and requirements into a concrete product definition anchored to a track.

## Use when
- The task is about drafting a PRD, defining MVP scope, clarifying acceptance criteria, or writing product requirements.
- The user wants PM output that becomes the source artifact for downstream design or implementation.
- The task references product goals, non-goals, users, scenarios, scope, dependencies, risks, or open questions.

## Do Not Use When
- The task is primarily about track lifecycle administration such as create, advance, update, or archive.
- The user wants design structure, implementation work, market research, or smoke testing as the main outcome.
- There is no clear product-definition demand and the user is only asking for track lifecycle administration.

## Inputs
- Explicit market evidence artifacts when they exist: `market-scan`, `pmf-report`, `customer-discovery`, `positioning-brief`, `channel-plan`, and `launch-prep`.
- Track context and existing task/artifact context when relevant.
- Constraints, assumptions, and requirements.
- Optional track context or summary hint.

## Outputs
- A PRD artifact object in `buddyswitch/objects/artifacts/`.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.
- Structured sections covering problem, goals, scenarios, scope, acceptance criteria, risks, and open questions.

## Steps

1. Define problem and user value from the available market evidence and requirements.
2. Draft goals and non-goals with clear boundaries.
3. Define users and scenarios.
4. Split scope into P0 and P1.
5. Add acceptance criteria, risks, and open questions.
6. Write the PRD using the PRD template.

## Verification
- Use track context when available, but keep the PRD demand clear enough to stand on its own.
- Prefer explicit market artifacts over a generic research summary so PM can trace the problem statement back to actual market evidence.
- Confirm the output is product-definition content rather than design or implementation detail.
- Confirm scope is split clearly enough for downstream buddies to act on it.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.

## PM Track Handling

- A PRD task that references `track-*` may use the track as context, but the core deliverable is still product-definition output.
- If the user is actually asking to create, update, advance, archive, or hand off a track, use `track-manager` for that lifecycle change.
- Keep track progression or buddy handoff explicit in demand text or in a separate `track-manager` result; do not silently turn PRD work into track mutation.

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

## Examples
- `Draft the MVP PRD for onboarding rewrite track`
- `Continue product definition and define P0/P1 scope`
- `Write acceptance criteria and risks for the creator livestream MVP`

## Counterexamples
- `create track and set next_buddy design`
- `refine the onboarding prototype and flow`
- `research competitor positioning for creator livestream tools`

## Gotchas
- Tasks mentioning a track are not automatically track-management tasks; PRD work often references a track as context.
- Avoid drifting into implementation detail or design specification when the user asked for product definition.
