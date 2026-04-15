# customer-discovery

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
- Stop at login-required sources and ask the user before continuing beyond public evidence.
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
