---
name: weak-signal-scout
description: Use when you need to capture small strange clues, language anomalies, or early demand hints before they are strong enough to look like a market pattern.
---

# weak-signal-scout

## Purpose
- Teach Market Role to notice subtle clues instead of only summarizing obvious trends.
- Preserve uncertainty while still proposing the next validation move.

## Use When
- The market looks noisy, early, fragmented, or weird.
- You are seeing repeated small clues but not enough for a strong claim.
- The task needs hidden-demand hypotheses rather than a polished market verdict.

## Do Not Use When
- You already have clear multi-source demand proof and need channel or experiment choice.
- The task is purely about structured competitor comparison.

## Inputs
- Community threads, reviews, notes, screenshots, small objections, workaround mentions, and edge-user complaints.

## Execution Order
1. Before forming external market claims, use `chrome-devtools-cockpit` to open, list, select, and inspect browser pages. Use `search__open_browser` only as a query-to-URL wrapper when the task specifically starts from a search query.
2. Read upstream artifacts and source evidence before naming the signal.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when browser-native evidence is required.
5. Use runtime discovery for exact payload semantics before durable writes.

## Workflow
1. Capture the small clue exactly as seen.
2. Explain why it is interesting without overstating certainty.
3. Offer one possible hidden demand and at least one alternative explanation.
4. Add expansion queries that could turn a spark into a pattern.
5. End with one validation probe and a confidence label.

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
- Use one of: spark, pattern, commitment.

## Verification
- Confirm the signal is traceable to a source row and not paraphrased into a fake quote.
- Confirm uncertainty stays visible.
- Confirm the artifact proposes a next validation probe.

## Shared Runtime Rules
- Runtime execution uses native BuddySwitch env MCP tools through env.tool; use runtime discovery when exact schemas matter.
- Use runtime discovery when exact payload semantics matter.
- Durable market deliverables use `artifact.create_revision` with `template: brief`.
- Market artifact commits require broker-issued `tool_evidence`; do not invent token strings.
- No silent downgrade is allowed from required browser-native evidence.

## Guardrails
- Do not invent evidence or unsupported patterns.
- Do not generalize one anecdote into broad demand.
- Do not treat likes, upvotes, or generic praise as commitment.
- Do not hide uncertainty.
- Do not turn hunches into facts.
- Always propose the next validation probe.
