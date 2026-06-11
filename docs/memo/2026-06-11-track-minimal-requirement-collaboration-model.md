# Track Minimal Requirement Collaboration Model

Date: 2026-06-11
Status: implementation reference

This memo is the implementation reference for the Track requirement-collaboration rebuild.

It is not a workflow design. The target is one clean Track model, implemented by direct
replacement. Do not keep the old PM-owned Track model beside the new owner-actor model.
All required Track model, tool, permission, projection, and test changes belong to the same
implementation changeset.

## Core Model

```text
Track = shared requirement facts
owner_actor = exact actor address that owns requirement facts
collaborators = actors who add scattered facts and comments
comment = the only actor-attention mechanism
proof = structured completion evidence
```

The smallest useful loop:

```text
owner actor creates Track
-> actors add material / update / proof / comment
-> owner reads Track facts through track.open
-> owner updates requirements or status
-> owner closes done after accepting proof
```

Owner does not route communication. Actors can mention and reply to each other directly inside
Track comments. Owner only owns requirement facts and final status.

## Product Rules

Persist only three states:

```text
active
blocked
done
```

Do not persist or expose these as Track states:

```text
review
pending
approved
waiting_owner
needs_decision
shaping
collaborating
validating
```

Actor attention has exactly one event:

```text
track.comment.added
```

Do not add Track notification events for:

```text
track.status.changed
track.proof.added
track.blocker.reported
material added
update added
all-collaborator broadcast
```

If an actor must notice a fact, write a Track comment and mention or reply to that actor.

## Target Track Shape

Every Track row must have this shape:

```text
id
title
outcome
owner_actor: {actor_id, role_id}
state: active | blocked | done
now: {
  next: string,
  blocker: string | null
}
acceptance_criteria: list[string]
non_goals: list[string]
artifact_relations: list[relation]
updates: list[update]
created_at
updated_at
archived_at: string | null
```

Creation accepts:

```text
track_id
title
outcome
now.next
acceptance_criteria optional, default []
non_goals optional, default []
```

Creation sets:

```text
owner_actor = active_actor
state = active
now.blocker = null
```

Do not keep these fields:

```text
owner_role
created_by_actor
health
appetite
```

`owner_actor` is the only ownership source.

## State Invariants

`active`:

```text
state = active
now.next is non-empty
now.blocker = null
```

`blocked`:

```text
state = blocked
now.next is non-empty
now.blocker is non-empty
```

`done`:

```text
state = done
now.next is non-empty
now.blocker = null
at least one current proof relation exists
```

No automatic transitions:

```text
blocker update -> blocked
proof added -> done
comment says blocked -> blocked
comment says done -> done
```

Only owner status mutation changes `state`.

## Facts

### Material

`track.add_material` adds a shared artifact relation.

Material is a fact. It does not notify actors and does not change state.

### Update

`track.add_update` appends a timeline fact.

Allowed public update kinds:

```text
progress
decision
blocker
```

A blocker report is only an update fact:

```text
reported blocker != state blocked
```

Owner accepts a blocker by calling `track.update_status` with:

```text
state = blocked
now.blocker = non-empty blocker text
```

### Proof

`track.add_proof` adds a current proof artifact relation.

Proof is structured evidence:

```text
proof added != state done
```

Owner accepts proof by calling `track.update_status` with:

```text
state = done
```

The tool must reject `done` if the Track has no current proof relation.

### Comment

`track.add_comment` adds Track-scoped communication.

Actors can:

```text
mention any actor
reply to any Track comment
ask another actor for context
ask owner to judge proof or blocker
continue peer discussion
```

A comment does not mutate Track requirements or status.

## Tool Surface

The implementation target has one Track tool surface:

```text
track.create
track.list
track.open
track.update_requirements
track.update_status
track.add_material
track.add_update
track.add_proof
track.add_comment
track.list_comments
track.resolve_comment_thread
track.archive
```

Remove:

```text
track.update_now
```

Do not keep `track.update_now` as a compatibility alias. It is the old shared mutation path for
`now/state/health` and conflicts with owner-owned requirement facts.

### Ownership And Permissions

Any actor can create a Track:

```text
track.create -> owner_actor = active_actor
```

All actors with Track access can read and add collaboration facts:

```text
track.list
track.open
track.add_material
track.add_update
track.add_proof
track.add_comment
track.list_comments
```

Only the exact `owner_actor` can mutate requirement facts or lifecycle:

