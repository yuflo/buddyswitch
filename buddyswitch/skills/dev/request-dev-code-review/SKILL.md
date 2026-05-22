---
name: request-dev-code-review
description: Use when Dev needs a scoped code review after significant implementation or before review handoff.
---

# Request Dev Code Review

## Purpose
- Ask for a review that is scoped, evidence-backed, and explicit about what matters.

## Use when
- Major feature work, cross-module changes, complex bugfixes, or review handoff needs another technical pass.

## Do not use when
- The change is tiny, isolated, and already covered by a clear focused check with no meaningful risk.

## Inputs
- Requirements, acceptance checks, changed files or diff range, verification evidence, and known risks.
- Runtime contract references: `context.get.tool_catalog`, `python3 scripts/turn_runtime.py status`.

## Steps
1. State whether the ask is spec compliance review, code quality review, or both.
2. Summarize the requirements and the changed files or diff range.
3. Attach verification evidence and call out known risks or unverified edges.
4. Ask the reviewer to identify critical and important issues first.
5. Fix critical and important issues before proceeding to final handoff.

## Outputs
- Review request with scope, requirements, changed files, evidence, and severity expectations.

## Guardrails
- Self-review is not enough for significant changes.
- Review does not replace tests.
- Do not bury wide blast radius or known risks.

## Verification
- The review request includes requirements, changed files, verification evidence, and known risks.

## Examples
- Ask for spec compliance on acceptance criteria and code quality on a shared parser refactor.

## Counterexamples
- "Please review" with no diff scope, no evidence, and no risk callouts.
