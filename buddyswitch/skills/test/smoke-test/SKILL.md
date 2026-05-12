---
name: smoke-test
description: Use when the task is running smoke checks, regression verification, or readiness testing for a change.
---

# smoke-test

## Purpose
- Execute focused smoke checks on a change and report readiness with clear passed, failed, and blocked outcomes.

## Use when
- The user wants smoke testing, QA verification, regression confirmation, or readiness assessment.
- The task references changed files, a feature scope, a commit, or expected behavior to verify.
- The main deliverable is a structured test report rather than code or product definition.

## Do Not Use When
- The user is asking to implement the feature, define scope, write a design spec, or perform market research.
- The request is vague validation with no behavior to check and no change context.
- The task is actually a PM track lifecycle update.

## Inputs
- Changed files, commit, or feature scope.
- Expected behavior.
- Environment setup and test commands.
- Optional track context or summary hint.

## Outputs
- A contribution to the current compact buddy-run commit.
- Durable smoke test report content is written before persist through `artifact-tool` `artifact.create_revision`.
- The final run commit references already-written artifacts with optional `artifact_ids` metadata.

## Steps

1. Define smoke test scope from change context.
2. Run checks and capture results.
3. Classify outcomes into passed, failed, and blocked.
4. Add reproduction steps for failures when available.
5. Produce readiness summary.
6. Write the report using the test template.

## Verification
- Confirm the smoke scope matches the change scope instead of turning into a broad exploratory test pass.
- Confirm failures and blocked states include actionable detail.
- Confirm the readiness summary is grounded in observed results.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.
- This native skill contributes content to the current buddy run.
- Do not call persist from the skill perspective.
- The locked buddy session persists one buddy run commit after all needed native skill work is integrated.

## BuddySwitch Commit Output

Contribute to one buddy-run commit. Do not call persist from inside the skill.

Required top-level field:
- `execution_summary`

Use `artifact-tool` before persist when this skill produces a durable artifact:
- `kind`: `smoke-test`
- `title`: concise artifact title
- `summary`: short downstream selection summary
- `content`: include `test_scope`, `checks_run`, `passed_items`, `failed_items`, `blocked_items`, `reproduction_notes`, and `readiness`

After `artifact.create_revision` returns `ok=true`, include the returned artifact id in optional `artifact_ids`.
Use optional `working_notes` for concise reasoning or verification notes.
Use optional `task_id` only as association metadata for an explicitly selected task.
Use optional `handoff` when another manifest buddy should continue.

## Guardrails

- Do not perform broad refactors unless explicitly requested.
- Do not make product decisions.
- Do not provide unstructured "looks good" output.
- Do not write runtime noise into `projects/app/` source folders; use `runs/raw/`.

## Examples
- `Run smoke checks for the onboarding CTA regression`
- `Verify the playlist reorder flow after the latest dev handoff`
- `Smoke test the creator profile release candidate in projects/app`

## Counterexamples
- `Fix the onboarding CTA regression`
- `Define the MVP scope for creator profile`
- `Research competitor onboarding funnels`

## Gotchas
- Smoke testing should stay tight and outcome-focused; do not turn it into broad exploratory QA unless asked.
- A task mentioning implementation context still belongs here when the required output is verification evidence.
