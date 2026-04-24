# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `test` buddy.

Inside this session, plain user requests belong to `test`. Do not ask the user to prefix normal product-mode requests with `switch test:`. The runtime adapter converts plain text to the canonical BuddySwitch wire form before resolve.

## Canonical Loop

1. Resolve with `scripts/switch_runtime.py resolve`.
2. Choose exactly one `skill_id` from `resolve_context.skills`.
3. Execute the selected BuddySwitch `SKILL.md`.
4. Persist with `scripts/switch_runtime.py persist`.
5. Continue from `refreshed_context` when it is valid.

## Buddy Lock

- The active buddy is `test`.
- Same-buddy canonical `switch test...:` commands are allowed.
- Cross-buddy canonical switches are external handoffs and must not execute in this session.
- Durable BuddySwitch state lives in the projected `buddyswitch/objects/**` and `buddyswitch/content/runs/**` paths.
- `runs/raw/` and `projects/app/.runtime/` are instance-local scratch.
