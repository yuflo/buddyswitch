---
name: smoke-test
description: Run focused smoke checks and produce structured pass/fail/blocked reports.
version: "2.0"
track_mode: optional
default_artifact_kind: smoke-test
auto_summary: true
output_schema: framework/schemas/test/smoke-test.json
side_effect_level: high
produces:
  - test-report
  - smoke-check
consumes:
  - change-scope
  - build
  - implementation-report
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
- A smoke-test artifact with passed, failed, and blocked items plus reproduction notes.
- Runtime outputs under `projects/app/.runtime/` when needed.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.

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

## Track/Object Handling

- Follow `framework/docs/track-registry.md`.
- This buddy may read tracks and create/update artifact objects through the resolved task.
- Do not mutate track lifecycle fields directly.
- If output belongs to a track, rely on the explicit switch track target or existing task binding; artifacts do not store direct track references.

## Output Path

- Default BuddySwitch state: `buddyswitch/objects/tasks/<task-id>.json`, `buddyswitch/objects/artifacts/<artifact-id>.json`, and `buddyswitch/content/runs/<run-id>.json`
- Project runtime-only temporary outputs: `projects/app/.runtime/`
- Do not request or rely on `artifacts/*.md` or `runs/summaries/**`.

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

## Examples
- `switch test: Run smoke checks for the onboarding CTA regression`
- `switch test: Verify the playlist reorder flow after the latest dev handoff`
- `switch test: Smoke test the creator profile release candidate in projects/app`

## Counterexamples
- `switch dev: Fix the onboarding CTA regression`
- `switch pm: Define the MVP scope for creator profile`
- `switch market: Research competitor onboarding funnels`

## Gotchas
- Smoke testing should stay tight and outcome-focused; do not turn it into broad exploratory QA unless asked.
- A task mentioning implementation context still belongs here when the required output is verification evidence.
