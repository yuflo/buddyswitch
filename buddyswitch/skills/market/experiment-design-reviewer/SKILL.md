---
name: experiment-design-reviewer
description: Use when you need to turn a market claim, channel, or positioning choice into one runnable experiment with clear success and kill signals.
---

# experiment-design-reviewer

## Purpose
- Replace vague launch prep with a disciplined learning loop.
- Make the next market experiment small, testable, and decision-relevant.

## Use When
- You need to design or review one landing, launch, pricing, outreach, or concierge experiment.
- The task needs stop, scale, or revise criteria before execution.
- You need a learning artifact, not a broad campaign plan.

## Do Not Use When
- The team still lacks a usable segment, message, or channel hypothesis.
- The task only asks for narrative market research.

## Inputs
- Positioning map, bottleneck diagnosis, channel choice, source evidence, and any draft experiment.

## Execution Order
1. Before forming external market claims, call `python3 scripts/env/client.py search open-browser --payload '{"query":"<channel> experiment benchmark complaint","engine":"google"}'`, then continue discovery in `chrome-devtools-cockpit` and keep the workflow browser-native.
2. Read upstream artifacts and source evidence before judging the experiment.
3. If a critical source requires login, pause for mandatory takeover.
4. Do not continue with snippet-only or text-only research when browser-native evidence is required.
5. Use runtime discovery for exact payload semantics before durable writes.

## Workflow
1. Write one hypothesis tied to one bottleneck and one audience.
2. Define the primary metric and one guardrail metric.
3. Set duration and sample sanity checks that fit the context.
4. Add a stop/scale rule and a kill signal.
5. Reject diffuse multi-channel plans that lack a kill signal.

## Artifact
- `template`: `brief`
- Required body sections:
  - Hypothesis
  - Audience
  - Channel
  - Message
  - Primary Metric
  - Guardrail Metric
  - Duration
  - Sample Sanity
  - Stop/Scale Rule
  - Kill Signal
  - Follow-up Decision

## Verification
- Confirm hypothesis, primary metric, guardrail metric, duration, sample sanity, stop/scale rule, and kill signal are all present.
- Confirm the experiment is small enough to run and strong enough to teach something.
- Confirm the artifact avoids a diffuse multi-channel plan that lacks a kill signal.

## Shared Runtime Rules
- Runtime execution uses env.tool through `python3 scripts/env/client.py ...`.
- Use runtime discovery when exact payload semantics matter.
- Durable market deliverables use `artifact.create_revision` with `template: brief`.
- Market artifact commits require broker-issued `tool_evidence`; do not invent token strings.
- No silent downgrade is allowed from required browser-native evidence.

## Guardrails
- Do not invent evidence, benchmarks, or certainty.
- Do not write an experiment with no kill signal.
- Do not choose vanity reach as the only success rule.
- Do not turn one learning loop into a broad campaign plan.
