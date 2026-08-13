---
name: plan-thin-slice-implementation
description: Use when Dev needs to turn non-trivial approved scope into the smallest verifiable implementation slice before editing source.
---

# Plan Thin Slice Implementation

## Purpose
- Turn approved scope into the smallest verifiable vertical slice with a concrete file map.

## Use when
- The change is multi-file, unfamiliar, non-obvious, or carries enough risk that editing immediately would be sloppy.

## Do not use when
- The task is trivial, single-path, and the next focused test is already obvious.

## Inputs
- Approved scope, acceptance criteria, non-goals, and locked source root.
- Existing source clues, failing behavior, and local verification commands.
- Runtime contract references: `context.get.tool_catalog`, `"$BUDDYSWITCH_PYTHON" -m buddyswitch.application.entrypoints.diagnostics status`.

## Steps
1. Restate the target as the smallest verifiable slice that materially advances the approved outcome.
2. Build a file map with every create, modify, and test path needed for that slice.
3. Mark in-scope work, explicit non-goals, and the acceptance checks that prove the slice is done.
4. Pick the focused verification that should fail first and pass after the change.
5. Note stop conditions and escalation points for product semantics, security, privacy, payment, or data migration risk.
6. Keep the plan short; split only when one slice cannot be verified clearly.

## Outputs
- Thin-slice brief with file map, acceptance checks, verification path, and blockers.

## Guardrails
- Do not inflate a short slice into a roadmap.
- Do not edit source before the file map and verification path are concrete.
- Do not add speculative follow-on work to the same slice.

## Stop Conditions
- Product semantics are ambiguous enough to change user-visible meaning.
- Security, privacy, payment, or data migration risk appears inside the slice.
- Required files or verification paths cannot be identified from current context.

## Verification
- The plan names the smallest verifiable slice, file map, non-goals, acceptance checks, and focused verification.

## Examples
- Scope one API handler and one regression test instead of planning a whole auth rewrite.

## Counterexamples
- Produce a broad architecture memo before identifying the next failing test and the exact files to touch.
