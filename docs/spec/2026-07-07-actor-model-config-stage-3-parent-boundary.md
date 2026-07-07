# Actor Model Config Stage 3 Plan: Parent Actor Boundary

Date: 2026-07-07

## Stage Target

Add the actor-aware parent submit boundary and route Task Sys plus daemon parent submits through it.

This stage covers memo Task 4 only.

## Current Code Facts

- `tools/launcher/submit_turn.py` is a low-level helper that chooses `turn/start` or `turn/steer`.
- `tools/launcher/task_sys_runtime.py` imports `submit_turn as launcher_submit_turn` and calls `launcher_submit_turn.submit_turn(...)`.
- `tools/launcher/daemon_core.py` imports `submit_turn as launcher_submit_turn` and calls `launcher_submit_turn.submit_turn(...)`.
- `tests/test_task_sys_runtime_executor.py` patches `self.module.launcher_submit_turn.submit_turn` for parent submit tests.
- `tests/test_daemon_service_contract.py` patches `self.core.launcher_submit_turn.submit_turn` for daemon parent submit tests.
- Stage 1 added `actor_model_config.resolve_parent_options(...)`.
- Stage 2 added `app_server.thread_settings_update(...)`.

## Files

Create:

- `tools/launcher/parent_thread_submit.py`
- `tests/test_parent_thread_submit.py`

Modify:

- `tools/launcher/task_sys_runtime.py`
- `tools/launcher/daemon_core.py`
- `tests/test_task_sys_runtime_executor.py`
- `tests/test_daemon_service_contract.py`
- `docs/spec/2026-07-07-actor-model-config-stage-3-parent-boundary.md`

Do not modify in this stage:

- `tools/launcher/submit_turn.py`
- `tools/launcher/side_thread_lifecycle.py`
- `tools/launcher/actor_side_thread.py`
- `tools/launcher/env.sh`
- `buddyswitch-codex` side behavior

## Module Boundary

`parent_thread_submit.py` owns:

- Loading parent model config for each controlled parent submit.
- Calling `app_server.thread_settings_update(...)` before submit when parent `model` or `effort` is configured.
- Delegating actual start/steer behavior to `submit_turn.submit_turn(...)`.
- Raising a parent-boundary error for invalid config before submit.

`submit_turn.py` remains config-unaware.

Task Sys and daemon only call the parent actor boundary. They must not read `model-config.json`, call `thread/settings/update`, or call `launcher_submit_turn.submit_turn(...)` directly.

## Development Steps

### Step 1: Write Parent Boundary Failing Tests

Create `tests/test_parent_thread_submit.py`.

Tests:

- Configured parent calls `app_server.thread_settings_update(...)` before `submit_turn.submit_turn(...)`.
- Missing config skips settings update and still submits.
- Invalid config raises `ParentThreadSubmitError` before submit.
- Active parent turn still performs settings update first and delegates to `submit_turn`; the test name/message must state that settings apply to subsequent turns.

Run:

```bash
python -m pytest tests/test_parent_thread_submit.py -q
```

Expected before implementation:

```text
ModuleNotFoundError: No module named 'parent_thread_submit'
```

### Step 2: Implement Parent Boundary

Create `tools/launcher/parent_thread_submit.py`.

Required public shape:

```python
class ParentThreadSubmitError(RuntimeError): ...

def submit_parent_turn(
    *,
    socket_path: Path,
    instance_json: Path,
    thread_id: str,
    text: str,
    permissions: str,
) -> dict[str, object]:
    options = actor_model_config.resolve_parent_options(instance_json)
    if options.has_values:
        app_server.thread_settings_update(
            socket_path,
            thread_id,
            model=options.model,
            effort=options.effort,
        )
    return submit_turn.submit_turn(
        socket_path=socket_path,
        thread_id=thread_id,
        text=text,
        permissions=permissions,
    )
```

Implementation requirements:

- Wrap `ActorModelConfigError` as `ParentThreadSubmitError`.
- Wrap app-server settings errors as `ParentThreadSubmitError`.
- Expose `SubmitTurnError = submit_turn.SubmitTurnError` so callers that need to classify low-level submit failures can keep using a clear public exception alias from the parent boundary.
- Do not add CLI behavior in this stage.

Run:

```bash
python -m pytest tests/test_parent_thread_submit.py -q
```

Expected:

```text
passed
```

### Step 3: Route Task Sys Parent Submit Through Boundary

Modify `tools/launcher/task_sys_runtime.py`:

- Replace `import submit_turn as launcher_submit_turn` with `import parent_thread_submit`.
- Replace `_execute_submit_parent(...)` direct submit call with `parent_thread_submit.submit_parent_turn(...)`.
- Pass `instance_json=_instance_json(context)`.

