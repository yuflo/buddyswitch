# S5 C4 Boundary Design and Preflight

## 1. Decision

C4 is one behavior-preserving checkpoint with three internally coherent
blocks:

```text
Foundation Identity       Foundation State          Foundation Process
model + profiles          locators + atomic JSON    activation + invocation
        |                 + private-delete safety   + start identity
        +-------------------------+-------------------------+
                                  |
                         current direct consumers
```

These are Foundation primitives, not plugin points. They are imported directly
from their owning modules. Package roots stay inert; no facade, service
locator, registry, dynamic discovery or compatibility layer is introduced.

The three blocks remain one handoff because they are small owner moves with the
same broad mechanical consumer rewrite and the same retired `env/**` deletion
boundary. Splitting them into repeated execution/acceptance round trips adds
coordination cost without isolating a distinct product effect. The executor may
implement and verify the blocks incrementally inside one candidate.

## 2. Target physical boundary

The final owners are:

- `foundation/identity/**` for identity models and profile persistence;
- `foundation/state/**` for canonical locators, atomic state primitives and
  the live Actor-private cleanup safety boundary;
- `foundation/process_runtime/**` for activation, invocation and exact process
  start identity.

The source-refresh candidate mapping used for feasibility was:

```text
env/domain/identity.py             -> foundation/identity/<direct module>
env/repos/identities.py            -> foundation/identity/<direct module>
env/repos/runtime_files.py         -> foundation/state/<direct module>
env/repos/actor_private_files.py    -> foundation/state/<live direct module>
runtime_kernel/process_identity.py -> foundation/process_runtime/<direct module>
```

This mapping is a topology witness, not a mandate to copy files verbatim. D-051
and D-059 give the executor local file split and symbol organization inside
those three owners, provided imports remain direct, the surface is no broader
than live demand, and every protected contract remains exact.

## 3. Dependency boundary

Allowed direction:

```text
identity profiles -> identity model + state primitives
state private safety -> state locators
Foundation/module/host consumers -> direct primitive owner
```

Forbidden direction:

- Foundation primitives importing a product module, concrete Role or adapter;
- identity/state/process primitives importing Browser, Broker, Daemon, Web,
  CLI or application composition;
- package-root re-exports used to hide owner placement;
- a generic repository/context/container replacing direct imports;
- C4 code interpreting product payloads or host commands.

## 4. C4 / C5 / C6 cut line

C4 may mechanically edit a later host file only to replace an import of a C4
primitive. It may not move or redesign that host.

Explicitly C5-owned and unchanged in ownership:

- `runtime_kernel/{broker,client,coordinator,dispatcher,lifecycle,protocol,server}`;
- Daemon contracts, mailbox, triggers, state, transport, host and handler
  execution;
- Broker/Daemon protocol, ordering, errors and lifecycle semantics.

Explicitly C6-owned and unchanged in ownership:

- Actor/App/Web/CLI host physical convergence and packaged interface assets.

This makes C4 independently runnable. No C5/C6 implementation is required to
remove `env/**` or the old process-identity module.

## 5. Preflight result

Preflight `S5C4P-20260806-01` parsed the complete current Python package with
the verified Python 3.13 runtime and applied the candidate owner mapping in
memory.

```text
candidate owner moves:                 5
zero-consumer owner deletion:          1
direct old-import representations:     68
new strongly connected components:     0
Foundation product/Role imports:       0
```

The current source already contains ten unrelated strongly connected
components in later technical roots. The hypothetical C4 topology introduces
none and does not claim to repair C5/C6 cycles.

## 6. Acceptance matrix

| Proof class | Required C4 claim |
|---|---|
| Product | accepted component, Web/CLI, Actor-private and service behavior remains observable and exact |
| Contract | identity payloads, canonical state paths/writes, runtime activation and process-record semantics are unchanged |
| Architecture | exactly three direct Foundation primitive owners; no product/Role imports, facade, broad context or new cycle |
| Replacement | `src/buddyswitch/env/**`, old process-identity module/imports/literals and dead helper surfaces are absent |
| Operations | stale PID refusal, parent-known process identity, cleanup ordering and all resources remain exact |
| Correspondence | installed distribution contains the final modules and no retired modules, and runtime verification matches the frozen source |

Architecture proof must stay proportional. Simple path/import/owner assertions
are sufficient. If a proposed test needs data-flow analysis, lexical-scope
simulation, alias-flow tracking or another test-only static-analysis engine,
the invariant must be reformulated at a simpler stable boundary before work
continues.

## 7. Stop conditions

Return `REPLANNING REQUIRED` only if current facts require:

- a persisted path/schema/environment-variable change;
- a product Public/semantic change or Role policy change;
- moving or redesigning Broker/Daemon/Actor/App/Web/CLI ownership;
- compatibility, dual writes, fallback imports or an intermediate unrunnable
  path;
- a new plugin/registry/container/bus or a broad shared service;
- another checkpoint to make C4 runnable.

A stale path example, an omitted mechanical consumer, a different equivalent
private file split or a dynamically corrected valid test target is executor
work inside the authorized boundary, not a stop condition.
