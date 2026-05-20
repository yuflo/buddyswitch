# Black-Box Tool Runtime Memo

Date: 2026-05-20
Status: architecture memo; no runtime code changes implemented here.

## Background Problem

BuddySwitch has already moved from a central env tool registry to per-tool packages:

```text
scripts/env/tools/<tool>/
  contract.py
  semantics.py
  cli.py
  handlers.py
  service.py
```

That structure improved independent tool development, but it is still not true black-box tool
encapsulation.

Current tool services still directly import BuddySwitch internals such as `env.domain`,
`env.repos`, manifest helpers, runtime files, browser state, and per-tool contract modules. This
means each tool is modular, but not opaque. A tool implementation can still reach across system
boundaries, and the host runtime still knows too much about how tool packages are structured.

The current bottleneck is therefore not tool discovery. The bottleneck is the remaining boundary
between:

- the host runtime that should discover, validate, route, authorize, and format;
- the tool implementation that should be replaceable behind a stable protocol;
- BuddySwitch runtime state that should be accessed through a controlled host API, not direct repo
  imports.

## Review Conclusion

The target architecture is clear enough and can remain small:

```text
env.tool request
  -> black-box tool registry
  -> tool protocol validation
  -> selected tool invoke(action, args, context)
  -> ToolContext host capabilities
  -> canonical ToolResult
```

This is a black-box tool runtime, not a plugin platform.

The design is acceptable only if it stays repo-local, in-process, and protocol-driven. Do not add
remote plugin loading, a marketplace, subprocess sandboxes, version negotiation, workflow engines,
event buses, generic DSLs, or a compatibility framework.

## Clean Runtime Baseline

This memo assumes the clean runtime environment repair has already landed.

The host-visible runtime workspace and broker-owned state root are now separate concerns:

```text
runtime workspace -> safe, searchable host surface
runtime state     -> shared/state, broker-owned, env-tool-backed
```

Black-box tool runtime work must preserve that contract. `ToolContext` may call host-owned
`env.repos`, `env.domain`, manifest, browser, and runtime file helpers internally, but tool packages
must not derive storage paths from `workspace_dir`, read or write `buddyswitch/objects/**`, or expose
`buddyswitch/local/buddybox/**` as ordinary workspace storage. Buddybox and runtime object access
must remain capability calls backed by the state root selected by the broker environment.

## Architecture Target

Introduce one small host-owned runtime package:

```text
scripts/env/tool_runtime/
  definition.py
  context.py
  results.py
  registry.py
```

Responsibilities:

| File | Owns | Does not own |
| --- | --- | --- |
| `definition.py` | `ToolDefinition`, `ActionDefinition`, input/output schema metadata, effect metadata | tool business behavior |
| `context.py` | `ToolContext` and host capabilities for runtime objects, buddybox, browser, manifest, identity, time/id helpers | concrete tool workflows |
| `results.py` | canonical success/rejection builders and output validation | per-tool state mutation |
| `registry.py` | repo-local tool discovery, catalog projection, selected tool invocation | compatibility shims, old per-tool module formats |

Each tool exposes one public entrypoint:

```text
scripts/env/tools/<tool>/tool.py
```

That file owns:

- `DEFINITION`: the externally discoverable protocol for the tool;
- `invoke(action, args, context)`: the only host-called implementation entrypoint.

Tool private implementation can be split behind `tool.py`, but the host runtime must not depend on
private files.

## Clean Tool Boundary

A tool package is black-box only when these rules hold:

1. Host runtime imports only `env.tools.<tool>.tool`.
2. Public tool entrypoints import only `env.tool_runtime.*` and local private files.
3. Public tool entrypoints do not import `env.repos.*`, `env.domain.*`, `runtime_kernel.*`,
   `env_manifest`, or sibling tools.
4. Tool state access goes through `ToolContext`.
5. Tool responses are created through `ToolResult` helpers.
6. Catalog, CLI, and context discovery are generated from `ToolDefinition`.
7. Adding or deleting a tool does not require editing `router.py`, `dispatch.py`, `catalog.py`, or
   shared skills.

## ToolContext Host Capabilities

`ToolContext` should be concrete and small. It should expose only capabilities that current tools
actually need:

```text
context.active_buddy
context.instance_id
context.instance_json
context.instance_payload
context.manifest
context.manifest_path
context.objects
context.buddybox
context.browser
context.catalog
context.now()
context.new_id(prefix)
```

The host owns these capabilities. Tools call the capability; they do not import the underlying
repos or runtime files.

The first implementation should keep capabilities blunt:

- `objects`: explicit methods for current runtime object reads/writes used by existing tools.
- `buddybox`: active-buddy-private file methods backed by the broker-owned state root.
- `browser`: search/browser session methods needed by `search`.
- `manifest`: read-only buddy and permission facts.
- `catalog`: registry projections needed by `context.get` and `context.summarize`.

Do not introduce a generic object query language. Do not introduce a permission framework beyond
what existing runtime behavior needs.

## External Protocol Surface

`ToolDefinition` is the only source for tool metadata exposed outside the tool:

```text
tool id
title
description
actions
input schema per action
output schema per action
required permission/effect metadata
read/write durability metadata
```

Runtime discovery surfaces continue to exist:

```text
context.get.tool_catalog
context.get.operation_semantics
context.summarize.tool_affordances
python3 scripts/turn_runtime.py status
python3 scripts/env/client.py <tool> ...
```

