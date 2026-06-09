# Track-Native Comment Rebuild Task

Date: 2026-06-09
Status: task alignment memo

## One-Line Goal

Rebuild Comment as the communication part of the Track collaboration model. A comment belongs to one
Track instance and never floats across arbitrary targets.

## Non-Negotiables

- This is a rebuild, not a compatibility migration.
- Delete the generic target-anything `comment` model.
- Do not keep actor-facing `comment.add/list/resolve` as a parallel path.
- Do not support `artifact` or `artifact_section` comments in this task.
- Do not keep old target fields as active behavior.
- Do not add notification wrapper tools.
- Track comment inbound handling must use a source-native Track event.

## Current Code Reality

Current Comment is independent and target-scoped:

- `scripts/env/tools/comment/tool.py`: exposes actor-facing `comment.add`, `comment.list`, and `comment.resolve`.
- `scripts/env/tools/comment/tool.py`: `target_type` supports `track`, `artifact`, and `artifact_section`.
- `scripts/env/repos/comments.py`: stores `target_type + target_id`, with thread and resolution fields.
- `scripts/env/domain/comment_targets.py`: validates both Track and Artifact readability.
- `scripts/env/tools/comment/_impl.py`: owns artifact section anchor, artifact revision chain, reply, mention, and PM resolve behavior.
- `scripts/env/tools/track/_impl.py`: `track.open` does not own or project Track comments as part of Track collaboration.
- `scripts/env/tools/context/_impl.py`: scans comments globally as `open_comment_threads`.
- `scripts/env/domain/artifact_relations.py`: backfills artifact comment counts and ids into Artifact summaries.

This is not Track-native collaboration. It is a generic object discussion layer.

## Target Boundary

```text
Track = collaboration model
Track comment = actor communication inside one Track instance
Comment thread = Track-scoped discussion thread
```

Track comments own:

- Track-scoped discussion rows;
- lightweight thread/reply relationships inside one Track;
- mentions inside one Track discussion;
- resolution/closure semantics for Track discussion;
- Track comment inbound event emission after writes.

Track comments do not own:

- Artifact annotation;
- Artifact lifecycle;
- direct actor inbox messages;
- cross-Track discussion;
- Notification Center lifecycle.

## Track Instance Isolation

This is the core requirement.

- Every comment row must carry exactly one `track_id`.
- `thread_id` is only meaningful within that `track_id`.
- `reply_to` must point to a comment in the same `track_id`.
- `list comments` must require a `track_id`.
- `resolve thread` must require a `track_id` and resolve only rows in that Track.
- No API should return one merged comment thread across multiple Tracks.
- No Artifact or Artifact section target should be accepted.

Thread is not a separate runtime object in this rebuild. It is a lightweight grouping over comment
rows:

```text
track_id
  thread_id
    root comment
    reply comment
    reply comment
```

For a root comment, `thread_id` can equal the root comment id. For a reply, `reply_to` points to a
comment in the same `track_id`, and the reply inherits that comment's `thread_id`.

Target runtime storage shape:

```text
buddyswitch/objects/track-comments/<track_id>/<comment_id>.json
```

The implementation should use a storage shape that makes Track instance isolation visible in the
object path and validation path. Do not keep a flat target-anything comment store as the final model.

## Target Object Shape

```json
{
  "id": "comment-...",
  "track_id": "track-...",
  "thread_id": "thread-...",
  "by_actor": {"actor_id": "act-dev-...", "role_id": "dev"},
  "content": "Need owner decision on acceptance criteria.",
  "reply_to": null,
  "mentioned_actors": [],
  "status": "open",
  "created_at": "2026-06-09T00:00:00Z",
  "resolved_by_actor": null,
  "resolved_at": null,
  "resolution_summary": null
}
```

No `target_type`, `target_id`, `anchor`, or `artifact_revision_id` active behavior.

## Rebuild Scope

### Runtime Object

- Replace generic comments with Track-scoped comment rows.
- Remove target-anything validation from comment storage.
- Ensure row validation enforces `track_id`.
- Ensure thread and reply validation is Track-local.

### Repo Boundary

Create or rename toward a Track-owned comment repo, such as:

```text
scripts/env/repos/track_comments.py
```

Public repo contract should be Track-specific:

- `create_track_comment`
- `reply_to_track_comment`
- `comments_for_track`
- `comments_for_track_thread`
- `get_track_comment`
- `resolve_track_comment_thread`

No `comments_for_target`.

### Domain Boundary

Replace `comment_targets.py` with Track comment domain rules:

- Track exists.
- Track is not archived.
- Active actor has Track collaboration visibility.
- Reply target belongs to the same Track.
- Mentioned actors are valid actor addresses.
- Resolution authority initially follows the existing PM/Track owner authority boundary.
- Do not redesign Track permissions inside this Comment rebuild; broader owner/participant/mention
  permission changes belong to the later Track permission/lifecycle rebuild.

### Tool Boundary

Remove the standalone `comment` tool from the final actor-facing catalog.

Track must expose Track-native comment actions before the standalone `comment` tool is removed.
Candidate final surface:

- `track.add_comment`
- `track.list_comments`
- `track.resolve_comment_thread`

These actions belong to the Track module because comment is part of Track collaboration.

Minimum preserved capability:

- add a root comment on one Track;
- reply to a comment in the same Track through `reply_to`;
- list full comment rows for one Track;
- group listed rows by lightweight `thread_id`;
- filter or summarize open/resolved/all comment rows with equivalent capability to current
  `comment.list`;
