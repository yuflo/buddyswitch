---
name: channel-discovery
description: Use when the task is choosing the first believable user-acquisition channel or planning a small-channel experiment for an early product.
---

# channel-discovery

## Execution Order
1. Before any market research, run discovery in the visible `chrome-devtools-cockpit` browser and keep the workflow `browser-native`.
2. Read all selected upstream inputs before forming new market claims.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when the skill contract requires browser-native work.
5. Only after the steps above should you synthesize findings into the structured result.

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
- A contribution to the current compact buddy-run commit.
- Durable channel discovery content is written before persist through `artifact-tool` `artifact.create_revision`.
- The final run commit references already-written artifacts with optional `artifact_ids` metadata.

## Market Research Cockpit Runtime

- This skill follows `framework/docs/browser-cockpit.md`.
- It uses `chrome-devtools-cockpit` as the browser executor.
- It runs in an instance headed cockpit (`browser_mode=headed-only`) with profile `instance-browser`.
- Discovery mode is `browser-native`: search in the browser and continue into real result pages, details, comments, and related pages where relevant.
- Critical-source login is mandatory takeover, and fallback policy is no silent degrade.
- Do not silently downgrade to low-density public alternatives when critical channel evidence is blocked.
- Do not use silent search API/snippet/crawler fallback.
- If browser-native access is genuinely blocked, only explicit user-approved one-off downgrade is allowed.
- The cockpit is execution-time only; canonical outputs remain BuddySwitch task/artifact/run objects.

## Verification
- Confirm candidate channels are compared against explicit selection criteria.
- Confirm the recommended primary and secondary channels are believable for the current product and audience maturity.
- Confirm the experiment plan is small, testable, and paired with kill signals rather than vague growth aspirations.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.
- This native skill contributes content to the current buddy run.
- Do not call persist from the skill perspective.
- The locked buddy session persists one buddy run commit after all needed native skill work is integrated.

## BuddySwitch Commit Output

Contribute to one buddy-run commit. Do not call persist from inside the skill.

Required top-level field:
- `execution_summary`

Use `artifact-tool` before persist when this skill produces a durable artifact:
- `kind`: `channel-plan`
- `title`: concise artifact title
- `summary`: short downstream selection summary
- `content`: include `research_question`, `evidence`, `insights`, `assumptions`, `risks`, `conclusion`, `recommended_next_step`, and channel-specific structured detail

After `artifact.create_revision` returns `ok=true`, include the returned artifact id in optional `artifact_ids`.
Use optional `working_notes` for concise reasoning or verification notes.
Use optional `task_id` only as association metadata for an explicitly selected task.
Use optional `handoff` when another manifest buddy should continue.

Market artifact commits require broker-issued `tool_evidence` from the browser evidence gate. Do not invent token strings.

## Guardrails

- Prefer believable, reachable first channels over abstract "best practices."
- Keep the experiment narrow enough to learn quickly.
- For critical sources, require mandatory takeover before continuing past login gates.
- Do not silently downgrade to low-density public alternatives; record explicit evidence downgrade only for user-approved one-off downgrade.
- Do not use silent search API/snippet/crawler fallback.
- Do not turn channel choice into growth automation or a multi-quarter marketing plan.
- Do not invent channel reach, conversion assumptions, or distribution access.

## Examples
- `Choose the first channel to test an AI assistant for sales engineers`
- `Rank early acquisition channels for this founder-led workflow tool`
- `Plan a small experiment to test whether niche communities can drive first users`

## Counterexamples
- `Build the launch checklist for the first public release`
- `Write the homepage positioning for the workflow tool`
- `Research whether the workflow tool solves a meaningful pain point`

## Gotchas
- The easiest channel to name is often not the most believable first channel to execute.
- A good channel plan should make it obvious what to stop doing if the experiment fails.
