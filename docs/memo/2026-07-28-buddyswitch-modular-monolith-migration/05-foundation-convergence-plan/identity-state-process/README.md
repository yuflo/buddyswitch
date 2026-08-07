# S5 C4 Identity / State / Process Primitives

> State: `ACCEPTED`
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
5. `S5-C4-GOAL-PACKET.md`;
6. `S5-C4-ACCEPTANCE.md`.

The R1 packet is consumed. Acceptance is recorded in
`S5-C4-ACCEPTANCE.md`. C5 source refresh and READY preparation are unblocked;
C5 implementation, C6–C7 and S6 remain unauthorized. No C1–C4 packet may
resume.
