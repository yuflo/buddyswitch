# Onboarding Minimal Design Spec

## ia

- Single-page flow container:
  - Header
  - Progress
  - Step content
  - Done state
- No cross-page navigation.

## primary_flows

- Flow 1 (happy path):
  - Open page -> Start -> Enter valid profile data -> Confirm -> Finish -> Done state.
- Flow 2 (validation path):
  - Start -> Leave required fields empty -> Continue -> See error -> Correct input -> Continue.
- Flow 3 (restart path):
  - Complete flow -> Click "Run Again" -> Return to step 1 with cleared data.

## key_screens

- Screen A: Welcome step with `Start`.
- Screen B: Profile setup with `Display Name` input and `Primary Goal` select.
- Screen C: Confirm step with summary values and `Finish`.
- Screen D: Done state with `Run Again`.

## state_coverage

- Active step states: step 1, step 2, step 3.
- Validation error state on profile step.
- Completion state after finish.
- Reset state after restart.

## interaction_notes

- `Next` advances step only when current step is valid.
- `Back` returns to previous step and clears inline error text.
- Progress bar and label reflect active step.
- Confirm step reads values from validated profile input.

## open_questions

- Should error messaging include inline field-level markers in addition to summary text?
- Should confirm step allow direct edit links to specific fields in future iterations?
