# S4 Independent Component Waves Plan

> Stage state: `TRACK–ARTIFACT READY`
> Executable packet: `BS-MM-S4-TRACK-ARTIFACT-R1-20260730-01`
> Other lanes: `PREPARATION ONLY`
> Merge unit: one accepted lane at a time

S4 is not one mechanical directory migration. Its six lanes share the same
physical-aggregation goal but not the same host or dependency boundary.
Accordingly, Search was accepted independently. Current-source review then
proved that Track and Artifact must cut over as one atomic migration candidate
while remaining two independent final modules. Communication, Evidence and
Context still require later refreshed packets and READY reviews.

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
15. `track-artifact/S4-TRACK-ARTIFACT-GOAL-PACKET.md`.

The target design and stage charter remain architectural authority. This plan
adds current-source execution facts; it does not broaden S4.

## Lane state

| Lane | Current state | Blocking or selected boundary |
|---|---|---|
| Search | ACCEPTED | `search/S4-SEARCH-ACCEPTANCE.md` |
| Track | READY WITH ARTIFACT | owns relations; consumes two injected Artifact Public callables |
| Artifact | READY WITH TRACK | owns content/read policy; reads Track Public |
| Communication | PREPARATION ONLY | iMessage worker lifecycle contribution |
| Evidence | PREPARATION ONLY | accepted Artifact Public and Browser foundation input |
| Context | PREPARATION ONLY | last; composes accepted Public reads from other lanes |

The initial Search packet was rejected before execution by the pre-handoff
review. R1 produced a coherent candidate but stopped before collection on an
invalid immutable target. R2 preserved that candidate, applied D-051's
execution authority, and passed direct, affected and single frozen FINAL
proof. All Search packets are consumed. No later lane may reuse a Search
packet; the coordinating hub refreshes source and issues a new packet after
accepting each lane.

## Current atomic lane acceptance sentence

> Track and Artifact become two physically independent product modules selected
> once by application composition. Track remains the sole owner of Track state,
> comments, updates, Artifact relations and lifecycle invariants. Artifact
> remains the sole owner of Artifact content, revisions, attachments, templates
> and read policy. Existing product behavior, durable object formats, external
> interfaces, failure effects and operational results remain unchanged.

## Checkpoint protocol

Only `BS-MM-S4-TRACK-ARTIFACT-R1-20260730-01` is authorized. It does not
authorize Communication, Evidence or Context component migration, S5, Git
integration or master-truth closure.
