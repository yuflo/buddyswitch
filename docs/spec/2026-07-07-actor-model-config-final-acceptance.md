# Actor Model Config Final Acceptance

Date: 2026-07-07

## Completed Stages

1. Stage 1: Config core and instance seed.
2. Stage 2: App-server settings update primitive.
3. Stage 3: Parent actor boundary.
4. Stage 4: Side actor boundary.
5. Stage 5: Consistency gates and contract slices.

## Implementation Summary

Added:

- `tools/launcher/actor_model_config.py`
- `tools/launcher/parent_thread_submit.py`
- `tools/launcher/actor_side_thread.py`
- `tests/test_actor_model_config.py`
- `tests/test_parent_thread_submit.py`
- `tests/test_actor_side_thread.py`
- Stage specs and this final acceptance document under `docs/spec/`.

Changed:

- `buddyswitch-codex` seeds `model-config.json` for new instances and routes new side starts through `actor_side_thread.py`.
- `tools/launcher/app_server.py` supports `thread_settings_update(...)` with matching notification capture.
- `tools/launcher/task_sys_runtime.py` routes parent submits through `parent_thread_submit.py` and side starts through `actor_side_thread.py`.
- `tools/launcher/daemon_core.py` routes parent submits through `parent_thread_submit.py`.
- `tools/launcher/env.sh` exposes `buddyswitch_actor_side_thread_start`.
- `tools/launcher/side_thread_lifecycle.py` no longer exposes a public `start` CLI subcommand.
- Tests and consistency gates now enforce the actor-aware boundaries.

## Final Verification

Command:

```bash
python -m pytest tests/test_actor_model_config.py -q && python -m pytest tests/test_app_server_client.py -k "thread_settings_update" -q && python -m pytest tests/test_parent_thread_submit.py -q && python -m pytest tests/test_actor_side_thread.py -q && python -m pytest tests/test_task_sys_runtime_executor.py -q && python -m pytest tests/test_daemon_service_contract.py -q && python -m pytest tests/test_repo_consistency.py -q && python -m pytest tests/test_buddyswitch_launcher.py -k "model_config or side and model" -q && python -m pytest tests/test_web_management.py -k "side and model" -q
```

Result:

```text
tests/test_actor_model_config.py: 8 passed, 8 subtests passed
tests/test_app_server_client.py -k thread_settings_update: 3 passed, 27 deselected
tests/test_parent_thread_submit.py: 4 passed
tests/test_actor_side_thread.py: 4 passed
tests/test_task_sys_runtime_executor.py: 23 passed, 14 subtests passed
tests/test_daemon_service_contract.py: 25 passed
tests/test_repo_consistency.py: 54 passed, 232 subtests passed
tests/test_buddyswitch_launcher.py -k "model_config or side and model": 5 passed, 207 deselected
tests/test_web_management.py -k "side and model": 2 passed, 64 deselected
```

## Contract Proof

Parent:

- `tests/test_task_sys_runtime_executor.py::test_execute_submit_parent_applies_model_config_settings_before_turn_start`
- Proves `model-config.json` parent config is loaded at the Task Sys parent boundary and `thread_settings_update` occurs before the delegated turn start path.

Side:

- `tests/test_buddyswitch_launcher.py::test_side_start_uses_model_config_side_defaults_as_thread_fork_only_actor_config`
- Proves `instance side` new-thread creation loads side config and sends resolved `model` and `model_reasoning_effort` through `thread/fork`.

Negative side existing-thread behavior:

- `tests/test_buddyswitch_launcher.py::test_side_send_existing_active_child_ignores_model_config_and_steers_side_not_parent`
- Proves existing side-thread sends do not fork, do not call `thread/settings/update`, and do not expose new model metadata.

## Residue Scans

Commands:

```bash
rg -n "model-config.json" tools/launcher/app_server.py tools/launcher/submit_turn.py tools/launcher/side_thread_lifecycle.py tools/launcher/daemon_core.py tools/launcher/task_sys_runtime.py
rg -n "side_thread_lifecycle\\.start_side_thread" tools/launcher/task_sys_runtime.py buddyswitch-codex tools/launcher/env.sh
rg -n "subparsers\\.add_parser\\(\"start\"" tools/launcher/side_thread_lifecycle.py
rg -n "launcher_submit_turn\\.submit_turn" tools/launcher/task_sys_runtime.py tools/launcher/daemon_core.py
rg -n "thread/settings/update|config/batchWrite" tools/launcher/actor_side_thread.py tools/launcher/side_thread_lifecycle.py buddyswitch-codex tools/launcher/web_management.py
```

Result:

```text
no output
```

Attach live-surface scan:

```bash
rg -n "attach.*(hot-load|hot load|model-config|model config)|model-config.*attach|model config.*attach" buddyswitch-codex tools tests README.md AGENTS.md framework
```

Result:

```text
no output
```

Broad docs scan note:

- The broader `docs` scan only hits the input memo and stage planning docs that explicitly discuss attach TUI hot-load as out of scope.
- No CLI, WebUI, root/framework doc, or test live surface claims attach TUI v1 hot-load support.

## Remaining Risk

No unresolved risk remains inside the requested v1 scope.

Attach TUI hot-load remains intentionally unsupported and out of scope for this implementation.
