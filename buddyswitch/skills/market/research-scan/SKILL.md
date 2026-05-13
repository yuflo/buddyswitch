---
name: research-scan
description: Use when the task is building broad market reality, category structure, competitor coverage, or external context before narrower demand or launch analysis.
---

# research-scan

## Execution Order
1. Before any market research, call `python3 scripts/env/client.py search open-browser --query "<initial query>" --engine <google|reddit|x|web>`, then continue discovery in `chrome-devtools-cockpit` and keep the workflow `browser-native`.
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
- A contribution to the current compact buddy-run commit.
- Durable market scan content is written before persist through `artifact-tool` `artifact.create_revision`.
- The final run commit references already-written artifacts with optional `artifact_ids` metadata.

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
  - if a critical source needs login, require mandatory takeover in the instance headed cockpit
  - continue only after takeover is completed in-session
- No silent degrade:
  - if blocked by paywall/rate-limit/region/anti-bot, record the blockage and impact
  - do not silently downgrade to low-density public alternatives
  - no silent search API/snippet/crawler fallback
  - request takeover or explicit user-approved one-off downgrade, then mark evidence quality downgrade in `risks_and_caveats`

## Market Research Cockpit Runtime

- This skill follows `framework/docs/browser-cockpit.md`.
- It uses `chrome-devtools-cockpit` as the browser executor.
- It runs in an instance headed cockpit (`browser_mode=headed-only`) with profile `instance-browser`.
- Discovery starts with `search.open_browser` to open the browser-native entry page, then continues into real result pages, details, comments, and related pages where relevant via `chrome-devtools-cockpit`.
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
- This native skill contributes content to the current buddy run.
- Do not call persist from the skill perspective.
- The locked buddy session persists one buddy run commit after all needed native skill work is integrated.

## BuddySwitch Commit Output

Contribute to one buddy-run commit. Do not call persist from inside the skill.

Required top-level field:
- `execution_summary`

Use `artifact-tool` before persist when this skill produces a durable artifact:
- `kind`: `market-scan`
- `title`: concise artifact title
- `summary`: short downstream selection summary
- `content`: include `research_question`, `evidence`, `insights`, `assumptions`, `risks`, `conclusion`, `recommended_next_step`, and any skill-specific structured detail

After `artifact.create_revision` returns `ok=true`, include the returned artifact id in optional `artifact_ids`.
Use optional `working_notes` for concise reasoning or verification notes.
Use optional `task_id` only as association metadata for an explicitly selected task.
Use optional `handoff` when another manifest buddy should continue.

Market artifact commits require broker-issued `tool_evidence` from the browser evidence gate. Do not invent token strings.

## Guardrails

- Do not write PRD content.
- Do not propose implementation details as if they were validated evidence.
- Do not invent evidence.
- Do not skip required channels unless user explicitly excludes them.
- For critical sources, require mandatory takeover before continuing past login gates.
- Do not silently downgrade to low-density public alternatives; record explicit evidence downgrade only for user-approved one-off downgrade.
- Do not use silent search API/snippet/crawler fallback.

## Examples
- `Research demand for AI companion live spaces`
- `Compare creator monetization products and capture evidence`
- `Validate whether playlist collaboration is becoming a standard expectation`

## Counterexamples
- `Write the MVP PRD for playlist collaboration`
- `Implement playlist collaboration in projects/app`
- `Run smoke checks on the playlist collaboration release candidate`

## Gotchas
- Source snippets are not final evidence; browse and validate pages directly.
- Research wording often includes product ideas, but this skill should not turn them into requirements artifacts.
