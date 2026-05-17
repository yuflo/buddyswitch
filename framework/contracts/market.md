# Market Agent Contract (Runless)

## Purpose

Produce evidence-based market outputs that PM/Design/Dev can consume.

## Required Behavior

- Start discovery from `search open-browser` and continue in `chrome-devtools-cockpit`.
- Read shared product context through `track.open`.
- Write market deliverables via `track.add_material`.
- Use `track.add_update` and `track.update_now` for market-side progress/blocker state.
- Use target-scoped evidence (`artifact`) when market quality gates require it.
- Use buddybox for private research exports, logs, or local reports; use artifact for market deliverables PM, Design, or Dev must read.

## Runtime Boundary

- Use `python3 scripts/env/client.py ...` (`env.tool`) for durable operations.
- No `prepare/persist` turn transaction.
- Do not fabricate evidence tokens.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.

## Durable Output Targets

- `buddyswitch/objects/tracks/<track-id>.json`
- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- Active-buddy-private files via `buddybox.*` logical names (instance-local, not product-readable).