- resolve one Track-local thread with PM/Track owner authority.

`track.open` should include a compact Track comment cue:

- recent comments;
- open thread count;
- relevant mentions/replies where useful;
- no full cross-Track comment dump.

`track.open` is not the full comment reader. Full thread/detail reads belong to the Track-native
comment list action.

### Context

- `context.summarize/get` should describe comments as Track collaboration comments.
- `open_comment_threads` should come from Track comment state.
- Context must not describe "target-scoped comments on tracks and artifacts."

## Capability Preservation Guardrails

This rebuild must remove the generic target-anything discussion model, not remove Track
collaboration discussion capability.

Capabilities to preserve inside Track:

- create Track-scoped comments;
- reply to Track comments with lightweight `reply_to` / `thread_id` grouping;
- list complete comment rows for one Track;
- inspect open/resolved/all comment state for one Track;
- resolve one Track-local thread with existing PM/Track owner authority;
- mention concrete actors in a Track discussion;
- expose compact comment cues in `track.open` without replacing full comment listing.

Capabilities intentionally removed:

- comments on `artifact`;
- comments on `artifact_section`;
- generic `target_type + target_id` comments;
- cross-Track comment threads;
- standalone actor-facing `comment.add/list/resolve`.

If Artifact discussion is needed later, it should be designed as an Artifact annotation/review model
outside this Track comment rebuild.

## Future Specific Inbound Info

Track comments may later become a source-native inbound info producer.

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

Track comments should reuse this mechanism shape, not message's direct-message semantics.

Native event:

```text
track.comment.added
```

Minimal payload:

```json
{
  "track_id": "track-...",
  "comment_id": "comment-...",
  "thread_id": "thread-..."
}
```

Rules:

- Payload identifies the Track comment; it does not carry comment body.
- `TrackCommentInboundHandler` is Track/source-owned.
- The handler validates target actor and exact Track/comment ids.
- The handler checks parent activity and owns parent/side routing.
- The handler owns Track comment innerTUI content.
- Actor handles source truth through Track comment tools.
- NC only registers and delivers the native event.
- Do not copy message dispositions such as `absorbed`, `replied`, or `needs_parent` into Track comments unless Track later defines its own source-native handling state.

No `nc.notification` wrapper and no `notification.mark/get/list` actor workflow.

## Worktree Boundary

Comment worktree owns:

- Track-native comment repo/domain/tool actions;
- removal of generic actor-facing `comment` tool semantics;
- Track instance isolation tests;
- Track comment inbound event contract;
- comment-specific role/tool semantic tests.

Comment worktree should avoid owning:

- Artifact publication rebuild;
- Artifact visibility/relation rebuild;
- Artifact content/attachment behavior;
- Track material/proof relation semantics.

Shared files that require explicit merge coordination:

- `scripts/env/tools/track/tool.py`
- `scripts/env/tools/track/_impl.py`
- `scripts/env/tools/context/_impl.py`
- `scripts/env/tool_runtime/context.py`
- tool catalog / role auth tests

## Parallel Worktree Notes

This task can run in parallel with:

- `docs/memo/2026-06-09-notification-center-message-inbound-tasks.md`
- `docs/memo/2026-06-09-artifact-decoupling-rebuild-task.md`

Parallel-safe ownership:

- Comment lane owns Track-native comment repo/domain/tool actions.
- Comment lane owns deletion of generic target-anything comment behavior.
- Comment lane owns Track instance isolation tests and comment-specific role/tool contract changes.
- Comment lane may update `track.open` and context output only for Track comment cues.

Forbidden in this worktree:

- Do not build NC core, daemon notify registration, or message inbound hookup.
- Do not register `track.comment.added` into NC in this task.
- Do not rebuild Artifact publication, Artifact visibility, or Track artifact relation behavior.
- Do not introduce `notification.*` env tools or `nc.notification` wrapper events.

Merge guidance:

- Preferred merge order: NC first, Artifact second, Comment third.
- Comment should rebase after Artifact if Artifact changes Track tool/context/catalog files first.
- Treat `scripts/env/tools/track/**`, context output, manifest/tool catalog, and role/schema tests as
  the integration gate with Artifact, not as independently owned files.
- After merge, rerun Track comment tests plus Track/context/shared role/schema/semantic contract tests.

## Acceptance Criteria

- No actor-facing `comment` tool remains in the final catalog.
- No `target_type=artifact` or `target_type=artifact_section` path remains.
- Track comment rows are isolated by exact `track_id`.
- Root comments create lightweight Track-local threads.
- Replies inherit the Track-local `thread_id` from their `reply_to` target.
- Replies cannot cross Tracks.
- Threads cannot cross Tracks.
- Track-native comment actions preserve add, reply, list, mention, and resolve capability for one Track.
- Track-native comment list can return full comment rows for one Track, not only `track.open` cues.
- Resolution authority uses existing PM/Track owner semantics until the later Track permission rebuild.
- `track.open` exposes Track comment cues as part of Track collaboration.
- Track comment tests replace generic comment tests.
- `track.comment.added` is the future source-native event boundary.
- No actor-facing notification tool is introduced.
- No dual-path old/new comment behavior remains.

## Definition Of Done

The task is done when Comment can no longer be understood as an independent object discussion
system. It is Track-scoped actor communication, with storage, tools, tests, and future inbound event
handling all enforcing Track instance isolation.
