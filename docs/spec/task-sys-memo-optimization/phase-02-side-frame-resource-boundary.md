# Phase 02 Side Frame Resource Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the memo-defined resource model into every rendered `task_sys.side_frame` so side threads decide `close` versus `need_parent` by required resources.

**Architecture:** Keep physical side-thread isolation in `SIDE_BOUNDARY_PROMPT` and per-task decision policy in `task_sys.side_frame`. This phase updates prompt rendering and prompt contract tests only; it does not add tool-layer hard resource isolation.

**Tech Stack:** `tools/launcher/task_sys_runtime.py`, `tests/test_task_sys_runtime_executor.py`, pytest, `py_compile`, scoped residue scans.

---

## 1. Background And Goal

This phase resolves `docs/memo/2026-06-30-task-sys-side-thread-resource-boundary-prompt.md`.

Current bottleneck:

- `render_side_frame()` currently names the task, source, context, and two result actions.
- It does not tell the side processor which resources it may read/write, which resources require parent work, or that short exact IM replies can be closed directly.
- Because existing side threads can be reused, the resource boundary must appear in every `task_sys.side_frame`, not only in the one-time `SIDE_BOUNDARY_PROMPT`.

Observable behavior change:

- Every side frame includes explicit resource-boundary policy.
- Side frames state that exact current-source IM reply or absorbed closure may be handled by side.
- Side frames state that research, browser/web, workspace, Track writes/comments, artifacts/evidence, durable deliverables, parent continuity, and multi-step execution require `task_sys.need_parent`.

## 2. Code Current-State Investigation

Relevant files:

- `tools/launcher/task_sys_runtime.py`
  - `render_side_frame(frame)` builds the active `task_sys.side_frame` text.
  - `render_parent_frame()` and `render_checkpoint_frame()` are not part of this phase.
  - `_execute_start_side()` passes `render_side_frame()` output to either `app_server.input_turn()` for reused side threads or `app_server.side_start()` for new side threads.
- `tools/launcher/app_server.py`
  - `SIDE_BOUNDARY_PROMPT` is injected when a new side thread is forked. This phase must not modify it.
- `tests/test_task_sys_runtime_executor.py`
  - `test_render_side_frame_is_task_sys_scoped_and_names_only_two_results` currently checks side-frame scope and old-prompt absence.
  - Start-side execution tests assert submitted side text includes `task_sys.side_frame`, `task_sys.close`, and `task_sys.need_parent`.

Old path or residue path:

- Old triage prompt markers: `[IM MESSAGE TRIAGE]`, `[TRACK COMMENT TRIAGE]`.
- Old side outcome names such as `side_interrupt`.
- Direct parent submit/interrupt language as a side outcome.

Existing coverage and gaps:

- Existing tests prove only the minimal frame shell exists.
- Missing tests for resource-boundary policy, IM exact closure, forbidden Track comments, forbidden browser/web/research, forbidden workspace/artifact/evidence writes, checkpoint prohibition, and "user-facing reply does not automatically mean parent".

## 3. Solution Design

Minimal direct change:

1. Add prompt assertions to `tests/test_task_sys_runtime_executor.py`.
2. Run those tests and confirm failure because the current frame lacks the new resource policy.
3. Replace the rule body inside `render_side_frame()` with the memo policy while preserving:
   - `task_sys.side_frame`
   - `Task id: {task_id}`
   - `Task Sys source:` JSON block
   - `Task Sys context:` JSON block
   - allowed result actions for `task_sys.close` and `task_sys.need_parent`
4. Do not change runtime execution, app-server side boundary injection, tool schemas, or role AGENTS files.

No compatibility or abstraction:

- Do not keep old short side prompt as a fallback.
- Do not introduce policy objects, prompt registries, route engines, or tool-layer resource enforcement.
- Do not allow Track comments as side-write resources in this phase.

Boundary with other memo phases:

- This phase does not fix idle-parent `interrupt_submit_parent`; that is phase 03.
- This phase does not remove Web input API; phase 01 already did.
- This phase does not change parent frame rendering.

## 4. Test Plan

### Red Tests

Add or extend `test_render_side_frame_is_task_sys_scoped_and_names_only_two_results` with assertions for these exact substrings:

- `Core policy: decide by required resources.`
- `Allowed side resources:`
- `Forbidden side resources:`
- `message.send(reply_to=source_message_id`
- `message.mark(message_id=source_message_id, disposition=absorbed)`
- `Do not call task_sys.need_parent merely because a user-facing reply is needed.`
- `Track shared state, including comments`
- `browser session, web search, webpage reading, evidence gathering, or research loops`
- `source files, git, config, dependencies, tests, builds, app runtime, or workspace state`
- `artifacts, evidence, durable deliverables`
- `checkpoint state or task_sys.checkpoint_update`
- `Finish this frame with exactly one Task Sys side result`

Run:

```bash
python -m pytest -q tests/test_task_sys_runtime_executor.py::TaskSysRuntimeExecutorTests::test_render_side_frame_is_task_sys_scoped_and_names_only_two_results
```

Expected red result before production edit:

- The test fails because the current side frame does not contain the resource-boundary sections.

### Focused Tests

After implementation:

```bash
python -m pytest -q tests/test_task_sys_runtime_executor.py
```

Expected:

- Runtime executor tests pass.

### Integration / End-To-End Contract Tests

