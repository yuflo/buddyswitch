---
name: decide-from-proof
description: Use when PM must decide continue, revise, send back, stop, or blocked after test proof or validation evidence.
---

# Decide From Proof

## Purpose
- Close the post-proof loop with an evidence-based iteration decision.
- Convert proof into continue, revise, send back, stop, or blocked.

## Use when
- Test proof, validation evidence, or user evidence is available and PM must decide what happens next.
- Proof is partial, conflicting, or has unverified areas.

## Do not use when
- There is no proof or validation evidence to inspect.
- The task is to execute tests, fix code, or write new requirements from scratch.

## Inputs
- Test proof, validation evidence, acceptance criteria, dev report, current track state, artifact bodies, and known risks.
- Runtime contract references: `context.get.tool_catalog`, `"$BUDDYSWITCH_PYTHON" scripts/turn_runtime.py status`, and runtime response fields.

## Steps
1. Read proof body with `artifact.get` and current shared state with `track.open`.
2. Map proof result to acceptance criteria and separate pass, fail, blocked, and unverified areas.
3. Choose continue, revise, send back, stop, or blocked; record evidence and residual risk.
4. Create/update owner follow-up if needed, or publish the iteration decision through `artifact.create_revision` and `track.add_proof`.

## Outputs
- Iteration decision, track update, proof publication, or owner-specific task.

## Quality Bar
- Decision follows evidence rather than optimism or process momentum.
- Partial pass with meaningful unverified areas is not treated as full readiness.

## Runtime Boundary
- Use env tools for durable state.
- Read exact payload and response fields from runtime discovery, not this skill.
- Do not edit projected runtime storage directly.
- Use runtime response fields to confirm whether durable state changed.

## Examples
- Input: desktop passes, mobile fails with repro steps, and one area is unverified. Output: revise or send back decision with evidence, residual risk, and owner action.

## Counterexamples
- Continuing after a failed proof without naming the failed criterion.
- Treating blocked proof as product readiness.
