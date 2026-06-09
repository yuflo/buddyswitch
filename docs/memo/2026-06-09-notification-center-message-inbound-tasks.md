# Notification Center And Message Inbound Integration Tasks

Date: 2026-06-09
Status: alignment task memo

## Alignment Summary

This work has two tasks:

1. **Large task: build Notification Center (NC) as notify infrastructure.**
2. **Small task: connect `message` as the first source-native inbound info module.**

The goal is not to build a notification inbox. The goal is to make inbound notify delivery stable,
observable, and modular while keeping source-specific handling semantics inside the owning source
module.

## Boundary Statement

```text
NC owns notify infrastructure.
Source-native inbound modules own event semantics, prompt content, and handling.
```

NC must stop at:

- daemon notify registration / subscription coordination;
- delivery plumbing;
- internal delivery attempt / failure visibility where needed;
- optional debounce / basic rate limiting;
- source handler contract constraints;
- innerTUI methodology requirements.

NC must not own:

- actor-facing notification lifecycle;
- `notification.mark`, `notification.needs_parent`, `notification.archive`, or similar tools;
- source event consumption semantics;
- source prompt content;
- parent/side routing decisions;
- cross-source aggregation UI;
- message disposition, Track lifecycle, comment resolution, or artifact sharing semantics.

## Bitter Lessons Applied

This task must follow the modularity lessons in `docs/bitter`:

- Keep shared contracts small and stable.
- Do not turn NC into a hidden router with one branch per business event.
- Do not move source semantics into a central registry, shared util, or broad manager.
- Consumers must use public contracts, not sibling module internals.
- Shared infrastructure should validate shape and coordinate plumbing; owning modules handle business variation.
- If adding a new source requires editing NC logic beyond registration wiring, the boundary is wrong.

## Task 1: Build NC Core

### Objective

Create NC as the shared daemon notify infrastructure for source-native inbound events.

NC should make daemon inbound notify delivery easier to register, observe, and verify without changing
how each inbound source decides what the actor should do.

### NC Responsibilities

NC owns:

- a small source registration contract;
- handler registration into the daemon notify path;
- stable delivery plumbing around native inbound events;
- internal delivery attempt / failure records if needed for debugging and retry visibility;
- shared tests that prove source handlers can be registered without embedding source semantics in NC.

NC does not own:

- event-specific payload meaning beyond shape validation required for routing;
- source-specific innerTUI text;
- source-specific side/parent routing;
- source-specific done / absorbed / replied / resolved / lifecycle state;
- actor-facing env tools.

### Expected Contract Shape

Each source-native inbound module should expose a small registration record:

```text
event_type
payload_contract
handler_factory
owner_module
```

The record is infrastructure metadata only. It must not encode business workflow steps.

### Key Design Point

NC registration can be centralized as a daemon capability, but source behavior must stay local:

```text
NC registry discovers / receives registrations
  -> daemon subscribes to native event types
  -> daemon receives native event
  -> owning source handler handles native event
```

The daemon should not receive an `nc.notification` wrapper event for source work.

### Acceptance Criteria

- NC has a clear module boundary and no actor-facing `notification.*` env tool.
- NC can register at least one native inbound event without knowing that event's business semantics.
- NC does not render source-specific innerTUI content.
- NC does not choose parent vs side for the source.
- NC does not define a notification consumption lifecycle.
- Tests prove the shared NC layer remains semantic-light and source-owned handlers remain the execution owner.

## Task 2: Connect Message As First Source-Native Inbound Info

### Objective

Use existing `message` as the first source-native inbound info module connected to NC.

This is the smallest meaningful proof that NC can manage daemon notify infrastructure while staying
decoupled from source handling semantics.

### Current Message Path

```text
message.send
  -> durable message row
  -> message.available signal
  -> MessageAvailableHandler
  -> parent/side message innerTUI
  -> actor uses message tools
```

### Target Message Path

