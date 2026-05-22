---
name: handle-empty-source-root
description: Use when the locked runtime source root state is missing, empty, or readme_only.
---

# Handle Empty Source Root

## Purpose
- Distinguish runtime/source blockers from legitimate scaffold scope.

## Use when
- `source_workspace.state` is `missing`, `empty`, or `readme_only`.

## Do not use when
- `source_workspace.state` is `has_source`; use implementation or debugging skills.

## Inputs
- Locked source root path and `source_workspace.state`.
- User request plus PM/PRD/approved artifact scope.
- Runtime contract references: `context.get.tool_catalog`, `python3 scripts/turn_runtime.py status`.

## Steps
1. Evaluate state exactly:
   - `missing`: runtime-declared path is absent or invalid.
   - `empty`: root exists with no visible entries.
   - `readme_only`: root exists with README-only content.
   - `has_source`: source content exists.
2. For `missing`, report runtime blocker; stop coding.
3. For `empty` or `readme_only`, scaffold only when scope explicitly requests app/source creation.
4. If scaffold scope is unclear, route decision to PM/user.
5. For `has_source`, continue with normal implementation flow.

## Outputs
- Clear decision: blocker, scaffold allowed, or continue implementation.

## Guardrails
- `readme_only` is present root state, not source-link missing.
- Do not invent product scope or framework defaults.
- If scaffold is allowed, keep all generated files under locked source root.
- Legitimate source-root writes include package files, lockfiles, generated source, tests, and fixtures.

## Stop Conditions
- Scope decision is ambiguous and requires PM/user confirmation.
- Runtime source path is missing and cannot be resolved.

## Examples
- User asks to build a new app and state is `readme_only`: scaffold is allowed.

## Counterexamples
- State is `readme_only`, request is only copy fix, but Dev scaffolds a full app anyway.