```text
track.update_requirements
track.update_status
track.resolve_comment_thread
track.archive
```

Owner checks must compare the full actor address:

```text
{actor_id, role_id}
```

Role-level auth must not keep PM-only Track lifecycle gates. Resource ownership is checked inside
the Track implementation.

## Tool Semantics

`track.create`:

```text
creates one active Track
requires title, outcome, now.next
sets owner_actor from active_actor
does not accept owner_role, health, appetite
does not accept created_by_actor
```

`track.update_requirements`:

```text
owner-only
patches title, outcome, acceptance_criteria, non_goals
does not patch state, now, material, update, proof, or comments
```

`track.update_status`:

```text
owner-only
patches state and now
enforces active/blocked/done invariants
does not patch title, outcome, acceptance_criteria, or non_goals
does not create notification events
```

`track.resolve_comment_thread`:

```text
owner-only discussion cleanup
not required before done
does not mutate Track requirements or status
```

`track.archive`:

```text
owner-only
archives the Track
blocks normal future writes
does not broadcast notifications
```

## `track.open` Read Model

`track.open` is a shared context view, not an owner decision queue.

It must return:

```text
id
title
outcome
owner_actor
state
now
acceptance_criteria
non_goals
materials
proofs
updates
comment_cues
updated_at
archived_at
```

`comment_cues` must include:

```text
open_thread_count
recent_comments
open_threads
mentions_to_me
replies_to_me
source_of_truth = track.list_comments
```

Actor-relative cues must match the full actor address:

```text
{actor_id, role_id}
```

Do not match only `actor_id`.

Each open thread summary must include:

```text
thread_id
latest_comment_id
latest_comment_preview
latest_by_actor
comment_count
status
mentions_me
replies_to_me
```

Do not classify comments as requirement-change, blocker, proof-review, or owner-decision items.

## Notification Boundary

The Track comment and Notification Center connection already has the correct boundary:

```text
event type: track.comment.added
payload: track_id, comment_id, thread_id
handler: TrackCommentAddedHandler
targets: derived from mentioned_actors and reply_to author
```

Notification Center must only register and dispatch the event. It must not know:

```text
track_id semantics
comment_id semantics
state rules
proof semantics
blocker semantics
owner authority rules
```

Keep the existing inbound shape. Do not build a notification wrapper around Track.

The Track comment handler must continue the message-style runtime behavior:

```text
parent idle -> parent prompt
parent running -> side triage prompt
```

Handler prompts must say owner authority, not PM authority, after the owner-actor rebuild.

## Required Replacement Points

Implement as direct replacement in these areas.

### Repo

File:

```text
scripts/env/repos/tracks.py
```

Required changes:

```text
VALID_TRACK_STATE = ("active", "blocked", "done")
remove VALID_TRACK_HEALTH
create_track requires owner_actor
validate_track requires owner_actor
validate_track rejects owner_role, created_by_actor, health, appetite
validate_track rejects state = review
update_track no longer accepts health or appetite
state validation enforces now.blocker invariants
done validation requires a current proof relation
```

### Tool Definition

File:

```text
scripts/env/tools/track/tool.py
```

Required changes:

```text
track.create is actor-owned, not PM-owned
track.create schema removes appetite, health, owner_role, created_by_actor, review
track.list state filter removes review
track.update_now is removed
track.update_requirements is added
track.update_status is added
track.resolve_comment_thread text says owner-only
track.archive text says owner-only
object_model describes owner_actor and scattered collaboration
capability_boundary removes PM lifecycle language
```

### Tool Implementation

File:

```text
scripts/env/tools/track/_impl.py
```

Required changes:

```text
replace create_track_for_pm with create_track_for_active_actor
remove active_role == "pm" create/archive checks
add exact owner_actor checks for owner-only actions
remove update_now_for_active_role
add update_requirements_for_owner
add update_status_for_owner
remove health and appetite handling
remove review state handling
track summary returns owner_actor, not owner_role
track page returns materials and proofs as explicit read projections
comment cues include mentions_to_me and replies_to_me using full actor address
add_proof allowed next action points to track.update_status, not track.update_now
```

### Track Artifact Relation Domain

File:

```text
scripts/env/domain/track_artifact_relations.py
```

Required changes:

```text
add_material_relation still writes material relation only
add_proof_relation writes proof relation only
add_proof_relation no longer appends a proof update row
remove update kind proof as an alternate proof path
```

Proof must have one public write path:

```text
track.add_proof
```

