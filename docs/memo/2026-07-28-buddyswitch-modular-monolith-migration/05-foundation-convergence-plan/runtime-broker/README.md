# S5 C5A Runtime Broker

> State: `ACCEPTED`
> Execution authority: none; packet `BS-MM-S5-RUNTIME-BROKER-R1-20260807-01` is consumed

C5A converges the existing local Runtime Broker into one earned Foundation
owner and removes the retired `runtime_kernel/**` root. It also gives the
already-shared Content-Length JSON socket framing one direct process-runtime
owner so Daemon does not depend on Broker internals.

Read in order:

1. `S5-C5A-SOURCE-AND-CONSUMER-SNAPSHOT.md`;
2. `S5-C5A-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
3. `S5-C5A-IMPLEMENTATION-PLAN.md`;
4. `S5-C5A-READY-REVIEW.md`;
5. `S5-C5A-GOAL-PACKET.md`;
6. `S5-C5A-ACCEPTANCE.md`.

C5B source refresh and READY preparation are unblocked. C5B implementation,
C6, C7 and S6 remain blocked until their own source-bound gates pass. C5A may
not resume.
