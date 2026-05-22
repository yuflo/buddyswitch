---
name: debug-regression
description: Use when the task is a bug, failing check, or regression that needs root-cause fixes.
---

# Debug Regression

## Purpose
- Fix regressions from reproduction and root-cause evidence, not symptom masking.

## Use when
- A bug report, failing test, or unexpected behavior needs correction.

## Do not use when
- Work is straightforward feature implementation with no failure symptoms.

## Inputs
- Reproduction steps, failing output, and relevant code paths.
- Runtime contract references: `context.get.tool_catalog`, `python3 scripts/turn_runtime.py status`.

## Steps
1. Reproduce failure or document exactly why reproduction is blocked.
2. Identify root cause from logs/state/code path.
3. Add a focused regression test when practical.
4. Patch the minimal root cause.
5. Re-run focused verification and record residual risk.

## Outputs
- Root-cause fix with regression evidence or explicit limitation.

## Guardrails
- Reproduce before patch unless it is an obvious typo/import with direct proof.
- Do not add broad fallback branches that hide failures.
- Do not bundle unrelated refactors during bugfix.

## Verification
- Regression proof fails before fix and passes after fix when practical.
- Focused verification confirms behavior and no immediate side regressions.

## Examples
- Reproduce submit failure, identify state reset bug, add regression test, patch state handling.

## Counterexamples
- Add generic fallback return without explaining or reproducing original failure.
