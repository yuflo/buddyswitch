# Phase 0: Boundary And Residue Map

## Phase Objective

Use the Phase 0 target in `docs/memo/2026-06-29-task-sys-proactive-rebuild.md` to freeze architecture boundaries and deletion targets before implementation.

## Current Code Findings

- CLI user input currently reaches app-server `turn/start` or `turn/steer` through `buddyswitch-codex:382`, `tools/launcher/submit_turn.py:23`, and `tools/launcher/app_server.py:806`.
- Web user input uses the same raw CLI path through `tools/launcher/web_management.py:358` and `tools/launcher/web_management.py:591`.
- IM actor wake is handler-prompt driven in `tools/launcher/im_wake_handler.py:39`, `:57`, and `:82`.
- Track comment actor wake is handler-prompt driven in `scripts/env/domain/track_comments.py:194`, `:222`, and `tools/launcher/track_comment_added_handler.py:99`.
- Turn complete checkpoint prompt is generated and submitted through `tools/launcher/task_checkout_handler.py:52` and `scripts/env/domain/task_tui.py:50`.
- Daemon runtime currently exposes handler-facing `submit_parent_prompt` and `submit_side_triage_prompt` in `tools/launcher/daemon_core.py:1059` and `:1172`.
- IM side escalation can submit parent prompt through `scripts/env/tool_runtime/im_client.py:268` and `scripts/env/tool_runtime/context.py:403`.
- Actor-facing task truth is currently taskbox via `scripts/env/repos/tasks.py`, `scripts/env/domain/task_management.py`, `scripts/env/tools/task`, and `buddyswitch/skills/shared/task-management/SKILL.md`.
- Active-task gate reads taskbox state through `scripts/env/tool_runtime/registry.py:424` and blocks pre-dispatch at `scripts/env/tool_runtime/registry.py:626`.
- Browser page expiry in `tools/launcher/browser_page_expired_handler.py` is runtime maintenance and does not submit actor input.

## Old Paths To Remove

- Raw CLI/Web user input directly submitting actor turns.
- IM and Track handlers rendering business prompts and directly waking parent/side.
- Turn-complete direct `[TASK CHECKPOINT]` prompt submission.
- Business handler calls to direct parent or side submit helpers.
- Side paths that directly submit parent or decide interrupt.
- Taskbox and active-task gate as a parallel task source of truth.

No old path is deleted in Phase 0; deletion begins in the phase that replaces each path.

## New Main Path

No product runtime path is introduced in Phase 0. The target main path for later phases is:

```text
inbound envelope -> task_sys.ingest -> task record -> task frame -> task sys runtime instruction -> daemon physical actuator
```

## Implementation Steps

- [x] Read required memo, AGENTS guidance, bitter docs, and relevant spec examples.
- [x] Create `docs/spec/task-sys-proactive-rebuild/00-orientation.md`.
- [x] Search code and tests for actor-driving inbound, submit helpers, taskbox, active-task gate, checkpoint, side, parent, and interrupt residue.
- [x] Create `docs/spec/task-sys-proactive-rebuild/01-codebase-survey.md`.
- [x] Create `docs/spec/task-sys-proactive-rebuild/02-master-development-plan.md`.
- [x] Create this phase document with acceptance evidence.

## Test Plan

Phase 0 has no product code changes, so no behavior test is expected to fail or pass for implementation. Verification is document integrity, survey coverage, residue mapping, and whitespace/diff sanity.

Test targets for later phases are mapped in `01-codebase-survey.md` and `02-master-development-plan.md`.

## Residue Search Plan

Phase 0 searches are expected to find old paths. They prove discovery, not cleanup:

- Direct submit and prompt paths: `submit_turn`, `submit_parent_prompt`, `submit_side_triage_prompt`, `[TASK CHECKPOINT]`.
- Actor-driving source paths: `wake_actor`, `wake_im_actor`, `deliver_track_comment_added`, `dispatch_trigger`, `mailbox.local_trigger`, `mailbox.schedule_trigger`.
- Parallel task truth: `taskbox`, `TaskViewModel`, `E_ACTIVE_TASK_REQUIRED`, `TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED`, `task-management`.

No no-hit residue gate applies until the phase that replaces a path.

## Verification Commands

```bash
rg -n "submit_turn|submit_parent_prompt|submit_side_triage_prompt|TASK CHECKPOINT|taskbox|active_task|task-management" tools scripts tests buddyswitch/skills -S
rg -n "wake_actor|wake_im_actor|deliver_track_comment_added|dispatch_trigger|mailbox\\.local_trigger|mailbox\\.schedule_trigger" tools scripts tests -S
git diff --check
```

## Acceptance Criteria

- Required source docs have been read.
- Orientation, codebase survey, and master plan exist under `docs/spec/task-sys-proactive-rebuild/`.
- Every discovered old path is assigned to a phase.
- Pure runtime maintenance is separated from actor-driving inbound.
- No compatibility adapter, dual-track migration, event bus, workflow engine, or plugin scheduler is proposed.

## Actual Modification Summary

- Added `00-orientation.md`.
- Added `01-codebase-survey.md`.
- Added `02-master-development-plan.md`.
- Added this Phase 0 plan and acceptance record.

## Deleted Old Paths

None. Phase 0 is discovery and planning only.

## Updated Tests

None. Phase 0 has no product code changes.

## Actual Verification

```text
rg -n "submit_turn|submit_parent_prompt|submit_side_triage_prompt|TASK CHECKPOINT|taskbox|active_task|task-management" tools scripts tests buddyswitch/skills -S
```

Result: expected Phase 0 hits found in the old direct submit, checkpoint, taskbox, and active-task surfaces mapped in `01-codebase-survey.md`.

```text
rg -n "wake_actor|wake_im_actor|deliver_track_comment_added|dispatch_trigger|mailbox\\.local_trigger|mailbox\\.schedule_trigger" tools scripts tests -S
```

Result: expected Phase 0 hits found in IM wake, Track comment delivery, daemon mailbox, daemon trigger dispatch, and related tests mapped in `01-codebase-survey.md`.

```text
git diff --check
```

Result: no output.

## Open Questions

None for Phase 0. The product semantics are clear enough to proceed to Phase 1 planning.
