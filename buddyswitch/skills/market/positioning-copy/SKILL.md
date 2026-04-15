# positioning-copy

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
- A positioning artifact object with target audience framing, alternatives, differentiated capabilities, value claims, message house, homepage angles, and evidence traceability.
- Founder-usable copy artifacts, not visual design specifications.
- A run audit in `buddyswitch/content/runs/` when default runtime persistence is used.

## Verification
- Confirm the positioning statement and message house are grounded in evidence from `market-scan`, `pmf-report`, and `customer-discovery` where available.
- Confirm every claim is supportable, clearly scoped, and free of invented proof points.
- Confirm the output stays at messaging and value framing rather than visual design direction.

## Shared Runtime Rules

- See `framework/docs/skill-runtime-shared-rules.md` for execution summary persistence, task/artifact boundaries, and durable output path rules.

## Required Output Fields

- `research_question`
- `target_audience`
- `status_quo_and_alternatives`
- `differentiated_capabilities`
- `value_claims`
- `positioning_statement`
- `message_house`
- `homepage_angles`
- `evidence`
- `source_traceability`
- `risks_and_unknowns`
- `conclusion`

## Guardrails

- Output founder-usable copy artifacts, not visual design specs.
- Ground claims in evidence from `market-scan`, `pmf-report`, and `customer-discovery`.
- Do not invent proof points.
- Do not imply traction, conversion, or customer validation that the evidence does not support.

## Examples
- `switch market: Turn the PMF findings into founder-facing homepage positioning`
- `switch market: Write a positioning brief for an AI assistant for operations leads`
- `switch market: Develop three evidence-grounded homepage angles from these market artifacts`

## Counterexamples
- `switch design: Create the landing page visual spec for the operations assistant`
- `switch market: Decide whether the operations assistant has enough PMF to pursue`
- `switch market: Prepare discovery interviews for operations leads`

## Gotchas
- Positioning language should simplify and sharpen the evidence, not outrun it.
- Strong copy can still be narrow; avoid bloating the message house to satisfy every possible audience.
