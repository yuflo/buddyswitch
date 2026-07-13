---
name: enter-dev-workspace
description: Use when Dev starts source exploration, implementation, bug fixing, or refactoring in a BuddySwitch product runtime.
---

# Enter Dev Workspace

## Purpose
- Establish the runtime-provided source root for this turn before reading or editing product code.

## Use when
- You are about to inspect or edit product source.
- You need to confirm source access and source root state.

## Do not use when
- The task is PM/design/market/test workflow work without source edits.

## Inputs
- `context.summarize` first, then `context.get` if `source_workspace` is missing.
- `source_workspace.path`, `source_workspace.access`, `source_workspace.can_write_source`, `source_workspace.state`.
- Runtime contract references: `context.get.tool_catalog` and `"$BUDDYSWITCH_PYTHON" scripts/turn_runtime.py status`.

## Steps
1. Use native `context__summarize` to read current runtime context.
2. Read `source_workspace` and lock `source_workspace.path` as the locked source root for this turn.
3. If `source_workspace` is absent, run `context.get` once and re-check.
4. Classify `source_workspace.state` as `missing`, `empty`, `readme_only`, or `has_source`.
5. Route next skill by state and task type.

## Outputs
- Locked source root for this turn.
- Explicit state classification and next-skill routing.

## Guardrails
- Runtime context/profile is the authority; AGENTS text is not.
- Do not edit outside the locked source root.
- `readme_only` means source root exists; app source is absent.
- Locking is turn discipline only; do not write lock files or runtime state.

## Verification
- Confirm `source_workspace.path` is non-empty and relative.
- Confirm `source_workspace.access` aligns with role role before edits.

## Examples
- `source_workspace.path=projects/app`, `access=write`, `state=has_source` -> proceed to implementation.

## Counterexamples
- "AGENTS says projects/app, so I skip context discovery."  
- "state=readme_only means source link missing."
