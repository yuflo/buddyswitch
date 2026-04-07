# BuddySwitch v1 Base Rubric

## Scoring Model

Use binary scoring per case:
- `1` = pass
- `0` = fail

No weighted score in v1.

## Required Cases

- `01-switch-pm-prd.md`
- `02-switch-design-state-coverage.md`
- `03-switch-dev-boundary.md`
- `04-switch-test-structure.md`
- `05-invalid-switch-error.md`
- `06-switch-market-deep-research.md`
- `07-cleanup-storage-script.md`

## Run-Level Verdict

- `PASS`: all 7 required cases pass.
- `FAIL`: any required case fails.

## Failure Logging Format

For each failed case, record:
1. case id and file
2. observed behavior
3. expected behavior
4. likely root cause
5. minimal fix proposal

## Suggested Result File

- `runs/summaries/eval-<date>-buddyswitch-v1.md`
