# S4 Communication Lane

> Lane state: `ACCEPTED`
> Acceptance: `S4-COMMUNICATION-ACCEPTANCE.md`
> Consumed packets: `BS-MM-S4-COMMUNICATION-R1-20260803-01`, `BS-MM-S4-COMMUNICATION-R2-20260803-01`, `BS-MM-S4-COMMUNICATION-R3-20260803-01`
> Next boundary: Context source refresh and READY preparation only

Communication completed one atomic
Forward replacement: Message state, Message Tool, actor delivery, IM inbound,
external sessions, `/api/im/*`, Web identity, iMessage channel, cleanup and
their single-module tests move under one physical Communication owner.

The lane also introduces the two exact WebHost contributions earned by the
current product: one route registration and one optional worker registration.
They are passive application data. The generic WebHost alone prepares routes,
starts/stops workers and closes the server; no component lifecycle framework,
plugin discovery or service locator is introduced.

## Read order

1. `S4-COMMUNICATION-SOURCE-AND-CONSUMER-SNAPSHOT.md`;
2. `S4-COMMUNICATION-OWNER-CONSUMER-MANIFEST.md`;
3. `S4-COMMUNICATION-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
4. `S4-COMMUNICATION-IMPLEMENTATION-PLAN.md`;
5. `S4-COMMUNICATION-READY-REVIEW.md`;
6. `S4-COMMUNICATION-GOAL-PACKET.md`.

R1 produced the intended Communication cutover and one passing frozen FINAL,
but hub review found a cleanup behavior gap that the selected tests did not
detect: current Message state discovery ignores non-JSON and nested entries,
and therefore all-data cleanup can silently leave owned residue. R1 is
consumed and must not be executed or accepted independently.

Continue with:

7. `S4-COMMUNICATION-R2-CLEANUP-REPAIR-PLAN.md`;
8. `S4-COMMUNICATION-R2-GOAL-PACKET.md`.

R2 repaired recursive Message discovery and produced a passing replacement
FINAL. Hub review then proved that the generic cleanup executor trusts stale
planner validation: replacing a parent with a symlink after plan creation can
delete a target outside the owned root, and a missing path can still be
reported as deleted. R2 is therefore consumed and cannot be accepted alone.

Continue with:

9. `S4-COMMUNICATION-R2-REJECTION-AND-EXECUTION-BOUNDARY-AUDIT.md`;
10. `S4-COMMUNICATION-R3-CLEANUP-EXECUTION-BOUNDARY-PLAN.md`;
11. `S4-COMMUNICATION-R3-GOAL-PACKET.md`.

R3 corrected the generic cleanup execution boundary once, proved every
plan-to-execution state-change regression, and passed one frozen replacement
FINAL. The coordinating hub accepted the complete candidate in
`S4-COMMUNICATION-ACCEPTANCE.md`. All three packets are historical and no
longer executable. Context source refresh is the only unlocked next action.
