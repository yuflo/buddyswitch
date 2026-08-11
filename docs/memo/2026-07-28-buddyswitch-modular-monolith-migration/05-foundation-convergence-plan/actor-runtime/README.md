# S5 C6B Actor Session and Side Runtime Cutover

> State: `ACCEPTED`
> Execution authority: none; R1 is consumed
> Executable base: `f441440d478d336a55599e49fdc554669d428da3`

C6B is the next independently runnable owner admitted by current-source
refresh. It converges the product-neutral Actor parent-session and side-thread
runtime without moving Role authority, Actor workspace construction, Host
Control, Web or CLI.

Read in order:

1. `S5-C6B-SOURCE-AND-CONSUMER-SNAPSHOT.md`;
2. `S5-C6B-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
3. `S5-C6B-IMPLEMENTATION-PLAN.md`;
4. `S5-C6B-READY-REVIEW.md`;
5. `S5-C6B-GOAL-PACKET.md`.

C6B is accepted in `S5-C6B-ACCEPTANCE.md`. R1 must not resume. Only remaining
C6 source refresh and READY preparation are unlocked; C7 and S6 remain
unauthorized.
