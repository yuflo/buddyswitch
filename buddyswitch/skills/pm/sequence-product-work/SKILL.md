---
name: sequence-product-work
description: Use when PM must order product, market, design, dev, and test work for a scoped track.
---

# Sequence Product Work

## Purpose
- Turn product direction into an ordered collaboration path.
- Keep sequencing tied to the current track outcome rather than a process system.

## Use when
- Market, design, dev, test, and PM follow-up need ordering.
- A scoped track has dependencies, owner constraints, or proof needs that are unclear.

## Do not use when
- The task is to build a scheduler, workflow engine, or broad project-management layer.
- The next owner is already obvious and only needs a task update.

## Inputs
- Scope, requirements, known dependencies, owner constraints, risks, proof needs, current track state, and artifact bodies.
- Runtime contract references: `context.get.tool_catalog`, `python3 scripts/turn_runtime.py status`, and runtime response fields.

## Steps
1. Identify the blocking dependency and the smallest sequence that can move the track forward.
2. Order owners and define expected output, dependency, stop condition, and current next action for each step.
3. Keep the sequence short enough to validate; avoid adding a general process layer.
4. Publish the sequence with `artifact.create_revision` and `track.add_material`, or create owner-specific tasks when action is needed.

## Outputs
- Short sequence with owner, output, dependency, stop condition, and current next action.

## Quality Bar
- Every next owner can start without re-deciding PM scope.
- The sequence is accountable to product outcome, not process ceremony.

## Runtime Boundary
- Use env tools for durable state.
- Read exact payload and response fields from runtime discovery, not this skill.
- Do not edit projected runtime storage directly.
- Read `track.open` first when sequencing mutates shared track state, and use `artifact.get` for referenced source material.

## Examples
- Input: a scoped brief needs market follow-up, design shaping, dev build, and test proof. Output: ordered owner sequence with expected output, dependency, and stop condition.

## Counterexamples
- A broad project plan detached from current track outcome.
- Sequencing work before scope and requirements are settled.