```text
message.send
  -> durable message row
  -> message.available native event
  -> NC-managed daemon registration / delivery plumbing
  -> MessageAvailableHandler
  -> parent/side message innerTUI
  -> actor uses message tools
```

### What Must Stay Message-Owned

- `message.available` event type.
- `message_id` payload semantics.
- `MessageAvailableHandler`.
- message parent/side routing.
- message innerTUI content.
- `message.get`, `message.send`, `message.mark`.
- `absorbed`, `replied`, and `needs_parent` disposition semantics.

### What NC May Own For Message

- the registration of `message.available` into daemon notify infrastructure;
- delivery attempt / failure plumbing around the native event;
- shared handler contract checks;
- test scaffolding that proves the handler is registered through NC without moving message logic into NC.

### Acceptance Criteria

- Existing message behavior remains unchanged from actor perspective.
- `MessageAvailableHandler` remains source-owned.
- NC code does not inspect message body, conversation state, disposition, or `needs_parent` rules.
- No actor-facing `notification.*` tools are introduced.
- No `nc.notification` wrapper replaces `message.available`.
- Tests prove message delivery still reaches parent/side through the message handler.
- Tests prove NC registration does not import or mutate message repository internals.

## Implementation Guardrails

- Start with message only. Do not add Track/comment/artifact until the message integration proves the boundary.
- Keep one intent per change set: NC core first, then message registration hookup.
- Do not mix NC construction with Track/comment/artifact redesign.
- Do not add a generic plugin framework.
- Do not add a cross-source queue UI or aggregate triage engine.
- If a future source needs custom behavior, add it in that source's inbound module, not in NC branching logic.

## Parallel Worktree Notes

This task can run in parallel with:

- `docs/memo/2026-06-09-artifact-decoupling-rebuild-task.md`
- `docs/memo/2026-06-09-track-comment-rebuild-task.md`

Parallel-safe ownership:

- NC lane owns daemon notify registration / subscription coordination.
- NC lane owns delivery plumbing and handler registration tests for `message.available`.
- NC lane owns only message inbound hookup as the first source-native proof.

Forbidden in this worktree:

- Do not redesign Artifact, Track artifact relations, or publication behavior.
- Do not redesign Comment or remove the generic comment tool.
- Do not register `artifact.shared` or `track.comment.added` yet.
- Do not move message body, disposition, `needs_parent`, or prompt content into NC.
- Do not introduce actor-facing `notification.*` env tools or `nc.notification` wrapper events.

Merge guidance:

- Preferred merge order: NC first, Artifact second, Comment third.
- NC should merge cleanly before Artifact/Comment integration because it is the least coupled lane.
- If NC touches shared daemon entrypoints such as `tools/launcher/instance_daemon.py`, keep the change
  limited to registration plumbing so future source handlers can be added without NC business branches.
- After merge, rerun message/daemon tests plus shared role/schema/semantic contract tests.

## Follow-On Source Integration Pattern

After message proves the boundary, future sources should be added by contributing source-native inbound modules:

```text
track.lifecycle.changed -> TrackLifecycleInboundHandler
track.comment.added     -> TrackCommentInboundHandler
artifact.shared         -> ArtifactSharedInboundHandler
```

Each source owns:

- native event type;
- payload contract;
- handler;
- parent/side routing;
- innerTUI content;
- source tools guidance;
- source state transitions.

NC should only coordinate registration and delivery plumbing.

## Main Risk

The main risk is rebuilding the old problem under a new name:

```text
source event
  -> NC notification wrapper
  -> actor handles notification
  -> actor then handles source
```

That path is explicitly out of scope. It creates duplicated lifecycle, duplicated triage, and unclear
ownership.

## Definition Of Done

This task is done when:

- NC exists as notify infrastructure, not a notification workbench.
- Message is the first registered source-native inbound event.
- Message handling semantics remain inside message.
- Shared NC code is small, boring, and stable.
- Tests prove registration, delivery, and handler ownership boundaries.
- The next source can be added by creating a source-owned inbound module and registering it, without changing NC business logic.
