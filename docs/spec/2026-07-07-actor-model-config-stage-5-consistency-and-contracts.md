# Actor Model Config Stage 5 Plan: Consistency Gates And Contract Slices

Date: 2026-07-07

## Stage Target

Add repository consistency gates and end-to-end contract slices for the actor model config boundaries.

This stage covers memo Task 6 and Task 7.

## Current Code Facts

- `tests/test_repo_consistency.py::test_side_thread_model_override_has_no_persistent_config_write_path` currently forbids `thread/settings/update` globally.
- Parent hot-load now legitimately uses `thread/settings/update` through `tools/launcher/app_server.py`.
- Side creation now reaches `actor_side_thread.py`; side lifecycle still owns send and cleanup.
- Launcher side creation already has a test proving `model-config.json` side defaults reach `thread/fork`.
- Existing side send tests prove no `thread/fork` for existing side sends, but do not yet edit `model-config.json` or assert no `thread/settings/update`.

## Files

Modify:

- `tests/test_repo_consistency.py`
- `tests/test_task_sys_runtime_executor.py`
- `tests/test_buddyswitch_launcher.py`
- `docs/spec/2026-07-07-actor-model-config-stage-5-consistency-and-contracts.md`

Do not modify in this stage unless a test proves it necessary:

- Runtime production modules.
- CLI/WebUI behavior.

## Consistency Gate Plan

Update `tests/test_repo_consistency.py`:

- Replace the global `thread/settings/update` ban with targeted gates.
- Allow parent settings update in `tools/launcher/app_server.py` and parent-related tests.
- Forbid `thread/settings/update` and `config/batchWrite` in:
  - `tools/launcher/actor_side_thread.py`
  - `tools/launcher/side_thread_lifecycle.py`
  - `buddyswitch-codex`
  - `tools/launcher/web_management.py`
- Forbid `model-config.json` references in:
  - `tools/launcher/app_server.py`
  - `tools/launcher/submit_turn.py`
  - `tools/launcher/side_thread_lifecycle.py`
  - `tools/launcher/daemon_core.py`
  - `tools/launcher/task_sys_runtime.py`
- Forbid direct `side_thread_lifecycle.start_side_thread` calls from:
  - `tools/launcher/task_sys_runtime.py`
  - `buddyswitch-codex`
  - `tools/launcher/env.sh`
- Forbid the `side_thread_lifecycle.py start` CLI parser.
- Forbid direct low-level parent submit calls from Task Sys and daemon:
  - `launcher_submit_turn.submit_turn`
  - `import submit_turn as launcher_submit_turn`

Run before production changes:

```bash
python -m pytest tests/test_repo_consistency.py -q
```

Expected before consistency update:

```text
failed
```

Run after update:

```bash
python -m pytest tests/test_repo_consistency.py -q
```

Expected:

```text
passed
```

## Contract Slice Plan

Add Task Sys parent contract test in `tests/test_task_sys_runtime_executor.py`:

```text
edit model-config.json parent -> execute Task Sys submit_parent -> app-server sees thread/settings/update before turn/start
```

Implementation:

- Use the real `parent_thread_submit` and `submit_turn` path.
- Write parent config to `context.instance_json.parent / "model-config.json"`.
- Monkeypatch `parent_thread_submit.app_server.thread_settings_update`, `parent_thread_submit.submit_turn.app_server.thread_read`, and `parent_thread_submit.submit_turn.app_server.turn_start`.
- Execute a real Task Sys `submit_parent` instruction.
- Assert call order is `thread_settings_update` then `thread_read` then `turn_start`.

Add launcher negative side-send contract in `tests/test_buddyswitch_launcher.py`:

```text
send to existing side after editing model-config.json -> no new thread/fork and no settings/update
```

Implementation:

- Edit `model-config.json` side defaults after the instance and existing side row are prepared.
- Execute `instance side --side-thread-id ...`.
- Assert no `thread/fork`.
- Assert no `thread/settings/update`.
- Assert no model fields are present in the send JSON output.

Existing side creation positive contract:

- `test_side_start_uses_model_config_side_defaults_as_thread_fork_only_actor_config` already proves `instance side` reads side config for new side creation and passes model/effort into `thread/fork`.

Focused run:

```bash
python -m pytest tests/test_task_sys_runtime_executor.py -q
python -m pytest tests/test_buddyswitch_launcher.py -k "side and model" -q
```

