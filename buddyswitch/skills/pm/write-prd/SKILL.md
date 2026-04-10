---
name: write-prd
description: Produce an MVP PRD from research and requirements, aligned with the PM contract.
version: "2.0"
track_mode: required
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
- The task is primarily about track lifecycle administration such as create/advance/attach/archive.
- The user wants design structure, implementation work, market research, or smoke testing as the main outcome.
- There is no valid track context and the user is not actually asking for a PRD.

## Inputs
- Research artifacts and product context.
- Track context and existing artifact ids when relevant.
- Constraints, assumptions, and requirements.
- Optional explicit output path.

## Outputs
- A PRD artifact in `artifacts/<artifact-id>--<slug>.md` unless overridden.
- A PM run summary in `runs/summaries/pm/` when default runtime persistence is used.
- Structured sections covering problem, goals, scenarios, scope, acceptance criteria, risks, and open questions.

## Steps

1. Define problem and user value from available evidence.
2. Draft goals and non-goals with clear boundaries.
3. Define users and scenarios.
4. Split scope into P0 and P1.
5. Add acceptance criteria, risks, and open questions.
6. Write the PRD using the PRD template.

## Verification
- Confirm a valid track context exists because this skill requires one.
- Confirm the output is product-definition content rather than design or implementation detail.
- Confirm scope is split clearly enough for downstream buddies to act on it.

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

## Examples
- `switch pm: Draft the MVP PRD for onboarding rewrite track`
- `switch pm: Continue track track-growth-loop and define P0/P1 scope`
- `switch pm: Write acceptance criteria and risks for the creator livestream MVP`

## Counterexamples
- `switch pm: create creator-livestream track and set next_buddy design`
- `switch design: produce IA spec for the onboarding rewrite`
- `switch market: research competitor positioning for creator livestream tools`

## Gotchas
- Tasks mentioning a track are not automatically track-management tasks; PRD work often references a track as context.
- Avoid drifting into implementation detail or design specification when the user asked for product definition.