```bash
python -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_task_sys_side_processing.py tests/test_task_sys_substrate.py
```

Expected:

- Side-frame prompt changes do not alter side result state transitions or parent handoff instruction construction.

### Residue Scans

```bash
rg -n "\\[IM MESSAGE TRIAGE|\\[TRACK COMMENT TRIAGE|side_interrupt" tools/launcher/task_sys_runtime.py tests/test_task_sys_runtime_executor.py -S
rg -n "Core policy: decide by required resources|Allowed side resources|Forbidden side resources|task_sys.checkpoint_update" tools/launcher/task_sys_runtime.py tests/test_task_sys_runtime_executor.py -S
```

Expected:

- First scan returns no hits.
- Second scan returns hits in the runtime prompt and prompt contract tests.

### Compile / Diff Checks

```bash
python -m py_compile tools/launcher/task_sys_runtime.py
git diff --check
```

Expected:

- Both pass.

## 5. Acceptance Criteria

Behavior acceptance:

- `render_side_frame()` emits the resource-boundary policy for every frame.
- `execute_instruction(... start_side ...)` continues to submit side-frame text through the existing physical side start/reuse paths.
- Side frames still list only `task_sys.close` and `task_sys.need_parent` as side outcomes.

State acceptance:

- No runtime object files under `buddyswitch/objects/**` are edited.
- No Task Sys record schema or state transition changes are made.

UI / CLI / WebUI observable acceptance:

- No UI/CLI behavior changes are made in this phase.
- WebUI IM short-reply behavior is improved indirectly by clearer side instructions, not by route changes.

Live surface no-residue acceptance:

- Side frame text has no old IM/Track triage prompt markers.
- Side frame text has no `side_interrupt` side outcome.
- Side frame text does not tell side to directly submit or interrupt parent; `interrupt` remains only a `task_sys.need_parent` parameter.

Actual Verification:

- Red check before production edit:
  - `python -m pytest -q tests/test_task_sys_runtime_executor.py::TaskSysRuntimeExecutorTests::test_render_side_frame_is_task_sys_scoped_and_names_only_two_results`
  - Result: failed because `Core policy: decide by required resources.` was not present in the current side frame.
- Focused green check:
  - `python -m pytest -q tests/test_task_sys_runtime_executor.py::TaskSysRuntimeExecutorTests::test_render_side_frame_is_task_sys_scoped_and_names_only_two_results`
  - Result: `1 passed`.
- Final phase verification:
  - `python -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_task_sys_side_processing.py tests/test_task_sys_substrate.py`
  - Result: `21 passed, 16 subtests passed`.
  - `python -m py_compile tools/launcher/task_sys_runtime.py`
  - Result: pass.
  - `rg -n "\\[IM MESSAGE TRIAGE|\\[TRACK COMMENT TRIAGE|side_interrupt" tools/launcher/task_sys_runtime.py tests/test_task_sys_runtime_executor.py -S`
  - Result: no hits.
  - `rg -n "Core policy: decide by required resources|Allowed side resources|Forbidden side resources|task_sys.checkpoint_update" tools/launcher/task_sys_runtime.py tests/test_task_sys_runtime_executor.py -S`
  - Result: hits only in `tools/launcher/task_sys_runtime.py` and `tests/test_task_sys_runtime_executor.py`.

## Actual Changes

- Expanded `tools/launcher/task_sys_runtime.py::render_side_frame()` with the resource-boundary prompt:
  - inherited parent history is reference-only;
  - side decisions are based on required resources;
  - exact source reads, bounded read-only inspection, current-source IM reply/absorbed closure, and Task Sys side result are allowed;
  - parent attention, workspace, browser/web/research, Track shared-state writes/comments, artifacts/evidence, checkpoint state, raw runtime writes, permissions, and new outbound communication are forbidden;
  - IM closure order requires `message.send(reply_to=...)` or `message.mark(... absorbed)` before `task_sys.close`;
  - parent handoff context must be minimal and concrete;
  - `interrupt` remains only a `task_sys.need_parent` parameter.
- Extended `tests/test_task_sys_runtime_executor.py` prompt assertions for all memo-critical resource rules.
- Kept old triage marker and side interrupt negative assertions without leaving literal residue hits.

## Acceptance Status

Accepted for Phase 02. Every rendered `task_sys.side_frame` now carries the resource boundary that lets side threads close exact current-source IM work and route parent-resource work through `task_sys.need_parent`.

## 6. Appendix

Search commands used during investigation:

```bash
rg -n "def render_side_frame|task_sys.side_frame|SIDE_BOUNDARY_PROMPT|Allowed result actions|need_parent|side_interrupt" tools/launcher tests scripts/env -S
nl -ba tests/test_task_sys_runtime_executor.py | sed -n '140,220p'
```

Key code references:

- `tools/launcher/task_sys_runtime.py::render_side_frame()`
- `tools/launcher/task_sys_runtime.py::_execute_start_side()`
- `tests/test_task_sys_runtime_executor.py::TaskSysRuntimeExecutorTests`
- `tools/launcher/app_server.py::SIDE_BOUNDARY_PROMPT` as a non-target

Decision record:

- Put the resource policy in `task_sys.side_frame` because reused side threads do not receive the one-time boundary prompt again.
- Keep this phase prompt-only because the memo explicitly excludes tool-layer hard isolation.
