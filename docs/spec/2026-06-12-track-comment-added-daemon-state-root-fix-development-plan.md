# Track Comment Added Daemon State Root Fix Development Plan

Date: 2026-06-12
Source: `docs/memo/2026-06-12-track-comment-added-daemon-state-root-fix.md`
Status: Phase 1 reviewed plan, ready for Phase 3 execution

## Goal

Bind daemon runtime object reads to the instance shared state root so `track.comment.added` handlers read durable Track comments from `<shared-root>/state`.

## Architecture

The daemon setup path owns runtime state-root binding. A concrete helper in `tools/launcher/daemon_core.py` derives the exact daemon runtime environment from `DaemonContext`, and both daemon entry paths use it. Repository helpers keep their single existing source of truth, `BUDDYSWITCH_STATE_ROOT`; no handler-level fallback or multi-root lookup is introduced.

## Files

Modify:

- `tools/launcher/daemon_core.py`: add daemon runtime env derivation, pass it to spawned daemon children, bind it in direct `run_daemon`, and refresh `runtime_files`.
- `tests/test_daemon_core.py`: add focused tests for env derivation, child process env, and direct run root refresh.
- `tests/test_track_comment_added_handler.py`: add regression proving the handler reads Track objects from daemon-bound shared state.

Do not modify:

- `tools/launcher/track_comment_added_handler.py`, unless existing validation breaks unexpectedly. The root binding belongs to daemon setup.
- `scripts/env/repos/runtime_files.py`, unless tests reveal its existing `refresh_runtime_roots_from_env()` contract is broken.
- `buddyswitch/objects/**`, `buddyswitch/local/private/**`, or any real runtime files under `.codex-buddyswitch`.

## Implementation Tasks

### Task 1: Add red test for daemon runtime env derivation

Edit `tests/test_daemon_core.py`.

Add this test to `DaemonCoreBindingTests`:

```python
    def test_derive_daemon_runtime_env_projects_shared_state_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])

            env = self.core.derive_daemon_runtime_env(context)

            shared_root = Path(temp_root)
            self.assertEqual(
                env,
                {
                    "BUDDYSWITCH_SHARED_ROOT": str(shared_root),
                    "BUDDYSWITCH_STATE_ROOT": str(shared_root / "state"),
                    "BUDDYSWITCH_INSTANCE_ROOT": str(instance["instance_root"]),
                    "BUDDYSWITCH_INSTANCE_JSON": str(instance["instance_json"]),
                    "BUDDYSWITCH_WORKSPACE_DIR": str(instance["workspace_dir"]),
                },
            )
```

Run:

```bash
python -m pytest tests/test_daemon_core.py::DaemonCoreBindingTests::test_derive_daemon_runtime_env_projects_shared_state_root -q
```

Expected before implementation:

```text
FAILED ... AttributeError: module ... has no attribute 'derive_daemon_runtime_env'
```

### Task 2: Implement daemon runtime env derivation

Edit `tools/launcher/daemon_core.py`.

Import `runtime_files` with the existing helper imports:

```python
from env.repos import runtime_files  # noqa: E402
```

Add this helper after `load_daemon_context`:

```python
def derive_daemon_runtime_env(context: DaemonContext) -> dict[str, str]:
    shared_root = context.instance_root.parent.parent
    return {
        "BUDDYSWITCH_SHARED_ROOT": str(shared_root),
        "BUDDYSWITCH_STATE_ROOT": str(shared_root / "state"),
        "BUDDYSWITCH_INSTANCE_ROOT": str(context.instance_root),
        "BUDDYSWITCH_INSTANCE_JSON": str(context.instance_json),
        "BUDDYSWITCH_WORKSPACE_DIR": str(context.workspace_dir),
    }
```

Run:

```bash
python -m pytest tests/test_daemon_core.py::DaemonCoreBindingTests::test_derive_daemon_runtime_env_projects_shared_state_root -q
```

Expected after implementation:

```text
1 passed
```

### Task 3: Add red test for spawned daemon child env

Edit `tests/test_daemon_core.py`.

Change `DaemonCoreLifecycleTests._patch_process_start` to capture kwargs:

