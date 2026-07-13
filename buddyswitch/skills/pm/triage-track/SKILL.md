---
name: triage-track
description: Use when a PM-owned track is stale, cluttered, blocked, missing proof, or unclear about the latest product truth.
---

# Triage Track

## Purpose
- Recover track clarity without rewriting product artifacts unnecessarily.
- Identify current truth, obsolete material, blockers, missing proof, and next action.

## Use when
- A track is stale, cluttered, blocked, missing proof, or unclear about latest direction.
- The user asks PM to clean up or continue a confusing track.

## Do not use when
- The track is clear and PM only needs to author a specific product output.
- A lower-layer runtime response is unclear; use runtime discovery or stop for the tool defect.

## Inputs
- Track state, shared materials, close proof, updates, tasks, comments, current owner, and artifact bodies.
- Runtime contract references: `context.get.tool_catalog`, `"$BUDDYSWITCH_PYTHON" scripts/turn_runtime.py status`, and runtime response fields.

## Steps
1. Use `track.open` to identify current shared state, materials, proof, tasks, and updates.
2. Read relevant full bodies with `artifact.get`; do not infer content from summaries alone.
3. Name current truth, obsolete or superseded material, missing proof, blockers, next PM action, and owner follow-ups.
4. Make the fewest durable mutations needed: track now update, task change, or triage note via `artifact.create_revision` and `track.add_material`.

## Outputs
- Triage note, track now update, or task changes tied to the current outcome.

## Quality Bar
- Track becomes easier to act on with minimal durable mutations.
- PM does not create a new artifact just to hide stale state.

## Runtime Boundary
- Use env tools for durable state.
- Read exact payload and response fields from runtime discovery, not this skill.
- Do not edit projected runtime storage directly.
- Use runtime response fields to distinguish rejected calls from state changes.

## Examples
- Input: old materials, no current proof, stale task, unclear latest direction. Output: current truth, obsolete material, missing proof, blockers, and one next action.

## Counterexamples
- Creating a new PRD-style document to make clutter look clean.
- Updating track status before reading shared state.
