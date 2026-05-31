---
name: channel-strategy-mapper
description: Use when you need to compare acquisition or distribution channels by ICP fit, intent fit, reachability, and speed to learning.
---

# channel-strategy-mapper

## Purpose
- Compare channels with an early-stage learning lens.
- Filter out channels that look broad but are not reachable or learnable now.

## Use When
- You have an ICP and bottleneck but not a believable channel choice.
- You need to compare channels using evidence rather than generic advice.
- The task needs one viable near-term path, not a full media mix.

## Do Not Use When
- The ICP is still undefined.
- The task only asks for message framing or source selection.

## Inputs
- Segment map, ICP score, bottleneck diagnosis, founder constraints, and market evidence.

## Execution Order
1. Before forming external market claims, use native `search__open_browser` with a focused query, then continue discovery in `chrome-devtools-cockpit` and keep the workflow browser-native.
2. Read upstream artifacts and source evidence before rating channels.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when browser-native evidence is required.
5. Use runtime discovery for exact payload semantics before durable writes.

## Workflow
1. Compare candidate channels on icp fit, intent fit, reachability, CAC plausibility, payback plausibility, founder access, and speed to learning.
2. Note credibility and signal quality so vanity channels do not win by default.
3. Pick the best near-term option and one backup path.
4. State what channel evidence is still missing.

## Artifact
- `template`: `brief`
- Required body sections:
  - Candidate Channels
  - ICP Fit
  - Intent Fit
  - Reachability
  - CAC Plausibility
  - Payback Plausibility
  - Founder Access
  - Speed To Learning
  - Credibility
  - Signal Quality
  - Recommended Channel
  - Backup Channel

## Verification
- Confirm icp fit, intent fit, reachability, cac plausibility, payback plausibility, founder access, and speed to learning are all evaluated.
- Confirm the recommendation is tied to learning value, not just theoretical scale.
- Confirm the artifact rejects channels that depend on paid scale from day one or vanity metrics without signal quality.

## Shared Runtime Rules
- Runtime execution uses native BuddySwitch env MCP tools through env.tool; use runtime discovery when exact schemas matter.
- Use runtime discovery when exact payload semantics matter.
- Durable market deliverables use `artifact.create_revision` with `template: brief`.
- Market artifact commits require broker-issued `tool_evidence`; do not invent token strings.
- No silent downgrade is allowed from required browser-native evidence.

## Guardrails
- Do not invent evidence or pretend channel economics are known if they are not.
- Do not recommend a channel because it sounds common.
- Do not hide weak reachability behind generic optimism.
- Do not output a multi-channel spread with no learning priority.
