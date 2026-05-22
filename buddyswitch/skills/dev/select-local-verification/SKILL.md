---
name: select-local-verification
description: Use when Dev needs to choose focused local proof for changed source behavior.
---

# Select Local Verification

## Purpose
- Choose the shortest meaningful verification that matches the change risk.

## Use when
- Source was changed.
- Verification planning is required before final report/review.

## Do not use when
- No code behavior changed and no verification expectation exists.

## Inputs
- Changed files and behavior intent.
- Local project scripts/configs (tests/lint/typecheck/build).
- Runtime contract references: `context.get.tool_catalog`, `python3 scripts/turn_runtime.py status`.

## Steps
1. Inspect project hints (`package.json`, test configs, makefiles, CI scripts).
2. Pick focused checks first.
3. Run selected checks.
4. If no project test command is discoverable, record that explicitly and pick nearest safe proof.
5. Escalate to broader checks only when blast radius requires it.

## Outputs
- Verification command set with pass/fail/blocked evidence.

## Guardrails
- Do not claim pass from stale output.
- Do not skip verification when cheap local proof exists.
- Distinguish fake topology checks from real permission/sandbox proof.

## Stop Conditions
- Verification blocked by missing dependency/tooling/environment; record exact blocker.

## Examples
- Component change -> focused component test plus build check.

## Counterexamples
- "Not tested" without checking available scripts or local commands.
