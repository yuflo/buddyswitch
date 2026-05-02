# Buddy Registry (Env Source)

BuddySwitch uses manifest-defined buddy metadata only.

## Source Of Truth

All buddy definitions come from `buddyswitch/manifest.toml`:

- `id`
- `label`
- `scope`
- `skills`
- `permissions`

## Runtime Resolution

- Turn runtime entry: `scripts/turn_runtime.py`
- Skill packages: `buddyswitch/skills/<buddy>/<skill>/`
- Canonical prepare/persist flow: `framework/docs/turn-runtime-spec.md`

## Current Core Model

- `pm` owns track lifecycle coordination.
- Other buddies operate on task/artifact outputs within their manifest scope.
- Track, task, artifact, and run state are persisted under `buddyswitch/objects/` and `buddyswitch/content/runs/`.
