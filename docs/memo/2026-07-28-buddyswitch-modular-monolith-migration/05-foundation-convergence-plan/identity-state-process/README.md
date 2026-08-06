# S5 C4 Identity / State / Process Primitives

> State: `READY — R1 ONLY` after the preparation commit is pushed
> Predecessor: S5 C3 ACCEPTED
> Execution authority: `S5-C4-GOAL-PACKET.md` only

C4 is a behavior-preserving Foundation ownership cutover. It moves the live,
product-neutral identity model/profile storage, canonical runtime-state
locators and atomic JSON primitives, Actor-private deletion safety, and exact
process-start identity into their final Foundation owners. It updates every
current consumer atomically and deletes the retired `env/**` owner plus the
old `runtime_kernel/process_identity.py` path.

Read in this order:

1. `S5-C4-SOURCE-AND-CONSUMER-SNAPSHOT.md`;
2. `S5-C4-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
3. `S5-C4-IMPLEMENTATION-PLAN.md`;
4. `S5-C4-READY-REVIEW.md`;
5. `S5-C4-GOAL-PACKET.md`.

The packet authorizes one independent C4 task. C5–C7 and S6 remain blocked.
No C1–C3 packet may resume.
