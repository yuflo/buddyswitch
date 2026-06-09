# Artifact Decoupling Rebuild Task

Date: 2026-06-09
Status: task alignment memo

## One-Line Goal

Rebuild Artifact as an independent collaboration/share content carrier. Artifact can be referenced by
Track, but Artifact is not contained by Track and does not use Track as its lifecycle source of truth.

## Non-Negotiables

- This is a rebuild, not a compatibility migration.
- Do not keep old and new artifact/track publication behavior side by side.
- Delete stale fields, stale tests, stale wording, and stale helper paths instead of preserving them.
- Do not add wrapper adapters to keep the old `published_to_track` model alive.
- Do not introduce `notification.*` tools or `nc.notification` wrapper events.
- Future inbound handling must use source-native Artifact events and source-owned handlers.

## Current Code Reality

Current Artifact is coupled to Track in several places:

- `scripts/env/tools/artifact/tool.py`: Artifact scope and object model describe published Track material/proof artifacts.
- `scripts/env/tools/track/tool.py`: `track.add_material` and `track.add_proof` are the current artifact publication entrypoints.
- `scripts/env/tools/track/_impl.py`: Track open/publish paths read Artifact repo and project Artifact attachment summaries.
- `scripts/env/domain/publication.py`: cross-object publication writes both Track and Artifact, including rollback.
- `scripts/env/repos/tracks.py`: Track rows embed `shared_materials`, `close_proof`, and artifact refs in updates.
- `scripts/env/repos/artifacts.py`: Artifact rows store Track-bound state such as `published_to_track`, `status`, `is_current`, and `supersedes_artifact_id`.
- `scripts/env/domain/artifact_visibility.py`: Artifact read decisions depend on Track refs and Track archived state.
- `scripts/env/domain/artifact_relations.py`: Artifact summaries back-scan Track updates and current comment relations.

## Target Boundary

```text
Artifact = content carrier
Track = collaboration model
Track artifact relation = reference from Track collaboration to one Artifact version/snapshot
```

Artifact owns:

- artifact identity;
- content body;
- metadata;
- template/type;
- revision lineage;
- artifact-local supersession / currentness, if kept;
- attachments;
- author / creator facts;
- artifact-local validation.

Track may own:

- the fact that a Track is using or referring to an Artifact;
- the role that Artifact plays in Track collaboration, such as material, input, deliverable, or proof;
- Track lifecycle and collaboration meaning around that reference.

Artifact must not own:

- Track lifecycle;
- Track state machine;
- Track comment state;
- Track material/proof slots;
- Track owner decisions.

Track must not mutate Artifact content or Artifact lifecycle when it references an Artifact.
Track may still create, update, and remove Track-side Artifact relation facts. That relation is how
Artifact participates in Track collaboration without becoming owned by Track.

## Rebuild Scope

### Runtime Object

- Remove Track-bound publication/currentness state as Artifact's source of truth.
- Do not keep `published_to_track` as a live behavior field.
- Keep Artifact rows focused on content, revision, attachments, authoring, and metadata.
- Keep Artifact-local revision lineage and supersession facts. Do not delete Artifact versioning just
  because old Track publication used `supersedes_artifact_id` and `is_current` incorrectly.
- If a currentness field remains, it must mean current within Artifact's own lineage, not current
  material/proof on a Track.
- Represent Track-to-Artifact usage as a relation/reference outside Artifact content truth.
- Remove runtime validation that requires Artifact to know which Track published it.

### Tool Boundary

Artifact tool should own content operations only:

- create Artifact revision;
- update Artifact metadata/body where author-owned;
- list/read readable Artifact content;
- attach/list/read Artifact attachments.

Artifact tool should not publish to Track.

This task must preserve the ability to put an Artifact into a Track collaboration context. If old
`track.add_material` / `track.add_proof` publication paths are removed or renamed, replacement
Track-side relation actions must land in the same rebuild slice.

Track relation actions must:

- store Track-side relation/reference facts;
- not mutate Artifact content;
- not change Artifact lifecycle;
- not make Artifact depend on Track for currentness;
- preserve the material/proof relation meaning as Track-side roles or relation metadata;
- preserve Track-side proof/timeline evidence behavior when replacing old proof publication.

### Domain Boundary

- Rewrite or remove `publication.py` as the old Track/Artifact lifecycle coupling point.
- Keep any required cross-object consistency in explicit domain operations, not in repos.
- Repos must not import sibling repos to enforce business behavior.
- Visibility/readability must be expressed through small public contracts, not by having Artifact visibility inspect Track internals everywhere.

### Context And Relations

- `context.summarize/get` should describe Artifacts as content carriers, not Track-owned publications.
- Artifact relation summaries should not backfill Track/comment semantics into Artifact content truth.
- Artifact may show relation metadata only as relation metadata, not as ownership or lifecycle.

## Capability Preservation Guardrails

This rebuild must remove coupling, not remove product capability.

Capabilities to preserve:

- active actors can create, revise, update metadata/body, attach files, list, read, and read
  attachments for Artifacts they are allowed to access;
