# conversation-and-clarity

## Purpose
- Improve prompts, clarifications, explanatory copy, and user-facing AI language.

## Use when
- The task is about wording, guidance, prompts, or clarification flow quality.
- The user wants the AI interaction to feel clearer, more direct, or easier to trust.
- There is enough existing design context to refine language and communication patterns.

## Do Not Use When
- The request is a broad first-pass design draft.
- The task is primarily about initiative, permissions, or recovery flow logic.
- The work is PM scoping, implementation, or testing.

## Inputs
- `prd`
- `design-spec`
- `requirements`
- `track`

## Outputs
- A `conversation-spec` artifact object in `buddyswitch/objects/artifacts/`.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.
- A focused conversation artifact covering objective, recommendations, edge cases, and open questions.

## Steps
1. Read the current product and design context for user-facing language.
2. Identify where the AI needs clearer prompts, clarifications, or explanatory copy.
3. Capture recommendations, edge cases, and unresolved questions.
4. Write the artifact using the conversation template.

## Verification
- Confirm the recommendations improve clarity without over-explaining.
- Confirm the output stays grounded in the actual product flows.
- Confirm the artifact stays focused on user-facing AI language.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.

## Required Output Fields

- `objective`
- `recommendations`
- `edge_cases`
- `open_questions`

## Guardrails

- Do not turn this into a visual design task.
- Do not implement copy changes in product code.
- Do not drift away from conversation and clarity scope.

## Examples

- `switch design: Improve the AI's clarification prompts for ambiguous tasks`
- `switch design: Refine explanatory copy around assistant-generated actions`

## Counterexamples

- `switch design: Define rollback and human handoff behavior`
- `switch dev: Update prompt copy in the app codebase`

## Gotchas

- Clarity work should reduce ambiguity without burying the user in extra words.
