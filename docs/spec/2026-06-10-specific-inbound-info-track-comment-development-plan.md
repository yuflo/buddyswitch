# Specific Inbound Track Comment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this
> plan task-by-task in `main`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add source-owned async inbound handling for Track comments without moving Track semantics
into Notification Center and without adding Artifact inbound.

**Architecture:** Keep one concrete Track comment inbound path. Track domain code derives target
actors and renders prompts; `track.add_comment` writes durable state before best-effort delivery;
Notification Center only aggregates source registrations; the Track handler re-reads source truth
before routing to parent or side runtime prompts.

**Tech Stack:** Python env tools, file-backed Track/Track comment repos, launcher daemon handlers,
unittest/pytest isolated runtime-root tests.

---

## File Map

- Create `scripts/env/domain/track_comments.py`: Track comment target derivation and Track-owned
  prompt rendering.
- Modify `scripts/env/tool_runtime/context.py`: add `DaemonAccess.deliver_track_comment_added`.
- Modify `scripts/env/tools/track/_impl.py`: after durable comment creation, derive target actors,
  deliver `track.comment.added`, and return delivery metadata.
- Create `tools/launcher/track_comment_added_handler.py`: source-owned daemon trigger handler for
  `track.comment.added`.
- Create `tools/launcher/track_comment_inbound.py`: Track-owned inbound registration metadata.
- Modify `tools/launcher/instance_daemon.py`: include Track comment source registrations through NC.
- Modify `tests/test_track_comment_env_tool.py`: delivery behavior tests.
- Create `tests/test_track_comment_added_handler.py`: handler validation and prompt routing tests.
- Modify `tests/test_notification_center.py`: Track comment registration contract.
- Modify `tests/test_instance_daemon_entrypoint.py`: default subscription and handler list.
- Modify `tests/test_daemon_communication_boundary.py`: NC semantic-light and Artifact inbound guards.
- Modify `tests/test_runtime_actor_profile.py`: context delivery helper contract.

## Task 1: Add Phase 1 Spec Artifacts

- [x] Create this implementation plan in `docs/spec`.
- [x] Create the matching test plan in `docs/spec`.
- [x] Create the Phase 2 prompt in `docs/spec`.
- [x] Review the plans against the source memo and resource lifecycle bitter note.

## Task 2: Add Failing Track Tool Delivery Tests

**Files:**
- Modify: `tests/test_track_comment_env_tool.py`

- [ ] Add a `_patch_daemon_delivery` helper that patches
  `env.tool_runtime.daemon_client.deliver_signal`, records signals, and restores the original in
  cleanup.
- [ ] Add `test_add_comment_delivers_track_comment_added_to_mentions_once`.
- [ ] Add `test_add_comment_reply_notifies_parent_author_once`.
- [ ] Add `test_add_comment_without_attention_creates_state_without_delivery`.
- [ ] Add `test_add_comment_delivery_failure_keeps_comment_and_reports_status`.
- [ ] Add `test_add_comment_delivery_exception_keeps_comment_and_reports_signal_error`.
- [ ] Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_track_comment_env_tool.py -q
```

Expected before implementation: new delivery assertions fail because `track.add_comment` does not
deliver `track.comment.added` or report delivery metadata.

## Task 3: Implement Track Domain Target Derivation And Tool Delivery

**Files:**
- Create: `scripts/env/domain/track_comments.py`
- Modify: `scripts/env/tool_runtime/context.py`
- Modify: `scripts/env/tools/track/_impl.py`

- [ ] Implement `track_comment_targets(comment, reply_to_comment=None)`:
  - normalize ActorAddress payloads;
  - include all `mentioned_actors`;
  - include `reply_to_comment["by_actor"]` when present;
  - remove the new comment author;
  - deduplicate by `(actor_id, role_id)`.
- [ ] Implement `track_comment_added_payload(comment)` returning exactly `track_id`, `comment_id`,
  and `thread_id`.
- [ ] Add `DaemonAccess.deliver_track_comment_added(track_id, comment_id, thread_id, target_actor_address)`.
- [ ] After `context.repos.track_comment.create_track_comment` or `reply_to_track_comment` succeeds,
  fetch the reply parent if `reply_to` is present, derive targets, deliver to each target, and catch
  delivery exceptions as response metadata.
- [ ] Add response fields:
  - `delivery_status`;
  - `delivery_summary`;
  - `delivery_results`.
- [ ] Do not roll back the comment row for `target_not_online`, `delivery_failed`, ignored handler,
  or delivery exceptions.
- [ ] Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_track_comment_env_tool.py -q
```

Expected after implementation: Track comment env-tool delivery tests pass.

## Task 4: Add Failing Track Comment Handler Tests

**Files:**
- Create: `tests/test_track_comment_added_handler.py`

- [ ] Add a fake runtime that records parent activity and prompt submissions.
- [ ] Add isolated runtime-root setup with seeded Track and Track comment rows.
- [ ] Add tests for unknown trigger, wrong target actor, invalid payload, wrong Track, wrong thread,
  unintended target, archived Track, idle parent routing, running parent routing, and unavailable
  parent activity.
