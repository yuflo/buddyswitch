---
name: segment-map-builder
description: Use when you need to turn market evidence into narrow, operational segment definitions with clear role, context, trigger, workaround, and reachability fields.
---

# segment-map-builder

## Purpose
- Narrow broad audiences into reachable segments.
- Make segment definitions concrete enough for ICP, channel, and experiment work.

## Use When
- The market question still uses broad labels like marketers, developers, or operators.
- You need segment definitions that can be compared or scored.
- You need exclusions and reachability before channel choice.

## Do Not Use When
- You only need voice-of-customer extraction without segmentation.
- You already have a stable ICP and only need message hierarchy.

## Inputs
- Customer voice artifact, source rows, competitor evidence, and any existing hypotheses.

## Execution Order
1. Before forming external market claims, use native `search__open_browser` with a focused query, then continue discovery in `chrome-devtools-cockpit` and keep the workflow browser-native.
2. Read upstream artifacts and source evidence before naming a segment.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when browser-native evidence is required.
5. Use runtime discovery for exact payload semantics before durable writes.

## Workflow
1. Start from evidence, not broad identity labels.
2. Define each segment by role, business context, workflow context, trigger moment, current workaround, exclusions, and reachability.
3. Note where the same pain appears in multiple roles but with different economics or urgency.
4. Keep segment edges sharp enough that one channel or one experiment can target them.

## Artifact
- `template`: `brief`
- Required body sections:
  - Segment Name
  - Role
  - Business Context
  - Workflow Context
  - Trigger Moment
  - Current Workaround
  - Exclusions
  - Reachability
  - Evidence Notes

## Verification
- Confirm every segment includes role, business context, workflow context, trigger moment, current workaround, exclusions, and reachability.
- Confirm segment names are narrower than generic market labels.
- Confirm exclusions prevent the segment from collapsing back into a broad audience.

## Shared Runtime Rules
- Runtime execution uses native BuddySwitch env MCP tools through env.tool; use runtime discovery when exact schemas matter.
- Use runtime discovery when exact payload semantics matter.
- Durable market deliverables use `artifact.create_revision` with `template: brief`.
- Market artifact commits require broker-issued `tool_evidence`; do not invent token strings.
- No silent downgrade is allowed from required browser-native evidence.

## Guardrails
- Do not invent evidence or pretend the segment is validated if it is only hypothesized.
- Do not define segments so broadly that channel choice becomes generic.
- Do not skip exclusions.
- Do not collapse different workflow contexts into one segment without proof.
