# BuddySwitch Workspace

BuddySwitch is a launcher-managed control layer for buddy-locked Codex instances.

The runtime model is runless:
- runtime broker methods are `env.tool`, `ping`, `status`;
- turns are disposable by default;
- durable state is written explicitly via product tools.

## Quick Start

Development mode:

```bash
codex
```

Product mode:

```bash
./buddyswitch-codex instance start --buddy pm
```

## Product Runtime Loop (Runless)

1. Call context discovery (`context.get` or `context.summarize`).
2. Pick explicit target ids (`track_id`, `task_id`, `artifact_id`, `handoff_id`, buddybox path).
3. Write durable outputs with env tools:
   - `task.*`, `track.*`, `artifact.*`, `handoff.*`, `buddybox.*`
4. Summarize what was written.

No `prepare/persist` lifecycle is required.

Runtime env tool operations use:

```bash
python3 scripts/env/client.py <resource> <operation> ...
```

## Workspace Layout

Launcher product mode:

- `${BUDDYSWITCH_SHARED_ROOT}` shared launcher root
- `${BUDDYSWITCH_SHARED_ROOT}/state` canonical BuddySwitch state
- `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace` runtime workspace per buddy
- `${BUDDYSWITCH_SHARED_ROOT}/project/workspace` shared product source
- `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace/.agents/skills` instance-only runtime skills

Canonical state paths:

- `buddyswitch/objects/tracks/*.json`
- `buddyswitch/objects/tasks/*.json`
- `buddyswitch/objects/artifacts/*.json`
- `buddyswitch/objects/handoffs/*.json`
- `buddyswitch/content/buddybox/<buddy>/**`

## Context Panel

```bash
python3 scripts/serve_context_panel.py
```

Open `http://127.0.0.1:8765/` and click `Refresh workspace`.

## Manage Instances

```bash
./buddyswitch-codex instance buddies
./buddyswitch-codex instance start --buddy <buddy>
./buddyswitch-codex instance list
./buddyswitch-codex instance open <instance-id>
./buddyswitch-codex instance delete <instance-id>
```

## Architecture Docs

- `framework/docs/architecture-overview.md`
- `framework/docs/turn-runtime-spec.md`
- `framework/docs/skill-runtime-shared-rules.md`
- `framework/docs/track-registry.md`
- `framework/docs/interface-spec.md`
