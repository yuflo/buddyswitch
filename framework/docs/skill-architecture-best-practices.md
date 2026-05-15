# BuddySwitch Skill Architecture Best Practices (Runless)

## Runtime Model

BuddySwitch is a deterministic control layer around host execution.

- Codex discovers and executes native skills from `.agents/skills`.
- BuddySwitch exposes context discovery and explicit env.tool writes.
- Native skills should write product-readable outputs through artifact/handoff tools; use buddybox only for active buddy private local working files.

## Package Contract

Skill registry source of truth is `buddyswitch/manifest.toml`:

- `[[skills]]`: `id`, `path`
- `[[buddies]]`: buddy membership, artifact kinds, permissions

Runtime materialization must remain instance-scoped under `.agents/skills` and must not be tracked at repo root.

## Runless Output Discipline

- Use `python3 scripts/env/client.py ...` through broker method `env.tool`.
- Use explicit ids and explicit object writes.
- Do not rely on deprecated prepare/persist lifecycle.
- Do not write runtime state by editing JSON files directly.

## Shared Runtime Guidance

- `framework/docs/turn-runtime-spec.md`
- `framework/docs/skill-runtime-shared-rules.md`
- `framework/docs/track-registry.md`
