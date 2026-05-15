---
name: positioning-copy
description: Use when the task is sharpening external positioning, value framing, or founder-facing market copy from validated market evidence.
---

# positioning-copy

## Execution Order
1. Before any market research, call `python3 scripts/env/client.py search open-browser --query "<initial query>" --engine <google|reddit|x|web>`, then continue discovery in `chrome-devtools-cockpit` and keep the workflow `browser-native`.
2. Read all selected upstream inputs before forming new market claims.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when the skill contract requires browser-native work.
5. Only after the steps above should you synthesize findings into the structured result.

## Purpose
- Produce evidence-grounded positioning artifacts that help a founder explain who the product is for, what it replaces, why it is differentiated, and which copy angles are worth testing.

## Use when
- The task is sharpening external positioning, value framing, or homepage-level copy from validated market evidence.
- The user wants founder-usable copy artifacts rather than a market scan or PMF decision.
- Inputs already include enough research, PMF, or discovery evidence to support concrete message choices.

## Do Not Use When
- The task still needs broad category research or competitor mapping; use `research-scan`.
- The task still needs PMF judgment, ICP prioritization, or demand confidence; use `pmf-recon`.
- The task is preparing interviews or discovery synthesis; use `customer-discovery`.
- The task is asking for visual design specs, page layouts, or brand-system deliverables.

## Inputs
- Research question or messaging objective.
- Relevant `market-scan`, `pmf-report`, or `customer-discovery` artifacts when available.
- Provided links, prior artifacts, or founder notes that need message synthesis.
- Optional constraints such as tone, target audience, or channel context.

## Outputs
- Durable outputs are written explicitly through env tools.
- Durable positioning content is written through `artifact-tool` `artifact.create_revision`.
- Reference written artifacts by explicit ids when relevant.

## Market Research Cockpit Runtime

- This skill follows `framework/docs/browser-cockpit.md`.
- It uses `chrome-devtools-cockpit` as the browser executor.
- It runs in an instance headed cockpit (`browser_mode=headed-only`) with profile `instance-browser`.
- Discovery starts with `search.open_browser` to open the browser-native entry page, then continues into real result pages, details, comments, and related pages where relevant via `chrome-devtools-cockpit`.
- Critical-source login is mandatory takeover, and fallback policy is no silent degrade.
- Do not silently downgrade to low-density public alternatives when critical evidence refresh is blocked.
- Do not use silent search API/snippet/crawler fallback.
- If browser-native access is genuinely blocked, only explicit user-approved one-off downgrade is allowed.
- The cockpit is execution-time only; canonical outputs remain BuddySwitch task/artifact/run objects.

## Verification
- Confirm the positioning statement and message house are grounded in evidence from `market-scan`, `pmf-report`, and `customer-discovery` where available.
- Confirm every claim is supportable, clearly scoped, and free of invented proof points.
- Confirm the output stays at messaging and value framing rather than visual design direction.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.
- This native skill contributes content to the current buddy run.
- Do not rely on deprecated prepare/persist flows.
- The locked buddy session returns after explicit durable writes are complete.

## BuddySwitch Commit Output

Write durable outputs explicitly via env tools. Do not rely on deprecated prepare/persist flows.

Required top-level field:
- `execution_summary`

Use `artifact-tool` when this skill produces a durable artifact:
- `kind`: `positioning-brief`
- `title`: concise artifact title
- `summary`: short downstream selection summary
- `content`: include `research_question`, `evidence`, `insights`, `assumptions`, `risks`, `conclusion`, `recommended_next_step`, and positioning-specific structured detail

After `artifact.create_revision` returns `ok=true`, include the returned artifact id in optional `artifact_ids`.
Use optional `working_notes` for concise reasoning or verification notes.
Use optional `task_id` only as association metadata for an explicitly selected task.
Use optional `handoff` when another manifest buddy should continue.

Market artifact commits require broker-issued `tool_evidence` from the browser evidence gate. Do not invent token strings.

## Guardrails

- Output founder-usable copy artifacts, not visual design specs.
- Ground claims in evidence from `market-scan`, `pmf-report`, and `customer-discovery`.
- For critical sources, require mandatory takeover before continuing past login gates.
- Do not silently downgrade to low-density public alternatives; record explicit evidence downgrade only for user-approved one-off downgrade.
- Do not use silent search API/snippet/crawler fallback.
- Do not invent proof points.
- Do not imply traction, conversion, or customer validation that the evidence does not support.

## Examples
- `Turn the PMF findings into founder-facing homepage positioning`
- `Write a positioning brief for an AI assistant for operations leads`
- `Develop three evidence-grounded homepage angles from these market artifacts`

## Counterexamples
- `Create the landing page prototype direction for the operations assistant`
- `Decide whether the operations assistant has enough PMF to pursue`
- `Prepare discovery interviews for operations leads`

## Gotchas
- Positioning language should simplify and sharpen the evidence, not outrun it.
- Strong copy can still be narrow; avoid bloating the message house to satisfy every possible audience.
