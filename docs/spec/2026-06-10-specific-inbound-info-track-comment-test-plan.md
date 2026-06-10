# Specific Inbound Track Comment Test Plan

Date: 2026-06-10
Source memo: `docs/memo/2026-06-10-specific-inbound-info-track-comment-task.md`
Resource warning: `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
Worktree: `main`

## Goal

Prove that Track comments can asynchronously reach exactly the actors explicitly named by Track
comment attention, while Notification Center remains delivery plumbing only and Artifact inbound
stays deferred.

Target path:

```text
track.add_comment
  -> durable Track comment row
  -> derive explicit target ActorAddress values from mentioned_actors and reply_to author
  -> deliver track.comment.added native signal to each target
  -> TrackCommentAddedHandler re-reads Track source truth
  -> parent or side Track-owned prompt
  -> actor uses Track tools
```

## Resource Lifecycle Guard

The planned tests are import, contract, pure handler, and isolated runtime-root env-tool tests.
They must not start product daemons, app servers, browsers, watchers, detached workers, or launcher
service suites.

If any service-starting check becomes necessary, follow the bitter note first:

1. inspect helper cleanup;
2. run one focused service test;
3. check residual processes and sockets;
4. repeat the focused group;
5. only then broaden verification;
6. check residuals again.

Completion evidence for any service-starting path is:

```text
behavior passes + host resources return to baseline
```

## Functional Requirements

- `track.add_comment` with `mentioned_actors` delivers `track.comment.added` to concrete target
  actor addresses.
- `track.add_comment` with `reply_to` delivers `track.comment.added` to the replied comment author.
- Mention and reply targets are deduplicated by normalized ActorAddress.
- The new comment author is not notified about their own comment.
- A comment without mentions or reply creates durable Track state and performs no delivery.
- Offline, unreachable, ignored, or failed delivery does not roll back the durable comment row.
- Delivery results are visible in the tool response.
- Signal payload contains only `track_id`, `comment_id`, and `thread_id`; it does not carry comment
  body, target actor, or Track prompt text.
- `TrackCommentAddedHandler` validates target actor, payload ids, exact Track/comment/thread, intended
  recipient status, non-archived readable Track state, and parent activity before prompting.
- Idle parent routes to a Track-owned parent prompt.
- Running parent routes to a Track-owned side triage prompt.
- Prompt text names Track tools and does not expose Notification Center, daemon mailbox, thread ids,
  notification tools, or message dispositions.
- `instance_daemon` registers Track comment inbound through source registration aggregation.
- NC does not import Track comment repos, render Track prompts, compute target actors, or choose
  parent/side routing.
- No `artifact.shared` event or Artifact inbound handler is added.

## Test Files

Create:

- `tests/test_track_comment_added_handler.py`

Update:

- `tests/test_track_comment_env_tool.py`
- `tests/test_notification_center.py`
- `tests/test_instance_daemon_entrypoint.py`
- `tests/test_daemon_communication_boundary.py`
- `tests/test_runtime_actor_profile.py`

## Test Cases

### Track Tool Delivery Behavior

File: `tests/test_track_comment_env_tool.py`

Use isolated runtime roots and patch `env.tool_runtime.daemon_client.deliver_signal`. Do not start a
central daemon.

Cases:

1. Mention delivery.
   - Seed one non-archived Track.
   - Call `track.add_comment` as dev with two duplicate pm mentions and one self mention.
   - Assert the comment row is created.
   - Assert exactly one signal is delivered to the pm ActorAddress.
   - Assert the signal type is `track.comment.added`.
   - Assert payload equals `{"track_id": track_id, "comment_id": comment_id, "thread_id": thread_id}`.
   - Assert signal does not include content, comment body, target role shortcuts, or notification
     wrapper fields.
   - Assert the response includes delivery summary and delivery results.

2. Reply target delivery.
   - Seed a root comment authored by dev.
   - Call `track.add_comment` as pm with `reply_to=<root comment id>`.
   - Assert exactly one signal targets the root comment author.
   - Assert adding the root author again in `mentioned_actors` still produces one delivery.

3. No explicit attention.
   - Call `track.add_comment` with no `mentioned_actors` and no `reply_to`.
   - Assert the comment row is durable.
   - Assert no delivery call occurs.
   - Assert response delivery status is `no_targets` with zero target count.

4. Delivery failure does not roll back Track state.
   - Patch delivery to return `{"delivery_status": "target_not_online", ...}`.
   - Call `track.add_comment` with one valid mention.
   - Assert response is still successful because the Track comment mutation succeeded.
   - Assert the comment file exists.
   - Assert delivery result reports the target and failure status.

5. Unexpected delivery exception is visible.
   - Patch delivery to raise `RuntimeError("socket gone")`.
   - Call `track.add_comment` with one valid mention.
   - Assert response is successful and durable.
   - Assert delivery result contains `delivery_status == "delivery_failed"` and `signal_error`.

### Track Comment Handler Behavior

File: `tests/test_track_comment_added_handler.py`

Use `tempfile.TemporaryDirectory`, `runtime_files.set_runtime_root_override`, and a fake runtime that
records `parent_activity`, `submit_parent_prompt`, and `submit_side_triage_prompt`.

Cases:

1. Unknown trigger type is ignored and runtime is not called.
2. Wrong target ActorAddress fails before runtime is called.
3. Missing or non-object payload fails before runtime is called.
4. Missing `track_id`, `comment_id`, or `thread_id` fails before runtime is called.
5. Comment id from the wrong Track fails.
6. Payload `thread_id` that does not match the stored comment fails.
7. Target actor that is not in recomputed mention/reply targets fails.
8. Archived Track fails before runtime prompt submission.
9. Idle parent routes to `submit_parent_prompt` with:
   - handler name `track_comment_added`;
   - origin id equal to the comment id;
   - interrupt policy `none`;
   - prompt containing `track.open`, `track.list_comments`, `track.add_comment`, and
     `track.resolve_comment_thread`;
   - no `notification.`, `nc.notification`, `message.available`, `absorbed`, `replied`,
     `needs_parent`, `parent_thread_id`, or `side_thread_id`.
10. Running parent routes to `submit_side_triage_prompt` with the same Track-owned prompt boundary.
11. Parent activity unavailable fails loudly with the activity error.

### Source Registration And NC Boundary

Files:

- `tests/test_notification_center.py`
- `tests/test_instance_daemon_entrypoint.py`
- `tests/test_daemon_communication_boundary.py`

Cases:

1. `track_comment_inbound.inbound_registrations()` returns one registration:
   - `event_type == "track.comment.added"`;
   - payload contract required fields are `("track_id", "comment_id", "thread_id")`;
   - owner module ends with `track_comment_inbound`;
   - handler factory creates `TrackCommentAddedHandler`.
2. `instance_daemon.default_notify_subscriptions()` returns:

```python
["message.available", "track.comment.added"]
```

3. `instance_daemon.default_daemon_handlers()` returns task checkout, message available, and Track
   comment handlers through NC registrations.
4. `instance_daemon.py` imports source inbound modules but does not import source handlers directly.
5. `notification_center.py` contains no Track or message business semantics:
   - no `track_id`;
   - no `comment_id`;
   - no Track repo imports;
   - no prompt rendering;
   - no parent/side routing decisions.
6. Daemon base delivery remains generic and does not learn Track comment payload fields.

### Runtime Context Delivery Helper

File: `tests/test_runtime_actor_profile.py`

Add one isolated test proving `ToolContext.daemon.deliver_track_comment_added(...)` delegates to
generic `deliver_signal(...)` with:

```python
signal_type = "track.comment.added"
payload = {"track_id": "...", "comment_id": "...", "thread_id": "..."}
```

The helper must not add body text, Notification Center wrapper fields, or role-only target fields.

### Negative Artifact Inbound Guard

File: `tests/test_daemon_communication_boundary.py`

Assert active production source does not contain:

```text
artifact.shared
ArtifactSharedHandler
artifact_inbound
```

Historical memos/specs may mention future Artifact inbound, but runtime code must not implement it
in this task.

## Verification Commands

Use the focused commands first:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_track_comment_added_handler -v
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_track_comment_env_tool.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_notification_center tests.test_instance_daemon_entrypoint tests.test_daemon_communication_boundary -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_runtime_actor_profile -v
```

