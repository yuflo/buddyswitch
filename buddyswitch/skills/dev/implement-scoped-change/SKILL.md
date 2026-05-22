---
name: implement-scoped-change
description: Use when Dev has approved scope and must change source behavior under the locked source root.
---

# Implement Scoped Change

## Purpose
- Apply the smallest direct code change that satisfies approved behavior.

## Use when
- Source scope is clear and the locked source root is ready for edits.
- Feature, refactor, or bug work requires code updates.

## Do not use when
- Product direction is still undecided.
- Required implementation context has not been read.

## Inputs
- Locked source root and approved implementation brief.
- Local project patterns, commands, and changed behavior expectation.
- Runtime contract references: `context.get.tool_catalog`, `python3 scripts/turn_runtime.py status`.

## Steps
1. Map requested behavior to concrete files under the locked source root.
2. Add/adjust a failing test first when practical for behavior change.
3. Implement the smallest direct change.
4. Keep refactors local to the scoped behavior.
5. Run focused verification and collect evidence.
6. Record changed files and rationale for reporting.

## Outputs
- Scoped code change with evidence and changed files list.

## Guardrails
- Changed files outside locked root are not allowed.
- Do not silently change product scope.
- Do not write runtime report noise into source directories.
- Reuse local project conventions before introducing new patterns.

## Verification
- Focused tests fail first (when practical), then pass after implementation.
- Changed files list confirms no path escapes.

## Examples
- Adjust one component and one focused test for approved CTA behavior.

## Counterexamples
- While fixing copy, Dev rewrites routing architecture and adds unrelated framework migration.