### Role Auth

File:

```text
scripts/env/tool_runtime/role_auth.py
```

Required changes:

```text
track.create is available to all manifest roles
track.update_requirements is available at role-policy level
track.update_status is available at role-policy level
track.archive is available at role-policy level
track.resolve_comment_thread is available at role-policy level
owner-only enforcement happens inside Track implementation
remove PM-only Track lifecycle additions
remove track.update_now permission
```

### Context Projection

File:

```text
scripts/env/tools/context/_impl.py
```

Required changes:

```text
candidate tracks use owner_actor
my relation is owner only when full actor address equals owner_actor
remove owner_role, health, appetite from Track summaries
runtime policy preview no longer reports PM-only Track lifecycle restrictions
```

### Track Comment Domain

File:

```text
scripts/env/domain/track_comments.py
```

Already correct:

```text
targets derive from mentioned_actors and reply_to author
target matching uses full actor address
```

Required wording change:

```text
prompts say owner authority, not PM authority
```

### Launcher / NC

Files:

```text
tools/launcher/track_comment_inbound.py
tools/launcher/track_comment_added_handler.py
tools/launcher/instance_daemon.py
```

Already implemented:

```text
track.comment.added registration exists
instance daemon registers message and track comment inbound
handler validates payload and intended target
handler dispatches parent idle / side running
```

Do not add:

```text
track.status.changed registration
track.proof.added registration
track.blocker.reported registration
NC wrapper
```

## Test Replacement Checklist

Update tests as part of the same implementation. Do not keep old expectations as compatibility.

Tests must prove:

```text
any manifest role can call track.create
track.create sets owner_actor to active_actor
non-owner cannot update_requirements
non-owner cannot update_status
non-owner cannot archive
non-owner cannot resolve_comment_thread
owner can update_requirements
owner can update_status
owner can archive
owner can resolve_comment_thread
review is rejected everywhere Track state is accepted
health is not accepted or returned as Track state
appetite is not accepted or returned
owner_role is not accepted or returned
created_by_actor is not accepted or returned as Track ownership
track.update_now is not present in schema, runtime policy, or handlers
blocked requires non-empty now.blocker
active requires now.blocker = null
done requires now.blocker = null
done requires at least one current proof relation
add_update(kind=blocker) does not change state
add_update(kind=proof) is rejected
add_proof does not change state
status changes do not emit notifications
proof additions do not emit notifications
blocker updates do not emit notifications
comment mention emits track.comment.added attention to mentioned actor
comment reply emits track.comment.added attention to reply_to author
comment target matching uses {actor_id, role_id}, not actor_id only
Notification Center remains business-semantic-free
```

Tests with known old assumptions must be rewritten, not preserved:

```text
PM-only track.create / track.archive / track.resolve_comment_thread
track.update_now
state enum containing review
health enum
appetite field
owner_role field
created_by_actor ownership field
context summaries keyed by owner_role
runtime policy preview showing Track lifecycle actions restricted to pm
```

## One-Shot Completion Criteria

The implementation is complete only when all are true:

```text
no production code references track.update_now
no Track schema accepts or returns health
no Track schema accepts or returns appetite
no Track schema accepts or returns owner_role as ownership
no Track schema accepts or returns created_by_actor as ownership
no Track state enum includes review
no public update kind enum includes proof
all Track lifecycle ownership checks use exact owner_actor
Track comments remain the only actor-attention path
NC has no Track state/proof/blocker semantics
track.open exposes mentions_to_me and replies_to_me with full actor matching
tests no longer assert old PM-owned Track lifecycle behavior
focused Track/comment/NC tests pass
broader env tool contract tests pass or are updated with the new contract
```

## Non-Goals

Do not build:

```text
Owner Decision Queue
needs_owner_decision flag
comment classification
proof coverage matrix
automatic proof review state
automatic done detection
automatic blocked detection
status-change notification
proof-added notification
blocker-reported notification
watcher/subscriber/participant list
all-collaborator broadcast
mandatory comment resolution before done
generic workflow state machine
backlog/request system
```

## Final Shape

```text
communication = scattered Track comments
actor attention = comment mention/reply only
owner = exact owner_actor
requirement mutation = owner-only
collaboration facts = material / update / proof / comment
state = active | blocked | done
proof = structured evidence, not automatic done
blocker report = update fact, not automatic blocked
status change = read signal, not notification
track.open = shared context, not queue
done = owner accepted enough proof
```
