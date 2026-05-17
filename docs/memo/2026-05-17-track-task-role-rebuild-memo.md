# Track And Task Role Rebuild Memo

Date: 2026-05-17
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem`
Branch: `dev_buddy_mem`

Status: product/design memo only. This is not an implementation plan.

## Purpose

This memo captures the next BuddySwitch collaboration model direction after challenging the
current `track -> task -> artifact` chain.

The design has two core goals:

1. Rebuild `track` as the shared collaboration surface for human users and buddies.
2. Reposition `task` as a buddy-private execution aid, not a cross-buddy collaboration object.

The north star is still:

**efficient, concise, simple, and clean.**

The first version should make the main collaboration path obvious before adding permissions,
participation, routing, or workflow abstractions.

## Current Problem

The current model makes `track` depend on task relations:

```text
track -> task_ids -> task.artifact_ids -> artifact visibility
```

That creates several product problems:

- a human user must understand internal task relations before understanding shared work;
- a buddy must often join, attach, detach, or reuse a task before reading shared material;
- artifact access becomes coupled to task ownership or participation logic;
- `track` starts to feel like a relationship container instead of a product-progress surface;
- `task` becomes overloaded: it is both a buddy work item and a collaboration permission bridge;
- cross-buddy collaboration is harder to explain than it should be.

The product should instead let a buddy open a track, see the shared materials, read what matters,
add progress, publish proof, and move on.

## Core Direction

Replace the current collaboration chain:

```text
track -> task -> artifact
```

with:

```text
track -> shared materials -> artifacts
track -> updates
track -> current now state

buddy -> private tasks
```

In this model:

- `track` is the shared product-progress page.
- `artifact` is shared collaboration content only after being published to a track.
- `task` is each buddy's private management aid and is not required for cross-buddy collaboration.

## Goal 1: Track Design Rebuild

### Definition

`track` is a short-cycle shared progress page.

It represents one concrete product push:

- what outcome we are trying to create;
- what is happening now;
- what shared materials exist;
- what updates and decisions matter;
- what proof closes the work.

It is not:

- a task tree;
- a workflow engine;
- a permission graph;
- a handoff router;
- a generic project-management database;
- a container whose main purpose is storing `task_ids`.

### Human-Readable Shape

A useful track should be readable as a page:

```text
Track: Landing page first proof

Owner: pm
State: active
Health: blocked
Appetite: 2 days

Outcome
Validate whether the BuddySwitch landing page clearly explains the core value.

Now
Next: design produces first-screen structure.
Blocker: one-line positioning is still unsettled.

Shared Materials
- PRD / pm / current / art-pm-prd-r1
- Positioning note / pm / current / art-pm-positioning-r1
- First-screen draft / design / current / art-design-draft-r1

Updates
- pm: Decided to validate one page first; no full brand system in this track.
- design: First-screen structure depends on final one-line positioning.

