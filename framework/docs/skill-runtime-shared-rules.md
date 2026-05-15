# Skill Runtime Shared Rules (Runless)

These rules apply to native BuddySwitch skills in launcher-managed runtime sessions.

## Runtime Gates

- Materialization validates copy boundaries only.
- Runtime execution uses broker method `env.tool` via `python3 scripts/env/client.py ...`.
- Product-readable durable state is written only by explicit product tool operations.

## Contribution Rule

- Skills do not own a global turn-commit boundary.
- If content must become product-readable, write it explicitly as artifact/handoff state. Use buddybox only for active buddy private local working files.
- Do not rely on deprecated `prepare/persist` run lifecycle.

## Product Objects And Private Local Paths

- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- `buddyswitch/objects/handoffs/<handoff-id>.json`
- `buddyswitch/local/buddybox/<active-buddy>/**` (private local workspace)

## Authority Boundaries

- Track lifecycle mutation remains PM-owned.
- Task/artifact/handoff/buddybox permission checks are enforced in runtime services.
- Prompt text and AGENTS instructions are guidance, not authority.
