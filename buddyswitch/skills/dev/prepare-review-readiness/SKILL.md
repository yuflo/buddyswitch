---
name: prepare-review-readiness
description: Use when Dev hands completed work to Test/review and needs a focused inspection map.
---

# Prepare Review Readiness

## Purpose
- Give downstream reviewers a focused map of what to inspect and why.

## Use when
- Implementation and focused verification are complete.
- You are handing work to Test or review.

## Do not use when
- There is no implementation evidence yet.

## Inputs
- Implementation report or equivalent changed-file summary.
- Verification evidence.
- Known risks and open questions.
- Runtime contract references: `context.get.tool_catalog`, `python3 scripts/turn_runtime.py status`.

## Steps
1. State the main path under review.
2. Summarize blast radius by behavior area.
3. Group changed files by behavior.
4. Attach verification evidence already run.
5. Call out residual risk and recommended test focus.

## Outputs
- Concise review entry map with hotspots and validation priorities.

## Guardrails
- Do not duplicate the full implementation report verbatim.
- Do not hide residual risk.
- Keep the map actionable for Test/review execution.

## Stop Conditions
- Missing verification evidence or unresolved high-impact risk prevents review-ready handoff.

## Examples
- "Focus review on CTA click path and responsive layout; blast radius limited to onboarding components."

## Counterexamples
- Repeating implementation notes without identifying hotspots or residual risk.