- [ ] Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_track_comment_added_handler -v
```

Expected before implementation: import failure because `tools/launcher/track_comment_added_handler.py`
does not exist.

## Task 5: Implement Track Comment Handler And Prompt Rendering

**Files:**
- Modify: `scripts/env/domain/track_comments.py`
- Create: `tools/launcher/track_comment_added_handler.py`

- [ ] Implement Track-owned prompt renderers:
  - `render_parent_track_comment_prompt(...)`;
  - `render_side_track_comment_prompt(...)`.
- [ ] Implement `TrackCommentAddedHandler.name = "track_comment_added"`.
- [ ] `handles(trigger)` returns true only for `track.comment.added`.
- [ ] `handle(...)` returns ignored for other trigger types.
- [ ] Validate target ActorAddress equals local daemon context actor address.
- [ ] Validate payload object and require `track_id`, `comment_id`, and `thread_id`.
- [ ] Fetch exact comment with `get_track_comment(track_id, comment_id)`.
- [ ] Verify stored Track id and thread id match payload.
- [ ] Fetch reply parent if present and recompute intended targets from source truth.
- [ ] Reject if target actor is not in recomputed targets.
- [ ] Fetch Track and reject missing or archived Track.
- [ ] Call `runtime.parent_activity()`.
- [ ] For `status == "idle"`, call `runtime.submit_parent_prompt(..., interrupt_policy="none")`.
- [ ] For `status == "running"`, call `runtime.submit_side_triage_prompt(...)`.
- [ ] For any other activity status, return failed with the activity error.
- [ ] Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_track_comment_added_handler -v
```

Expected after implementation: handler tests pass.

## Task 6: Add Failing Registration And Boundary Tests

**Files:**
- Modify: `tests/test_notification_center.py`
- Modify: `tests/test_instance_daemon_entrypoint.py`
- Modify: `tests/test_daemon_communication_boundary.py`
- Modify: `tests/test_runtime_actor_profile.py`

- [ ] Add Track inbound registration contract assertions.
- [ ] Update instance daemon expected subscriptions to include `track.comment.added`.
- [ ] Update instance daemon expected handlers to include `TrackCommentAddedHandler`.
- [ ] Assert instance daemon imports `track_comment_inbound`, not `track_comment_added_handler`.
- [ ] Add NC negative assertions for Track comment semantics.
- [ ] Exclude source-owned Track inbound modules from generic daemon base delivery scans.
- [ ] Add Artifact inbound absence guard.
- [ ] Add context helper delivery contract test.
- [ ] Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_notification_center \
  tests.test_instance_daemon_entrypoint \
  tests.test_daemon_communication_boundary \
  tests.test_runtime_actor_profile \
  -v
```

Expected before implementation: failures for missing `track_comment_inbound`, old subscription lists,
and missing context helper.

## Task 7: Implement Registration Wiring

**Files:**
- Create: `tools/launcher/track_comment_inbound.py`
- Modify: `tools/launcher/instance_daemon.py`

- [ ] Implement `TRACK_COMMENT_ADDED_EVENT_TYPE = "track.comment.added"`.
- [ ] Implement payload contract `{"required_fields": ("track_id", "comment_id", "thread_id")}`.
- [ ] Implement `track_comment_added_registration()`.
- [ ] Implement `inbound_registrations()`.
- [ ] Modify `instance_daemon.default_notification_registrations()` to return message registrations
  followed by Track comment registrations.
- [ ] Ensure handlers are still created by `notification_center.handlers_from_registrations`.
- [ ] Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_notification_center \
  tests.test_instance_daemon_entrypoint \
  tests.test_daemon_communication_boundary \
  tests.test_runtime_actor_profile \
  -v
```

Expected after implementation: registration and boundary tests pass.

## Task 8: Focused Behavior Verification

- [ ] Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_track_comment_env_tool.py -q
```

- [ ] Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_track_comment_added_handler -v
```

- [ ] Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_notification_center \
  tests.test_instance_daemon_entrypoint \
  tests.test_daemon_communication_boundary \
  tests.test_runtime_actor_profile \
  -v
```

Expected: all focused checks pass without starting launcher services.

## Task 9: Bounded Broad Verification And Residue Scan

- [ ] Run the bounded non-service test set:

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

- [ ] Run compile verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile \
  tools/launcher/track_comment_added_handler.py \
  tools/launcher/track_comment_inbound.py \
  tools/launcher/instance_daemon.py \
  scripts/env/domain/track_comments.py \
  scripts/env/tool_runtime/context.py \
  scripts/env/tools/track/_impl.py
```

- [ ] Run residue scans:

```bash
rg -n "artifact\\.shared|ArtifactSharedHandler|artifact_inbound" tools scripts tests -S
rg -n "nc\\.notification|notification__(mark|archive|needs_parent)|notification\\.(mark|archive|needs_parent)" tools scripts tests -S
```

Expected: tests and compile pass. Residue scan has no production implementation hits; test negative
assertion hits are allowed after inspection.

## Task 10: Final Review

- [ ] Review the diff against every acceptance criterion in the source memo.
- [ ] Confirm no Artifact inbound was implemented.
- [ ] Confirm NC has no Track comment business imports or prompt/routing logic.
- [ ] Confirm delivery failure cannot erase the durable Track comment row.
- [ ] Confirm verification followed the resource lifecycle guard.

## Phase 1 Plan Review

- [x] Spec coverage: every acceptance criterion in
  `docs/memo/2026-06-10-specific-inbound-info-track-comment-task.md` maps to tests and tasks above.
- [x] No transition path: no `nc.notification`, no generic inbound lifecycle, no Artifact inbound,
  and no Track semantics in NC.
- [x] Test-first loop: each behavior block starts with failing tests or failing contract updates.
- [x] Resource lifecycle: verification is bounded to isolated tests and pure daemon mailbox tests.
- [x] Implementation is concrete: one source-owned Track comment inbound path, no plugin/rule engine.
