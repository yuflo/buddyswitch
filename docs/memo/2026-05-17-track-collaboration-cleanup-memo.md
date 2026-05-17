# Track Collaboration Cleanup Memo

Date: 2026-05-17
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem`
Branch: `dev_buddy_mem`

Status: discussion convergence memo only. Do not treat this document as implementation.

## Background

This memo captures the current BuddySwitch collaboration cleanup task after reviewing the
existing `track`, `task`, `artifact`, `handoff`, and context/runtime tool behavior.

The immediate issue is that the current collaboration model contains several concepts that are
not carrying enough product value and are making the system harder to reason about:

- `handoff` exists as a full runtime object and env tool, but it is barely used and does not solve
  the current collaboration bottleneck.
- `next_buddy` tries to encode "who should do the next step", but that idea is premature and
  poorly aligned with the current product model.
- `track.advance` exists mainly to move `current_buddy` and `next_buddy`, which ties it to the same
  low-value staged-handoff model.
- `current_buddy` is named like a mutable stage owner, but the desired near-term meaning is closer
  to immutable track creator or owner metadata.
- Artifact read visibility is overcomplicated by role checks such as `current_buddy`, `next_buddy`,
  and participant, while artifact editing should remain owner-only.

The current goal is not to redesign track lifecycle. The goal is to simplify and remove invalid,
inefficient, or low-value design so the remaining runtime model becomes easier to advance.

## Current Code Reality

The relevant current implementation shape is:

- `track` is a durable runtime object under `buddyswitch/objects/tracks/*.json`.
- Track records currently contain `current_buddy`, `next_buddy`, `task_ids`, `status`, `summary`,
  and `updated_at`.
- `track.create`, `track.update`, `track.advance`, and `track.archive` are PM-only service actions.
- `track.update` and `track.advance` currently allow patching `current_buddy` and `next_buddy`.
- `track.advance` is not a materially distinct state machine. It reuses the same PM write helper as
  `track.update` and mainly labels the state change as `advanced`.
- `artifact.get` currently grants foreign artifact body reads through owner/current/next/participant
  relation logic.
- `artifact.list(track_id)` returns current artifact summary rows, while `track.get` can expose
  broader artifact summary information, which creates inconsistent collaboration surfaces.
- `handoff` is implemented across service, store, contracts, semantics, CLI, manifest skill
  registration, projection, cleanup, and tests.
- `handoff` and `next_buddy` both preserve a "next actor" design that should be removed for now.

## Cleanup Goal

Collapse the active collaboration model back to the useful core:

- `track`: a collaboration container and task relation surface.
- `task`: a buddy-owned work item and artifact attachment point.
- `artifact`: the product-readable deliverable surface.

Everything that exists mainly to represent "next step owner", "handoff target", "handoff source",
"next buddy", or "workflow advancement" should be removed from active runtime semantics in this
cleanup pass.

This is a contract-shrinking cleanup, not a replacement design.

## Target Principles

### 1. Remove "next actor" semantics

BuddySwitch should not currently model or persist "the next buddy", "the next executor", "handoff
recipient", or "who should continue next".

The system should not:

- infer the next buddy;
- recommend a next buddy;
- persist a handoff target;
- grant artifact access based on next-buddy or handoff-recipient status;
- expose action hints that imply a cross-buddy workflow router.

### 2. Remove `handoff`

`handoff` should be removed as an active runtime concept.

Expected cleanup scope:

- remove the `handoff` env tool and actions: `list`, `validate`, `create`;
- remove `handoff` from tool registry, router, semantic catalog, CLI, context surfaces, and response
  expectations;
- remove `handoff-tool` from manifest skill registration and buddy skill lists;
- remove `handoff.read` and `handoff.create` permissions;
- remove `buddyswitch/objects/handoffs` from active runtime surfaces;
- remove handoff projection and cleanup indexing as active product behavior;
- remove `source_refs.type="handoff"`;
- remove artifact/track/context next-action prose that points to `handoff.create`;
- update tests to assert the handoff surface is gone instead of maintaining handoff behavior.

No new handoff replacement object should be introduced in this pass.

### 3. Remove `next_buddy`

`next_buddy` should be removed from active track state.

Expected cleanup scope:

- remove `next_buddy` from track validation, creation, update, response summaries, context,
  projection, tests, docs, and skill examples;
- remove `next_buddy` from track tool payload fields;
- remove `next_buddy` from artifact read relation logic;
- remove `next_buddy` relation labels from context and artifact summaries.

No compatibility wrapper should preserve the field unless a failing test proves that active runtime
state still requires a temporary read-only normalization path. The default should be direct removal.

### 4. Remove `track.advance`

`track.advance` exists to support staged workflow progression. With `next_buddy` removed and
`current_buddy` no longer treated as a mutable stage field, `advance` becomes redundant and
misleading.

Expected cleanup scope:

- remove `track.advance` from env tool registry, router, dispatch, CLI, semantics, env profiles,
  manifest permissions, skills, tests, and docs;
- do not replace it with another lifecycle action in this task;
- keep status/title/summary updates under `track.update` until track lifecycle is redesigned later.

### 5. Rename `current_buddy` to `owner_buddy`

The current `current_buddy` name implies a mutable current stage or current assignee. The near-term
desired meaning is immutable track creator or owner metadata.

Target rule:

- track creation records `owner_buddy`;
- `owner_buddy` is not updateable after creation;
- `owner_buddy` does not participate in artifact read authorization;
- `owner_buddy` does not imply next-step routing or stage ownership.

This rename is a clarity cleanup, not a lifecycle redesign.

## Artifact Visibility Simplification

Artifact versioning should remain encapsulated inside the artifact/task layer. Collaboration surfaces
should only expose current artifacts.

Target artifact rules:

- artifact editing remains owner-only;
- `artifact.create_revision` can only write to an active-buddy-owned task;
- `artifact.update_metadata` can only update an active-buddy-owned artifact;
- non-owner artifact reads are allowed only through an active, non-archived track collaboration
  surface;
- collaboration-facing artifact summaries should use one current-artifact selection path;
- superseded revisions should not be exposed as collaboration-layer objects;
- archived-track-related artifact reads are rejected, regardless of owner.

This should be implemented through a small centralized artifact visibility helper instead of
duplicating checks in `artifact.get`, `artifact.list`, `track.get`, and `context`.

## Archived Track Rule

Archived tracks are a hard read boundary.

When `track.status == "archived"`:

- `track.get(track_id)` should reject;
- `artifact.list(track_id)` should reject;
- `artifact.get(artifact_id)` should reject if the artifact is associated with a task under the
  archived track;
- `context.get` and `context.summarize` should not expose the archived track as active
  collaboration context;
- no owner exception should bypass this archived-track read boundary.

For list-style discovery, filtering archived tracks out is acceptable. For explicit id reads,
rejection is clearer than silently returning no data.

## Track Lifecycle Non-Goal

Do not redesign track lifecycle in this task.

Specifically, do not decide or implement:

- a new lifecycle state machine;
- assignment or routing semantics;
- automatic stage transitions;
- a new replacement for `handoff`;
- a new replacement for `next_buddy`;
- multi-buddy workflow orchestration;
- track locking or claiming;
- task ownership redesign.

The current cleanup should remove concepts that are already known to be confusing or low-value.
Future lifecycle design should start from a smaller model after this cleanup lands.

## Expected Active Runtime Surface After Cleanup

The active env tool set should remain focused on:

- `track`
- `task`
- `artifact`
- `buddybox`
- `context`
- `evidence`
- `search`

The `handoff` tool should no longer be part of the active surface.

The track tool should support only operations that still have clear current value:

- `list`
- `get`
- `join`
- `create`
- `update`
- `archive`
- `attach_task`
- `detach_task`

`advance` should be absent.

## Testing Direction

Tests should prove the contracted cleanup, not preserve old behavior.

Important regression areas:

- handoff tool is absent from registry, router, CLI, context catalog, manifest skills, permissions,
  projections, cleanup surfaces, and runtime skills;
- `source_refs.type="handoff"` is rejected;
- `next_buddy` is absent from track records, tool payload fields, responses, context summaries,
  projections, skills, and examples;
- `track.advance` is unsupported everywhere;
- `owner_buddy` is present, stable after create, and not updateable;
- archived track explicit reads reject;
- artifact summaries are current-only across `artifact.list` and `track.get`;
- artifact body reads use the simplified owner/track visibility rule and do not depend on
  `current_buddy`, `next_buddy`, or participant relation labels;
- artifact writes remain owner-only.

Focused tests should run before broad suites. Broader verification should include env tool response
contracts, semantic contracts, runtime skill tests, repo consistency tests, and relevant launcher or
projection tests.

## Implementation Notes

Prefer direct removal over compatibility layers.

If existing runtime fixture JSON still contains retired fields, decide locally whether tests need a
small read-time normalization path. The default should be to remove active support and update
fixtures, because this is development-stage state and the repository guidance favors sharp-forward
cleanup over preserving obsolete internals.

Keep edits scoped:

- do not solve task same-buddy shared visibility in this task;
- do not build an ACL framework;
- do not introduce workflow engines or routing objects;
- do not rebrand `handoff` under a different name;
- do not keep hidden `next_buddy` semantics through another field.

## Open Follow-Up

After this cleanup, track lifecycle can be redesigned from a smaller base. That future design should
decide, separately, whether tracks need owner semantics, status semantics, assignment semantics,
or something else. This memo intentionally does not answer that future question.

