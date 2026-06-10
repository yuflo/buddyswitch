# Specific Inbound Info: Track Comment Inbound Task

Date: 2026-06-10
Status: task alignment memo

## Alignment Summary

This is the fourth task after:

1. Notification Center and `message.available` inbound integration.
2. Artifact decoupling.
3. Track-native Comment rebuild.

The goal is to complete source-owned async actor handling for Track comments by following the
existing message inbound mechanism shape without moving Track comment semantics into Notification
Center.

Artifact inbound is intentionally deferred in this task. The current Artifact model is a content
carrier: the owner actor creates and updates Artifacts, while collaborators read Artifacts through
Track relations. There is no current Artifact operation that clearly means "this exact actor must
handle this Artifact now."

## Boundary Statement

```text
Specific inbound info sources own concrete handling.
Notification Center owns registration and delivery plumbing only.
```

Track Comment owns:

- `track.comment.added` event meaning;
- target actor derivation from comment data;
- event emission after durable Track comment writes;
- `TrackCommentInboundHandler`;
- validation of target actor, Track id, comment id, thread id, and Track readability;
- parent/side routing decision;
- Track comment innerTUI prompt content.

Notification Center owns only:

- source registration shape;
- native event subscription list;
- handler construction from registrations;
- delivery plumbing around native daemon signals;
- shared handler contract checks.

NC must not import Track comment repos, inspect comment content, compute mentioned actors, render
Track prompts, choose parent vs side, or define comment consumption lifecycle.

## Current Code Reality

Message is the current complete source-owned inbound example:

```text
message.send
  -> durable message row
  -> deliver message.available
  -> MessageAvailableHandler
  -> parent/side message innerTUI
  -> actor uses message tools
```

Track comment currently has storage and tools but not async inbound:

```text
track.add_comment
  -> durable Track comment row
  -> no track.comment.added delivery
  -> no TrackCommentInboundHandler
  -> no parent/side Track comment prompt
```

Artifact currently has Track relation sharing but not a clear actor-attention event:

```text
track.add_material / track.add_proof
  -> Track-side Artifact relation
  -> no explicit target actor
  -> no artifact.shared fanout in this task
```

## Task Scope

Implement Track comment as the next specific inbound info source.

Target flow:

```text
track.add_comment
  -> durable Track comment row
  -> derive target actors from mentioned_actors and reply_to author
  -> deliver track.comment.added to each target actor
  -> TrackCommentInboundHandler receives native daemon trigger
  -> handler validates exact Track/comment/thread and target actor
  -> handler checks parent_activity()
  -> idle parent: submit_parent_prompt(render_parent_track_comment_prompt(...))
  -> running parent: submit_side_triage_prompt(render_side_track_comment_prompt(...))
  -> actor uses Track tools to process Track source truth
```

## Target Actor Rules

Target actors come only from explicit Track comment attention:

- `mentioned_actors` on the new comment;
- the author of the `reply_to` comment, when the new comment is a reply.

Rules:

- Deduplicate target actors by normalized ActorAddress.
- Do not notify the comment author.
- Do not notify when `mentioned_actors` is empty and `reply_to` is absent.
- Do not broadcast to all Track collaborators.
- Do not notify by role alone; target actor ids must be concrete.
- If a target actor is offline or unreachable, keep the durable comment row and report delivery
  status in the tool result. Comment creation is Track state; delivery is best-effort attention.

## Native Event Contract

Event type:

```text
track.comment.added
```

Minimal payload:

```json
{
  "track_id": "track-...",
  "comment_id": "comment-...",
  "thread_id": "comment-or-thread-..."
}
```

Payload rules:

- Payload identifies facts; it does not carry comment body.
- The target actor address is carried by the daemon signal envelope, not by the payload.
- Source actor address is carried by the daemon signal source context.
- Handler must re-read Track comment state from source truth before prompting.

## Handler Responsibilities

`TrackCommentInboundHandler` must:

- expose the same unified daemon handler shape as `MessageAvailableHandler`;
- handle only `track.comment.added`;
- reject triggers for the wrong target actor;
- require payload object with `track_id`, `comment_id`, and `thread_id`;
- fetch the exact Track comment row;
- verify the row belongs to the exact Track and thread in the payload;
- verify the target actor is a valid intended recipient for this comment by recomputing
  mention/reply targets from source truth;
- verify the Track is non-archived and readable to the target actor;
- check `runtime.parent_activity()`;
- submit a parent prompt when parent is idle;
- submit a side triage prompt when parent is running;
- fail loudly when runtime activity is unavailable.

