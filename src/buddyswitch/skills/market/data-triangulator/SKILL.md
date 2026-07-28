---
name: data-triangulator
description: Use when you need to combine multiple market sources into observed, inferred, and hypothesized claims with explicit confidence rules.
---

# data-triangulator

## Purpose
- Turn scattered market evidence into confidence-labeled conclusions.
- Prevent single-source narratives from being presented as settled truth.

## Use When
- You have evidence from several sources and need a synthesized claim map.
- A high-impact claim needs support from more than one source family.
- You need to label what is observed, inferred, and hypothesized.

## Do Not Use When
- The task is only to rate one source in isolation.
- The task is only to write launch messaging without evidence comparison.

## Inputs
- Source rows, extracted claims, quality ratings, and current hypotheses.

## Execution Order
1. Before forming external market claims, use `chrome-devtools-cockpit` to open, list, select, and inspect browser pages. Use `chrome-devtools-cockpit.search_page` for browser-native search page opening when starting from a query, then continue with cockpit evidence. Use `search__request` only for URL planning without opening and `search__status` for capability status.
2. Re-open the source pages behind each material claim.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when browser-native evidence is required.
5. Use runtime discovery for exact payload semantics before durable writes.

## Workflow
1. Split statements into observed, inferred, and hypothesized.
2. Map each statement to source family, recency, and evidence quality.
3. Require two independent source families before calling a claim high confidence.
4. Label any single-source conclusion as directional.
5. Block claims that collapse inference and observation into one sentence.

## Confidence Rules
- Observed: directly visible on the page or in the source row.
- Inferred: supported by multiple signals but not directly stated.
- Hypothesized: plausible explanation that still needs validation.
- High confidence needs two independent source families.
- Single-source conclusions stay directional.

## Artifact
- `template`: `brief`
- Required body sections:
  - Observed
  - Inferred
  - Hypothesized
  - Source Family Coverage
  - Directional Claims
  - High-Confidence Claims
  - Open Gaps

## Verification
- Confirm each high-confidence claim has support from two independent source families.
- Confirm observed, inferred, and hypothesized statements are separated.
- Confirm single-source conclusions are labeled directional.

## Shared Runtime Rules
- Runtime execution uses native BuddySwitch env MCP tools through env.tool; use runtime discovery when exact schemas matter.
- Use runtime discovery when exact payload semantics matter.
- Durable market deliverables use `artifact.create_revision` with `template: brief`.
- Market artifact commits require broker-issued `tool_evidence`; do not invent token strings.
- No silent downgrade is allowed from required browser-native evidence.

## Guardrails
- Do not invent consensus where only one source exists.
- Do not turn hypotheses into facts.
- Do not merge official claims and user complaints into one unqualified sentence.
- Do not skip contradictory evidence.
