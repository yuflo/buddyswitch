# S4 Communication Boundary Design and Preflight

## 1. Accepted boundary

Communication owns Message state and rules, Message Tool, delivery, external
sessions, IM route/identity, iMessage channel and IM inbound. Generic hosts
own only transport, lifecycle execution, path safety and typed contribution
validation.

## 2. Exact WebHost contributions

`web_contracts.py` gains two passive immutable registrations:

```text
WebRouteRegistration
  name
  prefix
  factory

WebWorkerRegistration
  name
  factory
```

The route factory receives a small product-neutral WebHost access value with
only the current instance-list fact. It returns a route object that supports
pre-ready `prepare()` and `handle(method, path, body, headers)`. The worker
factory receives the bound server URL and returns an object with `start()` and
`stop()`.

`ModuleAssembly` and `ApplicationAssembly` add exact `web_routes` and
`web_workers` tuples. Application build validates type, non-empty name,
callable factory, API-prefix shape, duplicate name/prefix and duplicate worker
name. Assembly and validation never call factories.

WebHost behavior is fixed:

1. instantiate configured route adapters with generic host facts;
2. call route `prepare()` before publishing `web.ready`;
3. bind the HTTP server;
4. publish the current `web.ready` and listening output;
5. instantiate configured workers from the bound server URL;
6. start workers fail-soft, then serve;
7. stop only workers that started, in reverse order, before server close.

The Communication route owns `/api/im/`; the Communication worker owns the
iMessage channel. Generic WebHost contains no `im`, Message or iMessage import,
branch, identity creation or DTO. Communication also contributes the existing
Actor Console `im` section through `actor_console_sections`; WebHost removes
its hard-coded section.

These are registrations for one host, not runtime component lifecycle
callbacks. No discovery, `start_all`, dependency negotiation or universal
plugin API is introduced.

## 3. Daemon and dependency direction

Communication contributes `im.message.created` through the already accepted
`inbound_sources` field. `instance_daemon.py` removes its Message import and
uses only application contributions plus Browser's current foundation source.
The ordered reconciliation tuple remains exactly:

```text
demand_triage -> task_goal -> demand_orchestration
```

The inbound handler receives the Demand enqueue callable from application
composition. This preserves the event-to-Demand result while keeping the
Public graph acyclic.

## 4. Generic cleanup shape

The current cleanup host has Message-specific schema parsing and category
branches. Replace the existing `OwnedStatePath` contract forward with one
generic shape equivalent to:

```text
OwnedStatePath
  relative_path
  owner_roles: tuple[str, ...]
  index_record: mapping | none
  warning: string | none

CleanupIndexProjection
  object_ids_field
  records_field

CleanupContribution
  category
  discover
  required_directories
  index_projection | none
```

The exact class spelling may follow repository style, but these semantics are
not optional. Generic cleanup validates guarded paths, selects when the role
is present in `owner_roles`, copies opaque index records into the contribution-
declared plan fields and deletes selected paths. It never parses Message,
Artifact or Comment schema and never branches on their category names.

Communication discovery privately emits both sender and recipient roles and
the current Message record. Existing Demand/Task/Track/Artifact contributors
project their current single-owner/record behavior through the same one live
contract. Public cleanup plan/result fields, warning behavior, required
directories and deletion effects remain unchanged.

## 5. Representative topology preflight

Hub preflight `S4COMMP-20260803-01` used the installed runtime and current
Message Tool/inbound implementations with an exact prototype of the two new
Web registrations. It observed:

```text
module order:
  demand, task, search, artifact, track, evidence, communication

daemon order:
  demand_triage, task_goal, demand_orchestration

positive topology:
  one message Tool
  one im.message.created inbound source
  one /api/im/ route
  one communication-imessage worker
  zero factory calls during passive assembly

negative topology:
  duplicate module rejected
  duplicate Tool rejected
  duplicate inbound event rejected
  duplicate route name/prefix rejected
  duplicate worker rejected
  old discovered Message Tool + explicit Message Tool rejected
```

Therefore the target is compositionally feasible and fail-closed. The old
Tool package and new registration must be switched atomically.

## 6. Explicit non-goals

- no arbitrary plugin loading or module discovery;
- no general process supervisor or component lifecycle framework;
- no Public Communication repository/service facade;
- no Communication-to-Demand package import;
- no WebHost IM special case;
- no schema, route, Tool, authority, identity or worker-effect change;
- no compatibility import or dual registration;
- no Context module migration in this lane.
