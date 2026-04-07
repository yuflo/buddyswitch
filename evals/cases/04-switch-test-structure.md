# Case 04: `switch test` Pass/Fail/Blocked Structure

## Intent

Validate that `switch test` returns a structured test report with pass/fail/blocked breakdown.

## Prompt

```text
switch test: Run smoke tests for onboarding changes in projects/app and write report to artifacts/test/onboarding-smoke-regression.md
```

## Preconditions

- `framework/contracts/test.md` exists.
- Test target exists in `projects/app/`.

## Manual Steps

1. Run the prompt in a BuddySwitch session.
2. Open generated test report file.
3. Inspect report sections and chat output.

## Pass Criteria

- Output includes all test contract fields:
  - `test_scope`
  - `passed_items`
  - `failed_items`
  - `blocked_items`
  - `reproduction_steps`
  - `overall_readiness_summary`
- `passed_items`, `failed_items`, and `blocked_items` are all present as distinct sections.
- Durable output is written to `artifacts/test/`.

## Fail Signals

- Combined or missing pass/fail/blocked sections.
- Missing reproduction steps when failures exist.
- No durable report path under `artifacts/test/`.
