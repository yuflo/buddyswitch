# Case 01: `switch pm` PRD Completeness

## Intent

Validate that `switch pm` produces a PRD-shaped output aligned with the PM contract.

## Prompt

```text
switch pm: Draft an MVP PRD from artifacts/research/live-space.md and write to artifacts/prd/live-space-mvp.md
```

## Preconditions

- `framework/contracts/pm.md` exists.
- `framework/templates/prd.md` exists.
- Input artifact exists or test fixture is provided.

## Manual Steps

1. Run the prompt in a BuddySwitch session.
2. Capture chat output and written file path.
3. Open generated PRD file under `artifacts/prd/`.

## Pass Criteria

- Output includes all PM contract fields:
  - `problem`
  - `goals`
  - `non_goals`
  - `users_and_scenarios`
  - `scope_p0_p1`
  - `acceptance_criteria`
  - `risks`
  - `open_questions`
- Durable output is written to `artifacts/prd/`.
- No code implementation is performed.

## Fail Signals

- Missing one or more required fields.
- PRD written outside `artifacts/prd/`.
- Agent drifts into implementation.
