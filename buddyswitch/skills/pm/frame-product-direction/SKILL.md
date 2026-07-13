---
name: frame-product-direction
description: Use when PM must define audience, problem, value, evidence, constraints, and non-goals for a product bet.
---

# Frame Product Direction

## Purpose
- Create product direction that design, dev, and test can use without re-deciding product intent.
- Make evidence strength and assumptions explicit before scope is cut.

## Use when
- A user goal is broad, ambiguous, or missing audience/problem/value clarity.
- Downstream work needs product direction before scope, requirements, or criteria.

## Do not use when
- The direction is already durable and the task is only to write requirements or decide from proof.
- The main work is copywriting, visual craft, implementation, or test execution.

## Inputs
- User goal, market evidence, current product constraints, previous decisions, risks, track state, and artifact bodies.
- Runtime contract references: `context.get.tool_catalog`, `"$BUDDYSWITCH_PYTHON" scripts/turn_runtime.py status`, and runtime response fields.

## Steps
1. State audience and usage context, problem, value, evidence strength, constraints, non-goals, and open product questions.
2. Label unsupported claims as assumptions and keep them separate from evidence.
3. Identify which direction choices affect scope, requirements, criteria, or owner sequencing.
4. If the direction should guide others, create an artifact through `artifact.create_revision` and publish with `track.add_material`.

## Outputs
- Product direction brief or section with audience, problem, value, evidence, constraints, non-goals, and open questions.

## Quality Bar
- Downstream owners can act without inventing product intent.
- Unsupported claims are visible assumptions, not hidden decisions.

## Runtime Boundary
- Use env tools for durable state.
- Read exact payload and response fields from runtime discovery, not this skill.
- Do not edit projected runtime storage directly.
- Use `track.open` before changing shared track state and `artifact.get` for referenced artifact bodies.

## Examples
- Input: "Improve onboarding for teams." Output: target user/context, current pain, value promise, constraints, non-goals, and unknowns that affect scope.

## Counterexamples
- Writing interface modules before audience, problem, value, and constraints are clear.
- Treating a product bet as proven without evidence.
