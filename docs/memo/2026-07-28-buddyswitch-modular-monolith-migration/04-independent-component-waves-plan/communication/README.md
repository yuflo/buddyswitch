# S4 Communication Lane

> Lane state: `READY`
> Executable packet: `BS-MM-S4-COMMUNICATION-R1-20260803-01`
> Context: `BLOCKED — remains last`

Communication is the next and only executable S4 lane. It is one atomic
Forward replacement: Message state, Message Tool, actor delivery, IM inbound,
external sessions, `/api/im/*`, Web identity, iMessage channel, cleanup and
their single-module tests move under one physical Communication owner.

The lane also introduces the two exact WebHost contributions earned by the
current product: one route registration and one optional worker registration.
They are passive application data. The generic WebHost alone prepares routes,
starts/stops workers and closes the server; no component lifecycle framework,
plugin discovery or service locator is introduced.

## Read order

1. `S4-COMMUNICATION-SOURCE-AND-CONSUMER-SNAPSHOT.md`;
2. `S4-COMMUNICATION-OWNER-CONSUMER-MANIFEST.md`;
3. `S4-COMMUNICATION-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
4. `S4-COMMUNICATION-IMPLEMENTATION-PLAN.md`;
5. `S4-COMMUNICATION-READY-REVIEW.md`;
6. `S4-COMMUNICATION-GOAL-PACKET.md`.

The packet is consumed once execution returns, whether it passes or stops.
Only the coordinating hub may accept the result, update migration truth,
commit or push.
