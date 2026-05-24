# BuddySwitch Co-work Forward Stages Memo

Date: 2026-05-23

This memo records the current direction only. It is not a full architecture spec.

## Current Conclusion

BuddySwitch co-work should move forward in stages:

1. Codex app-server service mode for BuddySwitch buddies is now the main path.
2. Next, design the daemon layer, including the co-work message upgrade and how the daemon can intervene in active Codex work.
3. Iterate based on verified behavior.

The immediate focus is Stage 2 design. Do not start daemon implementation before the design is confirmed.

## Core Problem

Multiple buddies already have useful collaboration foundations through tracks, artifacts, comments, and the message system.

The main unresolved problem is timing:

- A buddy may be busy inside a Codex turn and not read messages for a long time.
- Different buddies work at different speeds.
- The daemon likely cannot rely on Codex TUI logs during execution.
- We need a stronger control channel that can deliver messages, steering prompts, and interrupts to each buddy without modifying Codex source.

## Non-goals For Now

- Do not introduce a shared co-work task system.
- Do not turn task into the cross-buddy collaboration primitive.
- Do not build a generic workflow engine, event bus, plugin framework, or speculative orchestration platform.
- Do not keep old TUI-first behavior as a compatibility path if app-server mode becomes the new main path.

Task remains primarily a buddy-private self-management tool. Co-work coordination should use tracks, artifacts, comments, messages, and later daemon-managed intervention.

## Stage 1: Codex App-server Service Mode

Goal: make each buddy controllable through a Codex app-server API instead of relying on a TUI session as the primary control plane.

Status: implemented as the current BuddySwitch service-mode path.

Expected shape:

- One independent Codex app-server process per buddy instance.
- Each buddy keeps its own identity, config, role instructions, workspace, hooks, and runtime boundaries.
- BuddySwitch launcher starts and tracks each buddy server.
- The daemon or launcher can call structured Codex APIs for:
  - start turn
  - steer active turn
  - interrupt turn when needed
  - set/get/clear goal
  - compact thread
  - clear by starting a fresh thread
  - update model/settings where supported
- `codex --remote unix://...` remains available as a human viewer or manual intervention client.

This is a forward replacement of the control channel: TUI becomes optional, not the orchestration foundation.

Stage 1 success means BuddySwitch can start a buddy as a service, send it work through the app-server API, observe enough state to continue, and still allow a human to attach with remote TUI when needed.

## Stage 2: Daemon And Co-work Message Design

Goal: design the daemon after the app-server control channel is proven.

Expected daemon responsibilities:

- Maintain buddy heartbeats.
- Scan and summarize messages using an external LLM API if useful.
- Decide whether a buddy is idle, active, stale, or blocked.
- Send message digests into idle buddies with a new turn.
- Steer active buddies at safe Codex boundaries.
- Interrupt only when the message priority or stale state justifies it.
- Ensure each buddy writes durable turn-end checkpoints so other buddies can see progress.

The daemon should improve coordination, not replace the existing track/artifact/message foundation.

## Stage 3: Iterative Optimization

After stages 1 and 2 are verified, optimize based on real failures:

- message priority rules
- interrupt policy
- checkpoint format
- compaction/clear policy
- buddy visibility and status UI
- final proof and artifact publishing flow

Do not design these deeply before the service-mode control loop works.

## Immediate Next Step

Enter Stage 2 and investigate the daemon/co-work message design before implementation.

The design investigation should cover:

- current BuddySwitch track/artifact/comment/message/runtime surfaces
- current app-server service-mode control capabilities
- local Codex app-server and remote TUI source behavior
- internet-sourced upstream docs or references relevant to Codex control and agent coordination
- a shortest verified Stage 2 slice that can be reviewed before coding
