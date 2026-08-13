# Context Capability Architecture

## Purpose

Context is the read-only application projection that orients an active Actor
before downstream Tool use. It contributes exactly one Tool, `context`, with
the actions `get`, `summarize`, and `list_sources`.

Context preserves the current Tool schemas, Role authority, ToolResult
success and rejection semantics, filters, visibility, source-workspace facts,
writable-surface facts, Native MCP projection, and runless behavior. It owns
no durable state or resource lifecycle.

## Physical owner

Context has one live capability root:
`src/buddyswitch/modules/context/`.

- `src/buddyswitch/modules/context/module.py` exports the passive Context
  `ModuleAssembly`.
- `src/buddyswitch/modules/context/private/adapters/tool/tool.py` owns the
  Tool definition and invocation entrypoint.
- `src/buddyswitch/modules/context/private/adapters/tool/_impl.py` owns the
  read-only application projection.

Context has no Public package, state, Daemon, Web, CLI, Skill, cleanup,
inbound, or module-local test surface. Its behavior tests remain root-owned
because they cross component, Runtime Broker, package, Role, and process
boundaries.

## Application composition

`src/buddyswitch/application/composition.py` selects Context exactly once and
last. The application builder receives one explicit Context Tool registration;
Context is not filesystem-discovered. Its passive assembly contributes no
surface other than the Tool registration and does not change the existing
Daemon handler order.

## Dependency direction

The owning path is:

```text
Application composition
  -> Context ModuleAssembly (last)
    -> Context-private Tool adapter
      -> Track Public
      -> Task Public
      -> Artifact Public
      -> Communication Public
      -> generic Tool registry, Application Role authority, selected RoleRuntime, and ToolContext facts
```

Context Private consumes Track, Task, Artifact, and Communication only through
their accepted Public operations. It may also consume generic Tool runtime
definitions, registry projections, Role authorization, Tool results, selected
`RoleRuntime` facts, and host-provided identity, invocation, and workspace facts.
It does not import another component's Private package.

Application composition is the only consumer of the Context module. No
consumer imports Context Private, and no Context Public facade exists.

## Preserved contract

`context.get` returns full runtime sections, catalog, operation semantics, and
source/workspace facts. `context.summarize` returns compact candidate and
decision orientation. `context.list_sources` returns source descriptors.

All three actions are read-only, runless, non-durable, and resource-free.
Role-policy preview is projected directly through the generic Role
authorization contract using the selected `RoleRuntime` and Application Tool
authority.
Context does not configure source roots, grant write authority, reserve runs,
write product state, or expose a second registration or compatibility path.
