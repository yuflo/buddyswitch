# smoke-test

name: smoke-test
description: Run focused smoke checks and produce structured pass/fail/blocked reports.

## Agent

- `test`

## Contract And Template

- Contract: `framework/contracts/test.md`
- Template: `framework/templates/test-report.md`

## Inputs

- Changed files, commit, or feature scope.
- Expected behavior.
- Environment setup and test commands.
- Optional report output path.

## Steps

1. Define smoke test scope from change context.
2. Run checks and capture results.
3. Classify outcomes into passed, failed, and blocked.
4. Add reproduction steps for failures when available.
5. Produce readiness summary.
6. Write the report using the test template.

## Output Path

- Default: `artifacts/test/<slug>.md`
- Project runtime-only temporary outputs: `projects/app/.runtime/`
- If user provides a path, use it as-is.

## Required Output Fields

- `test_scope`
- `passed_items`
- `failed_items`
- `blocked_items`
- `reproduction_steps`
- `overall_readiness_summary`

## Guardrails

- Do not perform broad refactors unless explicitly requested.
- Do not make product decisions.
- Do not provide unstructured "looks good" output.
- Do not write runtime noise into `projects/app/` source folders; use `projects/app/.runtime/`.
