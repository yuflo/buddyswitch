# Phase 02 - Inbound Ingress

## Phase Objective

Rebuild every actor-driving inbound source so the first product artifact is a Task Sys task. CLI input, web input, IM wakes, Track comments, and turn-complete checkout must stop submitting raw prompts directly to parent or side turns. Daemon/launcher code may keep generic transport and trigger dispatch, but business decisions must be represented as task sys source/context records and runtime instructions.

## Current Code Findings

- `buddyswitch-codex instance_input` validates the actor, reads the instance thread id, checks app server health, and calls `tools/launcher/submit_turn.py` with the raw text.
- `tools/launcher/web_management.py` routes browser input through `instance input`, so web input inherits the same raw `submit_turn` path.
- `tools/launcher/submit_turn.py` delegates to `app_server.input_turn`, which starts or steers a turn with the raw text payload.
- `tools/launcher/im_wake_handler.py` validates IM trigger target and then branches on `runtime.parent_activity()` to call `runtime.submit_parent_prompt` or `runtime.submit_side_triage_prompt` with IM-specific prompts.
- `tools/launcher/track_comment_added_handler.py` validates Track comment targeting/readability and then branches on `runtime.parent_activity()` to call parent or side prompt submission with Track-specific prompt renderers.
- `tools/launcher/task_checkout_handler.py` handles completed parent turns by reading taskbox state, rendering `[TASK CHECKPOINT]`, and calling `runtime.submit_parent_prompt`.
- `tools/launcher/daemon_core.py` still owns generic parent/side turn actuation helpers. Phase 2 does not delete those helpers yet because later Task Sys phases need a generic executor target, but no inbound product source may call them directly.

## Old Paths To Remove

- CLI/Web raw text input to `tools/launcher/submit_turn.py`.
- IM handler `_parent_prompt`, `_side_prompt`, `runtime.parent_activity()`, `runtime.submit_parent_prompt`, and `runtime.submit_side_triage_prompt` decisions.
- Track comment handler prompt rendering and direct parent/side prompt submission.
- Turn-complete checkout handler taskbox read, `[TASK CHECKPOINT]` render, and direct parent submit.
- Tests that assert inbound sources choose parent vs side based on parent activity.

## New Main Path

- Add a launcher-side ingress module that converts actor-driving inbound events into Task Sys envelopes and calls `env.domain.task_sys.ingest`.
- `task_sys.ingest` remains the product-domain boundary. It persists the task and returns an instruction such as `start_side` or `no_actor_action`.
- CLI/Web input constructs a `user.input` source with the text in source context and returns the persisted task id/instruction as command JSON. It must not call `submit_turn.py`.
- IM wake handling constructs an `im.message.created` source with message, conversation, and event ids. It must validate target actor but must not inspect parent activity or decide parent/side prompt text.
- Track comment handling keeps concrete source validation needed to avoid delivering the wrong comment to the wrong actor, then constructs a `track.comment.added` source with track/comment/thread/source actor references. It must not render prompts.
- Turn-complete checkout constructs an `app_server.turn_completed` source task and returns a no-actor-action instruction for now. Checkpoint policy is rebuilt in a later phase.
- Runtime maintenance triggers that do not drive actor work remain outside Task Sys.

## Implementation Steps

- [x] Add failing CLI/Web user input tests that expect `instance input --json` to return a Task Sys task and prove it does not call `submit_turn.py`.
- [x] Implement the minimal launcher ingress helper and route `buddyswitch-codex instance_input` through it.
- [x] Add failing IM wake tests that expect a Task Sys task and no runtime parent/side calls.
- [x] Replace IM handler prompt branching with Task Sys ingestion.
- [x] Add failing Track comment tests that expect a Task Sys task and no prompt renderer or runtime parent/side calls.
- [x] Replace Track comment handler prompt branching with Task Sys ingestion while retaining target/readability validation.
- [x] Add failing turn-complete checkout tests that expect Task Sys ingestion and no `[TASK CHECKPOINT]` prompt submit.
- [x] Replace checkout prompt submission with Task Sys ingestion.
- [x] Remove obsolete prompt-render imports/functions from touched handlers.

## Test Plan

Focused tests:

