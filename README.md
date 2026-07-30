# BuddySwitch Workspace

BuddySwitch is a launcher-managed control layer for role-configured actor instances.

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
./buddyswitch-codex instance start --role pm
```

## Product Runtime Loop (Runless)

1. Call context discovery (`context.get` or `context.summarize`).
2. Pick explicit target ids (`track_id`, `task_id`, `artifact_id`) and decide whether any host-private file belongs under `$BUDDYSWITCH_ACTOR_PRIVATE_DIR`.
3. Write product objects with env tools:
   - `task.*`, `track.*`, `artifact.*`
4. Write active-instance private host files directly under `$BUDDYSWITCH_ACTOR_PRIVATE_DIR`, then attach them explicitly with `artifact.attach_file` using `source_path` when they must become product-readable.
5. Summarize what was written.

No `prepare/persist` lifecycle is required.

Direct local runtime diagnostics use:

```bash
./buddyswitch-codex env status
```

An active Actor obtains exact Tool schemas through `context.get`.

## Workspace Layout

Launcher product mode:

- `${BUDDYSWITCH_SHARED_ROOT}` shared launcher root
- `${BUDDYSWITCH_SHARED_ROOT}/state` canonical BuddySwitch state
- `${BUDDYSWITCH_SHARED_ROOT}/instances/<actor-id>/workspace` runtime workspace per actor
- `${BUDDYSWITCH_SHARED_ROOT}/project/workspace` shared product source
- `${BUDDYSWITCH_SHARED_ROOT}/instances/<actor-id>/workspace/.agents/skills` instance-only runtime skills

Canonical product state and private local paths:

- `buddyswitch/objects/tracks/*.json`
- `buddyswitch/objects/artifacts/*.json`
- `instances/<actor-id>/taskbox/<role>/tasks/*.json`
- `instances/<actor-id>/taskbox/<role>/history.md`

Private workspace private files are active-instance-local under `$BUDDYSWITCH_ACTOR_PRIVATE_DIR` (`workspace/private`); they are not product-readable object state until an explicit artifact attachment or other product write publishes them.

## Manage Instances

```bash
./buddyswitch-codex instance roles
./buddyswitch-codex instance start --role <role>
./buddyswitch-codex instance list
./buddyswitch-codex instance delete <actor-id>
```

Read actor-scoped Demand projections without exposing mutations:

```bash
./buddyswitch-codex demand list --actor <actor-id>
./buddyswitch-codex demand get <demand-id> --actor <actor-id>
```

## Test

Use the repository supervisor for every test run:

```bash
./buddyswitch-test focused tests/unit/actor/test_session.py
./buddyswitch-test full
```

`focused` accepts explicit files or node IDs. `full` runs the unit, integration,
process, and system tiers serially, then checks shell syntax and diff hygiene.

## Canonical Runtime Sources

Root launchers are thin stable interfaces. `pyproject.toml` is the sole
package/build declaration.

- `pyproject.toml` for package build and installed-distribution ownership.
- `src/buddyswitch/catalog/manifest.toml` for the environment manifest.
- `src/buddyswitch/env/tool_runtime/definition.py` for `ToolDefinition` / `ActionDefinition` protocol and schema validation.
- `src/buddyswitch/env/tool_runtime/context.py` for host-owned `ToolContext` capabilities that gate runtime-state access.
- `src/buddyswitch/env/tool_runtime/results.py` for canonical env.tool result/rejection shaping.
- `src/buddyswitch/env/tool_runtime/registry.py` for runtime discovery, catalog/semantics projection, and selected tool dispatch.
- `src/buddyswitch/modules/<component>/private/adapters/tool/{tool.py,_impl.py}` for a component-owned Tool entrypoint and private implementation.
- `src/buddyswitch/env/tools/<tool>/{tool.py,_impl.py}` for a not-yet-migrated dynamically discovered Tool entrypoint and private implementation.
- `src/buddyswitch/runtime_kernel/protocol.py` for the runtime broker protocol envelope.
- `src/buddyswitch/runtime_kernel/dispatcher.py` for supported broker methods: `env.tool`, `ping`, `status`.
- `src/buddyswitch/contracts/prepare-turn-context.json` for the context payload contract.
- `src/buddyswitch/contracts/{pm,design,dev,market,test}.md` for role-specific runtime boundaries.
- `src/buddyswitch/launcher/assets/roles/<role>/AGENTS.md` for Role bootstrap guidance.
- `tests/` for behavior and consistency gates.
