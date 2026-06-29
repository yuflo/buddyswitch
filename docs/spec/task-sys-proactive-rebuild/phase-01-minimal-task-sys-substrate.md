# Phase 1: Minimal Task Sys Substrate

## Phase Objective

Use the Phase 1 target in `docs/memo/2026-06-29-task-sys-proactive-rebuild.md` to create the smallest task sys core: ingest an actor-driving inbound envelope, persist a task record, and return a daemon-executable runtime instruction without calling daemon internals.

## Current Code Findings

- No `task_sys` module exists yet; searches for `task_sys`, `TaskSys`, `InboundEnvelope`, and `RuntimeInstruction` only hit the memo/spec docs.
- Domain modules live under `scripts/env/domain/` and generally use simple concrete functions.
- Runtime-managed JSON persistence should use `scripts/env/repos/runtime_files.py` helpers such as `OBJECTS_ROOT`, `now_iso()`, `require_id()`, `slugify()`, `read_json_object()`, and `write_json_object()`.
- Runtime tests can isolate state by using `tests/runtime_root_test_helper.py::RuntimeWorkspaceTestMixin`, which sets `runtime_files` root override.
- Existing taskbox modules in `scripts/env/repos/tasks.py`, `scripts/env/domain/task_management.py`, and `scripts/env/tools/task` must not become the task sys substrate.

## Old Paths To Remove

None in Phase 1. This phase adds the replacement substrate only. Old path deletion starts in Phase 2 after ingress can call task sys.

## New Main Path

Add `scripts/env/domain/task_sys.py` with:

- `ingest(envelope)` as the single semantic entrypoint for actor-driving inbound.
- Minimal task record persisted at `runtime_files.OBJECTS_ROOT / "task-sys" / "tasks" / "<task_id>.json"`.
- Record fields:
  - `id`
  - `source_type`
  - `source_ref`
  - `actor_target`
  - `inbound_context`
  - `status`
  - `active_processor`
  - `parent_handoff_params`
  - `checkpoint_metadata`
  - `created_at`
  - `updated_at`
- Minimal state behavior:
  - Default ingest creates `side_processing` with `active_processor: "side"`.
  - Explicit `initial_processor: "none"` creates `closed` with no active processor and returns `no_actor_action`.
- Runtime instructions:
  - `start_side`
  - `submit_parent`
  - `interrupt_submit_parent`
  - `no_actor_action`
- Initial side frame shape:
  - `kind: "task_sys.side_frame"`
  - `task_id`
  - `source`
  - `actor_target`
  - `context`

The module must not import daemon-service modules, app-server modules, launcher helpers, or old taskbox/task-management modules.

## Implementation Steps

- [x] Add failing test file `tests/test_task_sys_substrate.py`.
- [x] Test `ingest` persists a task record and returns `start_side` with a task frame.
- [x] Test `ingest` supports `initial_processor: "none"` and returns `no_actor_action`.
- [x] Test parent and interrupt parent runtime instruction shapes are task traceable.
- [x] Test invalid envelopes reject missing source, actor target, and non-object context.
- [x] Test source text proves no daemon-service imports and no taskbox/task-management dependency.
- [x] Run focused tests and observe failure because `env.domain.task_sys` does not exist.
- [x] Implement `scripts/env/domain/task_sys.py` with concrete helpers only.
- [x] Run focused tests until green.
- [x] Run phase residue searches.

## Test Plan

Test file: `tests/test_task_sys_substrate.py`

Behavior scenarios:

- `test_ingest_persists_task_record_and_returns_start_side_instruction`
  - Arrange an envelope with `source.type = "user.input"`, source ref id, actor target, and inbound text context.
  - Call `task_sys.ingest(envelope)`.
  - Assert persisted task record exists under runtime `buddyswitch/objects/task-sys/tasks`.
  - Assert record has task id, source type/ref, actor target, inbound context, `status == "side_processing"`, `active_processor == "side"`, null parent handoff params, and empty checkpoint metadata.
  - Assert returned instruction has `type == "start_side"`, same task id, same actor target, and a `task_sys.side_frame` frame.

- `test_ingest_can_record_without_actor_action`
  - Arrange an envelope with `initial_processor = "none"`.
  - Assert persisted record is `closed`, has no active processor, and returns a `no_actor_action` instruction.

- `test_ingest_rejects_invalid_envelope_shapes`
  - Missing/invalid `source`, missing/invalid `source.type`, missing/invalid `source.ref`, invalid `actor_target`, and non-object `context` should raise `ValueError`.

