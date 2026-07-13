---
name: pressure-test-dev-skill
description: Use when Dev creates or changes a dev skill and needs proof that the guidance changes behavior, not just text.
---

# Pressure Test Dev Skill

## Purpose
- Prove a dev skill changes behavior under realistic pressure, not just in a static read-through.

## Use when
- A dev skill is new, modified, or under suspicion for weak behavior.

## Do not use when
- The work does not involve skill behavior.

## Inputs
- Skill goal, changed guidance, target behaviors, and available checks or scenarios.
- Runtime contract references: `context.get.tool_catalog`, `"$BUDDYSWITCH_PYTHON" scripts/turn_runtime.py status`.

## Steps
1. Define one or more pressure scenario prompts that expose the behavior the skill should change.
2. Capture the baseline behavior or baseline failure before accepting new guidance when feasible.
3. Add or update static tests as minimum proof.
4. Change the skill text.
5. Verify that the pressure scenario behavior actually changes after the edit.
6. Record what improved, what still fails, and whether more pressure scenarios are needed.

## Outputs
- Skill test record with pressure scenario, baseline, failure mode, behavior change, and static tests.

## Guardrails
- Static tests alone are minimum proof, not the whole answer for behavior risk.
- Do not accept a skill because the prose sounds good.
- Do not turn a not a one-off scenario into a story doc with no reusable test value.

## Verification
- Baseline and post-change results show whether the skill changes behavior.

## Examples
- Compare a pre-change and post-change dev prompt run to confirm the skill now asks for failing-test-first evidence.

## Counterexamples
- Edit a skill, run no scenario, and call it done because lint and file existence pass.
