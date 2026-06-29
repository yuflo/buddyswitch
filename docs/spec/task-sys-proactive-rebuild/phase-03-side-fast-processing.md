# Phase 03 - Side Fast Processing

## Phase Objective

Make side threads the Task Sys fast-processing executor. A side thread must receive a `task_sys.side_frame`, not handler-owned IM/Track/user prompt text, and it must return only `close` or `need_parent(params)` through a Task Sys tool. Daemon/launcher code may execute physical side start/send actions, but it must not decide side outcomes, submit parent work, or interrupt parent work.

## Current Code Findings

- Phase 2 `task_sys.ingest` returns a `start_side` runtime instruction with a `task_sys.side_frame`, but CLI input and daemon handlers do not execute that instruction yet.
- `tools/launcher/daemon_core.py` has generic side physical helpers: `_start_side_triage`, `_send_side_triage`, and `submit_side_triage_prompt`. They start/reuse side threads with raw text and record runtime facts.
- `buddyswitch-codex instance side` remains a direct human/manual side command. It is not an actor-driving inbound source, but its app-server side-start code is the physical behavior Task Sys can reuse.
- No Task Sys tool exists for a side thread to report `close` or `need_parent(params)`.
- `scripts/env/domain/task_sys.py` has task persistence and runtime instruction shapes, but no side-result state transition.

## Old Paths To Remove

- Any Phase 2 handler or CLI path that creates a task but drops the returned `start_side` instruction.
- Any use of `submit_side_triage_prompt` from actor-driving inbound handlers.
- Side prompt text owned by business handlers.
- Any side result shape other than `close` or `need_parent(params)`.
- Any side result path that directly submits or interrupts the parent.

## New Main Path

- Add a generic Task Sys runtime executor for `start_side` instructions.
- The executor renders a generic Task Sys side frame from the instruction frame and starts or reuses a side thread using existing app-server side physical actions.
- CLI/Web user input executes the returned `start_side` instruction after task creation.
- IM and Track daemon handlers execute the returned `start_side` instruction through the daemon runtime.
- Add Task Sys side-result state transitions in `scripts/env/domain/task_sys.py`:
  - `close` sets the task closed and clears active processing.
  - `need_parent(params)` records normalized parent handoff params, sets the task to `needs_parent`, and clears active processing.
- Add a native env tool `task_sys` with exactly two side-result actions:
  - `task_sys.close`
  - `task_sys.need_parent`
- The `need_parent` payload may include parent frame context, relation/context note, `interrupt: true|false`, and simple ordering metadata. `interrupt` is a parameter, not an outcome.

## Implementation Steps

- [x] Add failing Task Sys domain tests for side result `close`, side result `need_parent`, and rejection of unsupported outcomes such as `interrupt`.
- [x] Implement Task Sys side-result state transitions in `scripts/env/domain/task_sys.py`.
- [x] Add failing native tool tests proving only `close` and `need_parent` are registered for side results.
- [x] Implement `scripts/env/tools/task_sys/tool.py` and `_impl.py`.
- [x] Add failing runtime executor tests for executing a `start_side` instruction without reading business source fields for decisions.
- [x] Implement a generic launcher/daemon Task Sys runtime executor for `start_side`.
- [x] Route CLI/Web input and IM/Track handlers to execute the `start_side` instruction after ingestion.
- [x] Render a generic side frame that names the task id, source ref/context, and the two legal Task Sys result tool actions.
- [x] Keep turn-complete `no_actor_action` unchanged until the checkpoint phase.

## Test Plan

Focused tests:

- `python -m pytest tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py -q`
- `python -m pytest tests/test_task_sys_runtime_executor.py tests/test_submit_turn.py tests/test_im_wake_handler.py tests/test_track_comment_added_handler.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_input_json_creates_task_sys_task_when_thread_idle -q`

Broader relevant tests:

- `python -m pytest tests/test_buddyswitch_launcher.py tests/test_daemon_service_contract.py tests/test_web_management.py -q`

## Residue Search Plan

- `rg -n "submit_side_triage_prompt\\(" tools/launcher scripts tests -S`
- `rg -n "\\[IM MESSAGE TRIAGE|\\[TRACK COMMENT TRIAGE|Side triage|triage prompt" tools/launcher scripts/env/domain tests -S`
- `rg -n "side_interrupt|outcome.*interrupt|interrupt.*side outcome" scripts/env tools tests -S`
- `rg -n "task_sys.side_frame|task_sys.close|task_sys.need_parent|start_side" tools scripts tests -S`

Expected residue after this phase:

- Generic physical side helpers may remain in daemon/app-server modules.
- Manual `instance side` command may remain as a manual runtime tool, not actor-driving ingress.
- Old domain prompt renderers may remain until their owning removal phase only if no inbound path calls them.

## Verification Commands

