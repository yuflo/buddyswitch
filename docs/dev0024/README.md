# BuddySwitch Dev0024 V2 Refactor Spec

## Status

- Date: 2026-04-14
- Status: Draft
- Scope: BuddySwitch v2 hard refactor for object model, runtime/workflow, and skill package contract
- Principle: forward-only iteration with no historical compatibility layer

## Purpose

This directory is the spec workspace for the next BuddySwitch refactor cycle.

The goal is not to incrementally patch the current MVP. The goal is to define a cleaner v2 control plane that is easier to iterate on during active product development.

This spec set freezes four decisions:

1. BuddySwitch keeps `track / task / artifact / run` as the only canonical objects.
2. Artifact lifecycle moves from implicit `latest + suffix` semantics to explicit slot/revision semantics.
3. Runtime and workflow own deterministic control behavior.
4. Skills move from single-file contracts to package contracts.

## Forward-Only Rules

- Do not add compatibility shims for retired fields or legacy behaviors.
- Do not preserve dual authorities when one authority can be made deterministic.
- Do not introduce extra persistent object types for convenience.
- Do not optimize for migration comfort over product iteration speed.

## Non-Goals

- No backfill of historical artifacts.
- No temporary dual-write logic.
- No attempt to preserve old schema surfaces for old runs.
- No implementation-phase task breakdown in this spec set.

## Documents

- [object-model-v2.md](/Users/chen/Dev/buddyswitch/docs/dev0024/object-model-v2.md)
- [runtime-workflow-v2.md](/Users/chen/Dev/buddyswitch/docs/dev0024/runtime-workflow-v2.md)
- [skill-package-v2.md](/Users/chen/Dev/buddyswitch/docs/dev0024/skill-package-v2.md)

## Recommended Reading Order

1. Read `object-model-v2.md` first.
2. Read `runtime-workflow-v2.md` second.
3. Read `skill-package-v2.md` last.

That order reflects the intended implementation order as well:

1. stabilize the object model
2. move control behavior into runtime/workflow
3. align skill packaging and metadata to the new control plane
