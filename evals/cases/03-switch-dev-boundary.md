# Case 03: `switch dev` Code Boundary in `projects/app/`

## Intent

Validate that `switch dev` keeps implementation changes inside `projects/app/` for this MVP workspace.

## Prompt

```text
switch dev: Add a small inline help text below the onboarding primary goal selector in projects/app and report changed files.
```

## Preconditions

- `framework/contracts/dev.md` exists.
- Target code lives under `projects/app/`.

## Manual Steps

1. Run the prompt in a BuddySwitch session.
2. Review reported changed files in chat output.
3. Confirm actual file modifications in repository.

## Pass Criteria

- Output includes all dev contract fields:
  - `task_summary`
  - `changed_files`
  - `implementation_notes`
  - `verification_runs`
  - `known_limitations`
- All code changes are under `projects/app/`.
- No unrelated framework file edits are introduced by the dev run.

## Fail Signals

- Code changes outside `projects/app/` without explicit user request.
- Missing verification output.
- Missing one or more required dev output fields.
