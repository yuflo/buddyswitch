# Communication Capability Architecture

## Owner

Communication has one physical owner at
`src/buddyswitch/modules/communication/`. Its Private tree owns Message state
and domain rules, the Message Tool, Actor delivery, Daemon inbound handling,
external sessions, the HTTP projection, Web identity, the iMessage channel,
and cleanup discovery. Its tests live with the owner only when they exercise
Communication plus foundation primitives.

Communication Public exposes exactly four consumer-earned operations:

```text
get_im_message
list_im_replies
send_im_message
list_im_events_for_identity
```

Demand triage and Context use those Public operations. No repository, mutable
state object, compatibility facade, or former entrypoint is Public.

## Composition

`build_communication_module(...)` returns one passive `ModuleAssembly`.
Application composition selects it once after Evidence and supplies Demand's
Public `enqueue_inbound` callable to Communication's input port. Communication
Private never imports Demand; application composition owns that concrete edge.

The assembly contributes exactly one of each current capability:

```text
Message Tool
im.message.created inbound source
/api/im/ WebRouteRegistration
communication-imessage WebWorkerRegistration
Actor Console im section
Message cleanup contribution
```

Assembly validation is passive and never calls route or worker factories.

## Generic host edges

The Web route factory receives only `WebHostAccess.list_instances`. The route
owns readiness, identity creation, routing, Actor contact projection, and
delivery. The worker factory receives only the bound server URL and owns the
iMessage channel controller and worker.

The passive Web types come directly from
`src/buddyswitch/foundation/web_runtime/contracts.py`; Communication does not
own, copy, or discover a host contract.

The generic Web host prepares routes before publishing readiness, dispatches
by the shared validated exact/prefix matcher contract, starts workers
fail-soft, stops only started workers in reverse order, and closes the server
last. Communication declares only its `/api/im/` prefix. The host contains no
Communication import, Message DTO, `/api/im/` branch, or iMessage construction.

The generic Daemon host receives Communication's existing inbound-source
registration from application assembly. The handler validates the persisted
Message and event, then calls its injected Demand input port. Daemon ordering
remains `demand_triage -> task_goal -> demand_orchestration`.

## Cleanup

Communication privately discovers current and retired Message objects and
projects every guarded path with both attributable Actor roles. The generic
cleanup host selects a path when the scoped role is in `owner_roles`, copies
opaque index records through the contribution's `CleanupIndexProjection`, and
deletes selected paths. The host does not parse Message, Artifact, or Track
Comment schemas and does not branch on their category names.

## Dependency rules

Valid paths:

```text
Demand Private -> Communication Public -> Communication Private
Context adapter -> Communication Public
Application composition -> Demand Public callable -> Communication input port
Application composition -> typed Web registrations -> generic Web host
```

Forbidden paths:

- Communication Private to Demand Public or Private;
- Demand Private to Communication Private;
- generic Web or Daemon hosts to Communication Private;
- dynamic Tool discovery for Message;
- service location, plugin discovery, compatibility adapters, fallback reads,
  or parallel Message schemas.
