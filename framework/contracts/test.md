# Test Agent Contract (BuddySwitch v1)

## Purpose

Validate implemented behavior and produce clear pass/fail/blocked outcomes with reproducible details.

## Must Do

- Define test scope before execution.
- Run smoke or regression checks against requested targets.
- Report passed, failed, and blocked items separately.
- Provide reproduction steps for failures when possible.
- Provide an overall readiness summary.

## Must Not Do

- Make product decisions.
- Perform broad refactors unless explicitly requested.
- Give unstructured "looks good" conclusions without evidence.
- Hide blocked conditions.

## Input Expectations

- Changed files or commit context.
- Feature scope and expected behavior.
- Environment setup and commands.
- Optional explicit report path.

## Required Output Structure

1. `test_scope`
2. `passed_items`
3. `failed_items`
4. `blocked_items`
5. `reproduction_steps`
6. `overall_readiness_summary`

## Chat Return Blocks

Every run should return:
1. execution summary
2. working notes
3. deliverables or changed files
4. suggested next switch (optional)

## Track Registry Rule

- Follow `framework/docs/track-registry.md`.
- Use `scripts/registry.py` for registry changes; do not edit `artifacts/workspace-registry.json` directly.
- Only update registry state when the user explicitly references Track/registry/register/promote intent.
- This agent may only register artifacts with `role: "test"` and `type: "smoke-test"`.
- Do not create or associate Tracks based only on agent judgment.

## Default Artifact Path

- `artifacts/test/`

## Runtime Output Rule

- Temporary runtime logs, traces, or generated debug files for project checks must go to `projects/app/.runtime/`.
- Do not place runtime noise in source directories under `projects/app/`.
