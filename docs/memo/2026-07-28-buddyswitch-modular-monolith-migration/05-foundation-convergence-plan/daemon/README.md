# S5 C5B Daemon Convergence

> State: `ACCEPTED`
> Packet: `BS-MM-S5-DAEMON-R1-20260807-01` is consumed
> Acceptance: `S5-C5B-ACCEPTANCE.md`

C5B gives the existing central and instance Daemon one direct Foundation
owner. It preserves the current subscription, trigger, mailbox, schedule,
handler, reconciliation and lifecycle behavior while removing the remaining
Launcher-owned Daemon implementation.

Read in order:

1. `S5-C5B-SOURCE-AND-CONSUMER-SNAPSHOT.md`;
2. `S5-C5B-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
3. `S5-C5B-IMPLEMENTATION-PLAN.md`;
4. `S5-C5B-READY-REVIEW.md`;
5. `S5-C5B-GOAL-PACKET.md`;
6. `S5-C5B-ACCEPTANCE.md`.

C5B does not converge Actor, App Server, Web, CLI or shell host ownership.
Those may receive only the narrow adapter/import changes required to consume
the new Daemon owner. C5B is accepted and its packet may not resume. C6
source refresh and READY preparation are unblocked; C6 implementation remains
unauthorized until that gate passes.
