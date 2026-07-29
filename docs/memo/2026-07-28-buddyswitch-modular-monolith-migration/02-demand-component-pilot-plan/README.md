# S2 Demand Component Pilot Execution Pack

> State: `ACCEPTED`
> Parent packet: `BS-MM-S2-20260729-01`
> Rejected packet: `BS-MM-S2-BROWSER-LIFECYCLE-20260729-01`
> Consumed final packet: `BS-MM-S2-BROWSER-LIFECYCLE-R1-20260729-01`
> Frozen source: `28ca25d93b84c0165fa4cd6f92744744c1df5d67`

This directory is the sole executable plan for S2. It turns Demand into the
first physically aggregated, explicitly composed BuddySwitch product module
without changing its accepted D2/M2/G1 semantics or preserving an old path.

Read in order:

1. `S2-SOURCE-SNAPSHOT.md`;
2. `S2-OWNER-CONSUMER-MANIFEST.md`;
3. `S2-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
4. `S2-IMPLEMENTATION-PLAN.md`;
5. `S2-GOAL-PACKET.md`;
6. `S2-READY-REVIEW.md`;
7. `S2-FIX-AFTER-FINAL-STATE.md`;
8. `S2-FINAL-F003-BROWSER-LIFECYCLE-IMPLEMENTATION-PLAN.md`;
9. `S2-FINAL-F003-BROWSER-LIFECYCLE-GOAL-PACKET.md`;
10. `S2-FINAL-F003-BROWSER-LIFECYCLE-R1-RESUME-PLAN.md`;
11. `S2-FINAL-F003-BROWSER-LIFECYCLE-R1-GOAL-PACKET.md`;
12. `S2-ACCEPTANCE.md`.

The executor owns implementation and source-bound evidence only. The
coordinating hub retains the master ledger, decisions, residue and acceptance
authority. S2 is closed by `S2-ACCEPTANCE.md`; no packet in this directory is
executable after acceptance.