But these surfaces must be projections of `ToolDefinition`, not parallel hand-written registries.

## One-Time Replacement Rule

This migration should be a direct replacement, not a long transition.

Do not keep old and new tool systems side by side after the implementation lands. The implementation
branch may temporarily edit old files while migrating, but the final state must remove the old
runtime ownership surfaces:

```text
scripts/env/tools/<tool>/contract.py
scripts/env/tools/<tool>/semantics.py
scripts/env/tools/<tool>/handlers.py
scripts/env/tools/<tool>/cli.py
scripts/env/tools/<tool>/service.py
```

Final runtime ownership should be:

```text
scripts/env/tool_runtime/*.py
scripts/env/tools/<tool>/tool.py
scripts/env/tools/<tool>/internal*.py   # optional private files
```

There should be no compatibility adapter that reads both old `contract.py` and new `tool.py`. There
should be no fallback registry. There should be no dual catalog source.

## Residual Cleanup Requirements

The implementation is not complete until these residual paths are gone or proven private-only:

1. `env.tools.catalog` no longer reads `TOOL_SPEC` or `ACTION_SEMANTICS`.
2. `env.tools.dispatch` no longer reads `HANDLER_SPECS`.
3. `env.client` no longer loads per-tool `cli.py`.
4. `context.get.tool_catalog` is generated from `ToolDefinition`.
5. `turn_runtime.py status` is generated from the same registry projection.
6. Shared skills still point to runtime discovery and do not name `tool.py` internals.
7. Tool public files do not import `env.repos`, `env.domain`, or sibling tool packages.
8. Tests reject the old module names as runtime surfaces.

Historical docs under `docs/spec/**` may mention old files as history, but active architecture docs,
skills, launcher guidance, and runtime tests must describe only the new black-box runtime.

## Minimal Migration Order

The shortest validated implementation loop is:

1. Add failing architecture tests for the final black-box boundary.
2. Add `scripts/env/tool_runtime/definition.py`, `context.py`, `results.py`, and `registry.py`.
3. Migrate one simple tool, preferably `message` or `task`, to `tool.py`.
4. Prove catalog, CLI, broker dispatch, and focused behavior tests pass for that tool.
5. Migrate the remaining tools.
6. Delete old per-tool public modules.
7. Update runtime discovery tests and skill boundary tests.
8. Run broad env/tool/runtime verification.

Do not build a compatibility bridge to make old and new tools coexist as a supported state. If a
temporary local step is needed during development, remove it before completion.

## Fit With BuddySwitch Modular Architecture

This target keeps the existing BuddySwitch layering, but tightens the tool boundary:

```text
SKILL
  -> runtime discovery
  -> env.tool
  -> black-box tool runtime
  -> ToolContext capabilities
  -> BuddySwitch runtime state
```

`SKILL` remains workflow guidance. It does not become a tool manual.

The host runtime owns discovery, validation, routing, identity, active instance boundaries, response
shape, and access to runtime state.

The tool owns only its declared capability and implementation behind `invoke`.

BuddySwitch object storage and business rules remain inside host-owned capabilities. The tool layer
uses those capabilities; it does not reach around them.

## Non-Goals

Do not add:

- remote plugin loading;
- third-party marketplace support;
- subprocess or container execution;
- version negotiation;
- compatibility adapters for old tool package formats;
- fallback registries;
- workflow engines;
- event buses;
- generic object frameworks;
- permission systems beyond the current runtime needs;
- schema DSLs beyond simple JSON-compatible action input/output schemas.

## Review Checks

The architecture is sufficiently clear and not overbuilt if these checks are true:

1. A new tool can be understood by reading one public `tool.py`.
2. The host can list, validate, and call a tool without knowing its private files.
3. A tool cannot mutate BuddySwitch state except through `ToolContext`.
4. Removing a tool means deleting its package and its registration/discovery entry, with no central
   branch cleanup.
5. Runtime discovery has one source of truth.
6. Shared skills do not change when a tool implementation changes.
7. There is no old/new dual path in the completed branch.

## Verification Targets

Required focused tests:

```text
tests/test_black_box_tool_runtime.py
tests/test_env_tool_package_independence.py
tests/test_env_tool_response_contract.py
tests/test_env_tool_payload_contract.py
tests/test_env_client_payload_cli.py
tests/test_runtime_skills.py
tests/test_repo_consistency.py
```

Required assertions:

- public tool entrypoints import only the tool runtime SDK and local private files;
- registry imports no tool private implementation until selected invocation;
- selected invocation imports no sibling tool;
- catalog and CLI are generated from one definition source;
- old per-tool public modules are absent after migration;
- response contracts still report `ok`, `state_changed`, `durability`, `permission_boundary`,
  `why_blocked`, and actionable next steps;
- focused behavior tests pass for every shipped tool;
- broad runtime broker and turn integration tests pass.
- clean runtime environment regression tests still pass, including workspace/state separation and
  host-visible exploration without denied runtime-state projections.

## Decision

Proceed with the black-box runtime only as a direct replacement.

The acceptable final architecture is smaller than a plugin platform but stronger than the current
per-tool package layout. It gives BuddySwitch a clean tool boundary, exposes clear input/output
protocols, supports registration-style add/delete, and removes the remaining implementation coupling
without adding future compatibility burden.
