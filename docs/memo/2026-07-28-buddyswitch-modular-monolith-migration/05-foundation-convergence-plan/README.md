# S5 Foundation Convergence Plan

> Stage state: `C1–C6C ACCEPTED; remaining C6 preparation only`
> Current execution authority: none until the next remaining C6 owner passes READY review
> Entry source: commit `a61951fe63ecc4dd8cf03b8c0256fbfb11d12227`
> Entry runtime source digest: `0f9c35e6a6431bd43974026ec41ea541babce6a63809e49fb78b108b1099af9b`

S5 is not one repository-wide rewrite. The refreshed source contains several
independent Foundation owners with different lifecycle and failure boundaries.
They converge through bounded, ordered cutovers and one final S5 acceptance.

## Cutover blueprint

Read `S5-SOURCE-REFRESH-AND-CUTOVER-BLUEPRINT.md` first. It owns the stage-wide
source facts, target topology, checkpoint order and dependency boundaries.

## Accepted checkpoints and current preparation

C1 is accepted in `tool-host/S5-TOOL-HOST-ACCEPTANCE.md`; both ToolHost packets
are consumed. C2 is accepted in `web-cleanup/S5-C2-ACCEPTANCE.md`; its packet
and evidence-only continuation are consumed. None may resume.

C3 is accepted in `browser-runtime/S5-C3-ACCEPTANCE.md`; both Browser packets
are consumed. C4 is accepted in
`identity-state-process/S5-C4-ACCEPTANCE.md`; its R1 packet is consumed. C5A
is accepted in `runtime-broker/S5-C5A-ACCEPTANCE.md`; its R1 packet is
consumed. C5B is accepted in `daemon/S5-C5B-ACCEPTANCE.md`; its R1 packet is
also consumed. C6A is accepted in
`app-server/S5-C6A-ACCEPTANCE.md`; its R1 packet is consumed. Remaining
C6B Actor Session/side runtime is accepted at
`actor-runtime/S5-C6B-ACCEPTANCE.md`; its R1 packet is consumed. Actor
Environment C6C is accepted at
`actor-environment/S5-C6C-ACCEPTANCE.md`; its R1 packet is consumed. Host Control, remaining
Actor/Web/CLI convergence, RoleHost and final S5 acceptance remain
unauthorized.

## Remaining checkpoints

| Checkpoint | Owner convergence | State |
|---|---|---|
| C1 | explicit ToolHost, narrow ToolContext, Daemon client placement | ACCEPTED |
| C2 | WebHost route contribution and generic cleanup projection | ACCEPTED |
| C3 | Browser runtime and public lifecycle operations | ACCEPTED |
| C4 | Identity, state and process primitives | ACCEPTED |
| C5A | Runtime Broker and shared JSON socket framing | ACCEPTED |
| C5B | central and instance Daemon host | ACCEPTED |
| C6A | App Server Python owner plus live shell projection | ACCEPTED |
| C6B | Actor Session and side-thread runtime | ACCEPTED |
| C6C | Actor Environment publication | ACCEPTED |
| C6 remaining | Host Control, Web and CLI physical convergence | BLOCKED pending refresh |
| C7 | final guidance, residue proof and frozen S5 acceptance | BLOCKED |

Checkpoint labels are program navigation. A checkpoint is handed off only
after its own source refresh, consumer manifest, affected baseline, topology
preflight and READY review. No later checkpoint inherits C1's permission.
