---
name: write-acceptance-criteria
description: Use when PM must define verifiable pass/fail criteria for scoped product behavior.
---

# Write Acceptance Criteria

## Purpose
- Give test and dev observable proof targets.
- Convert requirements into pass, fail, or blocked evidence without PM interpretation.

## Use when
- Scoped behavior needs verification standards before build or proof review.
- Existing criteria are subjective, incomplete, or missing edge states.

## Do not use when
- Direction, scope, or requirements are not yet clear enough to verify.
- The task is to execute tests or inspect implementation details.

## Inputs
- Requirements, scope, known risks, affected flows, proof expectations, current track state, and artifact bodies.
- Runtime contract references: `context.get.tool_catalog`, `python3 scripts/turn_runtime.py status`, and runtime response fields.

## Steps
1. Map each critical behavior to concrete pass/fail checks and blocked conditions.
2. Include negative and edge states when they affect product risk.
3. Name unverified areas separately instead of treating them as pass.
4. Publish criteria through `artifact.create_revision` and `track.add_material`, or use `track.add_proof` when criteria are part of close proof.

## Outputs
- Acceptance criteria grouped by behavior or flow, with pass, fail, blocked, proof, and unverified areas.

## Quality Bar
- A tester can produce pass/fail/blocked proof from the criteria.
- Criteria do not rely on subjective visual-only judgment.

## Runtime Boundary
- Use env tools for durable state.
- Read exact payload and response fields from runtime discovery, not this skill.
- Do not edit projected runtime storage directly.
- Use `track.open` before shared mutations and `artifact.get` for referenced requirement bodies.

## Examples
- Input: a scoped onboarding requirement. Output: criteria for first-run path, returning-user state, error path, and unverified risk.

## Counterexamples
- "Looks premium" as acceptance criteria without observable evidence.
- Treating an untested flow as pass because the main path passed.
