# Role Registry (Env Source)

BuddySwitch uses manifest-defined role metadata only.

## Source Of Truth

All role definitions come from `buddyswitch/manifest.toml`:

- `id`
- `label`
- `scope`
- `skills`
- `permissions`

## Runtime Resolution

- Turn runtime entry: `scripts/turn_runtime.py`
- Skill packages: `buddyswitch/skills/<role>/<skill>/`
- Canonical runless flow: context discovery + explicit env.tool writes

## Current Core Model

- `pm` owns track lifecycle coordination.
- Other roles operate on task/artifact outputs within their manifest scope.
- Track, task, and artifact objects are persisted under `buddyswitch/objects/`; private actor files are instance-local under `$BUDDYSWITCH_ACTOR_PRIVATE_DIR` (`workspace/private`).