```python
    def _patch_process_start(self, pids: list[int]) -> tuple[list[list[str]], list[dict[str, object]]]:
        commands: list[list[str]] = []
        popen_kwargs: list[dict[str, object]] = []
        original_popen = self.core.subprocess.Popen

        class FakeProcess:
            def __init__(self, pid: int) -> None:
                self.pid = pid

            def poll(self) -> None:
                return None

        def fake_popen(command: list[str], **kwargs: object) -> FakeProcess:
            commands.append(command)
            popen_kwargs.append(kwargs)
            return FakeProcess(pids.pop(0))

        self.addCleanup(setattr, self.core.subprocess, "Popen", original_popen)
        self.core.subprocess.Popen = fake_popen
        return commands, popen_kwargs
```

Update existing call sites to use `commands, _popen_kwargs = self._patch_process_start([...])`.

Add this test to `DaemonCoreLifecycleTests`:

```python
    def test_start_daemon_passes_shared_state_root_to_child_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            _commands, popen_kwargs = self._patch_process_start([4326])
            self._patch_pid_live({4326})
            self._patch_sleep_to_record_ready(instance_root=instance["instance_root"], pid=4326)

            payload = self.core.start_daemon(instance["instance_json"])

            self.assertTrue(payload["started"])
            self.assertEqual(len(popen_kwargs), 1)
            env = popen_kwargs[0].get("env")
            self.assertIsInstance(env, dict)
            assert isinstance(env, dict)
            self.assertEqual(env["BUDDYSWITCH_SHARED_ROOT"], str(Path(temp_root)))
            self.assertEqual(env["BUDDYSWITCH_STATE_ROOT"], str(Path(temp_root) / "state"))
            self.assertEqual(env["BUDDYSWITCH_INSTANCE_ROOT"], str(instance["instance_root"]))
            self.assertEqual(env["BUDDYSWITCH_INSTANCE_JSON"], str(instance["instance_json"]))
            self.assertEqual(env["BUDDYSWITCH_WORKSPACE_DIR"], str(instance["instance_root"] / "workspace"))
```

Run:

```bash
python -m pytest tests/test_daemon_core.py::DaemonCoreLifecycleTests::test_start_daemon_passes_shared_state_root_to_child_environment -q
```

Expected before implementation:

```text
FAILED ... AssertionError: None is not an instance of <class 'dict'>
```

### Task 4: Pass daemon runtime env to child process

Edit `tools/launcher/daemon_core.py`.

In `start_daemon`, create the child environment immediately before `subprocess.Popen`:

```python
    child_env = os.environ.copy()
    child_env.update(derive_daemon_runtime_env(context))
```

Pass it to `Popen`:

```python
            env=child_env,
```

Run:

```bash
python -m pytest tests/test_daemon_core.py::DaemonCoreLifecycleTests::test_start_daemon_passes_shared_state_root_to_child_environment -q
python -m pytest tests/test_daemon_core.py::DaemonCoreLifecycleTests::test_start_daemon_creates_runtime_files_and_is_idempotent_when_pid_is_live -q
```

Expected:

```text
2 passed
```

### Task 5: Add red test for direct run env binding and runtime root refresh

Edit `tests/test_daemon_core.py`.

At the top, add:

```python
import os
import sys
```

After `ROOT = ...`, add:

```python
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.repos import runtime_files  # noqa: E402
```

Add cleanup helpers in the test method itself to restore env and runtime roots.

Add this test to `DaemonCoreRunLoopTests`:

```python
    def test_run_daemon_binds_shared_state_root_before_handlers_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            wrong_root = Path(temp_root) / "wrong-state"
            original_env = {
                key: os.environ.get(key)
                for key in (
                    "BUDDYSWITCH_SHARED_ROOT",
                    "BUDDYSWITCH_STATE_ROOT",
                    "BUDDYSWITCH_INSTANCE_ROOT",
                    "BUDDYSWITCH_INSTANCE_JSON",
                    "BUDDYSWITCH_WORKSPACE_DIR",
                )
            }
            self.addCleanup(self._restore_runtime_env, original_env)
            os.environ.pop("BUDDYSWITCH_SHARED_ROOT", None)
            os.environ["BUDDYSWITCH_STATE_ROOT"] = str(wrong_root)
            runtime_files.refresh_runtime_roots_from_env()

            fake_client = FakeRunDaemonClient(notifications=[StopDaemonLoop("stop")])
            self._patch_app_server_client(fake_client)
            communication = self._patch_daemon_communication()
            observed_roots: list[Path] = []
            original_start_mailbox = self.core.start_daemon_mailbox

            def fake_start_mailbox(**kwargs: object) -> object:
                observed_roots.append(runtime_files.STATE_ROOT)
                return original_start_mailbox(**kwargs)

            self.core.start_daemon_mailbox = fake_start_mailbox

            with self.assertRaises(StopDaemonLoop):
                self.core.run_daemon(instance["instance_json"], handlers=[])

            self.assertEqual(os.environ["BUDDYSWITCH_STATE_ROOT"], str(Path(temp_root) / "state"))
            self.assertEqual(runtime_files.STATE_ROOT, Path(temp_root) / "state")
            self.assertEqual(observed_roots, [Path(temp_root) / "state"])
            self.assertEqual(len(communication["mailbox_closed"]), 1)
```

Add this helper to `DaemonCoreRunLoopTests`:

```python
    def _restore_runtime_env(self, values: dict[str, str | None]) -> None:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        runtime_files.reset_runtime_root_override()
        runtime_files.refresh_runtime_roots_from_env()
```

Run:

```bash
python -m pytest tests/test_daemon_core.py::DaemonCoreRunLoopTests::test_run_daemon_binds_shared_state_root_before_handlers_start -q
```

Expected before implementation:

```text
FAILED ... AssertionError: PosixPath('.../wrong-state') != PosixPath('.../state')
```

### Task 6: Bind env and refresh runtime roots in direct run path

Edit `tools/launcher/daemon_core.py`.

After `context = load_daemon_context(instance_json)` in `run_daemon`, add:

```python
    os.environ.update(derive_daemon_runtime_env(context))
    runtime_files.refresh_runtime_roots_from_env()
```

Run:

```bash
python -m pytest tests/test_daemon_core.py::DaemonCoreRunLoopTests::test_run_daemon_binds_shared_state_root_before_handlers_start -q
python -m pytest tests/test_daemon_core.py -q
```

Expected:

```text
1 passed
...
all tests in tests/test_daemon_core.py pass
```

### Task 7: Add red regression for Track comment handler shared state reads

Edit `tests/test_track_comment_added_handler.py`.

Add env cleanup imports and helper if needed:

```python
import os
```

Add this helper to `TrackCommentAddedHandlerTests`:

```python
    def _restore_runtime_env(self, values: dict[str, str | None]) -> None:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        runtime_files.reset_runtime_root_override()
        runtime_files.refresh_runtime_roots_from_env()
```

Add this test:

