---
name: read-product-context
description: Use when PM work depends on track, task, artifact, request, message, comment, or proof context that must be read before deciding.
---

# Read Product Context

## Purpose
- Turn durable collaboration state into a PM-readable context summary.
- Prevent product decisions from being made from stale chat memory.

## Use when
- A user asks PM to continue, recover, revise, or decide on work with existing ids.
- Track, task, artifact, request, message, comment, or proof context may change the next PM action.

## Do not use when
- The user only asks for a new product direction with no durable context to inspect.
- Another role owns the primary work and PM only needs to wait for an output.

## Inputs
- User request, track id, task id, artifact ids, request/comment/message ids, proof ids, and visible thread context.
- Full artifact bodies when artifact ids are available.
- Runtime contract references: `context.get.tool_catalog`, `python3 scripts/turn_runtime.py status`, and runtime response fields.

## Steps
1. Collect explicit ids and name any missing ids that would change the decision.
2. Read shared state with `track.open`; read full artifact and proof bodies with `artifact.get` when ids are present.
3. Separate facts, assumptions, decisions already made, blockers, missing inputs, and the next PM-owned move.
4. If durable output is needed, draft an artifact through `artifact.create_revision` and publish it with `track.add_material` or `track.add_proof` after the track state is understood.

## Outputs
- Context summary with facts, assumptions, decisions, blockers, missing inputs, and next action.
- Optional PM-owned follow-up request, task update, or product-readable artifact.

## Quality Bar
- Do not claim artifact content was read unless `artifact.get` returned the full body.
- The next owner can tell what is known, what is assumed, and what PM will do next.

## Runtime Boundary
- Use env tools for durable state.
- Read exact payload and response fields from runtime discovery, not this skill.
- Do not edit projected runtime storage directly.
- Use private workspace drafts only for PM working notes; use artifacts when content must be product-readable.

## Examples
- Input: "Continue track T with design artifact A and test proof P." Output: facts from `track.open`, full-body findings from A and P, current blockers, and one next PM action.

## Counterexamples
- Deciding from a chat summary while an artifact id is present.
- Creating a new brief before identifying current truth and missing inputs.
