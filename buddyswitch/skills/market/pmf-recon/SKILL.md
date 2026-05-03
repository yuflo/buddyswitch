---
name: pmf-recon
description: Use when the task is testing whether a product idea has credible demand, narrowing the sharpest ICP, or deciding whether the market is worth pursuing.
---

# pmf-recon

## Execution Order
1. Before any market research, run discovery in the visible `chrome-devtools-cockpit` browser and keep the workflow `browser-native`.
2. Read all selected upstream inputs before forming new market claims.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when the skill contract requires browser-native work.
5. Only after the steps above should you synthesize findings into the structured result.

## Purpose
- Produce evidence-backed PMF research that identifies the sharpest ICP, strongest pain signals, current alternatives, and the next validation move.

## Use when
- The task is about validating a startup or product idea, narrowing an ICP, comparing alternatives, or deciding whether a market is worth pursuing.
- The user wants PMF-oriented research rather than a broad category scan.
- The prompt references pain intensity, adoption likelihood, willingness to pay, wedge segments, or next-step validation tests.

## Do not use when
- The task is mainly a broad market/category scan without a concrete idea or user hypothesis; use `research-scan` instead.
- The main outcome should be a PRD, design spec, implementation change, or smoke-test report.
- The user wants unsupported opinion or product strategy without source-backed research.
- The task needs detailed interview-guide drafting beyond a PMF-oriented interview plan.
- The task needs homepage copy output, messaging frameworks, or positioning statements.
- The task needs first-channel selection or an acquisition experiment recommendation.
- The task needs launch execution prep, validation-page operations, or feedback-loop setup.

## Inputs
- Product idea in one or two sentences.
- Target user and workflow hypothesis.
- Optional alternatives, competitors, price band, geography, or channel constraints.
- Optional links, prior artifacts, or track context.

## Outputs
- A research artifact object with PMF evidence, ICP synthesis, alternatives analysis, confidence, and recommended next step.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.
- Explicit notes when login, paywall, or anti-bot constraints degrade evidence quality.

## Research Defaults

- Collection mode: `browser-native` in-browser search followed by real result-page traversal (details/comments/related pages when relevant).
- Start with user-language sources before polished market messaging.
- Prefer public sources first and log any access downgrade in the artifact.
- Read `references/source-map.md`, `references/evidence-rubric.md`, and `references/interview-prompts.md` as needed.

## Source Strategy

- Cover at least one user-language community source, one review/comparison source, and one official or competitor source when feasible.
- Begin with public communities and review sites that expose pain in the user's own words.
- Use `x.com` only when the category is fast-moving or the user explicitly wants it.

## Access And Blocking Rules

- If a critical source requires login, require mandatory takeover in the instance headed cockpit before continuing.
- If blocked by paywall, rate-limit, region lock, or anti-bot controls, record blockage and impact, do not silently downgrade to low-density public alternatives, do not use silent search API/snippet/crawler fallback, and request takeover or explicit user-approved one-off downgrade.
- Any approved downgrade path must be labeled as an evidence quality downgrade.

## Market Research Cockpit Runtime

- This skill follows `framework/docs/browser-cockpit.md`.
- It uses `chrome-devtools-cockpit` as the browser executor.
- It runs in an instance headed cockpit (`browser_mode=headed-only`) with profile `instance-browser`.
- Discovery mode is `browser-native`: search in the browser and continue into real result pages, details, comments, and related pages where relevant.
- Critical-source login is mandatory takeover, and fallback policy is no silent degrade.
- Do not use silent search API/snippet/crawler fallback.
- If browser-native access is genuinely blocked, only explicit user-approved one-off downgrade is allowed.
- The cockpit is execution-time only; canonical outputs remain BuddySwitch task/artifact/run objects.

## Steps

1. Restate the idea, user, workflow, and research depth.
2. Build the initial hypothesis frame and source plan.
3. Scan user-language communities for repeated pain and workarounds.
4. Scan review/comparison and official sources for alternative gaps and switching triggers.
5. Capture explicit evidence and trace it back to source IDs.
6. Synthesize the strongest ICPs, PMF confidence, and one next validation move.
7. Write the final report using the PMF report template.

## Verification
- Confirm every material conclusion can be traced back to captured evidence.
- Confirm the strongest ICP and pain signals are grounded in repeated or concrete evidence.
- Confirm the output separates observed evidence from inference and clearly labels assumptions.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.

## Required Output Fields

- `research_question`
- `research_strategy`
- `channel_plan`
- `iteration_log`
- `evidence`
- `source_traceability`
- `assumptions_used`
- `candidate_icps`
- `strongest_pain_signals`
- `existing_alternatives`
- `why_current_solutions_fall_short`
- `pmf_confidence`
- `recommended_next_step`
- `suggested_interview_angles`
- `risks_and_unknowns`
- `conclusion`

## Guardrails

- Do not write PRD content.
- Do not turn PMF research into implementation advice.
- Do not invent commitment signals, buyer intent, or willingness-to-pay evidence.
- For critical sources, require mandatory takeover before continuing past login gates.
- Do not silently downgrade to low-density public alternatives; record explicit evidence downgrade only for user-approved one-off downgrade.
- Do not use silent search API/snippet/crawler fallback.

## Examples
- `Validate whether an AI note-taking tool for consultants has enough PMF signal to test`
- `Narrow the best ICP for a lightweight CRM aimed at solo founders`
- `Compare current alternatives and pain signals for a devtool onboarding assistant`

## Counterexamples
- `Research the creator analytics category broadly and summarize competitors`
- `Draft the MVP PRD for a consultant note-taking tool`
- `Implement the onboarding assistant in projects/app`

## Gotchas
- A PMF-shaped research request can still mention competitors, but the output should stay focused on pain, alternatives, and next validation action.
- Keep the final recommendation to one primary next move instead of a vague menu of options.
