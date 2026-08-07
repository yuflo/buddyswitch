# S5 C5A Runtime Broker

> State: `READY`
> Execution authority: packet `BS-MM-S5-RUNTIME-BROKER-R1-20260807-01` only

C5A converges the existing local Runtime Broker into one earned Foundation
owner and removes the retired `runtime_kernel/**` root. It also gives the
already-shared Content-Length JSON socket framing one direct process-runtime
owner so Daemon does not depend on Broker internals.

Read in order:

1. `S5-C5A-SOURCE-AND-CONSUMER-SNAPSHOT.md`;
2. `S5-C5A-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
3. `S5-C5A-IMPLEMENTATION-PLAN.md`;
4. `S5-C5A-READY-REVIEW.md`;
5. `S5-C5A-GOAL-PACKET.md`.

C5B Daemon, C6, C7 and S6 are blocked. C5A may update current Daemon files
only where they consume the shared framing primitive; it may not move or
redesign Daemon ownership.
