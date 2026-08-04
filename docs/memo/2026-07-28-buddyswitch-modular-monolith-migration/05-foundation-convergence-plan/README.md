# S5 Foundation Convergence Plan

> Stage state: `READY — C1 TOOLHOST ONLY`
> Current execution authority: `BS-MM-S5-TOOLHOST-R1-20260804-01` only
> Entry source: commit `a61951fe63ecc4dd8cf03b8c0256fbfb11d12227`
> Entry runtime source digest: `0f9c35e6a6431bd43974026ec41ea541babce6a63809e49fb78b108b1099af9b`

S5 is not one repository-wide rewrite. The refreshed source contains several
independent Foundation owners with different lifecycle and failure boundaries.
They converge through bounded, ordered cutovers and one final S5 acceptance.

## Cutover blueprint

Read `S5-SOURCE-REFRESH-AND-CUTOVER-BLUEPRINT.md` first. It owns the stage-wide
source facts, target topology, checkpoint order and dependency boundaries.

## Current executable unit

Only `tool-host/` is READY:

1. `S5-TOOL-HOST-SOURCE-AND-CONSUMER-SNAPSHOT.md`;
2. `S5-TOOL-HOST-CONSUMER-MANIFEST.md`;
3. `S5-TOOL-HOST-IMPLEMENTATION-PLAN.md`;
4. `S5-TOOL-HOST-READY-REVIEW.md`;
5. `S5-TOOL-HOST-GOAL-PACKET.md`.

The Goal Packet authorizes one atomic ToolHost cutover. It does not authorize
Web, cleanup, Browser, Daemon, Broker, Actor, App, CLI, RoleHost or final S5
work beyond the explicitly classified ToolHost write set.

## Remaining checkpoints

| Checkpoint | Owner convergence | State |
|---|---|---|
| C1 | explicit ToolHost, narrow ToolContext, Daemon client placement | READY |
| C2 | WebHost route contribution and generic cleanup projection | BLOCKED on C1 acceptance |
| C3 | Browser runtime and public lifecycle operations | BLOCKED |
| C4 | Identity, state and process primitives | BLOCKED |
| C5 | Runtime Broker and Daemon host | BLOCKED |
| C6 | Actor, App, Web and CLI host physical convergence | BLOCKED |
| C7 | final guidance, residue proof and frozen S5 acceptance | BLOCKED |

Checkpoint labels are program navigation. A checkpoint is handed off only
after its own source refresh, consumer manifest, affected baseline, topology
preflight and READY review. No later checkpoint inherits C1's permission.
