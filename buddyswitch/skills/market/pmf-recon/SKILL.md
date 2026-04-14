# pmf-recon

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

- Collection mode: `browser-first + search-assist`.
- Start with user-language sources before polished market messaging.
- Prefer public sources first and log any access downgrade in the artifact.
- Read `references/source-map.md`, `references/evidence-rubric.md`, and `references/interview-prompts.md` as needed.

## Source Strategy

- Cover at least one user-language community source, one review/comparison source, and one official or competitor source when feasible.
- Begin with public communities and review sites that expose pain in the user's own words.
- Use `x.com` only when the category is fast-moving or the user explicitly wants it.

## Access And Blocking Rules

- If a valuable source requires login, stop and ask the user to log in before continuing.
- If blocked by paywall, rate-limit, region lock, or anti-bot controls, record the blockage, switch to public alternatives, and mark the evidence downgrade.

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
- Do not continue past login-required sources without user confirmation.

## Examples
- `switch market: Validate whether an AI note-taking tool for consultants has enough PMF signal to test`
- `switch market: Narrow the best ICP for a lightweight CRM aimed at solo founders`
- `switch market: Compare current alternatives and pain signals for a devtool onboarding assistant`

## Counterexamples
- `switch market: Research the creator analytics category broadly and summarize competitors`
- `switch pm: Draft the MVP PRD for a consultant note-taking tool`
- `switch dev: Implement the onboarding assistant in projects/app`

## Gotchas
- A PMF-shaped research request can still mention competitors, but the output should stay focused on pain, alternatives, and next validation action.
- Keep the final recommendation to one primary next move instead of a vague menu of options.
