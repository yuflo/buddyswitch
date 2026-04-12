---
name: write-prd
description: Produce an MVP PRD from research and requirements, aligned with the PM contract.
version: "2.0"
track_mode: optional
default_artifact_kind: prd
auto_summary: true
output_schema: framework/schemas/pm/write-prd.json
side_effect_level: medium
produces:
  - prd
  - scope
consumes:
  - research
  - requirements
  - track
---

# write-prd

## Purpose
- Produce a scoped MVP PRD that turns validated research and requirements into a concrete product definition anchored to a track.

## Use when
- The task is about drafting a PRD, defining MVP scope, clarifying acceptance criteria, or writing product requirements.
- The user wants PM output that becomes the source artifact for downstream design or implementation.
- The task references product goals, non-goals, users, scenarios, scope, dependencies, risks, or open questions.

## Do Not Use When
- The task is primarily about track lifecycle administration such as create, advance, update, or archive.
- The user wants design structure, implementation work, market research, or smoke testing as the main outcome.
- There is no clear product-definition demand and the user is only asking for track lifecycle administration.

## Inputs
- Research artifacts and product context.
- Track context and existing task/artifact context when relevant.
- Constraints, assumptions, and requirements.
- Optional track context or summary hint.

## Outputs
- A PRD artifact object in `buddyswitch/objects/artifacts/`.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.
- Structured sections covering problem, goals, scenarios, scope, acceptance criteria, risks, and open questions.

## Steps

1. Define problem and user value from available evidence.
2. Draft goals and non-goals with clear boundaries.
3. Define users and scenarios.
4. Split scope into P0 and P1.
5. Add acceptance criteria, risks, and open questions.
6. Write the PRD using the PRD template.

## Verification
- Use track context when available, but keep the PRD demand clear enough to stand on its own.
- Confirm the output is product-definition content rather than design or implementation detail.
- Confirm scope is split clearly enough for downstream buddies to act on it.

## Track/Object Handling

- Follow `framework/docs/track-registry.md`.
- PM can create/update/advance/archive tracks through track-manager when needed.
- PM can create/update artifact objects through the resolved task.
- Track creation/progression should stay explicit in demand text or track-manager output.

## Output Path

- Default BuddySwitch state: `buddyswitch/objects/tasks/<task-id>.json`, `buddyswitch/objects/artifacts/<artifact-id>.json`, and `buddyswitch/content/runs/<run-id>.json`
- Do not request or rely on `artifacts/*.md` or `runs/summaries/**`.

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
- `switch pm: Draft the MVP PRD for onboarding rewrite track`
- `switch pm -> track-growth-loop: Continue product definition and define P0/P1 scope`
- `switch pm: Write acceptance criteria and risks for the creator livestream MVP`

## Counterexamples
- `switch pm -> track-creator-livestream: create track and set next_buddy design`
- `switch design: produce IA spec for the onboarding rewrite`
- `switch market: research competitor positioning for creator livestream tools`

## Gotchas
- Tasks mentioning a track are not automatically track-management tasks; PRD work often references a track as context.
- Avoid drifting into implementation detail or design specification when the user asked for product definition.
