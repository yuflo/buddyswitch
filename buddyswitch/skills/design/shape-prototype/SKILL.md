---
name: shape-prototype
description: Use when the task is shaping a visible UI/UX prototype and producing a design artifact.
---

# shape-prototype

## Purpose
- Shape a visible UI/UX prototype direction and package a durable design artifact for downstream PM, dev, and test work.

## Use When
- The task is about prototype structure, page flow, interaction direction, layout shape, or design artifact outcomes.
- The user wants a concrete prototype plan or `.sandbox/design/` preview path rather than product scope or implementation code.
- The work should turn requirements, PRD, market context, or track context into an actionable design artifact.

## Do Not Use When
- The task is actually product scoping, market research, code implementation, or test execution.
- The request is only about track lifecycle mutation.
- The work would skip a design artifact and only return loose discussion notes.

## Inputs
- PRD, requirements, market evidence, and track context when available.
- Prior design artifacts when iterating an existing prototype direction.
- Constraints about target screens, CTA flow, navigation, or preview environment.

## Outputs
- Durable outputs are written explicitly through env tools.
- Durable design artifact content is written through `artifact-tool` `artifact.create_revision`.
- Reference written artifacts by explicit ids when relevant.

## Steps

1. Restate the target prototype scope and main user journey.
2. Shape the page map and primary flow before detailed polish.
3. Decide the preview root and entry file for the first runnable artifact package.
4. When visual evidence will reduce downstream ambiguity, capture it with `chrome-devtools-cockpit`, import it with `buddybox.import_file`, attach it with `artifact.attach_file`, and cite the resulting `attachment_id` in the handoff artifact.
5. Capture PM, dev, and test artifact notes in separate lists.
6. Record open questions that materially affect the next prototype pass, including why no screenshot was attached when visual evidence is unnecessary or unavailable.
7. Package the result as the structured `template="design"` artifact.

## Verification
- Confirm the prototype direction stays aligned with the active task and does not silently rewrite product scope.
- Confirm the preview path points to a concrete `.sandbox/design/` location when a runnable artifact is produced.
- Confirm PM, dev, and test artifact notes are actionable for the next buddy turn.

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
- `template`: `design`
- `title`: concise artifact title
- `summary`: short downstream selection summary
- `body`: include `design_goal`, `flow_or_screen_summary`, `interaction_notes`, `assets_or_preview_refs`, `artifact_notes`, and `open_questions` as markdown
- When screenshots or exports matter, keep the blob out of markdown body text. Store the file through generic attachment actions, cite the `attachment_id`, and tell downstream buddies to discover it from `track.open` or fetch exact bytes with `artifact.get_attachment`.

After `artifact.create_revision` returns `ok=true`, use `track.open` and `artifact.get` to verify shared visibility when needed.
Use optional `working_notes` for concise reasoning or verification notes.
Use optional `task_id` only as association metadata for an explicitly selected task.

## Guardrails

- Do not silently expand product scope while shaping the prototype.
- Do not output implementation code as the primary deliverable.
- Do not omit the preview path when a sandbox prototype exists.
- Do not collapse PM, dev, and test artifact notes into one mixed note list.

## Examples
- `Shape the landing-page prototype`
- `Turn the approved onboarding requirements into a first prototype artifact`
- `Refine the pricing-to-demo-request flow and package the design artifact`

## Counterexamples
- `Define the MVP scope for the landing page`
- `Implement the landing page in projects/app`
- `Smoke test the onboarding prototype`

## Gotchas
- Prototype shaping can use market and PRD inputs, but it should still end in a design artifact instead of a scope artifact.
- Keep the first pass structural; unanswered visual polish can stay in `open_questions`.
