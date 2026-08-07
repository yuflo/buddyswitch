# S5 C5B Boundary Design and Preflight

## Accepted topology

```text
application composition
  |-- selected module Daemon registrations
  |-- Browser Foundation inbound registrations
  `-- App/Actor host capability adapter
             |
             v
foundation/daemon
  |-- contracts + inbound registration validation
  |-- trigger + state + schedules + mailbox
  |-- instance dispatch/reconciliation/lifecycle
  |-- central protocol/registry/signal/lifecycle
  `-- client
       |-- foundation identity/state/process primitives
       |-- process-runtime JSON framing
       `-- injected host capability only

product handlers -> foundation/daemon public internal contracts
launcher/App/Actor/CLI hosts -> direct Foundation owner or application adapter
```

This is explicit composition, not runtime discovery. The Daemon receives
registrations, a host capability and opaque handler results; it does not know
which product or Browser event produced them.

## One-owner decisions

- All current central and instance Daemon semantics converge under one
  `foundation/daemon/**` package alongside the existing client.
- Inbound registration normalization is Daemon transport/dispatch policy and
  moves with Daemon.
- The shared append-only service event log becomes a direct process-runtime
  primitive; App Server changes only its import.
- App Server notification/client behavior and Actor input remain C6-owned.
  C5B defines only the narrow capability required by Daemon and supplies its
  current implementation from application wiring.
- Browser remains a separate Foundation owner. Application composition adds
  its current inbound registrations; generic Daemon code imports no Browser.
- Application remains the sole concrete composition root and preserves the
  accepted handler order.

Equivalent private file organization is executor-owned. These are semantic
ownership constraints, not a required file-by-file transcription.

## Positive preflight

`S5C5BP-20260807-01` traced every proposed edge and found a standalone runnable
C5B candidate:

- Foundation Daemon can depend directly on Identity, State, Process Runtime
  and its own client/contracts;
- modules and Foundation Browser can depend on Daemon contracts without a
  cycle;
- application can depend on both selected registrations and the generic
  Daemon host, then inject App/Actor behavior;
- existing public process entrypoints remain stable while their imports/wiring
  point at the new owner;
- App Server can consume the moved event-log primitive without importing
  Daemon;
- no C6 physical host movement is required to run or prove C5B.

## Negative preflight

The final candidate must prove:

- no `foundation/daemon/**` import of Launcher, application, modules, Browser
  implementation, Role or Runtime Broker;
- no generic Daemon branch, default list or literal naming Demand, Task,
  Track, Communication, Browser or a product command;
- no old Launcher Daemon implementation/import/literal/installed module;
- no compatibility alias, package-root re-export, fallback or dual path;
- no event bus, plugin loader, DI container, service locator or generalized
  capability framework;
- no C6 ownership movement beyond required consumer imports and one direct
  adapter;
- no architecture test that models private Python lexical/data-flow behavior.

## Protected contracts

- central and mailbox protocol names, envelopes, methods and failure codes;
- identity/role validation, registry rows, reachability and signal delivery;
- mailbox controls, registered application commands and timeout behavior;
- context/state path/schema, schedule semantics and opaque checkpoints;
- trigger normalization, explicit handler ordering, failure isolation and
  reconciliation recovery;
- App notification polling, parent activity/input effects and permissions;
- service process identity, readiness, status, logs, sockets and cleanup;
- accepted product handler behavior and all module Public contracts.

Internal Python module paths are not protected.
