# Daemon Service Architecture

## Purpose

The actor instance daemon is product-neutral host infrastructure. It owns the
process and delivery mechanics needed to host product modules, while product
modules own every product command, payload, state transition, read model, and
error contract.

The stable rule is:

```text
daemon hosts product modules; daemon does not know product modules
```

## Generic daemon responsibilities

The generic daemon owns:

- instance process lifecycle and readiness;
- actor, role, main-thread, workspace, socket, and permission host facts;
- generic mailbox request and response transport;
- generic local triggers, cross-actor signals, schedules, and handler dispatch;
- current daemon state and atomic persistence;
- host runtime facts required by registered handlers;
- host-control status for readiness, registered handlers, schedules, and errors.

Generic daemon contracts, state, runtime, core, mailbox, and client modules do
not import or branch on Task Sys, IM, Track, Browser, or Web product semantics.

## Product module responsibilities

Each product module owns its own business meaning and exposes a narrow adapter
to generic daemon capabilities.

- Task Sys owns task storage, lifecycle rules, actor task projection, runtime
  command names, payload validation, timeout policy, and Task errors.
- IM owns actor-directed message delivery, payload validation, identity and
  reachability decisions, and its trigger semantics.
- Track owns comment delivery and the Task lifecycle requests caused by a
  comment.
- Browser owns page and cockpit lifecycle meaning and uses only public generic
  schedule operations.

Product adapters may depend on generic daemon contracts and clients. Generic
daemon modules may not depend on product adapters.

## Explicit runtime capabilities

`ToolContext` exposes four separate runtime capabilities:

- `ActorDirectoryAccess` for actor listing and reachability;
- `SignalDeliveryAccess` for generic cross-actor signal envelopes;
- `TaskSysRuntimeAccess` for Task-owned runtime commands;
- `ImActorDeliveryAccess` for IM-owned actor delivery.

There is no aggregate runtime service locator. IM, Track, and Task consumers
receive only the capability their production path uses.

## Stable handler contract

`tools/launcher/daemon_contracts.py` is the sole owner of:

- `DaemonContext`, which carries stable host identity, path, role, socket, and
  permission facts;
- `HandlerResult`, which reports `ignored`, `handled`, or `failed`;
- `DaemonHandler`, which declares `handles(trigger)` and
  `handle(context, state, runtime, trigger)`.

Product handlers import these contracts directly. `daemon_core.py` executes
the contracts but does not define or re-export them.

## Composition root

`tools/launcher/instance_daemon.py` is the only production module allowed to
import both generic daemon orchestration and product adapters. It registers
product handlers and application commands when starting the instance daemon.

Registration is explicit. No generic daemon module discovers product modules,
loads product plugins, or recognizes product command prefixes.

## Mailbox application commands

The mailbox owns host-control methods and a product-neutral map from an opaque
command key to a callable. It validates registry structure, rejects duplicate
or conflicting keys, dispatches the callable, and returns a generic envelope.

The registered product adapter owns the command key, payload, validation,
timeout, operation result, and product error meaning. The mailbox does not
inspect command prefixes or retain aliases for replaced keys.

Task runtime commands follow one path:

```text
task_sys_runtime_client.py
  -> daemon_client.request_mailbox
      -> generic application command registry
          -> task_sys_daemon_adapter.py
              -> Task Sys runtime
```

The client and adapter share current command keys from
`task_sys_runtime_protocol.py`. The generic client and mailbox do not define a
Task command, timeout, payload, or error branch.

## Task read boundary

`env.domain.task_sys.actor_task_projection` is the only actor-visible Task read
projection. It accepts the current actor identity profile, reads Task records
once, and derives canonical task, active-task, and recoverable-task summaries
from that collection. Task tools, Context tools, runtime gating, and the Web
actor console all consume this projection.

## Status boundary

Daemon status contains host-control facts only. It does not read product
storage, classify product records, or return product DTOs.

Web product views compose daemon host facts with public product read models.
Task panels obtain Task state from the Task Sys actor projection, not daemon
status. Actor runtime tools likewise use their owning product client or read
model rather than daemon status.

## State boundary

Daemon state contains only the exact current host schema. Unknown fields are
invalid. Active code does not name, remove, translate, or preserve retired
state fields.

Products do not calculate daemon state paths or instantiate daemon state
internals. Generic public state operations provide the schedule queries and
owner-scoped cancellation needed by product lifecycle code.

Browser cleanup calls
`daemon_state.cancel_pending_schedules_by_source_owner` with the exact actor,
main thread, and source owner. `daemon_state.py` alone validates the state
identity, filters pending schedules, and persists the result.

## Dependency direction

Allowed:

```text
product adapter -> generic daemon contracts/client
product adapter -> owning product domain/runtime/repo
instance_daemon -> generic daemon + product adapters
Web API -> host-control API + public product read model
```

Forbidden:

```text
generic daemon -> product module/token/schema
generic daemon status -> product storage or projection
product module -> daemon core/state implementation
product tool -> broad daemon service locator
transport -> hardcoded product command/payload/error
new production path -> retired alias, wrapper, fallback, dual read, or dual write
```
