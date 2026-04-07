# Onboarding Minimal PRD

## problem

- New users have no quick path to provide basic profile intent, so the demo lacks a concrete first-run flow.
- We need a minimal onboarding sequence to validate BuddySwitch's PM -> Design -> Dev -> Test chain with real output.

## goals

- Provide a small 3-step onboarding flow: welcome, profile setup, confirm.
- Capture two required fields: `display name` and `primary goal`.
- Show a completion state after successful submission.

## non_goals

- No account backend integration.
- No persistence to database or API.
- No full product dashboard after onboarding.

## users_and_scenarios

- User segment: first-time visitor of the demo app.
- Scenario 1: user starts onboarding, provides valid data, and reaches completion.
- Scenario 2: user attempts to continue with missing fields and sees validation error.

## scope_p0_p1

### P0

- Single page onboarding UI in `projects/app/`.
- Step navigation (next/back) and progress indicator.
- Required field validation for name and goal.
- Confirmation step showing captured values.
- Completion state and restart action.

### P1

- Improved accessibility copy and keyboard focus polish.
- Optional local persistence.
- Visual polish and richer states.

## acceptance_criteria

- AC-1: user can start onboarding and navigate between 3 steps.
- AC-2: profile step blocks progress when `display name` is empty.
- AC-3: profile step blocks progress when `primary goal` is not selected.
- AC-4: confirmation step shows entered `display name` and selected `primary goal`.
- AC-5: finish action displays completion state and restart can reset flow.

## risks

- Manual validation only; no backend validation.
- Without automated UI tests, regressions rely on smoke checks.

## open_questions

- Should onboarding data be persisted in local storage for demo continuity?
- Should completion redirect to another demo page in next iteration?
