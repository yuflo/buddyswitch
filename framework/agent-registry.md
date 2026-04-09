# Buddy Registry (Env Source)

BuddySwitch no longer uses a separate hardcoded agent registry.

## Source Of Truth

All buddy definitions come from `buddyswitch/manifest.toml`:

- `id`
- `label`
- `scope`
- `skills`
- `permissions`

## Runtime Resolution

- Parser validation: `scripts/parse_switch.py`
- Codex routing: `scripts/codex_router.py`
- Skill docs: `buddyswitch/skills/<buddy>/<skill>/SKILL.md`

## Current Core Model

- `pm` owns track lifecycle.
- Other buddies read track context and produce artifacts.
- Tracks and artifacts are persisted as object dumps under `buddyswitch/objects/`.
