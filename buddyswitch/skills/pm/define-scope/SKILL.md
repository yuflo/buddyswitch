---
name: define-scope
description: Use when PM must cut product work to the smallest valuable iteration with explicit non-goals.
---

# Define Scope

## Purpose
- Make product work small enough to design, build, and test in the current appetite.
- Preserve user value while reducing ambiguity and downstream churn.

## Use when
- A product direction, request, or set of signals is too broad for one iteration.
- PM must state what is in-scope, out of scope, and why.

## Do not use when
- The task is to discover product direction from scratch.
- The scope is already approved and PM only needs requirements or acceptance criteria.

## Inputs
- Product direction, constraints, risks, design/dev/test signals, appetite, current track state, and artifact bodies.
- Runtime contract references: `context.get.tool_catalog`, `python3 scripts/turn_runtime.py status`, and runtime response fields.

## Steps
1. Choose the smallest valuable outcome that still solves the current user problem.
2. List in-scope behavior, non-goals, cut-line rationale, downstream impact, and unresolved scope questions.
3. Separate scope decisions from design craft and implementation choices.
4. Publish scope as shared material with `artifact.create_revision` and `track.add_material` when it governs downstream work.

## Outputs
- Scope section with in-scope items, non-goals, cut rationale, owner impact, and unresolved questions.

## Quality Bar
- Scope cuts preserve user value and reduce verification ambiguity.
- Downstream owners know what not to build or test in this iteration.

## Runtime Boundary
- Use env tools for durable state.
- Read exact payload and response fields from runtime discovery, not this skill.
- Do not edit projected runtime storage directly.
- Use `track.open` before mutating track state and `artifact.get` when prior material matters.

## Examples
- Input: a broad onboarding improvement with unclear appetite. Output: one smallest valuable flow, excluded enhancements, and downstream owner impact.

## Counterexamples
- Expanding scope to satisfy every stakeholder note.
- Hiding a risky cut by leaving it out of non-goals.
