# memory-and-context

## Purpose
- Define remembered context, visible context, and user control over AI memory.

## Use when
- The task is about what the AI remembers, surfaces, or forgets.
- The user wants clearer memory behavior or context transparency.
- Existing design context is available and needs memory-specific refinement.

## Do Not Use When
- The request is about broad design drafting or critique.
- The task is mainly about onboarding, copy, or recovery behavior.
- The work is PM scoping, implementation, or testing.

## Inputs
- `prd`
- `design-spec`
- `requirements`
- `track`

## Outputs
- A `memory-spec` artifact object in `buddyswitch/objects/artifacts/`.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.
- A focused memory artifact covering objective, recommendations, edge cases, and open questions.

## Steps
1. Read the current product and design context around context handling.
2. Define remembered, visible, and user-editable context behavior.
3. Capture recommendations, edge cases, and unresolved questions.
4. Write the artifact using the memory template.

## Verification
- Confirm the output makes memory behavior explicit and user-controllable.
- Confirm the recommendations distinguish visible context from hidden persistence.
- Confirm the artifact stays focused on memory and context handling.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.

## Required Output Fields

- `objective`
- `recommendations`
- `edge_cases`
- `open_questions`

## Guardrails

- Do not implement memory systems in code.
- Do not leave user control implicit.
- Do not expand into unrelated design areas.

## Examples

- `switch design: Define what the AI should remember between sessions`
- `switch design: Clarify visible versus hidden context in the assistant workspace`

## Counterexamples

- `switch design: Improve onboarding and time-to-value for first-run users`
- `switch dev: Implement memory persistence in projects/app`

## Gotchas

- Separate remembered context from user-visible context so trust rules stay clear.
