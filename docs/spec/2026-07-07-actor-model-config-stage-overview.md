# Actor Model Config Stage Overview

Date: 2026-07-07

## Target Outcome

Complete the actor model config forward optimization from `docs/memo/2026-07-07-actor-model-config-forward-optimization-plan.md`.

The final state is:

- `tools/launcher/actor_model_config.py` is the only owner of `model-config.json` path/schema/read/seed/resolve behavior.
- Parent submits route through `tools/launcher/parent_thread_submit.py`, which applies parent config with `thread/settings/update` before delegating to `submit_turn.py`.
- New side-thread creation routes through `tools/launcher/actor_side_thread.py`, which resolves side config and explicit overrides before delegating to `side_thread_lifecycle.py`.
- `submit_turn.py`, `side_thread_lifecycle.py`, `app_server.py`, daemon handlers, Task Sys, CLI, and WebUI do not own actor model policy.
- Existing side threads are not mutated by config changes after creation.
- Attach TUI hot-load remains out of scope for v1 and is not claimed by live docs/tests/UI/help.

## Current Evidence

Read before this overview:

- `AGENTS.md`
- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`
- `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`
- `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`
- `docs/bitter/2026-07-07-guarded-residue-boundary-principles.md`
- `docs/memo/2026-07-07-actor-model-config-forward-optimization-plan.md`
- `docs/memo/2026-07-07-actor-model-config-boundary-architecture.html`

Confirmed current code facts:

- `tools/launcher/task_sys_runtime.py` imports `submit_turn as launcher_submit_turn` and calls `launcher_submit_turn.submit_turn(...)` for parent submit.
- `tools/launcher/daemon_core.py` imports `submit_turn as launcher_submit_turn` and calls `launcher_submit_turn.submit_turn(...)` for daemon parent submit.
- `tools/launcher/task_sys_runtime.py` imports `side_thread_lifecycle` and calls `side_thread_lifecycle.start_side_thread(...)` for Task Sys side creation.
- `tools/launcher/env.sh` exposes `buddyswitch_side_thread_lifecycle_start`, which invokes `tools/launcher/side_thread_lifecycle.py start`.
- `tools/launcher/side_thread_lifecycle.py` still exposes `subparsers.add_parser("start")`.
- `tools/launcher/app_server.py` has `thread_fork(...)` model/effort support and initializes with `experimentalApi: True`, but does not yet expose `thread_settings_update(...)`.
- No actor-model-config stage docs existed before this file.

## Stage Split

### Stage 1: Config Core And Instance Seed

Memo coverage:

- Task 1: Add Actor Model Config Core.
- Task 2: Seed Model Config During Instance Creation.

Primary files:

- Create `tools/launcher/actor_model_config.py`.
- Create `tests/test_actor_model_config.py`.
- Modify `buddyswitch-codex`.
- Modify `tests/test_buddyswitch_launcher.py`.

Focused verification:

```bash
python -m pytest tests/test_actor_model_config.py -q
python -m pytest tests/test_buddyswitch_launcher.py -k "model_config" -q
```

Residue gate:

```bash
rg -n "model-config.json" tools/launcher/app_server.py tools/launcher/submit_turn.py tools/launcher/side_thread_lifecycle.py tools/launcher/daemon_core.py tools/launcher/task_sys_runtime.py
```

Expected residue: no hits.

### Stage 2: App-Server Parent Settings Primitive

Memo coverage:

- Task 3: Add App-Server Settings Update Primitive.

Primary files:

- Modify `tools/launcher/app_server.py`.
- Modify `tests/test_app_server_client.py`.

Focused verification:

```bash
python -m pytest tests/test_app_server_client.py -k "thread_settings_update" -q
```

Boundary gate:

- `thread/settings/update` is only a raw RPC primitive in `app_server.py`; it does not read `model-config.json`.
- The primitive captures the matching `thread/settings/updated` notification whether it arrives before or after the JSON-RPC response.

### Stage 3: Parent Actor Boundary

Memo coverage:

- Task 4: Add Parent Actor Boundary.

Primary files:

- Create `tools/launcher/parent_thread_submit.py`.
- Create `tests/test_parent_thread_submit.py`.
- Modify `tools/launcher/task_sys_runtime.py`.
- Modify `tools/launcher/daemon_core.py`.
- Modify `tests/test_task_sys_runtime_executor.py`.
- Modify `tests/test_daemon_service_contract.py`.

Focused verification:

```bash
python -m pytest tests/test_parent_thread_submit.py tests/test_task_sys_runtime_executor.py tests/test_daemon_service_contract.py -q
```

Residue gate:

```bash
rg -n "launcher_submit_turn\\.submit_turn" tools/launcher/task_sys_runtime.py tools/launcher/daemon_core.py
```

Expected residue: no hits.

### Stage 4: Side Actor Boundary

Memo coverage:

- Task 5: Add Side Actor Boundary.

Primary files:

- Create `tools/launcher/actor_side_thread.py`.
- Create `tests/test_actor_side_thread.py`.
- Modify `tools/launcher/task_sys_runtime.py`.
- Modify `tools/launcher/env.sh`.
- Modify `tools/launcher/side_thread_lifecycle.py`.
- Modify `buddyswitch-codex`.
- Modify `tests/test_task_sys_runtime_executor.py`.
- Modify `tests/test_buddyswitch_launcher.py`.
- Modify `tests/test_web_management.py`.

Focused verification:

```bash
python -m pytest tests/test_actor_side_thread.py tests/test_task_sys_runtime_executor.py -q
python -m pytest tests/test_buddyswitch_launcher.py -k "side and model" -q
python -m pytest tests/test_web_management.py -k "side and model" -q
```

Residue gate:

```bash
rg -n "side_thread_lifecycle\\.start_side_thread" tools/launcher/task_sys_runtime.py buddyswitch-codex tools/launcher/env.sh
rg -n "subparsers\\.add_parser\\(\"start\"" tools/launcher/side_thread_lifecycle.py
rg -n "thread/settings/update|config/batchWrite" tools/launcher/actor_side_thread.py tools/launcher/side_thread_lifecycle.py buddyswitch-codex tools/launcher/web_management.py
```

Expected residue: no hits.

### Stage 5: Consistency Gates And Contract Slices

Memo coverage:

- Task 6: Narrow Consistency Gates And Add Residue Scans.
- Task 7: End-To-End Contract Slices.

Primary files:

- Modify `tests/test_repo_consistency.py`.
- Modify `tests/test_buddyswitch_launcher.py`.
- Modify `tests/test_task_sys_runtime_executor.py`.
- Modify tests or docs only if a live attach surface claims unsupported v1 hot-load behavior.

Focused verification:

```bash
python -m pytest tests/test_repo_consistency.py -q
python -m pytest tests/test_buddyswitch_launcher.py -k "model_config or side and model" -q
python -m pytest tests/test_task_sys_runtime_executor.py -q
```

Residue gate:

Run all memo residue commands and record results in the stage doc and final acceptance doc.

### Stage 6: Final Acceptance

Memo coverage:

- Final acceptance items 1-8 from the pasted objective.

Primary files:

- Create `docs/spec/2026-07-07-actor-model-config-final-acceptance.md`.

Final verification:

```bash
python -m pytest tests/test_actor_model_config.py -q
python -m pytest tests/test_app_server_client.py -k "thread_settings_update" -q
python -m pytest tests/test_parent_thread_submit.py -q
python -m pytest tests/test_actor_side_thread.py -q
python -m pytest tests/test_task_sys_runtime_executor.py -q
python -m pytest tests/test_daemon_service_contract.py -q
python -m pytest tests/test_repo_consistency.py -q
python -m pytest tests/test_buddyswitch_launcher.py -k "model_config or side and model" -q
python -m pytest tests/test_web_management.py -k "side and model" -q
```

Required scans:

```bash
rg -n "model-config.json" tools/launcher/app_server.py tools/launcher/submit_turn.py tools/launcher/side_thread_lifecycle.py tools/launcher/daemon_core.py tools/launcher/task_sys_runtime.py
rg -n "side_thread_lifecycle\\.start_side_thread" tools/launcher/task_sys_runtime.py buddyswitch-codex tools/launcher/env.sh
rg -n "subparsers\\.add_parser\\(\"start\"" tools/launcher/side_thread_lifecycle.py
rg -n "launcher_submit_turn\\.submit_turn" tools/launcher/task_sys_runtime.py tools/launcher/daemon_core.py
rg -n "thread/settings/update|config/batchWrite" tools/launcher/actor_side_thread.py tools/launcher/side_thread_lifecycle.py buddyswitch-codex tools/launcher/web_management.py
rg -n "attach.*(hot-load|hot load|model-config|model config)|model-config.*attach|model config.*attach" buddyswitch-codex docs tools tests
```

Expected residue:

- No `model-config.json` reads in wrong layers.
- No direct side start calls from Task Sys, CLI shell projection, or CLI wrapper.
- No side lifecycle `start` CLI subcommand.
- No direct parent submit calls from Task Sys or daemon parent paths.
- No side path uses `thread/settings/update` or `config/batchWrite`.
- No live surface claims attach TUI v1 hot-load support.

## Stage Process

Each stage must have a dedicated `docs/spec/2026-07-07-actor-model-config-stage-N-<name>.md` plan before implementation begins.

Each stage plan must include:

- Stage target.
- Current code facts.
- Files to create, modify, or delete.
- Module boundary rules.
- Layers not allowed to own or read model policy.
- Detailed TDD steps.
- Focused tests.
- Residue scans.
- Acceptance criteria.
- Completion notes, test output, scan output, and remaining risk after implementation.

Do not move to the next stage until the focused tests and residue scans for the current stage have passed and the stage doc has been updated with evidence.
