# Track Comment Added Daemon State Root Fix

Date: 2026-06-12
Status: reviewed fix task memo

## Summary

`track.comment.added` delivery currently has a framework implementation bug in the target instance
daemon path.

The durable Track comment is written to the shared state root, but the target daemon process that
handles `track.comment.added` is running without `BUDDYSWITCH_STATE_ROOT`. Because the repository
helpers only use `BUDDYSWITCH_STATE_ROOT` to locate runtime object state, the daemon falls back to
the source checkout as `STATE_ROOT` and cannot find the comment row.

This explains why `act-market-b2ce8659d0c4` and `act-market-d75709cd8ac6` both failed to process
the Track comment attention event even though the comment object exists and mentions both actors.

## Observed Failure

The two target actor daemons recorded the same handler failure:

```text
comment not found for track 'track-june-ai-product-radar-proactive-2026': comment-7f5e788f6a52
```

Failing daemon state files:

```text
/Users/chen/.codex-buddyswitch/instances/act-market-b2ce8659d0c4/runtime/daemon/state.json
/Users/chen/.codex-buddyswitch/instances/act-market-d75709cd8ac6/runtime/daemon/state.json
```

The comment row exists at the correct shared state location:

```text
/Users/chen/.codex-buddyswitch/state/buddyswitch/objects/track-comments/track-june-ai-product-radar-proactive-2026/comment-7f5e788f6a52.json
```

The comment row is valid for both target actors:

```json
{
  "id": "comment-7f5e788f6a52",
  "track_id": "track-june-ai-product-radar-proactive-2026",
  "thread_id": "comment-7f5e788f6a52",
  "by_actor": {
    "actor_id": "act-market-8bc110b21321",
    "role_id": "market"
  },
  "mentioned_actors": [
    {
      "actor_id": "act-market-b2ce8659d0c4",
      "role_id": "market"
    },
    {
      "actor_id": "act-market-d75709cd8ac6",
      "role_id": "market"
    }
  ],
  "status": "open"
}
```

The live daemon processes have `BUDDYSWITCH_SHARED_ROOT` but not `BUDDYSWITCH_STATE_ROOT`:

```text
BUDDYSWITCH_SHARED_ROOT=/Users/chen/.codex-buddyswitch
BUDDYSWITCH_INSTANCE_ROOT=/Users/chen/.codex-buddyswitch/instances/<actor>
BUDDYSWITCH_WORKSPACE_DIR=/Users/chen/.codex-buddyswitch/instances/<actor>/workspace
```

When `BUDDYSWITCH_STATE_ROOT` is missing, `runtime_files.STATE_ROOT` resolves to the source checkout:

```text
STATE_ROOT=/Users/chen/Dev/buddyswitch
TRACK_COMMENTS_DIR=/Users/chen/Dev/buddyswitch/buddyswitch/objects/track-comments
```

That is the wrong location for runtime Track comment objects.

## Relevant Code Path

Creation and delivery path:

```text
track.add_comment
  -> context.repos.track_comment.create_track_comment(...)
  -> write comment row under shared state
  -> _deliver_track_comment_added(...)
  -> context.daemon.deliver_track_comment_added(...)
  -> target daemon receives track.comment.added
```

Handler path:

```text
TrackCommentAddedHandler._handle_track_comment_added(...)
  -> _ensure_target_actor(...)
  -> _source_actor_address(...)
  -> _payload(...)
  -> _comment(track_id, comment_id, thread_id)
  -> track_comment_repo.get_track_comment(...)
```

The failure occurs before parent or side thread prompting. The handler never reaches
`runtime.parent_activity()` because `_comment(...)` returns `None` and raises.

## Root Cause

`track_comment_added_handler.py` reads Track comment and Track objects through repository helpers.
Those helpers depend on process-global paths in `scripts/env/repos/runtime_files.py`.

`runtime_files.py` behavior:

```text
if BUDDYSWITCH_STATE_ROOT is set:
  STATE_ROOT = BUDDYSWITCH_STATE_ROOT
else:
  STATE_ROOT = source checkout root
```

It does not derive `STATE_ROOT` from `BUDDYSWITCH_SHARED_ROOT`.

`tools/launcher/daemon_core.py` starts the target daemon process without explicitly passing an
environment that includes:

```text
BUDDYSWITCH_STATE_ROOT=<shared-root>/state
```

