# Case 02: `switch design` Loading/Empty/Error Coverage

## Intent

Validate that `switch design` output includes explicit state coverage, especially `loading`, `empty`, and `error`.

## Prompt

```text
switch design: Produce IA and core flows for onboarding from artifacts/prd/onboarding-minimal.md and ensure state coverage includes loading, empty, and error states. Write to artifacts/design/onboarding-state-spec.md
```

## Preconditions

- `framework/contracts/design.md` exists.
- `framework/templates/design-spec.md` exists.
- Input PRD exists at `artifacts/prd/onboarding-minimal.md`.

## Manual Steps

1. Run the prompt in a BuddySwitch session.
2. Open generated design file.
3. Inspect `state_coverage` section content.

## Pass Criteria

- Output includes all design contract fields:
  - `ia`
  - `primary_flows`
  - `key_screens`
  - `state_coverage`
  - `interaction_notes`
  - `open_questions`
- `state_coverage` explicitly mentions:
  - loading
  - empty
  - error
- Durable output is written to `artifacts/design/`.

## Fail Signals

- Missing required contract field(s).
- Any of loading/empty/error is absent.
- Agent drifts into code implementation.