Modify `tests/test_task_sys_runtime_executor.py`:

- Patch `self.module.parent_thread_submit.submit_parent_turn`.
- Update helper labels from `submit_turn` to `submit_parent_turn`.
- Keep interrupt behavior unchanged.

Run:

```bash
python -m pytest tests/test_task_sys_runtime_executor.py -q
```

Expected:

```text
passed
```

### Step 4: Route Daemon Parent Submit Through Boundary

Modify `tools/launcher/daemon_core.py`:

- Replace `import submit_turn as launcher_submit_turn` with `import parent_thread_submit`.
- Replace `_submit_parent_once(...)` direct submit call with `parent_thread_submit.submit_parent_turn(...)`.
- Pass `instance_json=self.context.instance_json`.
- Raise `parent_thread_submit.SubmitTurnError("submit_turn did not return a turn id")` when no turn id is returned.

Modify `tests/test_daemon_service_contract.py`:

- Patch `self.core.parent_thread_submit.submit_parent_turn`.
- Use `self.core.parent_thread_submit.SubmitTurnError` in exception tests.
- Rename the direct-delegation test to reference parent boundary, not launcher submit.

Run:

```bash
python -m pytest tests/test_daemon_service_contract.py -q
```

Expected:

```text
passed
```

### Step 5: Run Stage Verification

Run:

```bash
python -m pytest tests/test_parent_thread_submit.py tests/test_task_sys_runtime_executor.py tests/test_daemon_service_contract.py -q
```

Expected:

```text
passed
```

### Step 6: Run Stage Residue Scan

Run:

```bash
rg -n "launcher_submit_turn\\.submit_turn" tools/launcher/task_sys_runtime.py tools/launcher/daemon_core.py
rg -n "model-config.json" tools/launcher/submit_turn.py tools/launcher/daemon_core.py tools/launcher/task_sys_runtime.py
```

Expected:

```text
no output
```

## Stage Acceptance

Stage 3 is accepted only when:

- Parent wrapper tests prove settings update before submit, missing-config submit, invalid-config fail-fast, and active-turn delegation.
- Task Sys parent submits route through `parent_thread_submit`.
- Daemon parent submits route through `parent_thread_submit`.
- Focused tests pass.
- Residue scans have no hits.
- This stage doc is updated with exact evidence.

## Completion Notes

- Added `tools/launcher/parent_thread_submit.py` with parent config resolution, settings update before submit, and low-level `submit_turn` delegation.
- Added `tests/test_parent_thread_submit.py`.
- Replaced Task Sys parent submit direct low-level call with `parent_thread_submit.submit_parent_turn(...)`.
- Replaced daemon parent submit direct low-level call with `parent_thread_submit.submit_parent_turn(...)`.
- Updated Task Sys and daemon tests to patch the actor-aware parent boundary.

## Test Results

Red checks:

```bash
python -m pytest tests/test_parent_thread_submit.py -q
```

Result:

```text
ModuleNotFoundError: No module named 'parent_thread_submit'
```

```bash
python -m pytest tests/test_task_sys_runtime_executor.py -q
```

Result:

```text
5 failed
AttributeError: module 'buddyswitch_task_sys_runtime_*' has no attribute 'parent_thread_submit'
```

```bash
python -m pytest tests/test_daemon_service_contract.py -q
```

Result:

```text
10 failed
AttributeError: module 'buddyswitch_daemon_core_service_*' has no attribute 'parent_thread_submit'
```

Green checks:

```bash
python -m pytest tests/test_parent_thread_submit.py -q
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
python -m pytest tests/test_daemon_service_contract.py -q
```

Result:

```text
25 passed in 0.06s
```

Stage command:

```bash
python -m pytest tests/test_parent_thread_submit.py tests/test_task_sys_runtime_executor.py tests/test_daemon_service_contract.py -q
```

Result:

```text
51 passed, 14 subtests passed in 0.08s
```

## Residue Scan Results

Commands:

```bash
rg -n "launcher_submit_turn\\.submit_turn" tools/launcher/task_sys_runtime.py tools/launcher/daemon_core.py
rg -n "model-config.json" tools/launcher/submit_turn.py tools/launcher/daemon_core.py tools/launcher/task_sys_runtime.py
rg -n "launcher_submit_turn|import submit_turn" tools/launcher/task_sys_runtime.py tools/launcher/daemon_core.py
```

Result:

```text
no output
```

## Remaining Risk

Side creation still uses the old lifecycle start boundary until Stage 4.
