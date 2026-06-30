# Task Sys IM Completion / Status / Observability Orientation

Date: 2026-06-30

## Target

Make IM-origin Task Sys work close explicitly through `task_sys.close`, show active Task Sys residue separately from daemon handler health, and add compact runtime breadcrumbs without touching the parallel iMessage channel/API optimization.

## Required Execution Constraints

- Correct boundary first: implement product semantics in the owning module, not in prompt bulk, daemon status, or watcher shortcuts.
- Task Sys owns task lifecycle state and transitions. Daemon/status may project Task Sys state read-only.
- Central IM owns message creation, reply, and disposition. This task does not prove external iMessage phone delivery.
- Replace stale side-only close semantics directly. Do not keep old and new close paths side by side.
- Clean live residue: code, tool descriptions, runtime prompts, tests, and current spec docs must teach the replacement semantics.
- Preserve the end-to-end contract: inbound IM task -> side need_parent -> parent work -> source-bound IM action -> explicit `task_sys.close` -> status/log visibility.
- Treat service-starting tests as lifecycle-owned. Use focused tests before broad launcher/runtime verification.
- Keep this change inside its parallel boundary. Do not touch iMessage channel/API files from the sibling optimization.

## Non-Goals

- Do not fix iMessage phone delivery, External IM event ack, or iMessage channel worker split.
- Do not infer Task Sys completion from parent turn completion.
- Do not infer Task Sys completion from message disposition watchers.
- Do not create a second Task Sys state machine in daemon status.
- Do not build a logging platform, event bus, generic tracing framework, feature flag, compatibility alias, or dual-path transition.
- Do not edit `buddyswitch/objects/**`, `buddyswitch/local/private/**`, or runtime state files directly.

## Prohibited Parallel Files

Do not modify these files unless the user explicitly approves merging this task with the parallel iMessage channel/API task:

- `tools/launcher/imessage_channel.py`
- `tools/launcher/external_im_session.py`
- `tools/launcher/im_http_router.py`
- `tools/launcher/web_management.py`
- `tests/test_imessage_channel.py`
- `tests/test_external_im_session.py`
- `tests/test_im_http_router.py`
- `tests/test_im_web_management_projection.py`

## Phase Plan

1. Task Sys close semantic replacement: make `task_sys.close` the shared side/parent frame completion operation.
2. Parent frame completion contract: require parent frames to complete source-bound work, then call `task_sys.close`.
3. Instance status Task Sys projection: show active Task Sys residue separately from daemon handler health and external delivery scope.
4. Minimal runtime breadcrumb logs: write small structured JSONL events at daemon/app-server/runtime-broker lifecycle and dispatch boundaries.
5. Status log metadata and final acceptance: expose compact log metadata and complete final verification/residue proof.

Each implementation phase gets its own plan doc before tests or production code, uses failing tests first, records actual verification output, and must pass its acceptance gates before the next phase starts.

## Current Code Investigation Summary

- At orientation time, `scripts/env/domain/task_sys.py` still allowed close through the side-result domain path and had no `record_task_close(...)` operation.
- At orientation time, `scripts/env/tools/task_sys/_impl.py` routed `task_sys.close` through that side-result close path, so parent-processing tasks were not explicitly supported by a shared close operation.
- `scripts/env/tools/task_sys/tool.py` still describes Task Sys as side-result reporting and describes `task_sys.close` as closing from side processing without parent handoff.
- `tests/test_task_sys_substrate.py` and `tests/test_task_sys_side_processing.py` cover the old side-result close shape and need new failing tests for side close, parent close, retry-safe closed close, and invalid statuses.
- `tools/launcher/task_sys_runtime.py` has strong side-frame IM closure order language, but `render_parent_frame(...)` still only says to process the parent frame and does not require source-bound IM action before `task_sys.close`.
- `tests/test_task_sys_runtime_executor.py` checks only the broad parent frame shape today, not explicit close requirements or checkpoint-update forbiddance in parent frames.
- `tools/launcher/daemon_core.py` status currently returns daemon runtime, schedules, handlers, and notify data. It does not include a read-only Task Sys active-residue projection or log metadata.
- `buddyswitch-codex instance status` prints daemon/app-server health and handler names, but not Task Sys active count, active statuses, or the delivery-scope warning.
- Existing runtime log files are created by service paths, but there is no `tools/launcher/runtime_event_log.py` JSONL breadcrumb helper and no structured daemon/app-server/runtime-broker events.
- Initial `git status --short` showed the target memo as untracked user-provided work. No prohibited parallel iMessage files were modified at orientation time.

## Total Acceptance Criteria

- `task_sys.close(task_id=...)` closes tasks in `side_processing` or `parent_processing`, records close metadata, clears `active_processor`, and is retry-safe for already closed tasks.
- `task_sys.need_parent` remains the side-owned handoff operation and still moves tasks through `needs_parent` to `parent_processing` only through Task Sys runtime instructions.
- `task_sys.checkpoint_update` remains checkpoint-only.
- Parent frame text explicitly requires source-bound completion and then `task_sys.close`, including IM reply/absorbed ordering and duplicate-reply avoidance if close must be retried.
- Status JSON includes a daemon `task_sys` read-only projection with active count, by-status counts, and compact active task summaries.
- Human status distinguishes daemon handler dispatch health from external iMessage phone delivery and prints active Task Sys residue.
- Runtime logs contain minimal structured breadcrumb JSONL events without raw IM content, artifact bodies, credentials, prompts, or full tool payloads.
- Status JSON exposes compact log metadata and last structured event, not arbitrary log tails.
- Focused Task Sys, env tool contract, daemon/status/logging, py_compile, and residue scans pass.
- `git diff --name-only` proves the prohibited parallel iMessage channel/API files were not touched.
