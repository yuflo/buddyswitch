# BuddySwitch Modular Monolith Migration Pack

> Current state: S0–S2 ACCEPTED; S3 READY — R1 COMPLETION
> Runtime authorization: S3 only through `BS-MM-S3-R1-20260730-01`
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
| S3 | `03-task-goal-boundary-cutover.md` | READY — R1 COMPLETION |
| S4 | `04-independent-component-waves.md` | BLOCKED |
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
`BS-MM-S3-R1-20260730-01` is the sole current execution authority.

Do not hand the whole program to one executor. The handoff unit is one current
stage, or one explicitly independent S4 lane, with its exact plan and relevant
ledger/residue rows.
