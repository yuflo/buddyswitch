# S5 C6D Host Control

> State: `R1 CONSUMED; READY — R2 ONLY`
> Packet: `BS-MM-S5-HOST-CONTROL-R2-20260812-01`
> Execution base: exact preserved R1 dirty candidate plus coordinating memos

C6D converges the private instance-lifecycle control path. Foundation owns
product-neutral lifecycle coordination and the shared runtime lock; application
composition supplies the current Role catalog/validation and any concrete
application-selected operation needed to start an Actor. CLI and Web remain
peer consumers and receive the same assembled control capability.

R1 completed the lifecycle/lock cutover and all behavior/replacement proof, but
hub review found concrete Application module invocations in two Foundation
helper shells. R2 only closes that reverse dependency and its escaped proof
class; it does not redo C6D.

Read the continuation in order:

1. `S5-C6D-R1-RETURN-REVIEW.md`;
2. `S5-C6D-R2-READY-REVIEW.md`;
3. `S5-C6D-R2-GOAL-PACKET.md`;
4. original snapshot, boundary design and Goal Packet for protected semantics.

C6D does not authorize physical WebHost/CliHost convergence, RoleHost, final
Launcher-root deletion, C7, or S6. Paths in these documents are source-grounded
hypotheses inside the semantic boundary, not mandatory edit instructions.
