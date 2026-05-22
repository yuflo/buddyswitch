---
name: read-implementation-context
description: Use when implementation depends on track, task, request, artifact, PRD, design, or test context.
---

# Read Implementation Context

## Purpose
- Turn upstream product material into an implementation brief without changing product direction.

## Use when
- The request references track/task/request ids or artifact ids.
- Scope, acceptance, or design constraints are not fully explicit in the direct prompt.

## Do not use when
- The task is trivial and complete context is already in the direct user request.

## Inputs
- Request text, task/request ids, track id.
- Artifact ids and artifact body content from `artifact.get`.
- Runtime contract references: `context.get.tool_catalog`, `python3 scripts/turn_runtime.py status`.

## Steps
1. Collect explicit ids from the request and context summary.
2. Read required objects with env tools; for artifacts, read full artifact body before coding.
3. Extract scope, non-goals, acceptance criteria, UX/API constraints, and verification expectations.
4. Record conflicts and send them back through product channels instead of resolving silently in code.
5. Hand off to `handle-empty-source-root`, `debug-regression`, or `implement-scoped-change`.

## Outputs
- Implementation brief with boundaries and acceptance checks.
- Explicit unresolved questions or blockers.

## Guardrails
- Do not claim context was read unless full bodies were read.
- Do not implement from memory when artifact ids are present.
- Do not silently widen scope.

## Stop Conditions
- Required artifact body is unavailable.
- PM/design constraints conflict and need owner decision.

## Examples
- Artifact id present, artifact body read, acceptance extracted, then implementation starts.

## Counterexamples
- Artifact id is mentioned but Dev skips reading artifact body and codes from memory.