`daemon_core.run_daemon(...)` also does not bind or refresh runtime roots after loading the instance
context.

Therefore, a daemon that has only `BUDDYSWITCH_SHARED_ROOT` will register and receive mailbox
signals, but any handler that pre-reads runtime objects through `runtime_files.STATE_ROOT` may read
from the wrong object directory.

`message.available` does not expose the same failure because its daemon handler only passes the
message id to the parent prompt. It does not pre-read the message object. `track.comment.added` does
pre-read the comment and Track, so the wrong state root fails immediately.

## Current Bottleneck

The bottleneck is not Track comment storage, mention target calculation, or daemon signal delivery.

The bottleneck is:

```text
target instance daemon object reads are not bound to the shared runtime state root.
```

Solving this should make `track.comment.added` prompts reach mentioned or reply-target actors when
the durable comment row already exists in shared state.

## Fix Scope

Fix framework code only.

Do not edit instance runtime object files under:

```text
/Users/chen/.codex-buddyswitch/instances/**
/Users/chen/.codex-buddyswitch/state/**
```

Do not add a compatibility lookup that searches multiple object roots. That would hide the root
binding error and make runtime truth ambiguous.

Do not weaken `TrackCommentAddedHandler._comment(...)` validation. The handler should continue to
fail when the exact Track comment row is genuinely missing.

## Recommended Minimal Fix

Bind the daemon process to the instance shared state root before any handler reads runtime objects.

The source of truth for the shared root is the instance layout:

```text
context.instance_root = <shared-root>/instances/<actor-id>
shared_root = context.instance_root.parent.parent
state_root = shared_root / "state"
```

The fix should cover both daemon entry paths:

1. `daemon_core.start_daemon(...)`
   - Spawn `instance_daemon.py run` with an explicit child environment.
   - Ensure the child environment includes:

```text
BUDDYSWITCH_SHARED_ROOT=<shared-root>
BUDDYSWITCH_STATE_ROOT=<shared-root>/state
BUDDYSWITCH_INSTANCE_ROOT=<instance-root>
BUDDYSWITCH_INSTANCE_JSON=<instance-json>
BUDDYSWITCH_WORKSPACE_DIR=<workspace-dir>
```

2. `daemon_core.run_daemon(...)`
   - After `load_daemon_context(instance_json)`, bind the current process environment to the same
     values.
   - Refresh `runtime_files` roots after binding the environment.

This two-point fix handles both normal daemon starts and direct `instance_daemon.py run` execution.

## Suggested Implementation Shape

Keep the implementation concrete and local to daemon runtime setup.

Suggested helper responsibility:

```text
derive_daemon_runtime_env(context) -> dict[str, str]
```

It should return the exact environment additions for the daemon process. It should not introduce a
generic runtime configuration system.

Suggested use:

```text
start_daemon(...)
  -> context = load_daemon_context(instance_json)
  -> child_env = os.environ.copy()
  -> child_env.update(derive_daemon_runtime_env(context))
  -> subprocess.Popen(..., env=child_env, cwd=str(context.instance_root))

run_daemon(...)
  -> context = load_daemon_context(instance_json)
  -> os.environ.update(derive_daemon_runtime_env(context))
  -> runtime_files.refresh_runtime_roots_from_env()
```

If importing `runtime_files` in `daemon_core.py` is undesirable, the refresh can live in a small
daemon-runtime helper. Do not put this logic in `TrackCommentAddedHandler`; the state root is a
daemon process invariant, not a Track-comment-specific rule.

## Regression Tests

Add focused tests before implementation.

### Test 1: `track.comment.added` handler reads from instance shared state root

File:

```text
tests/test_track_comment_added_handler.py
```

Test intent:

```text
Given:
  instance_root = <tmp>/instances/act-dev-track-handler
  shared state root = <tmp>/state
  comment exists only under <tmp>/state/buddyswitch/objects/track-comments/...
  process default runtime root points somewhere else

When:
  TrackCommentAddedHandler handles track.comment.added for the mentioned actor

Then:
  handler status is handled
  runtime receives parent_activity and submit_parent_prompt
  result is not "comment not found"
```

Expected failure before fix:

```text
result.status == "failed"
result.message contains "comment not found"
```

Expected pass after fix:

```text
result.status == "handled"
```

### Test 2: `start_daemon` passes state root to child process

File:

