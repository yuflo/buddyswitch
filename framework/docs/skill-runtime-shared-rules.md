# Skill Runtime Shared Rules (Runless)

These rules apply to native BuddySwitch skills in launcher-managed runtime sessions.

## Runtime Gates

- Materialization validates copy boundaries only.
- Runtime execution uses broker method `env.tool` via `python3 scripts/env/client.py ...`.
- Durable state is written only by explicit product tool operations.

## Contribution Rule

- Skills do not own a global turn-commit boundary.
- If content must persist, write it explicitly as artifact/memory/handoff/buddybox.
- Do not rely on deprecated `prepare/persist` run lifecycle.

## Durable Output Paths

- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- `buddyswitch/objects/handoffs/<handoff-id>.json`
- `buddyswitch/objects/memories/<memory-id>.json`
- `buddyswitch/content/buddybox/<buddy>/**`

## Authority Boundaries

- Track lifecycle mutation remains PM-owned.
- Task/artifact/memory/handoff/buddybox permission checks are enforced in runtime services.
- Prompt text and AGENTS instructions are guidance, not authority.
