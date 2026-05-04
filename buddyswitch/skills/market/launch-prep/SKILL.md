---
name: launch-prep
description: Use when the task is preparing a first launch, validation page, or feedback loop before public release.
---

# launch-prep

## Execution Order
1. Before any market research, run discovery in the visible `chrome-devtools-cockpit` browser and keep the workflow `browser-native`.
2. Read all selected upstream inputs before forming new market claims.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when the skill contract requires browser-native work.
5. Only after the steps above should you synthesize findings into the structured result.

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

## Market Research Cockpit Runtime

- This skill follows `framework/docs/browser-cockpit.md`.
- It uses `chrome-devtools-cockpit` as the browser executor.
- It runs in an instance headed cockpit (`browser_mode=headed-only`) with profile `instance-browser`.
- Discovery mode is `browser-native`: search in the browser and continue into real result pages, details, comments, and related pages where relevant.
- Critical-source login is mandatory takeover, and fallback policy is no silent degrade.
- Do not silently downgrade to low-density public alternatives when critical launch evidence is blocked.
- Do not use silent search API/snippet/crawler fallback.
- If browser-native access is genuinely blocked, only explicit user-approved one-off downgrade is allowed.
- The cockpit is execution-time only; canonical outputs remain BuddySwitch task/artifact/run objects.

## Verification
- Confirm this is launch preparation, not product shipping.
- Confirm this is not growth automation.
- Confirm the launch assets, instrumentation, and feedback loop are realistic for the current stage and selected channel.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.
- Emit buddy-level result JSON directly from this native skill and persist it with `persist --skill-id <native skill id>` using the same native `skill_id`.

## Required Output Fields

Top-level envelope keys:

- `execution_summary`
- `working_notes`
- `deliverables_or_changed_files`
- `artifact_content`

Buddy-specific fields inside `artifact_content`:

- `research_question`
- `evidence`
- `insights`
- `assumptions`
- `risks`
- `conclusion`
- `recommended_next_step`
- `specialized_sections`

Use `specialized_sections` for skill-specific detail (for example interview guides, channel scoring tables, launch asset plans, or source traceability maps).

## Guardrails

- This is launch preparation, not product shipping.
- This is not growth automation.
- For critical analytics/admin sources, require mandatory takeover before continuing past login gates.
- Do not silently downgrade to low-density public alternatives; record explicit evidence downgrade only for user-approved one-off downgrade.
- Do not use silent search API/snippet/crawler fallback.
- Do not imply operational readiness that the current evidence does not support.

## Examples
- `Prepare a first validation launch for an AI assistant landing page`
- `Build the launch-prep brief for a founder-led beta announcement`
- `Define feedback collection and instrumentation for a niche workflow launch`

## Counterexamples
- `Ship the beta announcement flow in projects/app`
- `Choose the first acquisition channel for the workflow launch`
- `Automate the full growth funnel after launch`

## Gotchas
- A strong launch-prep brief should make the feedback loop explicit before public release.
- Launch readiness at this stage is about learning quality, not polished scale.
