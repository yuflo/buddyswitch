---
name: growth-bottleneck-diagnoser
description: Use when you need to name one current growth bottleneck from evidence instead of drifting into a broad marketing plan.
---

# growth-bottleneck-diagnoser

## Purpose
- Force one bottleneck choice instead of a diffuse GTM wishlist.
- Tie the bottleneck to evidence, not instinct alone.

## Use When
- Multiple growth problems are plausible and prioritization is unclear.
- You need one current growth bottleneck before choosing a channel or experiment.
- The team keeps expanding scope into a broad marketing plan.

## Do Not Use When
- The task only asks for neutral evidence synthesis.
- The task already has a validated bottleneck and only needs a copy pass.

## Inputs
- Segment map, ICP score, voice-of-customer notes, channel evidence, and current funnel observations.

## Execution Order
1. Before forming external market claims, use `chrome-devtools-cockpit` to open, list, select, and inspect browser pages. Use `chrome-devtools-cockpit.search_page` for browser-native search page opening when starting from a query, then continue with cockpit evidence. Use `search__request` only for URL planning without opening and `search__status` for capability status.
2. Read upstream artifacts and source evidence before naming the bottleneck.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when browser-native evidence is required.
5. Use runtime discovery for exact payload semantics before durable writes.

## Workflow
1. List the most plausible constraints across awareness, trust, activation, conversion, and retention.
2. Choose one current growth bottleneck with the strongest evidence and the clearest learning value.
3. Explain why the other candidates are secondary right now.
4. Define what evidence would disconfirm the chosen bottleneck.

## Artifact
- `template`: `brief`
- Required body sections:
  - Candidate Bottlenecks
  - One Current Growth Bottleneck
  - Evidence For
  - Evidence Against
  - Why Not The Others
  - What Would Disconfirm It
  - Next Move

## Verification
- Confirm the artifact names one current growth bottleneck.
- Confirm it explicitly rejects drifting into a broad marketing plan.
- Confirm the bottleneck is evidence-backed and falsifiable.

## Shared Runtime Rules
- Runtime execution uses native BuddySwitch env MCP tools through env.tool; use runtime discovery when exact schemas matter.
- Use runtime discovery when exact payload semantics matter.
- Durable market deliverables use `artifact.create_revision` with `template: brief`.
- Market artifact commits require broker-issued `tool_evidence`; do not invent token strings.
- No silent downgrade is allowed from required browser-native evidence.

## Guardrails
- Do not invent evidence or certainty.
- Do not output a broad marketing plan when the task is bottleneck selection.
- Do not list five equal priorities.
- Do not confuse noisy top-of-funnel chatter with the true bottleneck without proof.
