# BuddySwitch Modular Monolith Migration Pack

> Current state: S0–S3 ACCEPTED; S4 TRACK–ARTIFACT ACCEPTED — NEXT LANE PREPARATION ONLY
> Runtime authorization: `NONE`
> The prior Demand-first pack was replaced after the readiness audit.

Read:

1. root `AGENTS.md`;
2. `../2026-07-28-buddyswitch-modular-monolith-readiness-audit.md`;
3. `../2026-07-28-buddyswitch-explicit-modular-monolith-design.md`;
4. `../2026-07-28-buddyswitch-modular-monolith-migration-roadmap.md`;
5. `00-coordination-hub.md`;
6. `00-execution-governance.md`;
7. only the current stage Goal Packet, charter and exact implementation plan.

## Stage charters

| Stage | Charter | State |
|---|---|---|
| S0 | `00-program-readiness.md` | ACCEPTED |
| S1 | `01-single-package-runtime-cutover.md` | ACCEPTED |
| S2 | `02-demand-component-pilot.md` | ACCEPTED |
| S3 | `03-task-goal-boundary-cutover.md` | ACCEPTED |
| S4 | `04-independent-component-waves.md` | TRACK–ARTIFACT ACCEPTED — NEXT LANE PREPARATION ONLY |
| S5 | `05-foundation-convergence.md` | BLOCKED |
| S6 | `06-role-host-cutover.md` | BLOCKED |
| S7 | `07-final-acceptance.md` | BLOCKED |

## Control surfaces

- `migration-ledger.md`: live state and next gate;
- `00-coordination-hub.md`: sole program-control and asynchronous session protocol;
- `decision-log.md`: accepted target/execution decisions;
- `residue-register.md`: old live surfaces and removal owner;
- `executor-handoff-card.md`: one executor payload;
- `stage-implementation-plan-template.md`: required READY plan;
- `stage-goal-packet-template.md`: exact independent-session handoff;
- `stage-acceptance-template.md`: required acceptance record.

S1 has an audit-reviewed structured blueprint at
`01-single-package-runtime-cutover-plan/README.md`. R4 and the first
entry-baseline repair are accepted. Formal packet `BS-MM-S1-20260728-01` and
bounded packet `BS-MM-S1-E1-20260728-01` both stopped correctly before C2.
The hub accepted only E1's Demand-proof repair and expanded the still-open C1
runtime-provenance finding in
`01-single-package-runtime-cutover-plan/S1-E1-RETURN-REVIEW.md`. D-037 now
forbids another patch-on-patch packet, and
`01-single-package-runtime-cutover-plan/S1-E2-PREFLIGHT.md` proves the selected
replacement mechanism is feasible across eleven scenarios. The source snapshot,
exact plan and Goal Packet passed
`01-single-package-runtime-cutover-plan/S1-E2-READY-REVIEW.md`. The returned
implementation is accepted in
`01-single-package-runtime-cutover-plan/S1-E2-ACCEPTANCE.md`; F-034 and
R-PKG-019 are closed and C1 is accepted. E2 is no longer executable. C2
READY preflight then found F-035: moving/deleting source before process and
Actor consumers cut over would create an unusable intermediate product path.
No standalone C2 packet may be issued. The maintainer accepted D-038, and the
hub froze exact source/consumer manifests, complete preservation evidence and
final-topology preflight in the atomic C2–C5 plan. Packet
`BS-MM-S1-C2C5-20260728-01` returned against the frozen source and is accepted
at the C5 gate in
`01-single-package-runtime-cutover-plan/S1-C2-C5-ACCEPTANCE.md`. C2–C5 now
form the sole live runtime path and that packet is consumed. The next action
was C6 current-guidance replacement and frozen FINAL. Packet
`BS-MM-S1-C6-20260729-01` completed that gate and is accepted in
`01-single-package-runtime-cutover-plan/S1-ACCEPTANCE.md`. S1 is closed.
That acceptance unlocked the S2 source refresh and READY preparation.

S2 then completed the direct Demand module cutover and the final
activation-first Browser lifecycle prerequisite. The coordinating hub accepted
the frozen candidate in
`02-demand-component-pilot-plan/S2-ACCEPTANCE.md`; every S2 implementation and
repair packet is consumed. S3 source refresh and READY preparation are now
unlocked. The hub adopted the S2 quality ratchet, refreshed the current
Task/Goal source and consumers, passed the affected preservation baseline,
selected and preflighted the acyclic Task–Demand boundary, and issued the
structured plan at `03-task-goal-boundary-cutover-plan/README.md`.
The initial S3 executor produced a coherent partial candidate and stopped
correctly when a generated package-discovery consumer was outside the exact
manifest. Hub review found the missing representation class, a neighboring
generated router expectation and three candidate proof-quality drifts. The
initial packet is consumed. D-049 and the reviewed R1 audit replace
Task-specific test exceptions with owner/composition-derived generic proof.
R1 was the sole successor execution authority.

S3 R1 then completed the preserved Task/Goal candidate, corrected the generic
package/router proof owners, passed the complete affected path and one frozen
FINAL, and returned with clean runtime and resource state. The coordinating
hub reproduced its complete source, untracked and activation identities,
reviewed the one-owner/Public/contribution boundaries and accepted S3 in
`03-task-goal-boundary-cutover-plan/S3-ACCEPTANCE.md`. Both S3 packets are
consumed.

The S4 source refresh then separated the six lanes by real host and dependency
boundaries. Search is stateless and needs only the existing Tool contribution;
Track, Artifact, Communication, Evidence and Context still require independent
boundary decisions and remain preparation-only. The affected Search
preservation group passed as `b96f488146524dbc97eb14463aea7780`, and
representative final-topology probe `S4SEARCHP-20260730-02` proved explicit
dispatch, atomic old/new registration failure, duplicate-module rejection and
unchanged Daemon order. The structured Search plan is at
`04-independent-component-waves-plan/README.md`. The initial Search packet was
rejected before execution after pre-handoff review found a manufactured
refactor RED, two omitted generated/enumerated consumers and an avoidable
second reprovision boundary. R1 then completed the coherent Search candidate
and runtime activation, but stopped before collection because its frozen
command named `modules/search/tests` instead of a runner-recognized tier.
R1 was consumed and its candidate preserved. D-051 keeps outcomes and
boundaries hub-owned while assigning target discovery and bounded execution
judgment to the executor. R2 then passed direct, affected and one frozen FINAL
on the preserved identity. Search is accepted in
`04-independent-component-waves-plan/search/S4-SEARCH-ACCEPTANCE.md`; all
Search packets are consumed.

The next source refresh proved Track and Artifact must cut over atomically
while remaining separate modules. R1 completed and proved the product
candidate. Hub review then found a false test-ownership boundary: ten
cross-component tests had moved under one module and the architecture proof
excluded module test roots. R2 changed no product source; it returned those
tests to root tiers, retained three true module-local tests, enforced the
cross-Private rule and passed exact, affected and one new frozen FINAL.
Track–Artifact is accepted in
`04-independent-component-waves-plan/track-artifact/S4-TRACK-ARTIFACT-ACCEPTANCE.md`.
Both packets are consumed. Communication, Evidence and Context remain
preparation-only; no next lane is executable yet.

Do not hand the whole program to one executor. The handoff unit is one current
stage, or one explicitly independent S4 lane, with its exact plan and relevant
ledger/residue rows.