- `python -m pytest tests/test_submit_turn.py tests/test_buddyswitch_launcher.py tests/test_im_wake_handler.py tests/test_track_comment_added_handler.py tests/test_task_checkout_handler.py -q`

Substrate guard:

- `python -m pytest tests/test_task_sys_substrate.py -q`

Broader relevant tests:

- `python -m pytest tests/test_daemon_core_decoupling.py tests/test_daemon_service_contract.py tests/test_notification_center.py tests/test_instance_daemon_entrypoint.py -q`

## Residue Search Plan

- `rg -n "python3 \"\\$\\{SUBMIT_TURN_HELPER\\}\"|SUBMIT_TURN_HELPER|submit_turn.py\" buddyswitch-codex tools tests -S`
- `rg -n "submit_parent_prompt|submit_side_triage_prompt|parent_activity\\(" tools/launcher/im_wake_handler.py tools/launcher/track_comment_added_handler.py tools/launcher/task_checkout_handler.py tests/test_im_wake_handler.py tests/test_track_comment_added_handler.py tests/test_task_checkout_handler.py -S`
- `rg -n "\\[IM MESSAGE|\\[IM MESSAGE TRIAGE|\\[TRACK COMMENT|\\[TRACK COMMENT TRIAGE|\\[TASK CHECKPOINT\\]|render_parent_track_comment_prompt|render_side_track_comment_prompt|render_stop_task_tui" tools/launcher scripts/env/domain tests -S`
- `rg -n "turn/start|turn/steer|text_input_payload\\(" buddyswitch-codex tools/launcher tests -S`

Expected residue after this phase:

- Generic runtime actuator helpers in `tools/launcher/daemon_core.py` and `tools/launcher/submit_turn.py` may remain until the Task Sys executor phase.
- Domain renderers in `scripts/env/domain/task_tui.py` and `scripts/env/domain/track_comments.py` may remain until their owning removal phase only if no inbound path imports or calls them.

## Verification Commands

- `python -m pytest tests/test_submit_turn.py tests/test_buddyswitch_launcher.py tests/test_im_wake_handler.py tests/test_track_comment_added_handler.py tests/test_task_checkout_handler.py -q`
- `python -m pytest tests/test_task_sys_substrate.py -q`
- `python -m pytest tests/test_daemon_core_decoupling.py tests/test_daemon_service_contract.py tests/test_notification_center.py tests/test_instance_daemon_entrypoint.py -q`
- Residue searches from this document.
- `git diff --check`

## Actual Modification Summary

- Added `tools/launcher/task_sys_ingress.py` as the launcher-side ingress adapter for actor-driving inbound sources. It builds concrete Task Sys envelopes for `user.input`, `im.message.created`, `track.comment.added`, and `app_server.turn_completed`.
- Routed `buddyswitch-codex instance input` through Task Sys ingress. It now returns `action=task_created`, `task_id`, and `instruction_type` instead of starting or steering a turn.
- Updated `tools/launcher/web_management.py` to project `task_id` and `instruction_type` for web user input and stop projecting input `turn_id`/`expected_turn_id`.
- Rebuilt `tools/launcher/im_wake_handler.py` so IM wakes validate the target actor and persist an `im.message.created` task without inspecting parent activity or submitting parent/side prompts.
- Rebuilt `tools/launcher/track_comment_added_handler.py` so Track comment wakes keep recipient/readability validation and persist a `track.comment.added` task without rendering Track prompts or submitting parent/side prompts.
- Rebuilt `tools/launcher/task_checkout_handler.py` so completed parent turns persist an `app_server.turn_completed` task with `initial_processor=none` and no checkpoint prompt.
- Updated boundary tests to assert the new Task Sys-first behavior and the absence of taskbox/TUI imports from daemon-side checkout.

## Deleted Old Paths

- Removed CLI user-input use of `python3 "${SUBMIT_TURN_HELPER}"`.
- Removed IM handler `_parent_prompt` and `_side_prompt`.
- Removed IM handler `runtime.parent_activity()`, `runtime.submit_parent_prompt`, and `runtime.submit_side_triage_prompt` decisions.
- Removed Track comment handler prompt rendering and parent/side submit branches.
- Removed task checkout handler imports of `submit_turn`, `task_management`, and `task_tui`.
- Removed task checkout handler `[TASK CHECKPOINT]` render and direct parent submit path.
- Removed dead checkout test helper that still rendered checkpoint prompts.

