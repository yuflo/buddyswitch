---
name: parallelize-independent-dev-work
description: Use when Dev has two or more independent work slices that may be executed in parallel without shared-state risk.
---

# Parallelize Independent Dev Work

## Purpose
- Parallelize only genuinely independent work so speed does not create integration debt.

## Use when
- There are two or more independent problem domains with disjoint scope and explicit expected outputs.

## Do not use when
- The work shares files, shared state, or depends on one result landing before the next can start.

## Inputs
- Candidate work slices, expected outputs, write sets, dependencies, and verification paths.
- Runtime contract references: `context.get.tool_catalog`, `"$BUDDYSWITCH_PYTHON" scripts/turn_runtime.py status`.

## Steps
1. Confirm there is no shared state, no overlapping write set, and no sequential dependency between slices.
2. Split work into disjoint scope with explicit outputs and focused verification for each slice.
3. Keep urgent blockers on the critical path single-threaded; do not parallelize them.
4. Review and integrate all results before claiming completion.

## Outputs
- Parallel work plan with disjoint scope, outputs, verification, and integration notes.

## Guardrails
- Do not parallelize when slices touch the same contract, same files, or same decision.
- Do not parallelize unclear work just to keep people busy.
- Do not skip integration review because each slice passed alone.

## Verification
- The split shows independent scope, no overlapping write, and a review and integrate step.

## Examples
- Run one slice on backend validation and another on unrelated docs cleanup only after confirming no shared write paths.

## Counterexamples
- Split two changes that both edit the same parser and hope merge conflict resolution will sort it out.