After focused groups pass, run the bounded non-service verification set:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/test_track_comment_env_tool.py \
  tests/test_track_comment_added_handler.py \
  tests/test_notification_center.py \
  tests/test_instance_daemon_entrypoint.py \
  tests/test_daemon_communication_boundary.py \
  tests/test_runtime_actor_profile.py \
  tests/test_message_available_handler.py \
  tests/test_daemon_trigger_router.py \
  tests/test_daemon_mailbox.py \
  -q
```

Run compile verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile \
  tools/launcher/track_comment_added_handler.py \
  tools/launcher/track_comment_inbound.py \
  tools/launcher/instance_daemon.py \
  scripts/env/domain/track_comments.py \
  scripts/env/tool_runtime/context.py \
  scripts/env/tools/track/_impl.py
```

Run residue checks:

```bash
rg -n "artifact\\.shared|ArtifactSharedHandler|artifact_inbound" tools scripts tests -S
rg -n "nc\\.notification|notification__(mark|archive|needs_parent)|notification\\.(mark|archive|needs_parent)" tools scripts tests -S
```

Expected: no production runtime implementation hits. Negative assertion strings in tests are allowed
after inspection.

## Phase 1 Review

- Functional coverage maps to every acceptance criterion in the memo.
- Tests start from product behavior, not implementation shortcuts.
- Delivery failure tests prove durable Track state is independent from best-effort attention.
- Handler tests prove source truth is re-read and prompt/routing stays Track-owned.
- NC tests prove NC remains semantic-light registration plumbing.
- Artifact inbound is explicitly guarded as out of scope.
- Resource lifecycle risk is controlled by avoiding daemon/app-server/browser launcher suites.