Close Proof
- smoke test result
- accepted page screenshot
```

### Minimal Track Fields

The first version should keep the track shape small:

```text
id
title
outcome
owner_buddy
state
health
appetite
now
shared_materials
updates
close_proof
created_at
updated_at
archived_at
```

Recommended meanings:

- `owner_buddy`: lifecycle owner. In V1 this is always `pm`.
- `state`: visible work state such as `active`, `blocked`, `review`, or `done`.
- `health`: lightweight signal such as `ok`, `risk`, `blocked`, or `stale`.
- `appetite`: intended effort/time budget, not a precise schedule.
- `now`: the current next move and current blocker.
- `shared_materials`: published collaboration material refs, usually artifacts.
- `updates`: concise progress, decision, and risk notes.
- `close_proof`: proof refs that show the track reached its outcome.
- `archived_at`: when set, the track is no longer viewable.

`state` and `health` should stay fixed and short. Do not add custom workflows in the first version.

### Lifecycle Rules

V1 lifecycle is intentionally narrow:

- only `pm` can create a track;
- only `pm` can archive a track;
- `owner_buddy` is set to `pm` at creation and is not patchable;
- archiving is a hard visibility boundary;
- archived tracks do not appear in normal track lists;
- opening an archived track rejects;
- adding updates, materials, proof, or now-state changes to an archived track rejects;
- reading track-published shared materials through an archived track rejects.

Use `archive`, not `delete`, as the internal term. Product copy can later choose whether it feels
like delete. Internally, archive is safer because it preserves durable state while removing it from
active collaboration.

Important distinction:

- `done` means viewable closed work with proof.
- `archived` means no longer viewable through the collaboration surface.

Do not use archive as the normal completion action if people still need to inspect the work later.

### Track Operations, Product Semantics

The env tool surface should speak product language:

```text
track.create
track.list
track.open
track.update_now
track.add_material
track.add_update
track.add_proof
track.archive
```

Avoid exposing collaboration-internal language as the main path:

```text
join
attach_task
detach_task
advance
handoff
participant
```

Those words describe machinery, not the user's progress model.

## Goal 2: Task Positioning Rebuild

### Definition

`task` becomes a buddy-private work-management tool.

It helps an individual buddy organize their own work, but it no longer defines the shared
collaboration graph.

Examples:

```text
Design buddy private tasks
- read PM PRD
- sketch first screen
- publish design draft
```

These tasks are useful to Design, but the track should not depend on them.

### Task Rules

In V1:

- tasks are owned by one buddy;
- tasks are readable/writable according to buddy-private task rules;
- tasks may optionally keep a local `track_id` hint for the buddy's own organization;
- `track` must not store `task_ids`;
- `track.open` must not require task relation state;
- artifact visibility must not depend on task ownership or track-task relation;
- cross-buddy collaboration must not require `task.join`, `track.join`, `attach_task`, or `detach_task`;
- task comments/statuses are not the shared source of truth for track progress.

If a buddy wants a private checklist, task is the right place. If the buddy wants to share a product
artifact, they publish an artifact to the track.

### Why This Matters

This removes a major source of conceptual friction:

```text
task = private execution
track = shared collaboration
artifact = shareable material/proof
```

That split is much easier for humans and buddies to reason about than using task relations as a
hidden bridge for artifact visibility.

## Artifact And Collaboration Content Model

### Artifact Definition

An artifact can exist in two collaboration states:

```text
draft/private artifact
published track material
```

Only published track materials are part of cross-buddy collaboration.

### Direct Track Association

Artifacts should associate directly with tracks when published:

```text
artifact -> published_to_track
track.shared_materials -> artifact refs
```

Do not route collaboration through task:

```text
track -> task -> artifact
```

### Minimal Shared Material Ref

The track stores a small reference, not the full artifact body:

```json
{
  "type": "artifact",
  "artifact_id": "art-pm-prd-r1",
  "label": "PRD",
  "kind": "prd",
  "from_buddy": "pm",
  "summary": "Landing page scope, constraints, and success checks.",
  "current": true,
  "published_at": "2026-05-17T12:00:00+08:00"
}
```

The artifact stores its own source metadata:

```json
{
  "id": "art-pm-prd-r1",
  "kind": "prd",
  "created_by": "pm",
  "published_to_track": "track-landing-proof",
  "summary": "Landing page scope, constraints, and success checks.",
  "content": {}
}
```

### Cross-Buddy Read Path

The first-version path should be direct:

```text
pm creates track
pm publishes PRD artifact to track.shared_materials
design opens track
design sees PRD in Shared Materials
design opens PRD artifact directly
design publishes design draft to the same track
dev opens track and reads PRD + design draft
test publishes smoke result as close proof
```

Design should not need to know PM's private task id to read the PM PRD.

The rule is:

```text
If a non-archived track is readable, its current shared materials are readable.
```

V1 intentionally does not model track participation. All buddies can read non-archived tracks and
the current materials published to them.

### Versioning And Currentness

Keep default collaboration view current-only:

- `shared_materials` shows current refs by default;
- a newer artifact can supersede an older material;
- old artifact revisions may remain in artifact history;
- historical versions should not clutter the default track page;
- close proof should point at the exact proof artifacts used to close the track.

This keeps the track page clean while preserving traceability.

## Updates And Decisions

Track updates are the shared timeline.

They should capture:

- progress summaries;
- decisions;
- blockers;
- risks;
- next move changes;
- proof added.

They should not become a general chat system.

Recommended update shape:

```json
{
  "id": "upd-landing-001",
  "by_buddy": "design",
  "summary": "First-screen structure is blocked by unresolved one-line positioning.",
  "kind": "progress | decision | blocker | proof",
  "refs": [
    {"type": "artifact", "id": "art-design-draft-r1"}
  ],
  "created_at": "2026-05-17T12:30:00+08:00"
}
```

General comments can exist later if needed, but V1 should prefer concise updates because they are
easier for both humans and buddies to scan.

## Access And Visibility For V1

Do not implement track participation in the first version.

V1 visibility rules:

- all buddies can list non-archived tracks;
- all buddies can open non-archived tracks;
- all buddies can read current shared materials published to non-archived tracks;
- all buddies can add updates/materials/proof to non-archived tracks unless a later product rule says otherwise;
- only `pm` can create tracks;
- only `pm` can archive tracks;
- archived tracks cannot be viewed or mutated through the collaboration surface.

This deliberately removes participant logic from the first version so the product can validate the
main collaboration path before adding access control.

## Non-Goals

Do not include these in the first version:

- track participation;
- buddy join/leave;
- task-track attach/detach;
- handoff objects;
- next-buddy routing;
- custom workflows;
- dependency engines;
- ACL frameworks;
- project portfolios;
- multi-level task hierarchies;
- complex comments/messages/status-update separation;
- artifact access through task relation checks;
- task-derived track visibility.

These may become useful later only after repeated real usage proves the need.

## Main Path To Validate

The first version should prove this flow:

1. PM creates a track with outcome, appetite, and now-state.
2. PM publishes a PRD artifact directly to the track as shared material.
3. Design opens the track and reads the PRD without joining or attaching a task.
4. Design publishes a design draft artifact to the same track.
5. Dev opens the track and reads both PM and Design materials.
6. Test publishes smoke-test proof to the track.
7. PM marks the track done with close proof, or archives it if it should disappear from collaboration.

If this path is not simple, the design has failed.

## Key Design Constraints

- Keep `track` human-readable first.
- Keep `task` private and optional for collaboration.
- Keep artifact publication direct to track.
- Keep archived track reads rejected.
- Keep PM-only lifecycle for create/archive.
- Keep current shared materials visible without task relations.
- Keep V1 open to all buddies; no participation model.
- Keep status vocabulary short.
- Prefer one obvious path over compatibility with older track/task/artifact chains.

## Summary

The rebuilt model is:

```text
Track = shared progress page
Task = buddy-private execution aid
Artifact = shareable material/proof after publication to a track
Update = concise shared progress/decision record
Archive = hard removal from collaboration visibility
```

The core product sentence is:

**Track is the shared collaboration surface; task is private execution management; artifacts become
cross-buddy collaboration content only when published directly to a non-archived track.**