## Prompt Requirements

Prompt text is Track-owned.

Parent prompt should say one exact Track comment needs attention and should direct the actor to use:

- `track.open(track_id=...)`;
- `track.list_comments(track_id=..., status="all")`;
- `track.add_comment(track_id=..., reply_to=...)` when a reply is useful;
- `track.resolve_comment_thread(...)` only when the active actor has PM authority and resolution is
  appropriate.

Side triage prompt should be similar but framed as quick triage while the parent is busy.

Prompts must not mention:

- Notification Center internals;
- daemon mailbox implementation details;
- parent thread ids or side thread ids;
- `notification.*` tools;
- `nc.notification`;
- message-specific `absorbed`, `replied`, or `needs_parent` dispositions.

## Tool Result Behavior

`track.add_comment` should remain a successful durable Track-state mutation when comment creation
succeeds.

On delivery:

- successful deliveries should be summarized in the result;
- unreachable/offline target actors should be reported without rolling back the comment row;
- invalid mention payloads should still reject before comment creation, as they do today;
- unexpected delivery plumbing errors should be visible in response metadata and tests, not hidden.

This differs from direct message delivery. Direct message creation depends on delivering to a target
inbox. Track comment creation is shared Track state and must not depend on every mentioned actor
being online.

## Artifact Inbound Decision

Do not implement Artifact inbound in this task.

Reason:

- Artifact is currently owner-created content.
- Track relation makes Artifact readable in shared Track context.
- `track.add_material` and `track.add_proof` do not name a concrete target actor.
- Notifying the Artifact owner is usually redundant because the owner created or related the
  Artifact.
- Broadcasting `artifact.shared` to all readable Track collaborators would turn Artifact into a
  noisy implicit notification source.

Future Artifact inbound is allowed only after an explicit actor-attention semantic exists, such as:

- `share_to`;
- `requested_review_by`;
- `attention_actors`;
- a future Artifact review/request-change workflow.

Only then should Artifact own a native event such as `artifact.shared` or a more specific
Artifact event.

## Non-Negotiables

- Do not add actor-facing `notification.*` tools.
- Do not add `nc.notification` wrapper events.
- Do not move Track comment semantics into NC.
- Do not copy message dispositions into Track comments.
- Do not add a generic cross-source inbound lifecycle.
- Do not broadcast Track comments or Artifacts without explicit target actors.
- Do not implement Artifact inbound until the product has a concrete target-actor attention action.

## Expected File Ownership

Track Comment source-owned work may touch:

- `scripts/env/tools/track/_impl.py`
- `scripts/env/tools/track/tool.py`
- `scripts/env/repos/track_comments.py`
- a new Track comment inbound module under `tools/launcher/`
- Track comment prompt/domain helper code if needed
- `scripts/env/tool_runtime/context.py` for a small `deliver_track_comment_added` convenience helper,
  or direct use of `deliver_signal`
- tests for Track comment delivery, handler routing, and tool result semantics

NC plumbing work may touch only registration aggregation:

- `tools/launcher/instance_daemon.py`
- source registration tests that prove Track comment registration is added without NC business logic

NC core must remain semantic-light.

## Acceptance Criteria

- `track.add_comment` with `mentioned_actors` delivers `track.comment.added` to those concrete actors.
- `track.add_comment` with `reply_to` delivers `track.comment.added` to the parent comment author.
- Duplicate targets are delivered once.
- The comment author is not notified for their own comment.
- Comments without mention or reply create durable state without async delivery.
- Offline/unreachable targets do not roll back the Track comment row.
- `TrackCommentInboundHandler` routes idle parent to parent prompt.
- `TrackCommentInboundHandler` routes running parent to side triage prompt.
- Handler rejects wrong target actor, missing ids, wrong Track/thread, unreadable Track, and archived
  Track.
- Prompt text uses Track tools and does not expose daemon/NC internals.
- `instance_daemon` registers the Track comment source through source registration aggregation, not
  NC business branching.
- Tests prove NC does not import Track comment repos, render prompts, or choose routing.
- No Artifact inbound handler or `artifact.shared` registration is added in this task.

## Definition Of Done

The task is done when Track comment mentions and replies can asynchronously reach the intended actor
through source-owned parent/side handling, while NC remains pure notify infrastructure and Artifact
inbound remains deferred until explicit actor-attention semantics exist.