- `test_task_sys_substrate_has_no_daemon_or_taskbox_dependencies`
  - Read `scripts/env/domain/task_sys.py`.
  - Assert it does not contain `daemon_core`, `daemon_client`, `app_server`, `tools.launcher`, `task_management`, or `taskbox`.

Focused command:

```bash
python -m pytest tests/test_task_sys_substrate.py -q
```

Expected red before implementation:

```text
ModuleNotFoundError: No module named 'env.domain.task_sys'
```

## Residue Search Plan

Phase 1 no-hit searches:

```bash
rg -n "daemon_core|daemon_client|app_server|tools\\.launcher|task_management|taskbox" scripts/env/domain/task_sys.py tests/test_task_sys_substrate.py -S
```

Expected: no hits, except the test file may contain forbidden tokens inside its source-code assertion list. If that makes the command unsuitable as a no-hit check, run the scoped check against `scripts/env/domain/task_sys.py` only and keep the test assertion as the live guard.

Phase 1 discovery search:

```bash
rg -n "task_sys|task-sys|task_sys\\.side_frame|start_side|no_actor_action" scripts/env/domain tests docs/spec/task-sys-proactive-rebuild -S
```

Expected: hits only in the new substrate module, focused tests, and this spec directory.

## Verification Commands

```bash
python -m pytest tests/test_task_sys_substrate.py -q
rg -n "daemon_core|daemon_client|app_server|tools\\.launcher|task_management|taskbox" scripts/env/domain/task_sys.py -S
rg -n "task_sys|task-sys|task_sys\\.side_frame|start_side|no_actor_action" scripts/env/domain tests/test_task_sys_substrate.py docs/spec/task-sys-proactive-rebuild -S
git diff --check
```

## Acceptance Criteria

- `tests/test_task_sys_substrate.py` fails before implementation for missing `env.domain.task_sys`.
- Focused task sys tests pass after implementation.
- `task_sys.ingest(envelope)` persists a task record.
- `task_sys.ingest(envelope)` returns a runtime instruction.
- Task sys does not import or call daemon-service internals.
- Task sys does not use taskbox or old task-management as its truth source.
- Phase residue searches are recorded with results.

## Actual Modification Summary

- Added `tests/test_task_sys_substrate.py` with red-first coverage for task sys ingest, persistence, runtime instruction shapes, invalid envelope rejection, and dependency boundaries.
- Added `scripts/env/domain/task_sys.py` as the minimal concrete substrate.
- Task sys records persist through `runtime_files.write_json_object()` under runtime-managed `buddyswitch/objects/task-sys/tasks/`.
- Default ingest now returns a `start_side` instruction with a `task_sys.side_frame`.
- `initial_processor: "none"` records a closed task and returns `no_actor_action`.
- `runtime_instruction()` supports `start_side`, `submit_parent`, `interrupt_submit_parent`, and `no_actor_action` shapes.

## Deleted Old Paths

None. Phase 1 intentionally adds the replacement substrate only.

## Updated Tests

- Added `tests/test_task_sys_substrate.py`.

## Actual Verification

Red check before implementation:

```text
python -m pytest tests/test_task_sys_substrate.py -q
5 failed in 0.07s
Failure reason: ModuleNotFoundError: No module named 'env.domain.task_sys'
```

Focused green check:

```text
python -m pytest tests/test_task_sys_substrate.py -q
5 passed, 16 subtests passed in 0.03s
```

Broader relevant task checks:

```text
python -m pytest tests/test_task_sys_substrate.py tests/test_task_env_tool.py tests/test_env_tool_active_task_gate.py -q
19 passed, 24 subtests passed in 0.11s
```

Compile check:

```text
python -m py_compile scripts/env/domain/task_sys.py
no output
```

Phase no-hit dependency scan:

```text
rg -n "daemon_core|daemon_client|app_server|tools\\.launcher|task_management|taskbox" scripts/env/domain/task_sys.py -S
no output; exit code 1
```

Phase discovery scan:

```text
rg -n "task_sys|task-sys|task_sys\\.side_frame|start_side|no_actor_action" scripts/env/domain tests/test_task_sys_substrate.py docs/spec/task-sys-proactive-rebuild -S
```

Result: hits are limited to `scripts/env/domain/task_sys.py`, `tests/test_task_sys_substrate.py`, and `docs/spec/task-sys-proactive-rebuild`.

Whitespace check:

```text
git diff --check
no output
```

## Acceptance Status

Accepted. Phase 1 criteria are satisfied.

## Open Questions

None. Phase 1 can proceed with conservative local implementation choices because it does not alter product semantics or external contracts yet.
