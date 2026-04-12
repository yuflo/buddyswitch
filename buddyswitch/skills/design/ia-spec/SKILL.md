---
name: ia-spec
description: Create IA and interaction specification artifacts aligned with the design contract.
version: "2.0"
default_artifact_kind: design-spec
auto_summary: true
output_schema: framework/schemas/design/ia-spec.json
side_effect_level: medium
produces:
  - design-spec
  - ia
  - interaction-flow
consumes:
  - prd
  - requirements
  - track
---

# ia-spec

## Purpose
- Translate approved product scope into an information architecture and interaction specification that design and implementation can follow.

## Use when
- The task is about IA, user flows, screen structure, interaction states, UX behavior, or design specification.
- The user wants a design artifact rather than code or product strategy.
- The prompt references flows, screens, navigation, state handling, or interaction details.

## Do Not Use When
- The user primarily wants PRD scoping, track lifecycle management, code implementation, research, or smoke testing.
- The task asks for unconstrained visual exploration rather than IA and interaction structure.
- There is no underlying product scope and the request is really still a PM definition problem.

## Inputs
- PRD or equivalent requirement artifact.
- Platform and component constraints.
- Existing patterns, references, or screenshots.
- Optional track context or summary hint.

## Outputs
- A design-spec artifact object in `buddyswitch/objects/artifacts/`.
- A structured IA and interaction spec covering flows, screens, states, and open questions.
- A run audit when default runtime persistence is used.

## Steps

1. Build IA map from product goals and scenarios.
2. Define primary user flows end to end.
3. Specify key screens and their responsibilities.
4. Cover key states and transitions.
5. Add interaction notes and unresolved design questions.
6. Write the design artifact using the design template.

## Verification
- Confirm the design output follows the approved product scope instead of redefining it.
- Confirm key states and transitions are covered for the main flows.
- Confirm unresolved design risks are called out explicitly.

## Track/Object Handling

- Follow `framework/docs/track-registry.md`.
- This buddy may read tracks and create/update artifact objects through the resolved task.
- Do not mutate track lifecycle fields directly.
- If output belongs to a track, rely on the explicit switch track target or existing task binding; artifacts do not store direct track references.

## Output Path

- Default BuddySwitch state: `buddyswitch/objects/tasks/<task-id>.json`, `buddyswitch/objects/artifacts/<artifact-id>.json`, and `buddyswitch/content/runs/<run-id>.json`
- Do not request or rely on `artifacts/*.md` or `runs/summaries/**`.

## Required Output Fields

- `ia`
- `primary_flows`
- `key_screens`
- `state_coverage`
- `interaction_notes`
- `open_questions`

## Guardrails

- Do not rewrite product strategy.
- Do not implement code.
- Do not run unconstrained visual exploration.

## Examples
- `switch design: Create the IA spec for creator onboarding flow`
- `switch design: Continue track-growth-loop and define key screens and interaction states`
- `switch design: Produce user flow and navigation structure for playlist management`

## Counterexamples
- `switch pm: Draft the PRD for playlist management`
- `switch dev: Implement playlist management in projects/app`
- `switch market: Research adoption patterns for creator onboarding products`

## Gotchas
- This skill should stay at IA and interaction depth; it is not a brand or visual exploration skill.
- A task mentioning a track or PRD often still belongs here if the required output is a design artifact.
