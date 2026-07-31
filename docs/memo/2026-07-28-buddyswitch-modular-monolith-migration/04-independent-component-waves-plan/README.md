# S4 Independent Component Waves Plan

> Stage state: `READY — EVIDENCE R1 ONLY`
> Executable packet: `BS-MM-S4-EVIDENCE-R1-20260731-01`
> Other lanes: Communication and Context remain `PREPARATION ONLY`
> Merge unit: one accepted lane at a time

S4 is not one mechanical directory migration. Its six lanes share the same
physical-aggregation goal but not the same host or dependency boundary.
Accordingly, Search was accepted independently. Current-source review then
proved that Track and Artifact must cut over as one atomic migration candidate
while remaining two independent final modules. The next refresh selected
Evidence because it needs only the existing Tool contribution and accepted
Artifact Public. Communication still lacks a worker-lifecycle contribution;
Context remains last.

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
9. `search/S4-SEARCH-ACCEPTANCE.md`;
10. `track-artifact/S4-TRACK-ARTIFACT-BOUNDARY-DESIGN.md`;
11. `track-artifact/S4-TRACK-ARTIFACT-SOURCE-SNAPSHOT.md`;
12. `track-artifact/S4-TRACK-ARTIFACT-OWNER-CONSUMER-MANIFEST.md`;
13. `track-artifact/S4-TRACK-ARTIFACT-IMPLEMENTATION-PLAN.md`;
14. `track-artifact/S4-TRACK-ARTIFACT-READY-REVIEW.md`;
15. `track-artifact/S4-TRACK-ARTIFACT-GOAL-PACKET.md`;
16. `track-artifact/S4-TRACK-ARTIFACT-R2-READY-REVIEW.md`;
17. `track-artifact/S4-TRACK-ARTIFACT-R2-CONTINUATION-PLAN.md`;
18. `track-artifact/S4-TRACK-ARTIFACT-R2-GOAL-PACKET.md`;
19. `track-artifact/S4-TRACK-ARTIFACT-ACCEPTANCE.md`.
20. `evidence/README.md` and its ordered Evidence lane documents.

The target design and stage charter remain architectural authority. This plan
adds current-source execution facts; it does not broaden S4.

## Lane state

| Lane | Current state | Blocking or selected boundary |
|---|---|---|
| Search | ACCEPTED | `search/S4-SEARCH-ACCEPTANCE.md` |
| Track | ACCEPTED WITH ARTIFACT | `track-artifact/S4-TRACK-ARTIFACT-ACCEPTANCE.md` |
| Artifact | ACCEPTED WITH TRACK | `track-artifact/S4-TRACK-ARTIFACT-ACCEPTANCE.md` |
| Communication | PREPARATION ONLY | iMessage worker lifecycle contribution |
| Evidence | READY — R1 ONLY | existing Tool contribution plus accepted Artifact Public |
| Context | PREPARATION ONLY | last; composes accepted Public reads from other lanes |

The initial Search packet was rejected before execution by the pre-handoff
review. R1 produced a coherent candidate but stopped before collection on an
invalid immutable target. R2 preserved that candidate, applied D-051's
execution authority, and passed direct, affected and single frozen FINAL
proof. All Search packets are consumed. No later lane may reuse a Search
packet; the coordinating hub refreshes source and issues a new packet after
accepting each lane.

Track and Artifact were cut over atomically while remaining two independent
modules. R1 supplied the product candidate and behavior evidence. Coordinating
review found that ten cross-component tests had been placed under a module and
that the architecture proofs skipped module test roots. R2 corrected only that
test topology, machine-enforced D-020, and passed exact, affected and one new
frozen FINAL. Both packets are consumed.

## Evidence admission

Current-source trace proved Evidence does not call Browser lifecycle. Its
stable `browser_evidence` command is a Runtime Broker adapter; the capability
itself issues transient metadata after Artifact Public scope validation.
Direct baseline `244e12758d9f41bebe4bd3754ab1f163`, affected baseline
`158f68a5d618496eb8444310f621162a`, and topology preflight
`EVIDENCEP-20260731-01` passed. D-052 freezes the no-Public/no-Browser-port
boundary.

## Later-lane admission rule

Communication and Context may not reuse this snapshot or packet. The
coordinating hub refreshes their owners, representations, host contracts,
tests and runtime identity only after Evidence acceptance.

## Checkpoint protocol

Only `BS-MM-S4-EVIDENCE-R1-20260731-01` is executable. It does not authorize
Communication, Context, S5, S6, S7, Git integration, or migration-master
acceptance.
