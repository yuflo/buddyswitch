---
name: select-local-verification
description: Use when Dev needs to choose focused local proof for changed source behavior.
---

# Select Local Verification

## Purpose
- Choose the shortest meaningful verification that matches the change risk and acts as a fresh evidence gate.

## Use when
- Source was changed.
- Verification planning is required before final report/review.

## Do not use when
- No code behavior changed and no verification expectation exists.

## Inputs
- Changed files and behavior intent.
- Local project scripts/configs (tests/lint/typecheck/build).
- Runtime contract references: `context.get.tool_catalog`, `"$BUDDYSWITCH_PYTHON" scripts/turn_runtime.py status`.

## Steps
1. Inspect project hints (`package.json`, test configs, makefiles, CI scripts).
2. Pick the command that proves the intended claim so the command proves the outcome you want to report.
3. Run fresh focused verification first.
4. Read output and exit code before claiming pass, fixed, ready, or complete.
5. If no project test command is discoverable, record that explicitly and pick the nearest safe proof.
6. Escalate from focused checks to broader checks when blast radius requires it.

## Outputs
- Verification command set with pass/fail/blocked evidence.

## Guardrails
- No stale output: do not claim pass from old runs or memory.
- Do not predict success without running the command that proves it.
- Do not skip verification when cheap local proof exists.
- Distinguish fake topology checks from real permission/sandbox proof.

## Stop Conditions
- Verification blocked by missing dependency/tooling/environment; record the exact blocker instead of success language.

## Verification
- Fresh verification output and exit code support the claim before claiming completion.
- Broader checks match the blast radius of the change.

## Examples
- Component change -> run the focused component test fresh, read output and exit code, then add build coverage if blast radius is wider.

## Counterexamples
- "Not tested" without checking available scripts or local commands.
- "Looks fixed" based on stale output.
