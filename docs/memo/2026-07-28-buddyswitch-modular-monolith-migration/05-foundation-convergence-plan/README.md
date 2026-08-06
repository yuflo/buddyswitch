# S5 Foundation Convergence Plan

> Stage state: `C1–C2 ACCEPTED — C3 PREPARATION ONLY`
> Current execution authority: none
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

Only C3 Browser source/consumer/lifecycle refresh and READY preparation are
unblocked. Browser implementation, Daemon, Broker, Actor, App, physical Web/CLI
host movement, RoleHost and final S5 implementation remain unauthorized.

## Remaining checkpoints

| Checkpoint | Owner convergence | State |
|---|---|---|
| C1 | explicit ToolHost, narrow ToolContext, Daemon client placement | ACCEPTED |
| C2 | WebHost route contribution and generic cleanup projection | ACCEPTED |
| C3 | Browser runtime and public lifecycle operations | PREPARATION ONLY |
| C4 | Identity, state and process primitives | BLOCKED |
| C5 | Runtime Broker and Daemon host | BLOCKED |
| C6 | Actor, App, Web and CLI host physical convergence | BLOCKED |
| C7 | final guidance, residue proof and frozen S5 acceptance | BLOCKED |

Checkpoint labels are program navigation. A checkpoint is handed off only
after its own source refresh, consumer manifest, affected baseline, topology
preflight and READY review. No later checkpoint inherits C1's permission.
