# S5 C1 ToolHost Source and Consumer Snapshot

> R1 source snapshot preserved for traceability. Hub return review supersedes
> its two unproved classifications: `new_id()` had no current consumer, and the
> Broker re-export facade had no current consumer or protected contract.

## Snapshot identity

| Field | Value |
|---|---|
| Source commit | `a61951fe63ecc4dd8cf03b8c0256fbfb11d12227` |
| Runtime source digest | `0f9c35e6a6431bd43974026ec41ea541babce6a63809e49fb78b108b1099af9b` |
| Distribution digest | `15026280b38866b282b6bf9dd73c2d2ee1cdebe49d8ee2fdb964ecb9d95ba2a8` |
| Runtime verification | `ok=true`, package `0.1.0`, Python `3.13` |
| Refresh date | `2026-08-04` |

This snapshot is the C1 planning source. An executor must compare its starting
identity and consumer representations before editing. Equivalent later source
requires a new hub refresh; it is not silently assumed.

## Current owner graph

```text
application.build
  -> configure explicit component Tool registrations
  -> env.tool_runtime.registry
       -> explicit registration map
       -> dynamic env.tools package scan/import
       -> active-Task gate
       -> central Role authorization import
       -> broad ToolContext construction
  -> component Tool invoke

env client / native MCP / runtime broker
  -> the same registry catalog and dispatch path
```

All eight current product Tools are already selected explicitly by application
composition:

```text
artifact, context, demand_sys, evidence, message, search, task_sys, track
```

The current package scan discovers zero Tool packages. The tracked
`src/buddyswitch/env/tools/__init__.py` and scanner still exist. A local empty
`env/tools/task/` filesystem directory is not tracked runtime source and is not
part of the migration claim.

## Current physical owners

| Current path | Current responsibility | Final C1 owner |
|---|---|---|
| `env/tool_runtime/definition.py` | Tool/Action schema and registration contract | `foundation/tool_runtime/definition.py` |
| `env/tool_runtime/registry.py` | catalog, semantics, gates and dispatch plus obsolete scanner | `foundation/tool_runtime/registry.py` |
| `env/tool_runtime/context.py` | ToolContext plus unrelated private/browser/domain/repo bags | `foundation/tool_runtime/context.py` after narrowing |
| `env/tool_runtime/results.py` | canonical result/rejection shaping | `foundation/tool_runtime/results.py` |
| `env/tool_runtime/auth_feedback.py` | authorization rejection projection | `foundation/tool_runtime/auth_feedback.py` |
| `env/tool_runtime/native_mcp.py` | native Tool names/schema projection | `foundation/tool_runtime/native_mcp.py` |
| `env/tool_runtime/broker_client.py` | zero-consumer Broker re-export at R1 return | R2 retains no facade unless a current production consumer or protected contract proves it necessary |
| `env/tool_runtime/daemon_client.py` | generic Daemon transport | `foundation/daemon/client.py` |
| `env/tool_runtime/role_auth.py` | current product/Role permission policy | `runtime_support/role_auth.py` until S6 |
| `env/client.py` | human/admin broker-routed Tool CLI | `foundation/tool_runtime/client.py` |
| `launcher/env_tool_mcp_server.py` | stdio native MCP host | `foundation/tool_runtime/mcp_server.py` |
| `env/tool_runtime/__init__.py` | package root | `foundation/tool_runtime/__init__.py` |

Moves are direct. No old-path re-export, alias, fallback or import shim is
allowed.

## Scanner and registry facts

`registry.py` currently owns both explicit registration and a second source of
truth:

- `pkgutil.iter_modules(buddyswitch.env.tools.__path__)`;
- dynamic `importlib.import_module` of `buddyswitch.env.tools.<id>.tool`;
- definition and load-error caches;
- duplicate detection between discovery and explicit registrations.

The final registry has only explicitly configured `ToolRegistration` values.
Duplicate or invalid registrations fail application construction/activation.
Unknown Tool/action requests continue to return the same structured terminal
failure. There is no dynamic Tool import and no discovery-shaped test probe.

## ToolContext facts

Current used host facts/capabilities are:

- identity profile, `role_id`, instance path/payload, manifest/path and
  invocation metadata;
- `actor_directory` and `signal_delivery`;
- consumed `now()` behavior. R1 review found no current consumer for `new_id()`.

The only product references through the broad `repos` bag are:

1. Artifact derives the Actor-private root through
   `context.repos.runtime_files.actor_private_dir(context.instance_payload)`;
2. Evidence derives a timestamp through `context.repos.runtime_files.now_iso()`.

C1 replaces them with an explicit host fact (`actor_private_root`) and existing
`context.now()` respectively. The following broad or unused ToolContext
surfaces are retired, not preserved in another bag:

- `DomainAccess` and `RepoAccess`;
- `ActorPrivateAccess`;
- `BrowserAccess`;
- `rules`, `repos`, `actor_private` and `browser` fields;
- test-only contracts whose sole purpose is to keep those surfaces alive.

Actor-private filesystem behavior and Browser behavior remain current
Foundation capabilities, but neither is a generic ToolContext service locator.

## Role policy boundary

`role_auth.py` names product permissions and Role manifest semantics. It cannot
be owned by product-neutral ToolHost. C1 moves the current policy intact to
`runtime_support/role_auth.py` and application activation supplies the
authorizer to ToolHost.

This is a temporary physical owner for a still-current S6 responsibility, not
a compatibility track. S6 later replaces central Role truth. C1 must preserve:

- all manifest Roles can use current registered permissions;
- unknown Roles are denied;
- unknown permissions are denied;
- authorization receipts and terminal rejection semantics remain exact.

No generic DI container is introduced. ToolHost receives the one capability it
needs through an explicit configuration function or constructor-level callable
owned at application composition.

## Baseline evidence

### ToolHost behavior

Run `fc856633c1f942b0a15f7d2e13dd74ef`:

```text
63 passed, 123 subtests
```

It covers architecture, ToolContext binding, Actor profile construction,
catalog/schema projection, native MCP, process dispatch and clean runtime.

### Neighboring Web/cleanup preservation

Run `d9048d5075ee4d529580f5a32c216eda`:

```text
83 passed, 42 subtests
```

### Neighboring Browser preservation

Run `81ea8226d61f44908ac341e3ba679724`:

```text
110 passed, 27 subtests
```

All run roots and attributable processes were absent after proof. These are
entry baselines, not acceptance of the future C1 candidate.

## Final-topology preflight

Preflight `S5TOOLP-20260804-01` simulated direct module relocation and complete
consumer import rewriting in memory. It proved:

- twelve direct source moves are acyclic when the package root is included;
- ten moved Foundation modules import no concrete module or Role implementation;
- old Tool runtime imports are zero after complete rewrite;
- explicit catalog IDs are exactly the eight current Tools;
- discovered IDs are empty;
- current `context.now()` is a valid replacement for Evidence time;
- Actor-private root can be resolved as an explicit host fact;
- no current product consumer needs the retired broad context surfaces.

Preflight is feasibility evidence. Candidate acceptance still requires real
source, installed-runtime and consumer-path proof.

## Adjacent work explicitly deferred

- Track routes and generic cleanup projection: C2;
- Browser ownership: C3;
- identity/state/process relocation: C4;
- Runtime Broker/Daemon relocation: C5;
- final Role policy/RoleHost: S6.
