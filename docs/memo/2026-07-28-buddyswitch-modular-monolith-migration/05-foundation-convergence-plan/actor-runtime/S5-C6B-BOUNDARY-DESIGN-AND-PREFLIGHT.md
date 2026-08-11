# S5 C6B Boundary Design and Preflight

## Selected design

```text
application / Demand / current Launcher hosts
                      |
                      v
foundation/actor_runtime
  |-- capability state and resolution
  |-- Codex runtime descriptor validation
  |-- parent Actor Session
  |-- side-thread start and lifecycle
  `-- side-thread registry
          |
          +--> foundation/app_server
          `--> foundation/process_runtime
```

The package root is inert. Consumers import concrete modules directly; there
is no compatibility facade or package-root re-export.

The shortest reviewed physical shape is:

```text
foundation/actor_runtime/
  __init__.py
  capability.py
  codex_runtime.py
  session.py
  side_thread.py
  side_thread_lifecycle.py
  side_thread_registry.py
```

This mapping is a reviewed hypothesis, not a command transcription. The
executor owns equivalent private naming or segmentation inside this exact
semantic boundary when the final package remains direct, cohesive and free of
duplicate rules.

## Alternatives considered

1. **Selected: session/side runtime first.** This is a complete runnable owner,
   has no Role dependency and mechanically serves current Host Control, CLI,
   Daemon and Demand consumers.
2. **WebHost first: rejected.** Current WebHost imports Launcher Host Control
   and CLI contracts; moving it now would create a Foundation-to-Launcher edge
   or force an oversized unrelated cutover.
3. **CLI contract only: rejected as the next checkpoint.** It is movable but
   does not close a runtime owner or materially reduce the Actor/Web dependency
   bottleneck.

## Positive topology preflight

`S5C6BP-20260811-01` parsed all 285 current production Python modules and
simulated the six owner moves plus every corresponding import edge.

Results:

- current graph: one pre-existing Artifact-private SCC;
- candidate graph: the same one SCC;
- new SCCs: zero;
- forbidden Actor Runtime edges to Launcher, application, modules or
  runtime-support: zero;
- direct external Actor Runtime dependencies: App Server and Process Runtime
  only.

The preflight result is `PASS`.

## Ownership and replacement rules

- Capability, Codex runtime descriptor, parent Session and side-thread
  registry/lifecycle rules each have one direct file owner inside one physical
  Actor Runtime package.
- Existing Host Control, CLI, application and Demand files are mechanical
  consumers only.
- All six retired Launcher files, imports, dynamic module names, source-path
  literals and installed projections disappear atomically.
- Stable instance payload field names, error codes, thread/turn semantics and
  Role-visible behavior do not change.
- No alias, re-export, fallback, dual import path, registry framework or
  generalized Actor service facade is introduced.

## Later-boundary protection

C6B does not move or redesign Role-bound instance start/list authority,
workspace publication, runtime locking, Web routes/assets or CLI command
dispatch. A later checkpoint may add other independently owned Actor lifecycle
files to `foundation/actor_runtime/**`; it may not be required to make C6B
runnable or repair a C6B semantic gap.

## Proof obligations

- direct capability/session/side lifecycle and registry behavior;
- Codex runtime resolution and recorded-runtime validation;
- Host Control, CLI, Daemon and Demand consumer behavior;
- source and installed old-path absence plus installed correspondence;
- no new cycle or forbidden reverse dependency;
- parent-known process/resource cleanup where lifecycle tests start resources;
- current Actor Runtime architecture guidance without a test-only static
  analysis framework.
