# product-design-spec

## Purpose
- Produce a first-pass product design specification for a functional AI product.

## Use when
- The user wants a design draft, not code or PM scope work.
- The request is broad enough that the design buddy should produce a coherent first version.
- The prompt is expressed in product language rather than internal design jargon.

## Do Not Use When
- The task is primarily about PM scope definition, track lifecycle work, implementation, or smoke testing.
- The request is only asking for a narrow review of an existing design artifact.
- The task is really unconstrained visual exploration rather than functional product design.

## Inputs
- PRD or equivalent requirements artifact.
- Explicit upstream context when available: `positioning-brief`, `launch-prep`, and `requirements`.
- Track context, product constraints, and relevant references.

## Outputs
- A `design-spec` artifact object in `buddyswitch/objects/artifacts/`.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.
- A structured first-pass design specification covering product frame, experience shape, interaction structure, control, trust, and open questions.

## Steps
1. If material information is missing, ask at most 3 text-only clarification questions before drafting.
2. Interpret the request in product language and do not ask the user to choose internal skill names.
3. Define the product frame so the user job, success moment, and AI role are explicit.
4. Draft the experience shape, interaction structure, and control/trust decisions.
5. Capture interaction notes and unresolved questions.
6. Write the output using the design spec template.

## Verification
- Confirm the output stays at product-design level and does not drift into PM scope rewriting or code implementation.
- Confirm clarification stays text-only and limited to the minimum needed to unblock the draft.
- Confirm the response does not imply the existence of option UI or a runtime interaction protocol.
- Confirm the resulting artifact is coherent enough for downstream specialist refinement.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.

## Required Output Fields

- `product_frame`
- `experience_shape`
- `interaction_structure`
- `control_and_trust`
- `notes`

## Guardrails

- Do not ask the user to choose internal skill names.
- Do not imply the existence of option UI or a runtime interaction protocol.
- Do not ask more than 3 text-only clarification questions.
- Do not rewrite PM scope or implement product code.

## Examples
- `switch design: Draft the product design for an AI-first onboarding flow`
- `switch design: Produce a first-pass design spec for an AI workflow tool`
- `switch design: Outline the product behavior and key screens for an AI assistant dashboard`

## Counterexamples
- `switch pm: Define MVP scope for the AI workflow tool`
- `switch dev: Implement the onboarding flow in projects/app`
- `switch test: Run smoke checks for the latest onboarding implementation`

## Gotchas
- Keep the artifact broad enough to serve as the first design handoff, not a narrow refinement note.
- Use explicit upstream market context when it exists, especially for first-touch experiences such as landing and onboarding.
