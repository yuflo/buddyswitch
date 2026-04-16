# activation-and-first-value

## Purpose
- Improve first-run experience, onboarding, empty states, and time-to-value for a functional AI product.

## Use when
- The task is about onboarding, first-touch UX, setup flow, or empty-state activation.
- The user wants the experience to deliver value faster or more clearly.
- Existing product and design context already exists and needs activation-focused refinement.

## Do Not Use When
- The task needs a broad first-pass design draft.
- The request is mainly about PM scope, implementation, or testing.
- The problem is unrelated to first-run or activation moments.

## Inputs
- `prd`
- `positioning-brief`
- `launch-prep`
- `design-spec`
- `requirements`
- `track`

## Outputs
- An `activation-spec` artifact object in `buddyswitch/objects/artifacts/`.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.
- A focused activation artifact covering objective, recommendations, edge cases, and open questions.

## Steps
1. Read the current design and market-facing context for first-touch experiences.
2. Identify the shortest path to first value and the points where users can stall.
3. Capture activation recommendations, edge cases, and unresolved questions.
4. Write the artifact using the activation template.

## Verification
- Confirm the recommendations reduce time-to-value and onboarding ambiguity.
- Confirm the artifact uses the existing design/product context rather than redefining it.
- Confirm the output is specific to activation moments.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.

## Required Output Fields

- `objective`
- `recommendations`
- `edge_cases`
- `open_questions`

## Guardrails

- Do not rewrite the entire product design.
- Do not implement code.
- Do not drift away from first-run and activation scope.

## Examples

- `switch design: Improve onboarding and first-value moments for the AI workflow tool`
- `switch design: Refine the empty-state activation path for a new workspace`

## Counterexamples

- `switch design: Review the current onboarding design and list issues`
- `switch test: Run smoke checks for the onboarding implementation`

## Gotchas

- Keep recommendations focused on first-touch and activation outcomes, not the full product surface.
