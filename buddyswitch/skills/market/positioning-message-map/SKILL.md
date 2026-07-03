---
name: positioning-message-map
description: Use when you need to convert market evidence into a who, alternative, value, proof, and message hierarchy for one focused GTM story.
---

# positioning-message-map

## Purpose
- Convert evidence into one believable positioning frame.
- Keep copy recommendations tied to actual pain, alternatives, and proof.

## Use When
- You have enough evidence to frame the audience and the alternative.
- The task needs message hierarchy or a testable angle for one segment.
- You need messaging that stays inside the evidence boundary.

## Do Not Use When
- The task still needs first-pass market research or source selection.
- The task is really asking for a multi-channel launch plan.

## Inputs
- Customer voice artifact, segment map, ICP scoring, competitor notes, and supporting source rows.

## Execution Order
1. Before forming external market claims, use `chrome-devtools-cockpit` to open, list, select, and inspect browser pages. Use `chrome-devtools-cockpit.search_page` for browser-native search page opening when starting from a query, then continue with cockpit evidence. Use `search__request` only for URL planning without opening and `search__status` for capability status.
2. Read upstream artifacts and source evidence before writing claims.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when browser-native evidence is required.
5. Use runtime discovery for exact payload semantics before durable writes.

## Workflow
1. Define who the message is for.
2. Name the current alternative or status quo.
3. State the differentiated value in plain language.
4. Add proof that is grounded in evidence, not invented traction.
5. Build a message hierarchy and one testable angle.

## Artifact
- `template`: `brief`
- Required body sections:
  - Who
  - Alternative
  - Differentiated Value
  - Proof
  - Message Hierarchy
  - Testable Angle
  - Claim Risks

## Verification
- Confirm who, alternative, differentiated value, proof, message hierarchy, and testable angle are all present.
- Confirm proof is evidence-backed and not invented.
- Confirm the message does not sound broader than the evidence supports.

## Shared Runtime Rules
- Runtime execution uses native BuddySwitch env MCP tools through env.tool; use runtime discovery when exact schemas matter.
- Use runtime discovery when exact payload semantics matter.
- Durable market deliverables use `artifact.create_revision` with `template: brief`.
- Market artifact commits require broker-issued `tool_evidence`; do not invent token strings.
- No silent downgrade is allowed from required browser-native evidence.

## Guardrails
- Do not invent evidence, traction, or certainty.
- Do not list features instead of differentiated value.
- Do not write proof claims that cannot be traced to source evidence.
- Do not mix visual design direction into the message map.
