# design-critique

## Purpose
- Review an existing design artifact, flow, or implementation from a functional AI product experience perspective.

## Use when
- The user wants critique, review, or prioritization of design issues rather than a fresh first-pass draft.
- There is already a design artifact, flow description, or implemented experience to examine.
- The expected output is findings, strengths, open questions, and recommended next moves.

## Do Not Use When
- The request needs a broad first design draft rather than a review.
- The task is primarily PM scoping, market research, implementation, or smoke testing.
- There is no existing design context to critique.

## Inputs
- Existing `design-spec` or equivalent flow/implementation context.
- PRD, requirements, and relevant track context.
- References, screenshots, or implementation notes when available.

## Outputs
- A `design-review` artifact object in `buddyswitch/objects/artifacts/`.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.
- Structured critique covering findings, strengths, open questions, and recommended next moves.

## Steps
1. Read the available design and implementation context before forming conclusions.
2. Evaluate clarity, control, flow quality, trust, and recovery from a functional AI product perspective.
3. Record the most important findings and note what is already working well.
4. Capture unresolved questions and concrete recommended next moves.
5. Write the review using the design review template.

## Verification
- Confirm the review is grounded in the provided design or implementation context.
- Confirm findings are specific enough to guide follow-up work.
- Confirm the review distinguishes strengths from issues instead of producing only negative commentary.
- Confirm the output does not drift into implementation or PM scope rewriting.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.

## Required Output Fields

- `findings`
- `strengths`
- `open_questions`
- `recommended_next_moves`

## Guardrails

- Do not silently rewrite product scope.
- Do not implement code.
- Do not turn the review into unconstrained visual exploration.

## Examples
- `switch design: Review the current onboarding design and call out the biggest issues`
- `switch design: Critique the AI workflow tool's first-run experience`
- `switch design: Evaluate the current design spec for trust and recovery gaps`

## Counterexamples
- `switch design: Draft the first-pass product design for the onboarding flow`
- `switch pm: Update the PRD scope for onboarding`
- `switch dev: Implement the revised onboarding flow in projects/app`

## Gotchas
- A good review should preserve useful strengths while still prioritizing the critical issues.
- Keep recommended next moves concrete enough that a follow-up design or dev task can act on them.
