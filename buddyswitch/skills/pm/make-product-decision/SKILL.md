---
name: make-product-decision
description: Use when PM must record a durable product decision, tradeoff, rejected alternative, or next owner action.
---

# Make Product Decision

## Purpose
- Make decisions inspectable, durable, and hard to relitigate accidentally.
- Tie each decision to evidence, tradeoff, residual risk, and next owner.

## Use when
- Competing options exist and PM must choose.
- A decision has been made in conversation but is not durable product truth.

## Do not use when
- PM only needs to read context or synthesize inputs before a choice is possible.
- The decision is owned by design, dev, test, market, or the user.

## Inputs
- Competing options, evidence, constraints, owner feedback, track state, prior decisions, and artifact bodies.
- Runtime contract references: `context.get.tool_catalog`, `python3 scripts/turn_runtime.py status`, and runtime response fields.

## Steps
1. State decision, evidence, tradeoff, rejected alternatives, residual risk, and next owner/action.
2. Make clear what changed and what should not be reopened without new evidence.
3. Choose whether the decision is current material or close proof at the business level.
4. Create a decision artifact with `artifact.create_revision` and publish via `track.add_material` or `track.add_proof`.

## Outputs
- Decision artifact or decision section with decision, evidence, tradeoff, rejected alternative, residual risk, and next owner.

## Quality Bar
- Downstream buddies know what changed and what not to relitigate.
- The decision can be found outside chat.

## Runtime Boundary
- Use env tools for durable state.
- Read exact payload and response fields from runtime discovery, not this skill.
- Do not edit projected runtime storage directly.
- Read `track.open` and referenced bodies with `artifact.get` before publishing a decision.

## Examples
- Input: ship a narrow feature this week or wait for a broader redesign. Output: chosen path, rejected path, evidence, risk, and next owner/action.

## Counterexamples
- Burying a decision in chat or a vague track update.
- Recording a choice without its rejected alternative.
