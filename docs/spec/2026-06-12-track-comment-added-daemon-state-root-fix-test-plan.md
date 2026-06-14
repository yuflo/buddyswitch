# Track Comment Added Daemon State Root Fix Test Plan

Date: 2026-06-12
Source: `docs/memo/2026-06-12-track-comment-added-daemon-state-root-fix.md`
Status: Phase 1 reviewed plan, ready for Phase 3 execution

## Goal

Prove daemon object reads use the shared runtime state root for both spawned daemon children and direct `instance_daemon.py run` execution.

The test boundary is the daemon runtime invariant. Do not add fallback object lookup, Track-comment-specific state-root binding, or relaxed comment validation.

## Resource Safety

Follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

The focused tests must not start real long-lived daemon services. `tests/test_daemon_core.py` will patch `subprocess.Popen`, `AppServerClient`, mailbox startup, central registration, heartbeat, and unregister calls. `tests/test_track_comment_added_handler.py` will use temporary state roots and fake daemon runtime objects only.

If any verification starts a persistent service, it must register the pid or process group, clean up on assertion failure, remove pid/socket/runtime files, and run a residual process/socket check before broader verification continues.

## Functional Requirements To Prove

1. `derive_daemon_runtime_env(context)` returns one concrete runtime environment for the instance:
   - `BUDDYSWITCH_SHARED_ROOT=<shared-root>`
   - `BUDDYSWITCH_STATE_ROOT=<shared-root>/state`
   - `BUDDYSWITCH_INSTANCE_ROOT=<instance-root>`
   - `BUDDYSWITCH_INSTANCE_JSON=<instance-json>`
   - `BUDDYSWITCH_WORKSPACE_DIR=<workspace-dir>`
2. `start_daemon(instance_json)` passes that environment to the child `instance_daemon.py run` process.
3. `run_daemon(instance_json, ...)` updates the current process environment to that same runtime environment before handler setup and notification handling.
4. `run_daemon(instance_json, ...)` refreshes `env.repos.runtime_files` after binding the environment so repository helpers read `<shared-root>/state`.
5. `TrackCommentAddedHandler` can handle a `track.comment.added` payload when Track and Track comment rows exist only under `<shared-root>/state`.
6. Existing handler validation remains intact for wrong target actor, missing payload ids, wrong Track payload, wrong thread payload, unintended target actor, and archived Track.
7. No test or implementation edits runtime instance object files under real shared roots.

## Focused Test Matrix

### Daemon Runtime Env Derivation

Target file: `tests/test_daemon_core.py`.

Case: direct helper output.

Given:

- `instance_json` is under `<tmp>/instances/act-dev-daed00000001/instance.json`.
- The instance payload has `instance_root=<tmp>/instances/act-dev-daed00000001` and `workspace_dir=<instance-root>/workspace`.

When:

- `context = load_daemon_context(instance_json)`
- `derive_daemon_runtime_env(context)` is called.

Expected:

- The returned dict contains the exact five keys listed in the functional requirements.
- `BUDDYSWITCH_SHARED_ROOT` is `<tmp>`.
- `BUDDYSWITCH_STATE_ROOT` is `<tmp>/state`.
- It does not include unrelated compatibility keys or alternate object roots.

Command:

```bash
python -m pytest tests/test_daemon_core.py::DaemonCoreBindingTests::test_derive_daemon_runtime_env_projects_shared_state_root -q
```

Expected red result before implementation:

```text
AttributeError: module ... has no attribute 'derive_daemon_runtime_env'
```

### Spawned Daemon Child Env

Target file: `tests/test_daemon_core.py`.

Case: `start_daemon` child process env.

Given:

- Existing `DaemonCoreLifecycleTests._patch_process_start` is extended to capture `Popen` kwargs.
- The fake child process becomes ready through the existing patched sleep path.

When:

- `start_daemon(instance_json)` runs.

Expected:

- `subprocess.Popen` receives `env=...`.
- The env contains the five exact runtime keys.
- Existing process lifecycle assertions still pass.
- No real daemon process is started.

Command:

```bash
python -m pytest tests/test_daemon_core.py::DaemonCoreLifecycleTests::test_start_daemon_passes_shared_state_root_to_child_environment -q
```

Expected red result before implementation:

```text
AssertionError: 'env' not found in captured Popen kwargs
```

### Direct Run Env Binding And Root Refresh

Target file: `tests/test_daemon_core.py`.

Case: `run_daemon` binds env before mailbox startup.

Given:

