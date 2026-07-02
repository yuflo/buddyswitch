# search.open_browser browser ensure source root issue

## Context

`bfcff30 feat: implement lazy browser cockpit release` added `_ensure_browser_runtime()` in `scripts/env/tools/search/_impl.py`.

When `search.open_browser` sees that an instance has no recorded `browser_port`, `_ensure_browser_runtime()` runs:

```text
buddyswitch-codex env browser ensure --instance <actor-id>
```

The implementation introduced in `bfcff30` used:

```python
env_profiles.ROOT / "buddyswitch-codex"
cwd=env_profiles.ROOT
```

## Runtime Boundary

Runtime env tools can run from a sparse execution workspace.

The sparse execution workspace may not contain the full source checkout or the expected launcher surface.

The launcher/runtime environment already carries the source checkout path through:

```text
BUDDYSWITCH_REPO_ROOT
```

`tools/launcher/env.sh`, `tools/launcher/env_tool_mcp_server.py`, and `scripts/runtime_kernel/dispatcher.py` set or propagate `BUDDYSWITCH_REPO_ROOT`.

## Removed Patch

`d974caf Update search env tool resource handling` added `_source_repo_root()` and changed the default browser ensure command to use `BUDDYSWITCH_REPO_ROOT` when set.

It changed the default ensure command from:

```python
str(env_profiles.ROOT / "buddyswitch-codex")
cwd=env_profiles.ROOT
```

to:

```python
repo_root = _source_repo_root()
str(repo_root / "buddyswitch-codex")
cwd=repo_root
```

It also added:

```text
test_search_open_browser_default_ensure_uses_source_launcher_from_sparse_runtime
```

## Issue

The patch addressed a path/source-root risk created by combining:

- sparse execution workspaces
- `search.open_browser`
- missing instance `browser_port`
- lazy browser ensure via a nested `buddyswitch-codex env browser ensure` subprocess

The patch did not come from a recorded current failure in this branch.

The underlying boundary is that env tool code shells back into the launcher CLI and therefore depends on source checkout path and current working directory.

The cleaner boundary would keep browser lifecycle ensure in launcher/runtime-owned code or expose it through an explicit runtime service or broker API, instead of making `search.open_browser` construct and execute the launcher CLI path.
