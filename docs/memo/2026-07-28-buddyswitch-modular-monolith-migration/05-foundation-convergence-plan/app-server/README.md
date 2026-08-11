# S5 C6A App Server Cutover

> State: `ACCEPTED`
> Execution authority: consumed; no packet may resume
> Executable base: `af75566665248fc56c91eab45b64e95c088be41c`

C6 was intentionally broad in the stage blueprint. Current-source refresh
proved that App Server is an independently runnable semantic owner with its
own protocol, process lifecycle and shell adapter. D-065 therefore admits it
as C6A before the remaining Actor, Web and CLI host convergence.

Read in order:

1. `S5-C6A-SOURCE-AND-CONSUMER-SNAPSHOT.md`;
2. `S5-C6A-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
3. `S5-C6A-IMPLEMENTATION-PLAN.md`;
4. `S5-C6A-READY-REVIEW.md`;
5. `S5-C6A-GOAL-PACKET.md`;
6. `S5-C6A-ACCEPTANCE.md`.

C6A is closed and its packet is historical execution context. Later C6 labels
remain navigation for fresh source-refresh work, not inherited authority.
Actor, Web and CLI hosts remain runnable; no remaining C6 implementation or
RoleHost work is authorized yet.
