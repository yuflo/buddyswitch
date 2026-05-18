---
name: write-prd
description: Use when the task is drafting a PRD, defining MVP scope, or turning validated requirements into product requirements.
---

# write-prd

## Purpose
- Produce a scoped MVP PRD that turns explicit market evidence and requirements into concrete product definition.

## Use when
- The task is about drafting a PRD, defining MVP scope, clarifying acceptance criteria, or writing product requirements.
- The user wants PM output that becomes source artifact for downstream design or implementation.

## Do Not Use When
- The task is primarily track lifecycle administration (`create`, `update`, `archive`).
- The user wants design structure, implementation work, market research, or smoke testing as main outcome.

## Inputs
- Market evidence artifacts when available (typically `template="brief"`).
- Track/task/artifact context when relevant.
- Constraints, assumptions, requirements.

## Outputs
- Durable outputs are written explicitly through env tools.
- Durable PRD content is written through `artifact-tool` `artifact.create_revision`.
- Reference written artifacts by explicit ids when relevant.

## Steps
1. Define the PRD summary and key decisions.
2. Capture risks, open questions, and one concrete suggested next step.
3. Put PRD-specific detail in artifact `body` markdown (problem, user value, requirements, scope).
4. If an explicit PM track lifecycle mutation is required, use `track-tool` before returning.

## Verification
- Keep the result product-definition centered.
- Keep PRD detail in the artifact `body` and supporting metadata (`template`, `summary`).
- Confirm any task or track lifecycle change was completed through `task-tool` or `track-tool` with `ok=true`.

## Shared Runtime Rules

- Runtime execution uses env.tool through python3 scripts/env/client.py ... .
- Product-readable durable state is written explicitly as task or artifact objects.
- Use buddybox env tools with `logical_name` for active-buddy-private working files.
- Return after required explicit durable writes are complete.

## BuddySwitch Commit Output

Write durable outputs explicitly via env tools. Do not rely on deprecated prepare/persist flows.

Required top-level field:
- `execution_summary`

Use `artifact-tool` when this skill produces a durable artifact:
- `template`: usually `brief`
- `title`: concise artifact title
- `summary`: short downstream selection summary
- `body`: include `decisions`, `risks`, `open_questions`, and `suggested_next_step`

After `artifact.create_revision` returns `ok=true`, use `track.open` and `artifact.get` to verify shared visibility when needed.
Use optional `working_notes` for concise reasoning or verification notes.
Use optional `task_id` or `track_id` only as association metadata for explicit env-tool state.

## Examples
- `Draft the MVP PRD for onboarding rewrite track`
- `Continue product definition and define P0/P1 scope`

## Counterexamples
- `create track, then wait for design to attach via track task-relation actions`
- `implement the approved onboarding rewrite scope`