```text
tests/test_daemon_core.py
```

Test intent:

```text
Given:
  instance_json under <tmp>/instances/<actor>/instance.json

When:
  start_daemon(instance_json) spawns instance_daemon.py run

Then:
  subprocess.Popen receives env with:
    BUDDYSWITCH_SHARED_ROOT=<tmp>
    BUDDYSWITCH_STATE_ROOT=<tmp>/state
    BUDDYSWITCH_INSTANCE_ROOT=<tmp>/instances/<actor>
    BUDDYSWITCH_INSTANCE_JSON=<tmp>/instances/<actor>/instance.json
    BUDDYSWITCH_WORKSPACE_DIR=<tmp>/instances/<actor>/workspace
```

Expected failure before fix:

```text
Popen kwargs do not include env, or env lacks BUDDYSWITCH_STATE_ROOT.
```

Expected pass after fix:

```text
Popen kwargs include the exact daemon runtime env.
```

### Test 3: direct `run_daemon` refreshes runtime roots

File:

```text
tests/test_daemon_core.py
```

Test intent:

```text
Given:
  process starts without BUDDYSWITCH_STATE_ROOT
  instance_json is under <tmp>/instances/<actor>/instance.json

When:
  run_daemon(instance_json, ...) initializes daemon context

Then:
  runtime_files.STATE_ROOT is <tmp>/state before handlers process mailbox signals.
```

This can be tested with a short-circuit fake app server or by extracting the environment binding
helper and testing it directly. Prefer testing the helper directly if that keeps the loop small and
deterministic.

## Verification Commands

Focused verification:

```bash
python -m pytest tests/test_track_comment_added_handler.py -q
python -m pytest tests/test_daemon_core.py -q
```

Broader relevant verification:

```bash
python -m pytest tests/test_track_comment_env_tool.py tests/test_track_comments_repo.py tests/test_daemon_core.py tests/test_track_comment_added_handler.py -q
```

Manual runtime verification after tests pass:

```text
1. Start two market instances.
2. From one actor, add a Track comment mentioning the other actor.
3. Confirm target daemon state has:
   handlers.track_comment_added.last_result = "handled"
4. Confirm target actor receives a Track comment parent or side prompt.
5. Confirm the prompt instructs the actor to use Track tools, not message tools.
```

## Acceptance Criteria

The fix is complete only when all of these are true:

- `track.comment.added` handler can read a comment row stored under `<shared-root>/state`.
- Target daemon child process receives `BUDDYSWITCH_STATE_ROOT=<shared-root>/state`.
- Direct daemon run path also binds and refreshes runtime state roots.
- Existing validation remains intact:
  - wrong target actor fails;
  - missing payload ids fail;
  - wrong thread payload fails;
  - unintended target actor fails;
  - archived Track fails.
- No runtime instance object files are edited as part of the fix.
- Tests demonstrate the old failure mode and the corrected behavior.

## Risk Review

Primary risk:

```text
Changing daemon environment setup can affect all daemon handlers, not only Track comment handling.
```

Why this risk is acceptable:

```text
Daemon handlers are supposed to read shared runtime object truth. Binding the daemon to
<shared-root>/state makes the process match the runtime object contract.
```

Avoid this risky alternative:

```text
Search both source checkout and shared state for missing objects.
```

That would make object truth ambiguous and could mask future environment bugs.

Avoid this narrower alternative:

```text
Patch only TrackCommentAddedHandler to derive state root before _comment(...).
```

That may fix the immediate symptom, but the daemon process would still have incorrect runtime roots.
The state root is a daemon invariant, so it belongs in daemon setup.

## Self Audit

Clarity check:

- The observed failure is tied to exact files and exact actor ids.
- The root cause is a missing daemon `BUDDYSWITCH_STATE_ROOT`, not a missing comment.
- The fix has one main intent: bind daemon runtime object reads to shared state.
- The plan does not introduce a generic config system, fallback search path, or compatibility layer.
- The test plan includes a regression for the actual failure mode.

Scope check:

- This task should not change Track comment domain semantics.
- This task should not change mention target derivation.
- This task should not change Track comment prompt text except if existing tests require updated
  wording due to daemon setup changes.
- This task should not mutate current production-like instance state.

Review conclusion:

```text
The repair task is clear and implementable.
The smallest correct fix is daemon runtime environment binding plus focused regression coverage.
```
