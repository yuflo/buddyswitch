# Daemon Service Architecture

## Purpose

The actor instance daemon is product-neutral host infrastructure:

```text
daemon hosts product modules; daemon does not know product modules
```

It owns process lifecycle, actor registration, mailbox transport, generic
triggers and schedules, handler dispatch, bounded polling, and host telemetry.
Product modules own every product command, payload, state transition, recovery
decision, prompt, and read model.

## Generic capabilities

The daemon core provides:

- `DaemonContext` with stable actor, role, main-thread, path, socket, workspace,
  and permission facts;
- `HandlerResult` with `ignored`, `handled`, or `failed`;
- `DaemonHandler.handles/handle` for trigger dispatch;
- optional `DaemonReconciler.reconcile` for durable-state recovery;
- generic due-now schedules and owner-scoped schedule cancellation;
- a product-neutral mailbox application-command registry;
- `DaemonRuntime.parent_activity()` and `input_actor(text)`.

After actor registration and on each bounded App Server timeout, the core calls
every available reconciliation hook in explicit handler order. One hook error
is recorded against that handler and does not stop later hooks. The core does
not interpret the hook result beyond generic status telemetry.

## Product ownership

- Demand Sys owns source-keyed ingress receipts, side purpose and capability
  semantics, resolver authority, Message/Demand coordination, pool revision
  cursors, retry policy, and orchestration prompts.
- Task Sys owns Task records, execution semantics, and its application command
  adapter.
- IM, Track, and Browser own their source validation and product lifecycle.

Demand recovery is implemented only in `DemandTriageHandler.reconcile`.
Generic daemon modules do not import Demand or Task modules, inspect product
storage, recognize product trigger strings, or branch on product state.

The dedicated Demand resolver reaches the runtime broker through the explicit
`demand.ingress.resolve` application operation. The runtime broker is a host
composition boundary; `demand_triage_runtime.py` owns all Demand/Message
semantics. Daemon liveness is not required for that operation.

## Composition root

`tools/launcher/instance_daemon.py` is the only production composition root
that imports generic daemon orchestration and concrete product adapters. It
registers inbound handlers, reconciliation-capable handlers, and application
commands explicitly.

There is no product plugin discovery, central product switch, semantic event
bus, or daemon-owned workflow engine.

## State and status

Daemon state contains host-control facts only: readiness, registered handler
telemetry and checkpoints, and generic schedules. Handler checkpoints are
opaque product-owned objects; the core persists and projects them without
understanding their fields.

Daemon status does not read Demand, Task, IM, Track, Browser, or Web storage.
Consumer views compose host status with the public read model owned by each
product.

## Dependency direction

Allowed:

```text
product adapter -> generic daemon contracts/client/runtime
product adapter -> owning product domain/runtime/repository
instance_daemon -> generic daemon + concrete product adapters
runtime broker composition -> explicit product application operation
```

Forbidden:

```text
generic daemon core/state/contracts -> product module/token/schema
generic daemon status -> product storage or projection
transport -> product payload or lifecycle policy
product tool -> broad daemon service locator
new path -> retired alias, fallback, dual read, or dual write
```
