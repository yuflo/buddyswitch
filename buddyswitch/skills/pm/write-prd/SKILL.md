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
- The task is primarily track lifecycle administration (`create`, `update`, `advance`, `archive`).
- The user wants design structure, implementation work, market research, or smoke testing as main outcome.

## Inputs
- Market evidence artifacts when available: `market-scan`, `pmf-report`, `customer-discovery`, `positioning-brief`, `channel-plan`, `launch-prep`.
- Track/task/artifact context when relevant.
- Constraints, assumptions, requirements.

## Outputs
- A PM artifact object in `buddyswitch/objects/artifacts/`.
- A run audit in `buddyswitch/content/runs/`.
- PM result JSON aligned to `framework/schemas/pm/pm-result.json`.

## Steps
1. Define the PRD summary and key decisions.
2. Capture risks, open questions, and one concrete suggested next step.
3. Put PRD-specific detail under `artifact_content.specialized_sections.prd` (problem, user_value, requirements, scope).
4. If an explicit PM track lifecycle mutation is required, include `state_effects.track` explicitly.

## Verification
- Keep the result product-definition centered.
- Keep PRD detail in `specialized_sections.prd`, not top-level PM fields.
- Use `state_effects.track` only for explicit PM lifecycle intent.

## Shared Runtime Rules
- See `framework/docs/skill-runtime-shared-rules.md`.
- This native skill contributes content to the current buddy run.
- Do not call persist from the skill perspective.
- The locked buddy session persists one buddy run commit after all needed native skill work is integrated.

## Required Output Fields
Top-level envelope keys:
- `execution_summary`
- `working_notes`
- `deliverables_or_changed_files`
- `artifact_content`

Required fields in `artifact_content`:
- `summary`
- `decisions`
- `risks`
- `open_questions`
- `suggested_next_step`
- `specialized_sections`

## Examples
- `Draft the MVP PRD for onboarding rewrite track`
- `Continue product definition and define P0/P1 scope`

## Counterexamples
- `create track and set next_buddy design`
- `implement the approved onboarding rewrite scope`
