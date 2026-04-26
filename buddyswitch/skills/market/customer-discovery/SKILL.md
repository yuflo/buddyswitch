# customer-discovery

## Execution Order
1. Before any market research, run discovery in the visible `chrome-devtools-cockpit` browser and keep the workflow `browser-native`.
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
- A customer-discovery artifact object with target segments, interview goals, recruiting criteria, guide structure, hypotheses, evidence, and next-step recommendation.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.
- Explicit notes when public evidence is thin, when recruiting assumptions are weak, or when access constraints reduce confidence.

## Market Research Cockpit Runtime

- This skill follows `framework/docs/browser-cockpit.md`.
- It uses `chrome-devtools-cockpit` as the browser executor.
- It runs in an instance headed cockpit (`browser_mode=headed-only`) with profile `instance-browser`.
- Discovery mode is `browser-native`: search in the browser and continue into real result pages, details, comments, and related pages where relevant.
- Critical-source login is mandatory takeover, and fallback policy is no silent degrade.
- Do not silently downgrade to low-density public alternatives when critical sources are blocked.
- Do not use silent search API/snippet/crawler fallback.
- If browser-native access is genuinely blocked, only explicit user-approved one-off downgrade is allowed.
- The cockpit is execution-time only; canonical outputs remain BuddySwitch task/artifact/run objects.

## Verification
- Confirm the interview guide is aligned to problem discovery rather than solution pitching.
- Confirm every meaningful hypothesis or pattern is tied to evidence, prior artifacts, or an explicit assumption.
- Confirm the output stops at interview planning and synthesis instead of turning into PRD scope or positioning copy.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.

## Required Output Fields

- `research_question`
- `target_segments`
- `interview_goals`
- `recruiting_criteria`
- `interview_guide`
- `hypotheses_to_test`
- `evidence`
- `source_traceability`
- `patterns_and_insights`
- `risks_and_unknowns`
- `recommended_next_step`
- `conclusion`

## Guardrails

- Use public-first browsing when user or market context is still thin.
- For critical sources, require mandatory takeover before continuing past login gates.
- Do not silently downgrade to low-density public alternatives; record explicit evidence downgrade only for user-approved one-off downgrade.
- Do not use silent search API/snippet/crawler fallback.
- Do not write PRD scope.
- Do not turn interview planning into positioning copy.
- Do not invent participant quotes, pain severity, or demand signals.

## Examples
- `switch market: Prepare customer-discovery interviews for an AI bookkeeping assistant`
- `switch market: Turn these founder notes into a problem-discovery brief and interview guide`
- `switch market: Synthesize early interview notes for solo-founder CRM pain patterns`

## Counterexamples
- `switch market: Decide if the AI bookkeeping assistant has credible PMF`
- `switch market: Write homepage messaging for the solo-founder CRM`
- `switch pm: Turn the interview findings into MVP scope`

## Gotchas
- Discovery interviews should stay focused on current behavior, pain, and alternatives before solution feedback.
- Thin context is a signal to strengthen public evidence first, not to invent sharper interview claims.
