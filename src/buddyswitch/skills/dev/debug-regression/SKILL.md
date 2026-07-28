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
- Runtime contract references: `context.get.tool_catalog`, `"$BUDDYSWITCH_PYTHON" -m buddyswitch.application.entrypoints.diagnostics status`.

## Steps
1. Reproduce the failure first, or document exactly why reproduction is blocked.
2. Read the error output and logs before proposing a fix.
3. Trace the bad state through code and data flow, then compare it with a working example or reference path.
4. Form a single hypothesis, change one variable, and make one change for that hypothesis.
5. Add a focused regression test before the fix whenever feasible.
6. Patch the minimal root cause, then re-run focused verification and record residual risk.
7. If three fix attempts fail or each patch reveals a new unrelated break, stop and question the approach or architecture before another patch.

## Outputs
- Root-cause fix with regression evidence or explicit limitation.

## Guardrails
- Reproduce before patch unless it is an obvious typo/import with direct proof.
- Do not add broad fallback branches that hide failures.
- Do not swallow errors, add arbitrary sleeps, or stack compatibility branches to mask the root cause.
- Do not bundle unrelated refactors during bugfix.

## Verification
- Regression test or equivalent regression proof fails before fix and passes after fix when practical.
- Focused verification confirms behavior and no immediate side regressions.

## Examples
- Reproduce submit failure, identify state reset bug, add regression test, patch state handling.

## Counterexamples
- Add generic fallback return without explaining or reproducing original failure.
