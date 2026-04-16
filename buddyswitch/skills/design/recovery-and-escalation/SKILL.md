# recovery-and-escalation

## Purpose
- Define fallback, retry, rollback, escalation, and human handoff behavior.

## Use when
- The task is about failure recovery, escalation paths, or human handoff logic.
- The user wants clearer behavior when the AI cannot complete the task safely or successfully.
- Existing design context is available and needs recovery-specific refinement.

## Do Not Use When
- The request is a broad first-pass design draft.
- The task is mainly about onboarding, memory, or wording improvements.
- The work is PM scoping, implementation, or testing.

## Inputs
- `prd`
- `design-spec`
- `requirements`
- `track`

## Outputs
- A `recovery-spec` artifact object in `buddyswitch/objects/artifacts/`.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.
- A focused recovery artifact covering objective, recommendations, edge cases, and open questions.

## Steps
1. Read the current product and design context around failure and fallback behavior.
2. Define retry, rollback, escalation, and human handoff expectations.
3. Capture recommendations, edge cases, and unresolved questions.
4. Write the artifact using the recovery template.

## Verification
- Confirm the output covers both automated recovery and explicit human handoff.
- Confirm the recommendations preserve trust during failure states.
- Confirm the artifact stays focused on recovery and escalation behavior.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.

## Required Output Fields

- `objective`
- `recommendations`
- `edge_cases`
- `open_questions`

## Guardrails

- Do not implement recovery logic in code.
- Do not leave escalation behavior vague.
- Do not drift into unrelated design work.

## Examples

- `switch design: Define fallback and escalation behavior when the AI cannot finish a task`
- `switch design: Clarify retry versus human handoff for failed assistant actions`

## Counterexamples

- `switch design: Improve prompts and explanatory AI language`
- `switch test: Run failure-path smoke checks for the assistant`

## Gotchas

- Cover both retry behavior and explicit human handoff so recovery paths do not end in ambiguity.
