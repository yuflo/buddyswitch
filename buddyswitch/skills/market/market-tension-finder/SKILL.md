---
name: market-tension-finder
description: Use when you need to extract contradictions between stated needs, observed behavior, and market narratives to expose real GTM tension.
---

# market-tension-finder

## Purpose
- Find contradictions that reveal real pain or adoption friction.
- Convert conflicting evidence into a concrete validation probe.

## Use When
- Users say one thing but observed behavior shows something else.
- Vendor claims conflict with reviews or category signals.
- Interest looks high but adoption or usage looks weak.

## Do Not Use When
- The task only needs a neutral evidence summary with no contradiction analysis.
- You already chose the core bottleneck and only need an experiment write-up.

## Inputs
- Reviews, user complaints, adoption notes, pricing pages, competitor copy, market metrics, and interview summaries.

## Execution Order
1. Before forming external market claims, use `chrome-devtools-cockpit` to open, list, select, and inspect browser pages. Use `search__open_browser` only as a query-to-URL wrapper when the task specifically starts from a search query.
2. Read upstream artifacts and source evidence before framing the contradiction.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when browser-native evidence is required.
5. Use runtime discovery for exact payload semantics before durable writes.

## Workflow
1. Compare stated needs with observed behavior.
2. Look for contradiction across complaints and continued usage, vendor claims and user reviews, category growth and buyer confusion, or high interest and low adoption.
3. Explain why the contradiction matters, what it may imply, and what other explanation could still be true.
4. Add expansion queries and one validation probe.
5. Mark the confidence as spark, pattern, or commitment.

## Artifact
- `template`: `brief`
- Required body sections:
  - Micro Signal
  - Why It Is Interesting
  - Possible Hidden Demand
  - Alternative Explanations
  - Expansion Queries
  - Validation Probe
  - Confidence
  - Stated Need
  - Observed Behavior
  - Contradiction
  - Market Implication
- Use one of: spark, pattern, commitment.

## Verification
- Confirm the tension includes stated evidence, observed behavior, contradiction, and market implication.
- Confirm buyer confusion, continued usage, or similar conflicting behavior is grounded in source evidence.
- Confirm the artifact ends in a validation probe rather than a sweeping conclusion.

## Shared Runtime Rules
- Runtime execution uses native BuddySwitch env MCP tools through env.tool; use runtime discovery when exact schemas matter.
- Use runtime discovery when exact payload semantics matter.
- Durable market deliverables use `artifact.create_revision` with `template: brief`.
- Market artifact commits require broker-issued `tool_evidence`; do not invent token strings.
- No silent downgrade is allowed from required browser-native evidence.

## Guardrails
- Do not invent evidence or contradiction where none exists.
- Do not generalize one anecdote into broad demand.
- Do not treat likes, upvotes, or generic praise as commitment.
- Do not hide uncertainty.
- Do not turn hunches into facts.
- Always propose the next validation probe.
