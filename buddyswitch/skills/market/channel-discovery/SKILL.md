# channel-discovery

## Purpose
- Produce a first-channel plan that compares believable acquisition options, scores them against explicit criteria, and recommends a small experiment with clear kill signals.

## Use when
- The task is choosing the first believable user-acquisition channel for an early product.
- The task is planning a narrow channel experiment rather than a broad growth strategy.
- Enough evidence exists from market, PMF, discovery, or positioning work to compare channels credibly.

## Do Not Use When
- The task still needs broad market evidence or problem validation before channel choice.
- The task is writing positioning or homepage copy instead of selecting a channel.
- The task is building launch operations, asset production, or feedback loops; use `launch-prep`.
- The task is asking for growth automation, scaling tactics, or multi-channel playbooks.

## Inputs
- Research question or channel-choice objective.
- Available `market-scan`, `pmf-report`, `customer-discovery`, and `positioning-brief` artifacts.
- Provided links, prior artifacts, or founder channel constraints.
- Optional assumptions about budget, effort, or available distribution access.

## Outputs
- A channel-discovery artifact object with candidate channels, scoring criteria, ranked options, recommended channels, experiment plan, kill signals, and conclusion.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.
- Explicit notes when channel confidence is limited by missing evidence or thin reachability data.

## Verification
- Confirm candidate channels are compared against explicit selection criteria.
- Confirm the recommended primary and secondary channels are believable for the current product and audience maturity.
- Confirm the experiment plan is small, testable, and paired with kill signals rather than vague growth aspirations.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.

## Required Output Fields

- `research_question`
- `candidate_channels`
- `selection_criteria`
- `channel_scores`
- `recommended_primary_channel`
- `recommended_secondary_channel`
- `experiment_plan`
- `kill_signals`
- `evidence`
- `source_traceability`
- `risks_and_unknowns`
- `conclusion`

## Guardrails

- Prefer believable, reachable first channels over abstract "best practices."
- Keep the experiment narrow enough to learn quickly.
- Do not turn channel choice into growth automation or a multi-quarter marketing plan.
- Do not invent channel reach, conversion assumptions, or distribution access.

## Examples
- `switch market: Choose the first channel to test an AI assistant for sales engineers`
- `switch market: Rank early acquisition channels for this founder-led workflow tool`
- `switch market: Plan a small experiment to test whether niche communities can drive first users`

## Counterexamples
- `switch market: Build the launch checklist for the first public release`
- `switch market: Write the homepage positioning for the workflow tool`
- `switch market: Research whether the workflow tool solves a meaningful pain point`

## Gotchas
- The easiest channel to name is often not the most believable first channel to execute.
- A good channel plan should make it obvious what to stop doing if the experiment fails.
