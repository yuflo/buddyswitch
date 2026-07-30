# S4 Independent Component Waves Plan

> Stage state: `READY — SEARCH R1 LANE ONLY`
> Executable packet: `BS-MM-S4-SEARCH-R1-20260730-01`
> Other lanes: `PREPARATION ONLY`
> Merge unit: one accepted lane at a time

S4 is not one mechanical directory migration. Its six lanes share the same
physical-aggregation goal but not the same host or dependency boundary.
Accordingly, this plan admits only Search. Track, Artifact, Communication,
Evidence and Context require their own refreshed packet and READY review.

## Read order for the current lane

1. root `AGENTS.md`;
2. `.agents/skills/buddyswitch-testing/SKILL.md` and its routed references;
3. `../00-execution-governance.md`;
4. `../02-demand-component-pilot-plan/S2-DELIVERY-RETROSPECTIVE.md` as
   historical delivery rationale only;
5. `S4-WAVE-DEPENDENCY-AND-HOST-CONTRACT-AUDIT.md`;
6. `search/S4-SEARCH-SOURCE-SNAPSHOT.md`;
7. `search/S4-SEARCH-OWNER-CONSUMER-MANIFEST.md`;
8. `search/S4-SEARCH-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
9. `search/S4-SEARCH-PRE-HANDOFF-REVIEW.md`;
10. `search/S4-SEARCH-IMPLEMENTATION-PLAN.md`;
11. `search/S4-SEARCH-GOAL-PACKET.md`;
12. `search/S4-SEARCH-READY-REVIEW.md`.

The target design and stage charter remain architectural authority. This plan
adds current-source execution facts; it does not broaden S4.

## Lane state

| Lane | Current state | Blocking or selected boundary |
|---|---|---|
| Search | READY | existing Tool contribution is sufficient; no lifecycle or state |
| Track | PREPARATION ONLY | real Web projection and inbound/Daemon contribution |
| Artifact | PREPARATION ONLY | exact Track/Artifact Public dependency direction |
| Communication | PREPARATION ONLY | iMessage worker lifecycle contribution |
| Evidence | PREPARATION ONLY | accepted Artifact Public and Browser foundation input |
| Context | PREPARATION ONLY | last; composes accepted Public reads from other lanes |

The initial Search packet was rejected before execution by the pre-handoff
review and must never run. Only the R1 packet may execute Search. No later lane
may reuse a Search packet; the coordinating hub refreshes source and issues a
new exact packet after accepting each lane.

## Search acceptance sentence

> Search is physically aggregated under one capability root, selected exactly
> once by application composition through the existing Tool contribution,
> preserves its non-opening URL-planning behavior, and leaves no Search
> implementation or Search-specific placeholder in the generic Tool host.

## Checkpoint protocol

The independent executor returns one complete result packet and stops. It does
not commit, push, update master migration truth, start another S4 lane, or wait
through repeated blocked turns. The coordinating hub alone reviews, accepts,
checkpoints and unlocks the next lane.
