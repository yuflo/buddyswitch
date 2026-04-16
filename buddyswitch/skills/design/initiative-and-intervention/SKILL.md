# initiative-and-intervention

## Purpose
- Define when AI should intervene, suggest, act, or stay silent.

## Use when
- The task is about agent initiative, nudges, proactive behavior, or restraint.
- The user wants clearer intervention logic in a functional AI experience.
- There is already enough product/design context to refine initiative behavior.

## Do Not Use When
- The request is a broad first-pass design draft.
- The task is mainly about permissions, memory, recovery, or user-facing copy.
- The work is PM scoping, implementation, or testing.

## Inputs
- `prd`
- `design-spec`
- `requirements`
- `track`

## Outputs
- An `initiative-spec` artifact object in `buddyswitch/objects/artifacts/`.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.
- A focused initiative artifact covering objective, recommendations, edge cases, and open questions.

## Steps
1. Read the current product and design context around AI actions.
2. Define where the AI should suggest, act, wait, or ask.
3. Capture the initiative recommendations, edge cases, and unresolved questions.
4. Write the artifact using the initiative template.

## Verification
- Confirm the output distinguishes proactive help from unwanted interruption.
- Confirm the logic is specific enough for downstream design or implementation work.
- Confirm the artifact stays focused on initiative behavior.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.

## Required Output Fields

- `objective`
- `recommendations`
- `edge_cases`
- `open_questions`

## Guardrails

- Do not turn this into a general design rewrite.
- Do not implement code.
- Do not ignore user control in favor of AI autonomy.

## Examples

- `switch design: Define when the AI should suggest actions versus stay silent`
- `switch design: Tighten intervention rules for proactive task follow-up`

## Counterexamples

- `switch design: Define permissions and confirmation points for AI actions`
- `switch pm: Update MVP scope for proactive suggestions`

## Gotchas

- Recommendations should cover both helpful intervention and intentional restraint.
