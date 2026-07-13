---
name: write-implementation-report
description: Use when Dev must publish a durable product-readable implementation result.
---

# Write Implementation Report

## Purpose
- Produce a clear implementation record for product/test/review consumers.

## Use when
- Source changes are ready to report.
- Durable result publication is requested or expected.

## Do not use when
- Implementation is still in progress and verification evidence is incomplete.

## Inputs
- Changed files under locked source root.
- Verification outputs (or blocked verification details).
- Relevant acceptance/design references.
- Runtime contract references: `context.get.tool_catalog`, `"$BUDDYSWITCH_PYTHON" scripts/turn_runtime.py status`.

## Steps
1. Summarize task and implemented behavior.
2. List changed files and why each changed.
3. Include verification commands and results; if blocked, include explicit verification blocked reason.
4. Record risks, unverified areas, and follow-ups.
5. Publish durable report through artifact/track routes when required.

## Outputs
- Product-readable report with changed files, evidence, risks, and follow-ups.

## Guardrails
- Do not write runtime report files into source folders.
- Do not omit known risks or blocked checks.
- Do not mark ready without verification evidence or explicit blocker.

## Verification
- Report contains changed files, command evidence, risks, and follow-ups.
- Durable artifact/track relation path is explicit when used.

## Examples
- Report references `src/App.tsx` behavior change and `src/App.test.tsx` proof.

## Counterexamples
- "Updated files and tests pass" with no file names, commands, or risk notes.
