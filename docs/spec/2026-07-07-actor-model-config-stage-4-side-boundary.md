# Actor Model Config Stage 4 Plan: Side Actor Boundary

Date: 2026-07-07

## Stage Target

Add the actor-aware side-thread creation boundary and route Task Sys plus CLI side creation through it.

This stage covers memo Task 5 only.

## Current Code Facts

- `tools/launcher/side_thread_lifecycle.py::start_side_thread(...)` already accepts resolved `model` and `model_reasoning_effort`.
- `side_thread_lifecycle.py` currently owns a `start` CLI subcommand, which places public creation policy at the lifecycle boundary.
- `tools/launcher/task_sys_runtime.py` imports `side_thread_lifecycle` and calls `side_thread_lifecycle.start_side_thread(...)` for Task Sys side creation.
- `tools/launcher/env.sh::buddyswitch_side_thread_lifecycle_start` invokes `side_thread_lifecycle.py start`.
- `buddyswitch-codex::instance_side` calls `buddyswitch_side_thread_lifecycle_start` when starting a new side thread.
- WebUI uses `buddyswitch-codex instance side ... --json`; it should remain a projection and not own model policy.
- Stage 1 added side config resolution and metadata helpers in `actor_model_config.py`.

## Files

Create:

- `tools/launcher/actor_side_thread.py`
- `tests/test_actor_side_thread.py`

Modify:

- `tools/launcher/task_sys_runtime.py`
- `tools/launcher/env.sh`
- `tools/launcher/side_thread_lifecycle.py`
- `buddyswitch-codex`
- `tests/test_task_sys_runtime_executor.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_web_management.py`
- `docs/spec/2026-07-07-actor-model-config-stage-4-side-boundary.md`

Do not modify in this stage:

- `tools/launcher/app_server.py`
- `tools/launcher/submit_turn.py`
- `tools/launcher/parent_thread_submit.py`
- `tools/launcher/daemon_core.py`

## Module Boundary

`actor_side_thread.py` owns:

- Loading side model config for each new actor side-thread creation.
- Merging explicit `--model` and `--effort` values over config values field-by-field.
- Calling `side_thread_lifecycle.start_side_thread(...)` with resolved creation-time values.
- Rewriting side output metadata source names to `actor_config`, `override`, and `codex_default`.

`side_thread_lifecycle.py` owns:

- `thread/fork`, boundary injection, turn start, registry lease creation.
- Send, cleanup, and task lease cleanup.

`side_thread_lifecycle.py` does not own:

- Reading `model-config.json`.
- Public side start CLI parsing.
- Actor-config metadata source semantics.

Task Sys, CLI, and WebUI must reach side creation only through the actor side boundary.

## Development Steps

### Step 1: Write Actor Side Boundary Failing Tests

Create `tests/test_actor_side_thread.py`.

Tests:

- Configured side passes `model` and `model_reasoning_effort` to `side_thread_lifecycle.start_side_thread(...)`.
- Explicit `model` and `effort` override file values field-by-field.
- Missing config passes `None` for model and effort and reports `codex_default` source metadata.
- Invalid config raises `ActorSideThreadError` before lifecycle starts.
- Output metadata reports actor config values as `actor_config`, explicit values as `override`, and omitted values as `codex_default`.

Run:

```bash
python -m pytest tests/test_actor_side_thread.py -q
```

Expected before implementation:

```text
ModuleNotFoundError: No module named 'actor_side_thread'
```

### Step 2: Implement Actor Side Boundary

Create `tools/launcher/actor_side_thread.py`.

Required public shape:

```python
class ActorSideThreadError(RuntimeError): ...

def start_actor_side_thread(
    *,
    socket_path: Path,
    instance_json: Path,
    actor_id: str,
    parent_thread_id: str,
    text: str,
    purpose: str,
    workspace_dir: Path,
    shared_project_workspace_dir: Path,
    permissions: str,
    task_id: str | None = None,
    model: str | None = None,
    model_reasoning_effort: str | None = None,
) -> dict[str, Any]:
    ...
```

Implementation requirements:

- Wrap `ActorModelConfigError` as `ActorSideThreadError`.
- Let lifecycle errors propagate unchanged.
- Do not call `thread/settings/update`.
- Do not write persistent Codex config.

Add CLI:

```text
actor_side_thread.py start --socket ... --instance-json ... --actor-id ... --parent-thread-id ... --text ... --purpose ... --workspace-dir ... --shared-project-workspace-dir ... --permissions ... [--task-id ...] [--model ...] [--effort ...]
```

Run:

```bash
python -m pytest tests/test_actor_side_thread.py -q
```

Expected:

```text
passed
```

### Step 3: Route Task Sys Side Creation Through Boundary

Modify `tools/launcher/task_sys_runtime.py`:

- Import `actor_side_thread`.
- Replace `side_thread_lifecycle.start_side_thread(...)` with `actor_side_thread.start_actor_side_thread(...)`.
- Keep cleanup through `side_thread_lifecycle.cleanup_task_side_lease(...)`.

Modify `tests/test_task_sys_runtime_executor.py`:

- Patch `self.module.actor_side_thread.start_actor_side_thread` in side-start tests.
- Keep cleanup tests patching `side_thread_lifecycle`.

Run:

```bash
python -m pytest tests/test_task_sys_runtime_executor.py -q
```

Expected:

```text
passed
```

### Step 4: Move CLI Start Projection To Actor Boundary

Modify `tools/launcher/env.sh`:

- Add `buddyswitch_actor_side_thread_start`.
- Have it invoke `tools/launcher/actor_side_thread.py start`.
- Keep `buddyswitch_side_thread_lifecycle_send` and `buddyswitch_side_thread_lifecycle_cleanup`.
- Remove `buddyswitch_side_thread_lifecycle_start`.

