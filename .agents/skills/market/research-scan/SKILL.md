---
name: research-scan
description: Run browser-first deep market research with iterative query refinement and strong source traceability.
---

# research-scan

## Agent

- `market`

## Contract And Template

- Contract: `framework/contracts/market.md`
- Template: `framework/templates/research-report.md`

## Inputs

- Research question or hypothesis.
- Target market and user context.
- Provided sources, links, or prior artifacts.
- Optional output file path.

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

## Output Path

- Default: `artifacts/research/<slug>.md`
- If user provides a path, use it as-is.

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
