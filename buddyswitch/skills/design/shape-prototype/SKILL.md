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
- A contribution to the current compact buddy-run commit.
- When persisted by the locked buddy session, one authorized artifact entry under `artifacts[]`.
- Commit JSON aligned to the active buddy schema under `framework/schemas/`.

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
- This native skill contributes content to the current buddy run.
- Do not call persist from the skill perspective.
- The locked buddy session persists one buddy run commit after all needed native skill work is integrated.

## BuddySwitch Commit Output

Contribute to one buddy-run commit. Do not call persist from inside the skill.

Required top-level field:
- `execution_summary`

Use `artifacts` when this skill produces a durable artifact:
- `kind`: `design-handoff`
- `title`: concise artifact title
- `summary`: short downstream selection summary
- `content`: include `design_goal`, `flow_or_screen_summary`, `interaction_notes`, `assets_or_preview_refs`, `handoff_notes`, and `open_questions`

Use optional `working_notes` for concise reasoning or verification notes.
Use optional `state_effects.task` only for the current prepared task.
Use optional `handoff` when another manifest buddy should continue.

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
