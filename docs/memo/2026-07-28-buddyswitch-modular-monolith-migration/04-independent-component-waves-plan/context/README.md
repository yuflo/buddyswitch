# S4 Context Lane

> State: `ACCEPTED`
> Executable packet: none; both Context preparation packets are consumed
> Product base: `84734395f7b9088ad130ae8ace310cb55220865f`
> Acceptance owner: coordinating hub

Context is the final S4 lane. It is a read-only application projection over
accepted component Public reads and generic runtime facts. It owns one Tool,
no state and no Public API.

Read in this order:

1. `S4-CONTEXT-SOURCE-AND-CONSUMER-SNAPSHOT.md`;
2. `S4-CONTEXT-OWNER-CONSUMER-MANIFEST.md`;
3. `S4-CONTEXT-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
4. `S4-CONTEXT-PRE-HANDOFF-AUDIT.md`;
5. `S4-CONTEXT-IMPLEMENTATION-PLAN.md`;
6. `S4-CONTEXT-READY-REVIEW.md`;
7. `S4-CONTEXT-GOAL-PACKET.md`.
8. `S4-CONTEXT-ACCEPTANCE.md`.

The first preparation packet was rejected before execution. Its successor
completed the atomic cutover and is accepted. Neither packet may resume. S5
begins from the committed accepted source with a fresh Foundation trace and no
implementation authority until a new READY-reviewed packet exists.
