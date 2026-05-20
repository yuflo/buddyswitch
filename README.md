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
2. Pick explicit target ids (`track_id`, `task_id`, `artifact_id`) or buddybox `logical_name` values for private files.
3. Write product objects or active buddy private local files with env tools:
   - `task.*`, `track.*`, `artifact.*`, `buddybox.*`
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

Canonical product state and private local paths:

- `buddyswitch/objects/tracks/*.json`
- `buddyswitch/objects/tasks/*.json`
- `buddyswitch/objects/artifacts/*.json`

Buddybox private files are active-instance-local and tool-managed through `buddybox.*` with `logical_name`; they are not product-readable object state.

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

## Canonical Runtime Sources

- `scripts/env/tool_runtime/definition.py` for `ToolDefinition` / `ActionDefinition` protocol and schema validation.
- `scripts/env/tool_runtime/context.py` for host-owned `ToolContext` capabilities that gate runtime-state access.
- `scripts/env/tool_runtime/results.py` for canonical env.tool result/rejection shaping.
- `scripts/env/tool_runtime/registry.py` for runtime discovery, catalog/semantics projection, and selected tool dispatch.
- `scripts/env/tools/<tool>/tool.py` as each tool's only public runtime entrypoint (`DEFINITION` + `invoke`).
- `scripts/env/tools/<tool>/_impl.py` for selected private implementation invoked by `tool.py`.
- `scripts/runtime_kernel/protocol.py` for runtime broker protocol envelope.
- `scripts/runtime_kernel/dispatcher.py` for supported broker methods: `env.tool`, `ping`, `status`.
- `framework/contracts/prepare-turn-context.json` for context payload contract compatibility.
- `framework/contracts/workspace-projection.json` for context panel workspace projection shape.
- `framework/contracts/{pm,design,dev,market,test}.md` for role-specific runtime boundaries.
- `tests/` for behavior and consistency gates.