```python
    def test_track_comment_handler_reads_rows_from_daemon_bound_shared_state_root(self) -> None:
        original_env = {
            key: os.environ.get(key)
            for key in (
                "BUDDYSWITCH_SHARED_ROOT",
                "BUDDYSWITCH_STATE_ROOT",
                "BUDDYSWITCH_INSTANCE_ROOT",
                "BUDDYSWITCH_INSTANCE_JSON",
                "BUDDYSWITCH_WORKSPACE_DIR",
            )
        }
        self.addCleanup(self._restore_runtime_env, original_env)
        runtime_files.reset_runtime_root_override()
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_root_text:
            shared_root = Path(temp_root_text)
            state_root = shared_root / "state"
            wrong_root = shared_root / "wrong-state"
            os.environ["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            os.environ["BUDDYSWITCH_STATE_ROOT"] = str(state_root)
            runtime_files.refresh_runtime_roots_from_env()
            (wrong_root / "AGENTS.md").write_text(
                "# BuddySwitch Runtime Workspace\n\nWrong root.\n",
                encoding="utf-8",
            )
            instance_root = shared_root / "instances" / "act-dev-track-handler"
            workspace_dir = instance_root / "workspace"
            workspace_dir.mkdir(parents=True, exist_ok=True)
            instance_json = instance_root / "instance.json"
            payload = {
                "actor_id": "act-dev-track-handler",
                "role": "dev",
                "status": "active",
                "instance_root": str(instance_root),
                "workspace_dir": str(workspace_dir),
                "thread_id": "thr-main-track",
                "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
            }
            instance_json.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
            os.environ["BUDDYSWITCH_INSTANCE_ROOT"] = str(instance_root)
            os.environ["BUDDYSWITCH_INSTANCE_JSON"] = str(instance_json)
            os.environ["BUDDYSWITCH_WORKSPACE_DIR"] = str(workspace_dir)

            track_id = "track-comment-shared-root"
            self._seed_track(track_id)
            comment = self._seed_comment(
                track_id=track_id,
                mentioned_actors=[{"actor_id": "act-dev-track-handler", "role_id": "dev"}],
            )
            runtime_files.set_runtime_root_override(wrong_root)

            context = self.daemon_core.load_daemon_context(instance_json)
            os.environ["BUDDYSWITCH_STATE_ROOT"] = str(state_root)
            runtime_files.reset_runtime_root_override()
            runtime_files.refresh_runtime_roots_from_env()
            state = self.daemon_core.DaemonState.load(
                instance_root=instance_root,
                actor_id="act-dev-track-handler",
                main_thread_id="thr-main-track",
            )
            runtime = FakeDaemonRuntime()

            result = self.handler.handle(
                context,
                state,
                runtime,
                self._trigger(payload=self._payload_for(comment)),
            )

            self.assertEqual(result.status, "handled")
            self.assertEqual([call["method"] for call in runtime.calls], ["parent_activity", "submit_parent_prompt"])
```

Run:

```bash
python -m pytest tests/test_track_comment_added_handler.py::TrackCommentAddedHandlerTests::test_track_comment_handler_reads_rows_from_daemon_bound_shared_state_root -q
```

Expected red behavior before Task 6 if run independently:

```text
FAILED ... failed != handled
```

If this test is added after Task 6, it should pass because it validates the invariant directly rather than driving `run_daemon`.

### Task 8: Focused verification and residue check

Run:

```bash
python -m pytest tests/test_track_comment_added_handler.py -q
python -m pytest tests/test_daemon_core.py -q
```

Expected:

```text
all tests pass
```

The tests are patched/fake-bound and should not leave daemon processes. If a command unexpectedly starts a persistent process, stop broad verification, identify the start boundary, and add cleanup before continuing.

### Task 9: Broader relevant verification

Run:

```bash
python -m pytest tests/test_track_comment_env_tool.py tests/test_track_comments_repo.py tests/test_daemon_core.py tests/test_track_comment_added_handler.py -q
```

Expected:

```text
all tests pass
```

### Task 10: Final code review for single-path rebuild

Search:

```bash
rg "BUDDYSWITCH_STATE_ROOT|derive_daemon_runtime_env|refresh_runtime_roots_from_env|comment not found|track.comment.added" tools/launcher scripts/env tests/test_daemon_core.py tests/test_track_comment_added_handler.py
```

Review findings:

- `BUDDYSWITCH_STATE_ROOT` is bound by daemon setup, not by handler code.
- There is no multi-root repository lookup.
- `TrackCommentAddedHandler._comment(...)` still fails when the exact comment row is missing.
- No production code searches the source checkout as a fallback after a shared-root miss.

## Phase 1 Review

Spec coverage:

- The plan covers the two daemon entry paths and the observed handler failure.
- It preserves existing Track comment validation instead of weakening it.
- It avoids broad launcher/service integration until focused tests pass.

Execution clarity:

- Each task has exact files, code-level changes, expected failure or pass result, and verification commands.
- The implementation stays local to daemon runtime setup.

Rebuild-forward check:

- The final system has one daemon object-read path: repositories read from `BUDDYSWITCH_STATE_ROOT=<shared-root>/state`.
- No compatibility fallback, adapter, legacy root search, or handler-specific workaround is planned.
