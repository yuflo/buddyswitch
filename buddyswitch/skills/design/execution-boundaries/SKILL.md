# execution-boundaries

## Purpose
- Define permissions, confirmation points, and user control boundaries for AI actions.

## Use when
- The task is about what the AI may do directly versus what requires confirmation.
- The user wants clearer boundaries around automation and control.
- There is existing design context that needs boundary-specific refinement.

## Do Not Use When
- The request is mainly about broad design drafting or critique.
- The task is about memory strategy, recovery behavior, or explanatory copy.
- The work is PM scoping, implementation, or testing.

## Inputs
- `prd`
- `design-spec`
- `requirements`
- `track`

## Outputs
- A `boundaries-spec` artifact object in `buddyswitch/objects/artifacts/`.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.
- A focused boundaries artifact covering objective, recommendations, edge cases, and open questions.

## Steps
1. Read the current product and design context for AI actions.
2. Define where the user retains control and where the AI may execute directly.
3. Capture confirmation rules, edge cases, and unresolved questions.
4. Write the artifact using the boundaries template.

## Verification
- Confirm the output makes execution boundaries explicit and actionable.
- Confirm the recommendations prioritize trust and user control.
- Confirm the artifact stays focused on permissions and confirmations.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.

## Required Output Fields

- `objective`
- `recommendations`
- `edge_cases`
- `open_questions`

## Guardrails

- Do not rewrite the full product design.
- Do not implement code.
- Do not leave confirmation behavior implicit.

## Examples

- `switch design: Define which AI actions need confirmation before execution`
- `switch design: Set user-control boundaries for automated task execution`

## Counterexamples

- `switch design: Define when the AI should proactively intervene`
- `switch dev: Implement confirmation modals in projects/app`

## Gotchas

- Make the user-control rule explicit for every meaningful action category.