- Track collaborators can still discover and read Artifacts that are shared into their Track
  context;
- Track can still represent Artifact usage as material, input, deliverable, proof, or equivalent
  Track-side relation roles;
- proof relations still create Track-side evidence/timeline meaning where the old proof publication
  path provided it;
- Artifact-local revision lineage and supersession remain available for content versioning.

Capabilities to remove:

- Artifact content/lifecycle being published by Track;
- Artifact readability depending on `published_to_track`;
- Track material/proof currentness being stored as Artifact lifecycle truth;
- Track/comment summaries being backfilled into Artifact content truth.

## Future Specific Inbound Info

Artifact may later become a source-native inbound info producer.

Reference the current message inbound pattern:

```text
message.send writes the message row
  -> deliver message.available with payload {"message_id": ...}
  -> MessageAvailableHandler receives the native daemon trigger
  -> handler validates target actor and exact message id
  -> handler checks parent_activity()
  -> idle parent: submit_parent_prompt(render_parent_message_prompt(...))
  -> running parent: submit_side_triage_prompt(render_side_triage_prompt(...))
  -> actor uses message tools to process message source truth
```

Artifact should reuse this mechanism shape, not message's business semantics.

Native event shape:

```text
artifact.shared
```

Minimal payload:

```json
{
  "artifact_id": "art-...",
  "relation_id": "rel-..."
}
```

Rules:

- Payload identifies facts; it does not carry Artifact body.
- `ArtifactSharedHandler` is Artifact/source-owned.
- Artifact handler validates target actor, exact Artifact/share relation ids, and readability.
- Artifact handler checks parent activity and owns parent/side routing.
- Artifact handler owns source-specific innerTUI text.
- Actor handles source truth through Artifact/Track source tools, not through notification tools.
- NC only registers and delivers the native event.
- Do not copy message dispositions such as `absorbed`, `replied`, or `needs_parent` into Artifact unless Artifact later defines its own source-native handling state.

No `nc.notification` wrapper and no `notification.mark/get/list` actor workflow.

## Worktree Boundary

Artifact worktree owns:

- `scripts/env/tools/artifact/**`
- `scripts/env/repos/artifacts.py`
- Artifact content/revision/attachment domain code
- `scripts/env/domain/publication.py`
- Artifact visibility/relation rebuild
- Track-side Artifact relation replacement needed to preserve material/proof sharing ability
- Artifact and publication tests

Artifact worktree should avoid owning:

- Track-native comment repo/domain/tool actions;
- generic comment tool deletion;
- Track comment inbound handler;
- comment-specific role semantics.

Shared files that require explicit merge coordination:

- `scripts/env/tools/track/tool.py`
- `scripts/env/tools/track/_impl.py`
- `scripts/env/tools/context/_impl.py`
- `scripts/env/tool_runtime/context.py`
- tool catalog / role auth tests

## Parallel Worktree Notes

This task can run in parallel with:

- `docs/memo/2026-06-09-notification-center-message-inbound-tasks.md`
- `docs/memo/2026-06-09-track-comment-rebuild-task.md`

Parallel-safe ownership:

- Artifact lane owns Artifact content/revision/attachment behavior.
- Artifact lane owns the removal or rewrite of old Track/Artifact publication coupling.
- Artifact lane may update Track artifact relation behavior only where needed to remove
  `published_to_track`, `shared_materials`, and `close_proof` as live product contracts.

Forbidden in this worktree:

- Do not build NC core, daemon notify registration, or message inbound hookup.
- Do not register `artifact.shared` into NC in this task.
- Do not implement Track-native comments or delete the generic comment tool from this lane.
- Do not introduce `notification.*` env tools or `nc.notification` wrapper events.

Merge guidance:

- Preferred merge order: NC first, Artifact second, Comment third.
- If Artifact and Comment are developed concurrently, treat Track tool/context/catalog files as the
  integration gate, not as independently owned files.
- After merge, rerun Artifact/Track tests plus shared role/schema/semantic contract tests.

## Acceptance Criteria

- Artifact can be created, revised, updated, listed, read, and attached without Track lifecycle coupling.
- Track can reference Artifact without mutating Artifact content/lifecycle.
- Track-side Artifact relation/share ability replaces old publication paths before those paths are removed.
- Track collaborators can read/list/get related Artifacts and readable attachments through Artifact tools.
- Material/proof relation meaning remains available as Track-side relation metadata.
- Artifact-local revision lineage and supersession remain available for content versioning.
- Artifact no longer treats `published_to_track` as live source-of-truth behavior.
- Old publication coupling tests are removed or rewritten to the new boundary.
- Artifact summaries do not claim Track containment.
- Artifact inbound design uses `artifact.shared` as source-native event and source-owned handler.
- No actor-facing notification tool is introduced.
- No dual-path old/new publication behavior remains.

## Definition Of Done

The task is done when Artifact's module boundary is clear enough that future Track, Comment, and NC
work can use Artifact through public content/relation contracts without importing Artifact internals
or preserving the old Track publication lifecycle.
