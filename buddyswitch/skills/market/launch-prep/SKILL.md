---
name: launch-prep
description: Use when the task is preparing a first launch, validation page, or feedback loop before public release.
---

# launch-prep

## Execution Order
1. Before any market research, call `python3 scripts/env/client.py search open-browser --query "<initial query>" --engine <google|reddit|x|web>`, then continue discovery in `chrome-devtools-cockpit` and keep the workflow `browser-native`.
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
- Durable outputs are written explicitly through env tools.
- Durable launch prep content is written through `artifact-tool` `artifact.create_revision`.
- Reference written artifacts by explicit ids when relevant.

## Market Research Cockpit Runtime

- It uses `chrome-devtools-cockpit` as the browser executor.
- It runs in an instance headed cockpit (`browser_mode=headed-only`) with profile `instance-browser`.
- Discovery starts with `search.open_browser` to open the browser-native entry page, then continues into real result pages, details, comments, and related pages where relevant via `chrome-devtools-cockpit`.
- Critical-source login is mandatory takeover, and fallback policy is no silent degrade.
- Do not silently downgrade to low-density public alternatives when critical launch evidence is blocked.
- Do not use silent search API/snippet/crawler fallback.
- If browser-native access is genuinely blocked, only explicit user-approved one-off downgrade is allowed.
- The cockpit is execution-time only; canonical outputs remain BuddySwitch task or artifact objects; buddybox remains active-buddy private local workspace state.
- Market evidence is target-scoped to artifact ids; do not invent evidence tokens.

## Verification
- Confirm this is launch preparation, not product shipping.
- Confirm this is not growth automation.
- Confirm the launch assets, instrumentation, and feedback loop are realistic for the current stage and selected channel.

## Shared Runtime Rules

- Runtime execution uses env.tool through python3 scripts/env/client.py ... .
- Product-readable durable state is written explicitly as task or artifact objects.
- Use buddybox env tools with `logical_name` for active-buddy-private working files.
- Return after required explicit durable writes are complete.
- Do not rely on deprecated prepare/persist flows.

## BuddySwitch Commit Output

Write durable outputs explicitly via env tools. Do not rely on deprecated prepare/persist flows.

Required top-level field:
- `execution_summary`

Use `artifact-tool` when this skill produces a durable artifact:
- `template`: `brief`
- `title`: concise artifact title
- `summary`: short downstream selection summary
- `body`: include `research_question`, `evidence`, `insights`, `assumptions`, `risks`, `conclusion`, `recommended_next_step`, and launch-prep-specific structured detail as markdown

After `artifact.create_revision` returns `ok=true`, include the returned artifact id in optional `artifact_ids`.
Use optional `working_notes` for concise reasoning or verification notes.
Use optional `task_id` only as association metadata for an explicitly selected task.

Market artifact commits require broker-issued `tool_evidence` from the browser evidence gate. Do not invent token strings.

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
