# S5 C3 Browser Runtime Cutover

> State: `ACCEPTED`
> Packets: `BS-MM-S5-BROWSER-RUNTIME-R1-20260806-01` and
> `BS-MM-S5-BROWSER-RUNTIME-R2-20260806-01` consumed
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
6. `S5-C3-ACCEPTANCE.md`.

The packet fixes the outcome, owner boundary, protected behavior and proof
classes. File names inside the new private owner are a reviewed reference
topology, not coordinator-authored local coding instructions. Repository facts
and the public test runner remain authoritative.

C3 is accepted in `S5-C3-ACCEPTANCE.md` and neither packet may resume. C4
source refresh and READY preparation are unblocked; C4–C7 implementation and
S6 remain unauthorized until their own gates pass.
