---
name: shape-prototype
description: Use when the task is shaping a visible UI/UX prototype and producing a design handoff artifact.
---

# shape-prototype

## Purpose
- Shape a visible UI/UX prototype direction and package a durable design handoff artifact for downstream PM, dev, and test work.

## Use When
- The task is about prototype structure, page flow, interaction direction, layout shape, or design handoff outcomes.
- The user wants a concrete prototype plan or `.sandbox/design/` preview path rather than product scope or implementation code.
- The work should turn requirements, PRD, market context, or track context into an actionable design artifact.

## Do Not Use When
- The task is actually product scoping, market research, code implementation, or test execution.
- The request is only about track lifecycle mutation.
- The work would skip a design handoff artifact and only return loose discussion notes.

## Inputs
- PRD, requirements, market evidence, and track context when available.
- Prior design handoff artifacts when iterating an existing prototype direction.
- Constraints about target screens, CTA flow, navigation, or preview environment.

## Outputs
- A design-handoff artifact describing prototype kind, page map, user flow, preview path, handoff notes, and open questions.
- Preview-oriented runtime outputs under `.sandbox/design/` when needed.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.

## Steps

1. Restate the target prototype scope and main user journey.
2. Shape the page map and primary flow before detailed polish.
3. Decide the preview root and entry file for the first runnable handoff.
4. Capture PM, dev, and test handoff notes in separate lists.
5. Record open questions that materially affect the next prototype pass.
6. Package the result as the structured design-handoff artifact.

## Verification
- Confirm the prototype direction stays aligned with the active task and does not silently rewrite product scope.
- Confirm the preview path points to a concrete `.sandbox/design/` location when a runnable artifact is produced.
- Confirm PM, dev, and test handoff notes are actionable for the next buddy turn.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.

## Required Output Fields

- `prototype_kind`
- `page_map`
- `primary_user_flow`
- `preview`
- `handoff`
- `open_questions`

## Guardrails

- Do not silently expand product scope while shaping the prototype.
- Do not output implementation code as the primary deliverable.
- Do not omit the preview path when a sandbox prototype exists.
- Do not collapse PM, dev, and test handoff into one mixed note list.

## Examples
- `Shape the landing-page prototype`
- `Turn the approved onboarding requirements into a first prototype handoff`
- `Refine the pricing-to-demo-request flow and package the design handoff`

## Counterexamples
- `Define the MVP scope for the landing page`
- `Implement the landing page in projects/app`
- `Smoke test the onboarding prototype`

## Gotchas
- Prototype shaping can use market and PRD inputs, but it should still end in a design artifact instead of a scope artifact.
- Keep the first pass structural; unanswered visual polish can stay in `open_questions`.
