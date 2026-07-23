# Daemon Service Architecture

## Purpose

Daemon service is product-neutral host infrastructure:

```text
daemon hosts product handlers; handlers own product meaning
```

It owns process lifecycle, Actor registration, mailbox transport, generic
triggers and schedules, handler dispatch, bounded polling, and host telemetry.
It does not own Demand, Task, Goal, IM, Track, Browser, or Web semantics.

## Generic capabilities

The daemon core provides:

- `DaemonContext` with Actor, role, main-thread, path, socket, workspace, and
  permission facts;
- `DaemonHandler.handles/handle` for trigger dispatch;
- optional product-neutral `reconcile(context, state, runtime)` activation;
- due-now schedules and owner-scoped schedule cancellation;
- a mailbox application-command registry;
- generic parent-activity observation and parent input;
- isolated handler telemetry and opaque checkpoints.

After Actor registration and during bounded App Server polling, the core calls
registered reconciliation hooks in explicit order. One handler failure is
recorded and does not stop later handlers. The core never interprets a
checkpoint, derives a product transition, or discovers product handlers.

## Product handlers

The instance composition currently registers, among other owners:

- `DemandTriageHandler` for isolated inbound Demand triage recovery;
- `TaskGoalHandler` for canonical Task/native Goal convergence;
- `DemandOrchestrationHandler` for Demand reconciliation and Task selection;
- IM, Track, and Browser handlers for their own source lifecycles.

These modules may import product domains and App Server adapters. Generic
daemon modules may not.

`TaskGoalHandler` illustrates the boundary precisely:

```text
daemon generic command/reconcile callback
  -> product-owned TaskGoalHandler
  -> canonical Task + App Server goal/get|set|clear
```

The daemon activates and reconciles the bridge. Codex App Server owns native
Goal persistence, continuation, turn scheduling, and model API calls. The
daemon does not execute the Task objective.

## Notifications and recovery

App Server notifications are acceleration signals. Product handlers reread
canonical product state and App Server state during reconciliation, so daemon
correctness does not depend on notification replay.

Examples:

- Demand triage recovers from canonical ingress receipts and side leases;
- Task–Goal convergence recovers from canonical Task plus `goal/get`;
- Demand orchestration recovers from pool revision plus terminal Tasks.

This is the general value of daemon reconciliation: a product-independent
activation opportunity over product-owned durable truth. Adding a new product
does not add a product switch to daemon core.

## Composition root

`tools/launcher/instance_daemon.py` is the only production composition root
that imports generic daemon orchestration and concrete product handlers. It
registers handlers and application commands explicitly and in visible order.

There is no plugin discovery, semantic event bus, central product workflow
engine, or product service locator.

## State and status

Daemon state contains host facts only: readiness, schedules, handler telemetry,
and opaque checkpoints. Daemon status does not read product storage.

Consumer views compose daemon/host status with public read projections owned by
each product.

## Dependency direction

Allowed:

```text
product handler -> daemon contracts/runtime
product handler -> product domain or App Server adapter
instance_daemon -> daemon core + concrete product handlers
product tool -> narrow application-command capability
```

Forbidden:

```text
daemon core/state/contracts -> product module or schema
daemon status -> product storage
transport -> product transition policy
product tool -> broad daemon service locator
```