- `BUDDYSWITCH_STATE_ROOT` is absent or points to a wrong temporary path.
- `runtime_files.refresh_runtime_roots_from_env()` has been called with that wrong value.
- `AppServerClient`, mailbox, registration, heartbeat, and unregister are fake in-memory objects.
- The fake client raises `StopDaemonLoop` after `thread/resume`, so the loop exits without a persistent service.

When:

- `run_daemon(instance_json, handlers=[])` initializes and reaches mailbox startup.

Expected:

- Before the fake mailbox starts, `os.environ["BUDDYSWITCH_STATE_ROOT"] == <tmp>/state`.
- `runtime_files.STATE_ROOT == <tmp>/state`.
- The fake mailbox closes in `finally`.
- The original process environment and runtime root override are restored by test cleanup.

Command:

```bash
python -m pytest tests/test_daemon_core.py::DaemonCoreRunLoopTests::test_run_daemon_binds_shared_state_root_before_handlers_start -q
```

Expected red result before implementation:

```text
AssertionError: runtime_files.STATE_ROOT still equals the wrong root or source checkout root
```

### Track Comment Handler Shared State Regression

Target file: `tests/test_track_comment_added_handler.py`.

Case: handler reads only from daemon-bound shared state root.

Given:

- The process default runtime root is a wrong temporary root.
- The instance lives at `<tmp>/instances/act-dev-track-handler`.
- `BUDDYSWITCH_STATE_ROOT` is bound to `<tmp>/state`.
- Track and Track comment rows exist only under `<tmp>/state/buddyswitch/objects/...`.
- The comment mentions the target actor.

When:

- `runtime_files.refresh_runtime_roots_from_env()` is called after the env binding.
- `TrackCommentAddedHandler.handle(...)` receives `track.comment.added`.

Expected:

- Result status is `handled`.
- Runtime calls are `parent_activity` then `submit_parent_prompt`.
- The prompt contains Track tool instructions.
- The result is not a `comment not found` failure.

Command:

```bash
python -m pytest tests/test_track_comment_added_handler.py::TrackCommentAddedHandlerTests::test_track_comment_handler_reads_rows_from_daemon_bound_shared_state_root -q
```

Expected red result before implementation:

```text
AssertionError: failed != handled
```

## Existing Regression Coverage To Preserve

Target file: `tests/test_track_comment_added_handler.py`.

Existing cases already prove:

- unknown trigger types are ignored;
- wrong target actor fails;
- missing payload ids fail;
- wrong Track payload fails with `comment not found`;
- wrong thread payload fails;
- unintended target actor fails;
- archived Track fails;
- idle parent receives a parent prompt;
- running parent receives a side triage prompt;
- reply attention reaches the parent comment author;
- unavailable parent activity fails.

These tests must stay meaningful. Do not rewrite them to pass through fallback lookup or weakened validation.

## Focused Verification

Run the new red tests first, one at a time:

```bash
python -m pytest tests/test_daemon_core.py::DaemonCoreBindingTests::test_derive_daemon_runtime_env_projects_shared_state_root -q
python -m pytest tests/test_daemon_core.py::DaemonCoreLifecycleTests::test_start_daemon_passes_shared_state_root_to_child_environment -q
python -m pytest tests/test_daemon_core.py::DaemonCoreRunLoopTests::test_run_daemon_binds_shared_state_root_before_handlers_start -q
python -m pytest tests/test_track_comment_added_handler.py::TrackCommentAddedHandlerTests::test_track_comment_handler_reads_rows_from_daemon_bound_shared_state_root -q
```

Then run the focused files:

```bash
python -m pytest tests/test_track_comment_added_handler.py -q
python -m pytest tests/test_daemon_core.py -q
```

## Broader Verification

After focused tests pass:

```bash
python -m pytest tests/test_track_comment_env_tool.py tests/test_track_comments_repo.py tests/test_daemon_core.py tests/test_track_comment_added_handler.py -q
```

Run a residue-oriented check only if a verification command starts persistent processes. The focused commands above must not create real daemon children because their process and service boundaries are patched.

## Phase 1 Review

Spec coverage:

- The matrix covers daemon child env, direct run env binding, runtime root refresh, and the actual `track.comment.added` failure mode.
- Existing handler validation remains explicitly protected.
- The tests target the daemon invariant rather than adding Track-comment-specific fallback behavior.

Resource lifecycle:

- Focused tests patch process, app-server, mailbox, and central daemon boundaries.
- No test starts a real persistent daemon.
- Temporary state roots are scoped to `TemporaryDirectory` and runtime roots are reset by cleanup.

Rebuild-forward check:

- There is one runtime object root: `<shared-root>/state`.
- No compatibility lookup, adapter, fallback root, or legacy path is planned.
