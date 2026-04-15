# launch-prep

## Purpose
- Produce a first-launch preparation brief that connects PMF, positioning, and channel decisions into a validation-ready launch plan with instrumentation and feedback loops.

## Use when
- The task is preparing a first launch, validation page, or structured feedback loop before public release.
- The task needs a credible launch goal, selected channel, launch assets list, and learning plan.
- The product direction is already defined enough that launch preparation is the next market step.

## Do Not Use When
- The task still needs PMF judgment, discovery work, or first-channel selection.
- The task is shipping product functionality or coordinating implementation work.
- The task is asking for growth automation, scaled lifecycle marketing, or admin-system execution.
- The task is writing visual design specs or frontend implementation details.

## Inputs
- Research question or launch objective.
- Available `pmf-report`, `positioning-brief`, and `channel-plan` artifacts.
- Provided links, prior artifacts, or founder constraints around launch timing and assets.
- Optional notes on audience, success criteria, or manual follow-up capacity.

## Outputs
- A launch-prep artifact object with launch goal, audience, selected channel, launch assets, instrumentation plan, feedback collection plan, success and failure signals, and conclusion.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.
- Explicit notes when launch confidence depends on assumptions rather than observed evidence.

## Verification
- Confirm this is launch preparation, not product shipping.
- Confirm this is not growth automation.
- Confirm the launch assets, instrumentation, and feedback loop are realistic for the current stage and selected channel.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.

## Required Output Fields

- `research_question`
- `launch_goal`
- `target_audience`
- `selected_channel`
- `launch_assets`
- `instrumentation_plan`
- `feedback_collection_plan`
- `success_signals`
- `failure_signals`
- `evidence`
- `source_traceability`
- `risks_and_unknowns`
- `conclusion`

## Guardrails

- This is launch preparation, not product shipping.
- This is not growth automation.
- Stop before login-required analytics or admin systems unless the user confirms access.
- Do not imply operational readiness that the current evidence does not support.

## Examples
- `switch market: Prepare a first validation launch for an AI assistant landing page`
- `switch market: Build the launch-prep brief for a founder-led beta announcement`
- `switch market: Define feedback collection and instrumentation for a niche workflow launch`

## Counterexamples
- `switch dev: Ship the beta announcement flow in projects/app`
- `switch market: Choose the first acquisition channel for the workflow launch`
- `switch market: Automate the full growth funnel after launch`

## Gotchas
- A strong launch-prep brief should make the feedback loop explicit before public release.
- Launch readiness at this stage is about learning quality, not polished scale.
