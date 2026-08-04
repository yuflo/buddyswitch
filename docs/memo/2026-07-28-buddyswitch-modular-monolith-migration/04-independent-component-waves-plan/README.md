# S4 Independent Component Waves Plan

> Stage state: `CONTEXT READY`
> Executable packet: `BS-MM-S4-CONTEXT-R1-20260804-01`
> Current lane: Context atomic cutover; remains last
> Merge unit: one accepted lane at a time

S4 is not one mechanical directory migration. Its six lanes share the same
physical-aggregation goal but not the same host or dependency boundary.
Accordingly, Search was accepted independently. Current-source review then
proved that Track and Artifact must cut over as one atomic migration candidate
while remaining two independent final modules. The next refresh selected
Evidence because it needs only the existing Tool contribution and accepted
Artifact Public. Communication then completed its route/worker boundary,
physical cutover and generic cleanup execution repair. Search, Track,
Artifact, Evidence and Communication are accepted. Context remains last; its
committed-source refresh and READY review now authorize one atomic packet.

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
21. `communication/README.md` and its ordered Communication lane documents.
22. `context/README.md` and its ordered Context lane documents.

The target design and stage charter remain architectural authority. This plan
adds current-source execution facts; it does not broaden S4.

## Lane state

| Lane | Current state | Blocking or selected boundary |
|---|---|---|
| Search | ACCEPTED | `search/S4-SEARCH-ACCEPTANCE.md` |
| Track | ACCEPTED WITH ARTIFACT | `track-artifact/S4-TRACK-ARTIFACT-ACCEPTANCE.md` |
| Artifact | ACCEPTED WITH TRACK | `track-artifact/S4-TRACK-ARTIFACT-ACCEPTANCE.md` |
| Communication | ACCEPTED | `communication/S4-COMMUNICATION-ACCEPTANCE.md` |
| Evidence | ACCEPTED | `evidence/S4-EVIDENCE-ACCEPTANCE.md` |
| Context | READY | `context/S4-CONTEXT-GOAL-PACKET.md` |

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
boundary. R1 then produced the complete structural candidate, but correctly
stopped before FINAL because the protected CLI had no terminal-loop proof.
Hub preflight subsequently proved the preserved command rejects successful
canonical ToolResult payloads by requiring a nonexistent `feedback` field.
R1 was consumed; R2 owned only the command adapter repair and real-Broker
process proof on the preserved candidate.

R2 then selected the canonical Broker ToolResult as the single response owner,
proved successful issue and downgrade plus business and transport failures
through the installed stable command and real Broker, and passed direct,
affected and one frozen FINAL. Evidence is accepted. Both Evidence packets are
consumed permanently.

## Context admission

Context did not reuse another lane's packet. Its fresh source/consumer trace
proved Public-only product reads and three exact Context-specific shared-host
residues. Direct baseline `f905a017ab6f455b9efd04dda9c2bcb3`, affected
baseline `0b6cafba442b403ea441df38b6393241` and topology probe
`S4CONTEXTP-20260804-01` passed. Only the packet under `context/` may execute.

## Checkpoint protocol

Only `BS-MM-S4-CONTEXT-R1-20260804-01` is executable. It does not authorize
Context acceptance, S5, S6 or S7.
