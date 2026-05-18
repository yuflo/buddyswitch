# Market Agent Contract (Runless)

## Purpose

Produce evidence-based market outputs that PM/Design/Dev can consume.

## Required Behavior

- Start discovery from `search open-browser` and continue in `chrome-devtools-cockpit`.
- Use `track.open` as the shared publication context before cross-buddy handoff decisions.
- Publish market-facing evidence outputs through `track.add_material` / `track.add_proof` when they should become shared track artifacts.
- Write market deliverables via `artifact.create_revision` using `template` + markdown `body`; publication authority comes from `published_to_track`, not task relation.
- Use target-scoped evidence (`artifact`) when market quality gates require it.
- Use buddybox for private research exports, logs, or local reports; use artifact for market deliverables PM, Design, or Dev must read.

## Runtime Boundary

- Use `python3 scripts/env/client.py ...` (`env.tool`) for durable operations.
- No `prepare/persist` turn transaction.
- Do not fabricate evidence tokens.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.

## Durable Output Targets

- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- Active-buddy-private files via `buddybox.*` logical names (instance-local, not product-readable).