- Focused tests from this document.
- Broader relevant tests from this document.
- Residue searches from this document.
- `python -m py_compile scripts/env/domain/task_sys.py scripts/env/tools/task_sys/tool.py scripts/env/tools/task_sys/_impl.py tools/launcher/task_sys_runtime.py tools/launcher/task_sys_ingress.py`
- `git diff --check`

## Actual Modification Summary

- Added Task Sys side-result transitions to `scripts/env/domain/task_sys.py`.
  - `close` marks the task `closed`, clears active processing, records a side result, and leaves `parent_handoff_params` empty.
  - `need_parent(params)` marks the task `needs_parent`, clears active processing, records normalized parent handoff params, and keeps `interrupt` as a parameter.
- Added native env tool package `scripts/env/tools/task_sys/` with exactly `close` and `need_parent` actions.
- Added `task_sys.close` and `task_sys.need_parent` to common role permissions.
- Added `tools/launcher/task_sys_runtime.py` to render generic `task_sys.side_frame` text and execute `start_side`/`no_actor_action` instructions.
- Updated `tools/launcher/task_sys_ingress.py` to return the full runtime instruction in its payload.
- Updated CLI input and IM/Track handlers to execute returned `start_side` instructions.
- Updated checkout to execute returned `no_actor_action`; it remains a no-op until the checkpoint phase.
- Updated launcher input tests so user input now proves side thread start with a Task Sys frame, not direct parent start/steer.

## Deleted Old Paths

- Removed the Phase 2 behavior where actor-driving inbound sources created tasks but dropped `start_side` instructions.
- No actor-driving inbound handler calls `submit_side_triage_prompt`.
- Business-owned IM/Track side prompt text is not used by active inbound handlers.
- Side `interrupt` is not accepted as an outcome; it is only valid inside `need_parent(params)`.

## Tests Added Or Changed

- Added `tests/test_task_sys_side_processing.py` for side result state transitions and tool registration.
- Added `tests/test_task_sys_runtime_executor.py` for generic side-frame rendering and physical side execution.
- Updated IM and Track handler tests to assert a `start_side` instruction is executed through the generic Task Sys executor.
- Updated launcher input tests to assert side `turn/start` uses a `task_sys.side_frame` and does not steer the parent turn.
- Kept checkout tests on `no_actor_action`.

## Actual Verification

- Red checks observed before implementation:
  - `python -m pytest tests/test_task_sys_side_processing.py -q` failed because `record_side_result` and the `task_sys` tool did not exist.
  - `python -m pytest tests/test_task_sys_runtime_executor.py -q` failed because `tools/launcher/task_sys_runtime.py` did not exist.
  - Handler and launcher input tests failed after wiring execution until their contracts were updated to assert `start_side`.
- Focused tests:
  - `python -m pytest tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_runtime_executor.py tests/test_im_wake_handler.py tests/test_track_comment_added_handler.py tests/test_task_checkout_handler.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_input_creates_task_sys_task_when_thread_idle tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_input_json_creates_task_sys_task_when_thread_idle tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_input_creates_task_sys_task_when_thread_active tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_input_json_creates_task_sys_task_when_thread_active tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_input_records_task_without_steering_non_steerable_active_turn tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_input_records_task_without_materializing_turn -q`
  - Result: `46 passed, 23 subtests passed in 35.34s`.
- Broader relevant tests:
  - `python -m pytest tests/test_buddyswitch_launcher.py tests/test_daemon_service_contract.py tests/test_web_management.py -q`
  - Result: `285 passed, 81 subtests passed in 764.16s`.
- Compile/diff checks:
  - `python -m py_compile scripts/env/domain/task_sys.py scripts/env/tools/task_sys/tool.py scripts/env/tools/task_sys/_impl.py tools/launcher/task_sys_runtime.py tools/launcher/task_sys_ingress.py tools/launcher/im_wake_handler.py tools/launcher/track_comment_added_handler.py tools/launcher/task_checkout_handler.py`
  - Result: pass.
  - `git diff --check`
  - Result: pass.
- Residue search results:
  - `submit_side_triage_prompt(` remains only in generic daemon runtime/tests and test fakes, not in actor-driving inbound handlers.
  - Old IM/Track side triage prompt strings remain only in old domain helper/test surfaces, not active inbound handlers.
  - `interrupt` as side outcome is rejected by tests; runtime frame text names interrupt only as a `task_sys.need_parent` parameter.
  - `task_sys.side_frame`, `task_sys.close`, `task_sys.need_parent`, and `start_side` are present in the new Task Sys runtime path and tests.

## Acceptance Status

Accepted for Phase 3. Actor-driving inbound sources now execute Task Sys `start_side` instructions through a generic side frame, and side processors have only `task_sys.close` or `task_sys.need_parent(params)` as structured outcomes.