## Tests Added Or Changed

- `tests/test_submit_turn.py` now asserts `instance_input` routes through `task_sys_ingress.py`, not `submit_turn.py`.
- `tests/test_buddyswitch_launcher.py` now asserts input creates persisted Task Sys records, no input `turn/start` or `turn/steer` RPCs occur, and daemon turn-complete notifications create Task Sys completion records instead of checkpoint turns.
- `tests/test_web_management.py` now asserts web input returns task ids and instruction types, not input turn ids.
- `tests/test_im_wake_handler.py` now asserts IM wakes create `im.message.created` tasks and do not call runtime prompt methods.
- `tests/test_track_comment_added_handler.py` now asserts Track comments create `track.comment.added` tasks and do not call runtime prompt methods.
- `tests/test_task_checkout_handler.py` now asserts completed turns create closed `app_server.turn_completed` tasks and do not record daemon-origin prompt turns.
- `tests/test_daemon_core_decoupling.py` now asserts daemon-side checkout has no taskbox/TUI imports.

## Actual Verification

- Red checks observed before implementation:
  - `python -m pytest tests/test_submit_turn.py::SubmitTurnTests::test_instance_input_source_routes_through_task_sys_ingress tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_input_json_creates_task_sys_task_when_thread_idle -q` failed on the old `submit_turn.py` path.
  - `python -m pytest tests/test_im_wake_handler.py -q` failed on the old `parent_activity()`/prompt path.
  - `python -m pytest tests/test_track_comment_added_handler.py -q` failed on the old parent/side routing path.
  - `python -m pytest tests/test_task_checkout_handler.py -q` failed on the old checkpoint prompt path.
- Focused tests:
  - `python -m pytest tests/test_submit_turn.py tests/test_buddyswitch_launcher.py tests/test_im_wake_handler.py tests/test_track_comment_added_handler.py tests/test_task_checkout_handler.py tests/test_web_management.py::WebManagementHTTPTests::test_input_route_delegates_and_reports_task_sys_task tests/test_web_management.py::WebManagementHTTPActionTests::test_user_input_does_not_use_internal_bootstrap_marker -q`
  - Result: `231 passed, 49 subtests passed in 626.51s`.
- Substrate guard:
  - `python -m pytest tests/test_task_sys_substrate.py -q`
  - Result: `5 passed, 16 subtests passed in 0.05s`.
- Broader relevant tests:
  - `python -m pytest tests/test_daemon_core_decoupling.py tests/test_daemon_service_contract.py tests/test_notification_center.py tests/test_instance_daemon_entrypoint.py -q`
  - First run failed on stale taskbox-import expectation; after updating that contract, result was `47 passed, 26 subtests passed in 0.17s`.
- Syntax/diff checks:
  - `python -m py_compile tools/launcher/task_sys_ingress.py tools/launcher/im_wake_handler.py tools/launcher/track_comment_added_handler.py tools/launcher/task_checkout_handler.py scripts/env/domain/task_sys.py`
  - Result: pass.
  - `git diff --check`
  - Result: pass.
- Residue search results:
  - `SUBMIT_TURN_HELPER` remains only as the generic helper declaration/check and submit-turn tests; `instance_input` no longer calls it.
  - Touched launcher handlers have no `submit_parent_prompt`, `submit_side_triage_prompt`, or `parent_activity()` hits; remaining hits are test fakes that assert those methods are not called.
  - `[TASK CHECKPOINT]`, Track prompt renderers, and task TUI helpers remain only in domain helpers and their existing tests for later phases; no touched inbound handler imports or calls them.
  - `turn/start`, `turn/steer`, and `text_input_payload` remain in generic app-server/side/fake-Codex surfaces and tests; user input and turn-complete tests assert they are absent from the rebuilt inbound paths.

## Acceptance Status

Accepted for Phase 2. All actor-driving inbound sources touched by this phase now create Task Sys tasks first, and the old direct prompt/turn submission paths were removed from CLI/Web user input, IM wakes, Track comment wakes, and turn-complete checkout.