Expected:

```text
passed
```

## Stage Verification

Run:

```bash
python -m pytest tests/test_repo_consistency.py -q
python -m pytest tests/test_task_sys_runtime_executor.py -q
python -m pytest tests/test_buddyswitch_launcher.py -k "model_config or side and model" -q
```

## Stage Residue Scans

Run:

```bash
rg -n "model-config.json" tools/launcher/app_server.py tools/launcher/submit_turn.py tools/launcher/side_thread_lifecycle.py tools/launcher/daemon_core.py tools/launcher/task_sys_runtime.py
rg -n "side_thread_lifecycle\\.start_side_thread" tools/launcher/task_sys_runtime.py buddyswitch-codex tools/launcher/env.sh
rg -n "subparsers\\.add_parser\\(\"start\"" tools/launcher/side_thread_lifecycle.py
rg -n "launcher_submit_turn\\.submit_turn|import submit_turn as launcher_submit_turn" tools/launcher/task_sys_runtime.py tools/launcher/daemon_core.py
rg -n "thread/settings/update|config/batchWrite" tools/launcher/actor_side_thread.py tools/launcher/side_thread_lifecycle.py buddyswitch-codex tools/launcher/web_management.py
```

Expected:

```text
no output
```

## Stage Acceptance

Stage 5 is accepted only when:

- Repository consistency tests pass.
- Parent contract slice proves settings update before controlled parent submit.
- Side positive creation contract remains passing.
- Side negative existing-send contract proves no side config reload or settings update.
- Residue scans have no hits.
- This stage doc is updated with exact evidence.

## Completion Notes

- Replaced the old global `thread/settings/update` consistency ban with targeted parent/side boundary rules.
- Added repo consistency checks for wrong-layer `model-config.json` references, direct side start calls, lifecycle start CLI parser residue, and direct low-level parent submit calls.
- Added `tests/test_task_sys_runtime_executor.py::test_execute_submit_parent_applies_model_config_settings_before_turn_start`.
- Strengthened the existing side send launcher contract so editing side config does not affect existing side-thread sends and does not call `thread/settings/update`.

## Test Results

Red check:

```bash
python -m pytest tests/test_repo_consistency.py -q
```

Result:

```text
1 failed, 50 passed
test_side_thread_model_override_has_no_persistent_config_write_path
```

Focused green checks:

```bash
python -m pytest tests/test_repo_consistency.py -q
```

Result:

```text
54 passed, 232 subtests passed in 0.95s
```

```bash
python -m pytest tests/test_task_sys_runtime_executor.py -q
```

Result:

```text
23 passed, 14 subtests passed in 0.04s
```

```bash
python -m pytest tests/test_buddyswitch_launcher.py -k "side and model" -q
```

Result:

```text
4 passed, 208 deselected in 10.81s
```

Stage command:

```bash
python -m pytest tests/test_repo_consistency.py -q && python -m pytest tests/test_task_sys_runtime_executor.py -q && python -m pytest tests/test_buddyswitch_launcher.py -k "model_config or side and model" -q
```

Result:

```text
54 passed, 232 subtests passed in 0.94s
23 passed, 14 subtests passed in 0.03s
5 passed, 207 deselected in 13.00s
```

## Residue Scan Results

Commands:

```bash
rg -n "model-config.json" tools/launcher/app_server.py tools/launcher/submit_turn.py tools/launcher/side_thread_lifecycle.py tools/launcher/daemon_core.py tools/launcher/task_sys_runtime.py
rg -n "side_thread_lifecycle\\.start_side_thread" tools/launcher/task_sys_runtime.py buddyswitch-codex tools/launcher/env.sh
rg -n "subparsers\\.add_parser\\(\"start\"" tools/launcher/side_thread_lifecycle.py
rg -n "launcher_submit_turn\\.submit_turn|import submit_turn as launcher_submit_turn" tools/launcher/task_sys_runtime.py tools/launcher/daemon_core.py
rg -n "thread/settings/update|config/batchWrite" tools/launcher/actor_side_thread.py tools/launcher/side_thread_lifecycle.py buddyswitch-codex tools/launcher/web_management.py
```

Result:

```text
no output
```

## Remaining Risk

Final acceptance still requires running all memo verification commands, attach live-surface scan, and writing the final acceptance doc.