Modify `buddyswitch-codex`:

- Update `instance_side` new-side path to call `buddyswitch_actor_side_thread_start`.
- Keep send and close paths using lifecycle helpers.

Modify `tools/launcher/side_thread_lifecycle.py`:

- Remove `_command_start`.
- Remove the `start` parser.
- Keep `start_side_thread(...)` as Python API for `actor_side_thread.py`.

Update `tests/test_buddyswitch_launcher.py`:

- Existing side explicit override test should still prove `thread/fork` receives model/effort and no persistent config write occurs.
- Add or update one test proving a configured `model-config.json` side section influences `instance side` new-thread creation without explicit CLI overrides.
- Existing side send tests should still prove no `thread/fork` occurs for existing side send.

Update `tests/test_web_management.py` only if command expectations need field assertions. WebUI should continue to pass model/effort only through `instance side`.

Run:

```bash
python -m pytest tests/test_buddyswitch_launcher.py -k "side and model" -q
python -m pytest tests/test_web_management.py -k "side and model" -q
```

Expected:

```text
passed
```

### Step 5: Run Stage Verification

Run:

```bash
python -m pytest tests/test_actor_side_thread.py tests/test_task_sys_runtime_executor.py -q
python -m pytest tests/test_buddyswitch_launcher.py -k "side and model" -q
python -m pytest tests/test_web_management.py -k "side and model" -q
```

Expected:

```text
passed
```

### Step 6: Run Stage Residue Scans

Run:

```bash
rg -n "side_thread_lifecycle\\.start_side_thread" tools/launcher/task_sys_runtime.py buddyswitch-codex tools/launcher/env.sh
rg -n "subparsers\\.add_parser\\(\"start\"" tools/launcher/side_thread_lifecycle.py
rg -n "thread/settings/update|config/batchWrite" tools/launcher/actor_side_thread.py tools/launcher/side_thread_lifecycle.py buddyswitch-codex tools/launcher/web_management.py
rg -n "model-config.json" tools/launcher/side_thread_lifecycle.py tools/launcher/task_sys_runtime.py
```

Expected:

```text
no output
```

## Stage Acceptance

Stage 4 is accepted only when:

- Actor side wrapper tests pass.
- Task Sys side creation routes through `actor_side_thread`.
- CLI new-side creation routes through `actor_side_thread.py`.
- Lifecycle send/cleanup still route through lifecycle.
- Side lifecycle no longer exposes a public `start` CLI subcommand.
- Focused launcher/WebUI side model tests pass.
- Residue scans have no hits.
- This stage doc is updated with exact evidence.

## Completion Notes

- Added `tools/launcher/actor_side_thread.py` with side config resolution, explicit override merge, lifecycle delegation, source metadata rewrite, and a public `start` CLI.
- Added `tests/test_actor_side_thread.py`.
- Routed Task Sys side creation through `actor_side_thread.start_actor_side_thread(...)`.
- Replaced the shell new-side start projection with `buddyswitch_actor_side_thread_start`, which invokes `actor_side_thread.py start`.
- Updated `buddyswitch-codex instance side` new-side path to call the actor-side shell projection.
- Removed the public `start` CLI subcommand from `side_thread_lifecycle.py`; lifecycle keeps send/cleanup CLI commands.
- Added launcher coverage for side defaults loaded from `model-config.json`.

## Test Results

Red checks:

```bash
python -m pytest tests/test_actor_side_thread.py -q
```

Result:

```text
ModuleNotFoundError: No module named 'actor_side_thread'
```

```bash
python -m pytest tests/test_task_sys_runtime_executor.py -q
```

Result:

```text
5 failed
AttributeError: module 'buddyswitch_task_sys_runtime_*' has no attribute 'actor_side_thread'
```

```bash
python -m pytest tests/test_buddyswitch_launcher.py -k "side and model" -q
```

Result:

```text
1 failed, 2 passed
KeyError: 'model'
```

Green checks:

```bash
python -m pytest tests/test_actor_side_thread.py -q
```

Result:

```text
4 passed in 0.02s
```

```bash
python -m pytest tests/test_task_sys_runtime_executor.py -q
```

Result:

```text
22 passed, 14 subtests passed in 0.03s
```

```bash
python -m pytest tests/test_buddyswitch_launcher.py -k "side and model" -q
```

Result:

```text
3 passed, 209 deselected in 8.10s
```

```bash
python -m pytest tests/test_web_management.py -k "side and model" -q
```

Result:

```text
2 passed, 64 deselected in 5.11s
```

Stage command:

```bash
python -m pytest tests/test_actor_side_thread.py tests/test_task_sys_runtime_executor.py -q && python -m pytest tests/test_buddyswitch_launcher.py -k "side and model" -q && python -m pytest tests/test_web_management.py -k "side and model" -q
```

Result:

```text
26 passed, 14 subtests passed in 0.04s
3 passed, 209 deselected in 7.76s
2 passed, 64 deselected in 5.08s
```

## Residue Scan Results

Commands:

```bash
rg -n "side_thread_lifecycle\\.start_side_thread" tools/launcher/task_sys_runtime.py buddyswitch-codex tools/launcher/env.sh
rg -n "subparsers\\.add_parser\\(\"start\"" tools/launcher/side_thread_lifecycle.py
rg -n "thread/settings/update|config/batchWrite" tools/launcher/actor_side_thread.py tools/launcher/side_thread_lifecycle.py buddyswitch-codex tools/launcher/web_management.py
rg -n "model-config.json" tools/launcher/side_thread_lifecycle.py tools/launcher/task_sys_runtime.py
```

Result:

```text
no output
```

## Remaining Risk

Repo-wide consistency gates and final end-to-end contract naming are left for Stage 5.
