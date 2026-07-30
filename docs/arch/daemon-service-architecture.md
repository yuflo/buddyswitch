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

Demand inbound resolution illustrates the transport boundary:

```text
isolated Side -> unified buddyswitch-env MCP -> env.tool
  -> explicitly registered Demand adapter
  -> product-owned authority validation + Demand domain
```

The generic environment dispatcher supplies Actor, instance, thread, and
`bound_capability` facts. Capability environment lookup is declared by action
metadata, so native MCP, the registry, the dispatcher, and `ToolContext`
contain no Demand branch or Demand application class. They do not interpret a
Demand proposal or choose a transition. There is no dedicated Demand
transport, special broker method, or daemon application command for inbound
resolution.

`TaskGoalHandler` illustrates the boundary precisely:

```text
daemon generic command/reconcile callback
  -> product-owned TaskGoalHandler
  -> canonical Task + App Server goal/get|set|clear
```

The daemon activates and reconciles the bridge. Codex App Server owns native
Goal persistence, continuation, turn scheduling, and model API calls. The
daemon does not execute the Task objective.

The Task registration also owns the factory for the single mailbox command
`task_goal.reconcile_task`. The generic daemon extracts application-command
factories from typed handler registrations; it neither imports Task nor names
that command.

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

`src/buddyswitch/application/composition.py` is the production component
selection root and the only owner of the complete current component list. It
selects each passive `ModuleAssembly` once and owns concrete cross-component
wiring such as Task's Demand resolver. Search contributes no daemon handler,
so the exact daemon order remains:

```text
demand_triage -> task_goal -> demand_orchestration
```

`src/buddyswitch/application/build.py` validates that this order is a
one-to-one permutation of the contributed handler names and flattens each
typed registration, including Task's mailbox command factory.
`src/buddyswitch/launcher/instance_daemon.py` imports only generic daemon
orchestration and current unmigrated handlers, then merges the injected
registrations in that explicit order.

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
product module -> typed daemon registration
product handler -> daemon contracts/runtime
product handler -> product domain or App Server adapter
application -> selected product module + generic host
instance_daemon -> daemon core + typed handler registrations
product tool -> generic invocation facts + product-private runtime
```

Forbidden:

```text
daemon core/state/contracts -> product module or schema
daemon status -> product storage
transport -> product transition policy
product tool -> broad daemon service locator
generic host -> Demand private package
generic host -> Task private package
```
