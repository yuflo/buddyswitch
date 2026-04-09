---
name: ia-spec
description: Create IA and interaction specification artifacts aligned with the design contract.
track_mode: optional
default_artifact_kind: design-spec
auto_summary: true
triggers:
  - design
  - ia
  - flow
  - ux
---

# ia-spec

## Agent

- `design`

## Contract And Template

- Contract: `framework/contracts/design.md`
- Template: `framework/templates/design-spec.md`

## Inputs

- PRD or equivalent requirement artifact.
- Platform and component constraints.
- References such as screenshots or existing patterns.
- Optional output file path.

## Steps

1. Build IA map from product goals and scenarios.
2. Define primary user flows end to end.
3. Specify key screens and their responsibilities.
4. Cover key states and transitions.
5. Add interaction notes and unresolved design questions.
6. Write the design artifact using the design template.

## Track/Object Handling

- Follow `framework/docs/track-registry.md`.
- This buddy may read tracks and create/update artifact objects.
- Do not mutate track lifecycle fields directly.
- If output belongs to a track, set `context_track_id` on artifact creation/update.

## Output Path

- Default: `artifacts/<artifact-id>--<slug>.md`
- If user provides a path, use it as-is.

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
