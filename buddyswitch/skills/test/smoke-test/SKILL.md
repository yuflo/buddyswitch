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
- Durable outputs are written explicitly through env tools.
- Durable smoke test report content is written through `artifact-tool` `artifact.create_revision`.
- Reference written artifacts by explicit ids when relevant.

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

- Runtime execution uses native BuddySwitch env MCP tools through env.tool; use runtime discovery when exact schemas matter.
- Product-readable durable state is written explicitly as task or artifact objects.
- Use `$BUDDYSWITCH_ACTOR_PRIVATE_DIR` for active-role-private working files.
- Return after required explicit durable writes are complete.

## BuddySwitch Commit Output

Write durable outputs explicitly via native BuddySwitch env MCP tools. Do not rely on deprecated prepare/persist flows.

Required top-level field:
- `execution_summary`

Use `artifact-tool` when this skill produces a durable artifact:
- `template`: `proof`
- `title`: concise artifact title
- `summary`: short downstream selection summary
- `body`: include `test_scope`, `checks_run`, `passed_items`, `failed_items`, `blocked_items`, `reproduction_notes`, and `readiness` as markdown

After `artifact.create_revision` returns `ok=true`, use `track.open` and `artifact.get` to verify shared visibility when needed.
Use optional `working_notes` for concise reasoning or verification notes.
Use optional `task_id` only as association metadata for an explicitly selected task.

## Guardrails

- Do not perform broad refactors unless explicitly requested.
- Do not make product decisions.
- Do not provide unstructured "looks good" output.
- Do not write runtime noise into `projects/app/` source folders; write temporary private files under `$BUDDYSWITCH_ACTOR_PRIVATE_DIR`.

## Examples
- `Run smoke checks for the onboarding CTA regression`
- `Verify the playlist reorder flow after the latest dev artifact update`
- `Smoke test the creator profile release candidate in projects/app`

## Counterexamples
- `Fix the onboarding CTA regression`
- `Define the MVP scope for creator profile`
- `Research competitor onboarding funnels`

## Gotchas
- Smoke testing should stay tight and outcome-focused; do not turn it into broad exploratory QA unless asked.
- A task mentioning implementation context still belongs here when the required output is verification evidence.
