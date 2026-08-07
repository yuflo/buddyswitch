# S5 C5B Daemon Convergence

> State: `READY`
> Packet: `BS-MM-S5-DAEMON-R1-20260807-01`
> Executable base: `25ba242e402f505c91ac5bf0a18cd29fa84591a9`

C5B gives the existing central and instance Daemon one direct Foundation
owner. It preserves the current subscription, trigger, mailbox, schedule,
handler, reconciliation and lifecycle behavior while removing the remaining
Launcher-owned Daemon implementation.

Read in order:

1. `S5-C5B-SOURCE-AND-CONSUMER-SNAPSHOT.md`;
2. `S5-C5B-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
3. `S5-C5B-IMPLEMENTATION-PLAN.md`;
4. `S5-C5B-READY-REVIEW.md`;
5. `S5-C5B-GOAL-PACKET.md`.

C5B does not converge Actor, App Server, Web, CLI or shell host ownership.
Those may receive only the narrow adapter/import changes required to consume
the new Daemon owner. C6 remains blocked.
