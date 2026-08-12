# S5 C6D Host Control

> State: `READY — R1 ONLY`
> Packet: `BS-MM-S5-HOST-CONTROL-R1-20260812-01`
> Execution base: the exact clean READY commit supplied by the coordinating hub

C6D converges the private instance-lifecycle control path. Foundation owns
product-neutral lifecycle coordination and the shared runtime lock; application
composition supplies the current Role catalog/validation and any concrete
application-selected operation needed to start an Actor. CLI and Web remain
peer consumers and receive the same assembled control capability.

Read in order:

1. `S5-C6D-SOURCE-AND-CONSUMER-SNAPSHOT.md`;
2. `S5-C6D-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
3. `S5-C6D-IMPLEMENTATION-PLAN.md`;
4. `S5-C6D-READY-REVIEW.md`;
5. `S5-C6D-GOAL-PACKET.md`.

C6D does not authorize physical WebHost/CliHost convergence, RoleHost, final
Launcher-root deletion, C7, or S6. Paths in these documents are source-grounded
hypotheses inside the semantic boundary, not mandatory edit instructions.
