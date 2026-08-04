# S4 Context Lane

> State: `READY`
> Executable packet: `BS-MM-S4-CONTEXT-R1-20260804-01`
> Product base: `84734395f7b9088ad130ae8ace310cb55220865f`
> Acceptance owner: coordinating hub

Context is the final S4 lane. It is a read-only application projection over
accepted component Public reads and generic runtime facts. It owns one Tool,
no state and no Public API.

Read in this order:

1. `S4-CONTEXT-SOURCE-AND-CONSUMER-SNAPSHOT.md`;
2. `S4-CONTEXT-OWNER-CONSUMER-MANIFEST.md`;
3. `S4-CONTEXT-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
4. `S4-CONTEXT-IMPLEMENTATION-PLAN.md`;
5. `S4-CONTEXT-READY-REVIEW.md`;
6. `S4-CONTEXT-GOAL-PACKET.md`.

The packet authorizes one atomic Context cutover. It does not authorize S5,
Foundation convergence, a Public Context facade, test relocation, compatibility,
commit/push, or migration-master-truth edits.
