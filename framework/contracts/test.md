# Test Agent Contract (Runless)

## Purpose

Validate behavior, report pass/fail/blocked outcomes, and persist test evidence explicitly.

## Required Behavior

- Keep test scope explicit.
- Persist smoke or verification reports via `artifact.create_revision`.
- Use `buddybox.write` for durable logs/evidence attachments when needed.

## Runtime Boundary

- Use `python3 scripts/env/client.py ...` (`env.tool`) for durable operations.
- No `prepare/persist` turn transaction.
- Test buddy must not edit source code when profile is read-only.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.

## Durable Output Targets

- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- `buddyswitch/objects/handoffs/<handoff-id>.json`
- `buddyswitch/local/buddybox/test/**` (active buddy private local workspace)
