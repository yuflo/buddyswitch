---
name: customer-discovery
description: Use when the task is preparing customer interviews, structuring problem discovery, or turning early user conversations into usable demand signals.
---

# customer-discovery

## Execution Order
1. Before any market research, call `python3 scripts/env/client.py search open-browser --query "<initial query>" --engine <google|reddit|x|web>`, then continue discovery in `chrome-devtools-cockpit` and keep the workflow `browser-native`.
2. Read all selected upstream inputs before forming new market claims.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when the skill contract requires browser-native work.
5. Only after the steps above should you synthesize findings into the structured result.

## Purpose
- Produce interview-ready customer-discovery artifacts that turn early market context into interview goals, recruiting criteria, structured guides, and usable demand signals.

## Use when
- The task is preparing customer interviews, structuring discovery conversations, or translating early market context into a sharper problem-discovery plan.
- The user wants a concrete interview brief, hypotheses to test, or synthesis of early customer conversations.
- The market or user context is still thin enough that you need public-first browsing to ground the interview plan before talking to users.

## Do Not Use When
- The task is mainly a broad category or competitor scan without an interview-planning outcome; use `research-scan`.
- The task is judging whether a product idea has PMF or should be pursued at all; use `pmf-recon`.
- The task is writing founder-facing positioning, homepage messaging, or value framing; use `positioning-copy`.
- The task is writing PRD scope, product requirements, or implementation acceptance criteria.

## Inputs
- Research question or product hypothesis.
- Known target users, contexts, and constraints.
- Provided links, prior artifacts, or partial interview notes.
- Optional market context from `market-scan` or PMF artifacts when they already exist.

## Outputs
- Durable outputs are written explicitly through env tools.
- Durable customer discovery content is written through `artifact-tool` `artifact.create_revision`.
- Reference written artifacts by explicit ids when relevant.

## Market Research Cockpit Runtime

- It uses `chrome-devtools-cockpit` as the browser executor.
- It runs in an instance headed cockpit (`browser_mode=headed-only`) with profile `instance-browser`.
- Discovery starts with `search.open_browser` to open the browser-native entry page, then continues into real result pages, details, comments, and related pages where relevant via `chrome-devtools-cockpit`.
- Critical-source login is mandatory takeover, and fallback policy is no silent degrade.
- Do not silently downgrade to low-density public alternatives when critical sources are blocked.
- Do not use silent search API/snippet/crawler fallback.
- If browser-native access is genuinely blocked, only explicit user-approved one-off downgrade is allowed.
- The cockpit is execution-time only; canonical outputs remain BuddySwitch task or artifact objects; buddybox remains active-buddy private local workspace state.
- Market evidence is target-scoped to artifact ids; do not invent evidence tokens.

## Verification
- Confirm the interview guide is aligned to problem discovery rather than solution pitching.
- Confirm every meaningful hypothesis or pattern is tied to evidence, prior artifacts, or an explicit assumption.
- Confirm the output stops at interview planning and synthesis instead of turning into PRD scope or positioning copy.

## Shared Runtime Rules

- Runtime execution uses env.tool through python3 scripts/env/client.py ... .
- Product-readable durable state is written explicitly as task or artifact objects.
- Use buddybox env tools with `logical_name` for active-buddy-private working files.
- Return after required explicit durable writes are complete.
- Do not rely on deprecated prepare/persist flows.

## BuddySwitch Commit Output

Write durable outputs explicitly via env tools. Do not rely on deprecated prepare/persist flows.

Required top-level field:
- `execution_summary`

Use `artifact-tool` when this skill produces a durable artifact:
- `kind`: `customer-discovery`
- `title`: concise artifact title
- `summary`: short downstream selection summary
- `content`: include `research_question`, `evidence`, `insights`, `assumptions`, `risks`, `conclusion`, `recommended_next_step`, and discovery-specific structured detail

After `artifact.create_revision` returns `ok=true`, include the returned artifact id in optional `artifact_ids`.
Use optional `working_notes` for concise reasoning or verification notes.
Use optional `task_id` only as association metadata for an explicitly selected task.

Market artifact commits require broker-issued `tool_evidence` from the browser evidence gate. Do not invent token strings.

## Guardrails

- Use public-first browsing when user or market context is still thin.
- For critical sources, require mandatory takeover before continuing past login gates.
- Do not silently downgrade to low-density public alternatives; record explicit evidence downgrade only for user-approved one-off downgrade.
- Do not use silent search API/snippet/crawler fallback.
- Do not write PRD scope.
- Do not turn interview planning into positioning copy.
- Do not invent participant quotes, pain severity, or demand signals.

## Examples
- `Prepare customer-discovery interviews for an AI bookkeeping assistant`
- `Turn these founder notes into a problem-discovery brief and interview guide`
- `Synthesize early interview notes for solo-founder CRM pain patterns`

## Counterexamples
- `Decide if the AI bookkeeping assistant has credible PMF`
- `Write homepage messaging for the solo-founder CRM`
- `Turn the interview findings into MVP scope`

## Gotchas
- Discovery interviews should stay focused on current behavior, pain, and alternatives before solution feedback.
- Thin context is a signal to strengthen public evidence first, not to invent sharper interview claims.
