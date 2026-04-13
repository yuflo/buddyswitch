# research-scan

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

- Collection mode: `browser-first + search-assist`.
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

- Login checkpoint:
  - if a key source needs login, pause and ask user confirmation with target URL and reason
  - continue only after user confirmation
- Blocking fallback:
  - if blocked by paywall/rate-limit/region/anti-bot, record the blockage
  - switch to public alternatives
  - mark evidence quality downgrade in `risks_and_caveats`

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

## Execution Summary Rule

- `execution_summary` persists as `artifact.summary`.
- Keep it selection-ready for downstream buddies:
  - artifact role
  - key resolved outcome
  - downstream relevance

## Track/Object Handling

- Follow `framework/docs/track-registry.md`.
- This buddy may read tracks and create/update artifact objects through the resolved task.
- Do not mutate track lifecycle fields directly.
- If output belongs to a track, rely on the explicit switch track target or existing task binding; artifacts do not store direct track references.

## Output Path

- Default BuddySwitch state: `buddyswitch/objects/tasks/<task-id>.json`, `buddyswitch/objects/artifacts/<artifact-id>.json`, and `buddyswitch/content/runs/<run-id>.json`
- Do not request or rely on `artifacts/*.md` or `runs/summaries/**`.

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
- Do not continue past login-required sources without user confirmation.

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
