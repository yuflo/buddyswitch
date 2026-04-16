# experience-shaping

## Purpose
- Clarify the user job, success moment, and overall experience frame before detailed flow design.

## Use when
- The task is still framing the experience and needs a crisp design brief before deeper specification.
- The user is asking about user job clarity, success conditions, or the high-level experience shape.
- A downstream design task will benefit from a tighter framing artifact.

## Do Not Use When
- The task needs a broad first-pass design specification across the whole product.
- The request is specifically about onboarding, intervention, memory, recovery, or critique depth.
- The user is asking for PM scope, implementation work, or smoke testing.

## Inputs
- `prd`
- `requirements`
- `track`

## Outputs
- A `design-brief` artifact object in `buddyswitch/objects/artifacts/`.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.
- A focused framing artifact covering objective, recommendations, edge cases, and open questions.

## Steps
1. Read the available product and requirement context.
2. Clarify the user job, desired success moment, and experience direction.
3. Capture the framing recommendations and important edge cases.
4. Write the artifact using the design brief template.

## Verification
- Confirm the output frames the experience instead of specifying detailed UI flows.
- Confirm the recommendations are concrete enough to guide follow-up design work.
- Confirm the artifact stays grounded in the provided requirements.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.

## Required Output Fields

- `objective`
- `recommendations`
- `edge_cases`
- `open_questions`

## Guardrails

- Do not rewrite PM scope.
- Do not implement code.
- Do not drift into detailed screen-by-screen design.

## Examples

- `switch design: Clarify the user job and success moment for the AI workflow tool`
- `switch design: Shape the high-level experience brief for first-time team setup`

## Counterexamples

- `switch design: Draft the full product design spec for the AI workflow tool`
- `switch dev: Implement the first-run setup flow in projects/app`

## Gotchas

- Keep this artifact at framing depth; it should prepare downstream design work, not replace it.
