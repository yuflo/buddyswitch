---
name: icp-scorer
description: Use when you need to score candidate ICPs with explicit fit factors, negative fit rules, score bands, and the next validation action.
---

# icp-scorer

## Purpose
- Compare candidate segments with a repeatable scoring frame.
- Keep positive fit, negative fit, and false-positive risk explicit.

## Use When
- You have more than one plausible segment and need to prioritize.
- You need a crisp ICP recommendation before positioning, channel, or experiment work.
- The task needs score bands and reasons, not just a qualitative preference.

## Do Not Use When
- You do not yet have any usable segment definitions.
- The task only asks for raw customer language extraction.

## Inputs
- Segment map, customer voice artifact, source rows, and current GTM constraints.

## Execution Order
1. Before forming external market claims, use `chrome-devtools-cockpit` to open, list, select, and inspect browser pages. Use `chrome-devtools-cockpit.search_page` for browser-native search page opening when starting from a query, then continue with cockpit evidence. Use `search__request` only for URL planning without opening and `search__status` for capability status.
2. Read upstream artifacts and source evidence before assigning scores.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when browser-native evidence is required.
5. Use runtime discovery for exact payload semantics before durable writes.

## Workflow
1. Score each segment on pain urgency, reachability, ability to pay, switching trigger, referenceability, and retention or expansion proxy.
2. Record positive fit, negative fit, false-positive risks, and evidence gaps.
3. Convert raw factor scores into score bands.
4. End with the next validation action for the best and riskiest segment.

## Score Bands
- High
- Medium
- Low

## Artifact
- `template`: `brief`
- Required body sections:
  - Candidate ICPs
  - Pain Urgency
  - Reachability
  - Ability To Pay
  - Switching Trigger
  - Referenceability
  - Retention Or Expansion Proxy
  - Positive Fit
  - Negative Fit
  - Score Bands
  - False-Positive Risks
  - Next Validation Action

## Verification
- Confirm pain urgency, reachability, ability to pay, switching trigger, referenceability, retention or expansion proxy, positive fit, negative fit, score bands, and next validation action all appear.
- Confirm negative fit and false-positive risks are explicit.
- Confirm the winning ICP still points to a concrete next validation action.

## Shared Runtime Rules
- Runtime execution uses native BuddySwitch env MCP tools through env.tool; use runtime discovery when exact schemas matter.
- Use runtime discovery when exact payload semantics matter.
- Durable market deliverables use `artifact.create_revision` with `template: brief`.
- Market artifact commits require broker-issued `tool_evidence`; do not invent token strings.
- No silent downgrade is allowed from required browser-native evidence.

## Guardrails
- Do not invent evidence or precision that the source set cannot support.
- Do not confuse reachability with demand.
- Do not ignore negative fit because one segment sounds exciting.
- Do not present score bands without a reason and a next validation action.
