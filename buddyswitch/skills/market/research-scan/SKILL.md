# research-scan

## Execution Order
1. Before any market research, run discovery in the visible `chrome-devtools-cockpit` browser and keep the workflow `browser-native`.
2. Read all selected upstream inputs before forming new market claims.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when the skill contract requires browser-native work.
5. Only after the steps above should you synthesize findings into the structured result.

## Purpose
- Produce evidence-backed market research with explicit source traceability and a clear synthesis of patterns, risks, and conclusions.

## Use when
- The task is about market demand, competitor behavior, user sentiment, category analysis, or source-backed external research.
- The user wants browsing, evidence capture, and a research artifact as the main deliverable.
- The prompt references demand, trends, competitors, audience behavior, or validating a market hypothesis.

## Do Not Use When
- The main outcome should be a PRD, design spec, implementation change, or smoke-test report.
- The task is asking for unverified opinion or product strategy without research.
- The user has already supplied enough evidence and is really asking PM to scope a solution.
- The task is asking for PMF judgment on whether a specific product idea is worth pursuing; use `pmf-recon`.
- The task is asking for interview planning or structured customer-discovery output.
- The task is asking for positioning writing or founder-facing copy.
- The task is asking for first-channel choice or experiment selection.
- The task is asking for launch preparation or validation-page planning.

## Inputs
- Research question or hypothesis.
- Target market and user context.
- Provided links, prior artifacts, or required channels.
- Optional track context or summary hint.

## Outputs
- A research artifact object with evidence, source traceability, patterns, caveats, and conclusion.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.
- Explicit notes when login, paywall, or anti-bot constraints degrade evidence quality.

## Research Defaults

- Collection mode: `browser-native` in-browser search followed by real result-page traversal (details/comments/related pages when relevant).
- Unless user explicitly excludes them, include both:
  - `x.com`
  - `reddit`
- Cross-check social channels with official and general web sources.
- Do not treat search snippets as final evidence; validate via page-level browsing.

## Complexity Tiers

- `quick` (2 rounds): narrow question, known category, low ambiguity.
- `standard` (4 rounds): moderate ambiguity or multiple segments.
- `deep` (6 rounds): broad market question, high uncertainty, conflicting signals.

Choose tier at run start and record rationale in `research_strategy`.

## Iterative Workflow

For each round, run this fixed loop:
1. query planning
2. candidate discovery
3. browser evidence capture
4. round synthesis
5. query refinement for next round

## Access And Blocking Rules

- Mandatory takeover:
  - if a critical source needs login, require mandatory takeover in the shared headed cockpit
  - continue only after takeover is completed in-session
- No silent degrade:
  - if blocked by paywall/rate-limit/region/anti-bot, record the blockage and impact
  - do not silently downgrade to low-density public alternatives
  - no silent search API/snippet/crawler fallback
  - request takeover or explicit user-approved one-off downgrade, then mark evidence quality downgrade in `risks_and_caveats`

## Market Research Cockpit Runtime

- This skill follows `framework/docs/browser-cockpit.md`.
- It uses `chrome-devtools-cockpit` as the browser executor.
- It runs in a shared headed cockpit (`browser_mode=headed-only`) with profile `shared-browser`.
- Discovery mode is `browser-native`: search in the browser and continue into real result pages, details, comments, and related pages where relevant.
- Critical-source login is mandatory takeover, and fallback policy is no silent degrade.
- Do not use silent search API/snippet/crawler fallback.
- If browser-native access is genuinely blocked, only explicit user-approved one-off downgrade is allowed.
- The cockpit is execution-time only; canonical outputs remain BuddySwitch task/artifact/run objects.

## Steps

1. Restate research objective, scope, and complexity tier.
2. Build initial channel/query plan with mandatory channels.
3. Run iterative rounds according to selected tier.
4. Capture evidence with explicit source metadata.
5. Map key claims and conclusions to source IDs.
6. Write the final report using the research template.

## Verification
- Confirm every material conclusion can be traced back to captured evidence.
- Confirm blocking conditions and evidence quality downgrades are documented.
- Confirm the report separates observed evidence from inference.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.

## Required Output Fields

- `research_question`
- `research_strategy`
- `channel_plan`
- `iteration_log`
- `evidence`
- `source_traceability`
- `patterns_and_insights`
- `risks_and_caveats`
- `conclusion`

## Guardrails

- Do not write PRD content.
- Do not propose implementation details as if they were validated evidence.
- Do not invent evidence.
- Do not skip required channels unless user explicitly excludes them.
- For critical sources, require mandatory takeover before continuing past login gates.
- Do not silently downgrade to low-density public alternatives; record explicit evidence downgrade only for user-approved one-off downgrade.
- Do not use silent search API/snippet/crawler fallback.

## Examples
- `switch market: Research demand for AI companion live spaces`
- `switch market: Compare creator monetization products and capture evidence`
- `switch market: Validate whether playlist collaboration is becoming a standard expectation`

## Counterexamples
- `switch pm: Write the MVP PRD for playlist collaboration`
- `switch dev: Implement playlist collaboration in projects/app`
- `switch test: Run smoke checks on the playlist collaboration release candidate`

## Gotchas
- Source snippets are not final evidence; browse and validate pages directly.
- Research wording often includes product ideas, but this skill should not turn them into requirements artifacts.
