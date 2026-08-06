# S5 C3 Browser Runtime Cutover

> State: `READY — C3 R1 ONLY`
> Packet: `BS-MM-S5-BROWSER-RUNTIME-R1-20260806-01`
> Executable base: `34cb192f2d9ee01a2c35b9b0d439c0802da66c7a`
> Preparation HEAD: exact pushed docs checkpoint supplied in the handoff
> Later checkpoints: blocked

C3 makes Browser one Actor-scoped Foundation owner. It moves the current
Browser implementation and its only private runtime asset into
`src/buddyswitch/foundation/browser_runtime/**`, replaces cross-module private
lifecycle calls with owned public-internal operations, updates every current
consumer atomically, and deletes every retired Browser implementation path.

Read in order:

1. `S5-C3-SOURCE-AND-CONSUMER-SNAPSHOT.md`;
2. `S5-C3-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
3. `S5-C3-IMPLEMENTATION-PLAN.md`;
4. `S5-C3-READY-REVIEW.md`;
5. `S5-C3-GOAL-PACKET.md`.

The packet fixes the outcome, owner boundary, protected behavior and proof
classes. File names inside the new private owner are a reviewed reference
topology, not coordinator-authored local coding instructions. Repository facts
and the public test runner remain authoritative.

C4–C7 and S6 remain unauthorized. C3 must leave one runnable product path; it
must not rely on C4 identity/state/process relocation or C5 Broker/Daemon
relocation to complete Browser ownership.
