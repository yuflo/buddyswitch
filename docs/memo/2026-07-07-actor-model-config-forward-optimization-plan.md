# Actor Model Config Forward Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add actor instance-local parent and side model/effort configuration with clean hot-load boundaries and no legacy dual-track behavior.

**Architecture:** The product policy lives in actor-aware wrappers, not in daemon handlers, raw RPC helpers, or low-level lifecycle helpers. Parent flows through `parent_thread_submit.py -> submit_turn.py -> app_server.py`; side creation flows through `actor_side_thread.py -> side_thread_lifecycle.py -> app_server.py`. `actor_model_config.py` is the single reader, validator, and seeder for `model-config.json`.

**Tech Stack:** Python launcher helpers, Bash launcher projections, Codex app-server JSON-RPC, `unittest`/`pytest` style tests, scoped repository consistency scans.

---

## Source Of Truth

Primary architecture artifact:

- `docs/memo/2026-07-07-actor-model-config-boundary-architecture.html`

Principles read from `docs/bitter`:

- Fix the owning layer instead of compensating with prompts or handler branches.
- Semantic replacement requires behavior proof and live-surface residue scans.
- A narrow change is still wrong if it lands at the wrong boundary.
- Built-in product semantics belong in product core, with CLI/Web/daemon as projections.
- End-to-end contract slices must prove the user-visible loop, not only local units.
- Runtime guards for retired shapes are residue unless there is a real migration or external contract.

## Task Goal Restatement

Create an actor-local config file:

```text
<instance-root>/model-config.json
```

with schema:

```json
{
  "schema_version": 1,
  "parent": {
    "model": "gpt-5.4",
    "effort": "high"
  },
  "side": {
    "model": "gpt-5.4-mini",
    "effort": "medium"
  }
}
```

New actor instances should seed a schema-valid editable file. Existing instances with no file should behave as schema version 1 with empty parent/side defaults in memory, not as an old schema. Users can edit the local file while the actor is running.

Hot-load behavior:

- Parent: every BuddySwitch-controlled parent submit reads the current file, applies `thread/settings/update` when parent model/effort fields are present, waits for `thread/settings/updated`, then delegates to `submit_turn.py`.
- Side: every new side-thread creation reads the current file, merges explicit request overrides, and passes resolved values into `side_thread_lifecycle.start_side_thread(...)`.
- Existing side threads are not mutated after creation.
- `instance attach` TUI direct input is out of scope for v1.

## Non-Negotiable Requirements

- No daemon-by-scenario model logic.
- No `model-config.json` reads in `app_server.py`, `submit_turn.py`, `side_thread_lifecycle.py`, `daemon_core.py`, or `task_sys_runtime.py`.
- No persistent Codex config writes for side model selection.
- No use of `thread/settings/update` for side-thread model selection.
- No compatibility dual path where Task Sys, CLI, or WebUI can keep calling side creation directly while the new actor side wrapper also exists.
- No expansion into a generic runtime policy engine, config DSL, watcher, or attach TUI background reconciler.
- Attach TUI support remains a separate future design, not a hidden v1 side path.

## Current Code Facts

- `tools/launcher/app_server.py` already sends `experimentalApi: True` during initialize.
- `tools/launcher/app_server.py::thread_fork(...)` already accepts `model` and `model_reasoning_effort` and sends them as `thread/fork` creation params.
- `tools/launcher/submit_turn.py::submit_turn(...)` is a narrow start/steer helper and should remain actor-config unaware.
- `tools/launcher/side_thread_lifecycle.py::start_side_thread(...)` already accepts resolved `model` and `model_reasoning_effort`; it also owns side registry lease execution.
- `tools/launcher/task_sys_runtime.py` currently calls `side_thread_lifecycle.start_side_thread(...)` and `launcher_submit_turn.submit_turn(...)` directly.
- `tools/launcher/daemon_core.py` currently calls `launcher_submit_turn.submit_turn(...)` directly for daemon parent submit.
- `tools/launcher/env.sh` currently exposes `buddyswitch_side_thread_lifecycle_start`, and `buddyswitch-codex instance side` uses that path.
- `tools/launcher/web_management.py` projects WebUI side creation through `buddyswitch-codex instance side`.
- `tests/test_repo_consistency.py::test_side_thread_model_override_has_no_persistent_config_write_path` currently forbids `thread/settings/update` globally and must be narrowed because parent hot-load now needs that method.
- Local Codex source confirms `thread/settings/update` supports `model` and `effort` for subsequent turns and emits `thread/settings/updated`.
- `AppServerClient.request(...)` skips notifications while waiting for a response, so parent settings update needs a dedicated primitive that captures the matching notification rather than losing it.

## Module Boundary Contract

### `tools/launcher/actor_model_config.py`

Owns:

- `model-config.json` path derivation from `instance_json`.
- schema version 1 validation.
- seed file creation for new instances.
- load/resolve of parent and side model options.
- explicit override merge helper for side creation.

Does not own:

- Codex RPC calls.
- side registry writes.
- start/steer mechanics.
- daemon, Task Sys, CLI, or WebUI routing.

### `tools/launcher/parent_thread_submit.py`

Owns:

- actor-aware parent config load.
- parent `thread/settings/update`.
- delegation to `submit_turn.submit_turn(...)`.

Does not own:

- active/idle start/steer branching.
- side-thread creation.
- daemon handler semantics.

### `tools/launcher/actor_side_thread.py`

Owns:

- actor-aware side config load.
- explicit side override precedence.
- delegation to `side_thread_lifecycle.start_side_thread(...)`.

Does not own:

- side registry storage format.
- side send/cleanup behavior.
- app-server JSON-RPC framing.

### Existing Execution Helpers

`submit_turn.py` remains only:

```text
thread/read -> idle turn/start OR active turn/steer
```

`side_thread_lifecycle.py` remains only:

```text
thread/fork -> inject boundary -> turn/start -> registry lease
send -> read status -> turn/start or turn/steer -> registry update
cleanup -> interrupt if needed -> registry close
```

`app_server.py` remains only JSON-RPC primitives.

## Key Questions Resolved

- Should parent config be implemented inside `submit_turn.py`?
  - No. Add `parent_thread_submit.py` above it.

- Should side config be implemented inside `side_thread_lifecycle.py`?
  - No. Add `actor_side_thread.py` above it. Keep lifecycle registry work where it is for now.

- Does daemon need to know model policy?
  - No. Daemon reaches policy only by calling controlled actor-aware boundaries.

- Does attach TUI get hot-load behavior?
  - No for v1. It bypasses BuddySwitch actor-aware wrappers.

- Is missing `model-config.json` a legacy mode?
  - No. It is schema version 1 empty default in memory. New instances seed the file.

## Implementation Tasks

### Task 1: Add Actor Model Config Core

**Files:**

- Create: `tools/launcher/actor_model_config.py`
- Test: `tests/test_actor_model_config.py`

- [ ] Write tests for path derivation and default seed.

Run:

```bash
python -m pytest tests/test_actor_model_config.py -q
```

Expected before implementation:

```text
ModuleNotFoundError: No module named 'actor_model_config'
```

- [ ] Implement:

```python
MODEL_CONFIG_FILENAME = "model-config.json"

def model_config_path(instance_json: Path) -> Path:
    return instance_json.parent / MODEL_CONFIG_FILENAME
```

Expected seed payload:

```json
{
  "schema_version": 1,
  "parent": {},
  "side": {}
}
```

- [ ] Add validation tests:
  - `schema_version` must be `1`.
  - `parent` and `side`, when present, must be objects.
  - `model`, when present, must be non-empty string.
  - `effort`, when present, must be one of `minimal`, `low`, `medium`, `high`, `ultra`.
  - unknown top-level keys fail.
  - unknown parent/side keys fail.

- [ ] Add resolve tests:
  - missing file returns empty parent/side options without writing.
  - seeded file loads empty options.
  - configured parent returns model/effort.
  - configured side returns model/effort.
  - explicit side override beats file value field-by-field.
  - side result sources distinguish `actor_config`, `override`, and `codex_default`.

- [ ] Run:

```bash
python -m pytest tests/test_actor_model_config.py -q
```

Expected after implementation:

```text
passed
```

### Task 2: Seed Model Config During Instance Creation

**Files:**

- Modify: `buddyswitch-codex`
- Test: `tests/test_buddyswitch_launcher.py`

- [ ] Add a focused launcher test that starts an instance and asserts `<instance-root>/model-config.json` exists with the default schema payload.

Run:

```bash
python -m pytest tests/test_buddyswitch_launcher.py -k "model_config" -q
```

Expected before implementation:

```text
failed
```

- [ ] Call `actor_model_config.seed_model_config_if_missing(instance_json)` during locked start bootstrap after the instance root exists and before successful start returns.

- [ ] Do not write model config fields into `instance.json`.

- [ ] Re-run the focused launcher test.

Expected after implementation:

```text
passed
```

### Task 3: Add App-Server Settings Update Primitive

**Files:**

- Modify: `tools/launcher/app_server.py`
- Test: `tests/test_app_server_client.py`

- [ ] Add tests for `thread_settings_update(...)`:
  - sends method `thread/settings/update`.
  - sends params `{"threadId": "thread-main", "model": "gpt-5.4", "effort": "high"}`.
  - returns the matching `thread/settings/updated` notification payload.
  - captures the notification whether it arrives before or after the JSON-RPC response.
  - omits absent fields rather than sending null.

- [ ] Implement a dedicated client method or helper that does not lose the target notification while waiting for the response.

Required public primitive shape:

```python
def thread_settings_update(
    socket_path: Path,
    thread_id: str,
    *,
    model: str | None = None,
    effort: str | None = None,
) -> dict[str, Any]:
    params = build_thread_settings_update_params(thread_id, model=model, effort=effort)
    with AppServerClient(socket_path, timeout_seconds=DEFAULT_RPC_TIMEOUT_SECONDS) as client:
        return client.request_with_notification(
            "thread/settings/update",
            params,
            notification_method="thread/settings/updated",
            notification_thread_id=thread_id,
        )
```

- [ ] Make `build_thread_settings_update_params(...)` raise `AppServerProtocolError` when both `model` and `effort` are absent. Parent wrapper must skip the primitive in that case.

- [ ] Run:

```bash
python -m pytest tests/test_app_server_client.py -k "thread_settings_update" -q
```

Expected after implementation:

```text
passed
```

### Task 4: Add Parent Actor Boundary

**Files:**

- Create: `tools/launcher/parent_thread_submit.py`
- Modify: `tools/launcher/task_sys_runtime.py`
- Modify: `tools/launcher/daemon_core.py`
- Test: `tests/test_parent_thread_submit.py`
- Test: `tests/test_task_sys_runtime_executor.py`
- Test: `tests/test_daemon_service_contract.py`

- [ ] Write `tests/test_parent_thread_submit.py`:
  - configured parent calls `app_server.thread_settings_update(...)` before `submit_turn.submit_turn(...)`.
  - missing config skips settings update and still submits.
  - invalid config raises a clear parent submit error before submit.
  - active parent turn still performs settings update first and delegates to `submit_turn`; test wording must state the setting applies to subsequent turns.

- [ ] Implement:

```python
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

- [ ] Replace `launcher_submit_turn.submit_turn(...)` in `task_sys_runtime.py` with `parent_thread_submit.submit_parent_turn(...)`.

- [ ] Replace `launcher_submit_turn.submit_turn(...)` in `daemon_core.py` with `parent_thread_submit.submit_parent_turn(...)`.

- [ ] Update tests that currently monkeypatch `launcher_submit_turn.submit_turn` to patch `parent_thread_submit.submit_parent_turn`.

- [ ] Keep `submit_turn.py` tests unchanged except for residue assertions proving it stays config-unaware.

- [ ] Run:

```bash
python -m pytest tests/test_parent_thread_submit.py tests/test_task_sys_runtime_executor.py tests/test_daemon_service_contract.py -q
```

Expected after implementation:

```text
passed
```

### Task 5: Add Side Actor Boundary

**Files:**

- Create: `tools/launcher/actor_side_thread.py`
- Modify: `tools/launcher/task_sys_runtime.py`
- Modify: `tools/launcher/env.sh`
- Modify: `buddyswitch-codex`
- Test: `tests/test_actor_side_thread.py`
- Test: `tests/test_task_sys_runtime_executor.py`
- Test: `tests/test_buddyswitch_launcher.py`
- Test: `tests/test_web_management.py`

- [ ] Write `tests/test_actor_side_thread.py`:
  - configured side passes model/effort to `side_thread_lifecycle.start_side_thread(...)`.
  - explicit `--model` and `--effort` override file values field-by-field.
  - missing config passes no model/effort.
  - invalid config fails before lifecycle starts.
  - wrapper corrects output metadata so actor-config values are reported as `actor_config`, explicit values as `override`, and omitted values as `codex_default`.

- [ ] Implement:

```python
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
    options = actor_model_config.resolve_side_options(
        instance_json,
        explicit_model=model,
        explicit_effort=model_reasoning_effort,
    )
    payload = side_thread_lifecycle.start_side_thread(
        socket_path=socket_path,
        instance_json=instance_json,
        actor_id=actor_id,
        parent_thread_id=parent_thread_id,
        text=text,
        purpose=purpose,
        workspace_dir=workspace_dir,
        shared_project_workspace_dir=shared_project_workspace_dir,
        permissions=permissions,
        task_id=task_id,
        model=options.model,
        model_reasoning_effort=options.effort,
    )
    return actor_model_config.apply_side_source_metadata(payload, options)
```

- [ ] Replace Task Sys side creation call from `side_thread_lifecycle.start_side_thread(...)` to `actor_side_thread.start_actor_side_thread(...)`.

- [ ] Replace shell start projection:
  - remove direct `buddyswitch_side_thread_lifecycle_start` usage for new side start.
  - add one actor-side start helper that invokes `tools/launcher/actor_side_thread.py`.
  - keep lifecycle send/cleanup helpers only for send/cleanup, not creation config policy.
  - remove the `start` subcommand from `side_thread_lifecycle.py` CLI. The public side start script entry must be `actor_side_thread.py`.

- [ ] Update `buddyswitch-codex instance side` to call the actor-side start helper.

- [ ] Update WebUI side tests only through the CLI projection; do not add WebUI-specific model policy.

- [ ] Run:

```bash
python -m pytest tests/test_actor_side_thread.py tests/test_task_sys_runtime_executor.py -q
python -m pytest tests/test_buddyswitch_launcher.py -k "side and model" -q
python -m pytest tests/test_web_management.py -k "side and model" -q
```

Expected after implementation:

```text
passed
```

### Task 6: Narrow Consistency Gates And Add Residue Scans

**Files:**

- Modify: `tests/test_repo_consistency.py`

- [ ] Replace the current global `thread/settings/update` ban with targeted rules:
  - allow `thread/settings/update` in `tools/launcher/app_server.py`, `tools/launcher/parent_thread_submit.py`, and related tests.
  - forbid `thread/settings/update` in side start paths, `actor_side_thread.py`, `side_thread_lifecycle.py`, `buddyswitch-codex` side start code, and WebUI side projection.

- [ ] Add no-residue scans:
  - `model-config.json` must not be read from `app_server.py`, `submit_turn.py`, `side_thread_lifecycle.py`, `daemon_core.py`, or `task_sys_runtime.py`.
  - `side_thread_lifecycle.start_side_thread` must not be called directly from Task Sys or CLI side start projections.
  - `launcher_submit_turn.submit_turn` must not be called directly from Task Sys or daemon parent submit paths.
  - side model selection must not use `config/batchWrite`.

- [ ] Run:

```bash
python -m pytest tests/test_repo_consistency.py -q
```

Expected after implementation:

```text
passed
```

### Task 7: End-To-End Contract Slices

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_task_sys_runtime_executor.py`

- [ ] Add parent contract test:

```text
edit model-config.json parent -> execute controlled parent submit -> app-server sees thread/settings/update before turn/start or turn/steer
```

- [ ] Add side contract test:

```text
edit model-config.json side -> start new side through instance side or Task Sys -> app-server sees thread/fork model/config params
```

- [ ] Add negative side contract test:

```text
send to existing side after editing model-config.json -> no new thread/fork and no settings/update
```

- [ ] Add attach scope assertion in docs or tests only if a live surface claims attach coverage. Do not add attach runtime reconciliation in v1.

- [ ] Run the focused contract tests first.

Expected after implementation:

```text
passed
```

## Verification Plan

Focused commands:

```bash
python -m pytest tests/test_actor_model_config.py -q
python -m pytest tests/test_app_server_client.py -k "thread_settings_update" -q
python -m pytest tests/test_parent_thread_submit.py -q
python -m pytest tests/test_actor_side_thread.py -q
python -m pytest tests/test_task_sys_runtime_executor.py -q
python -m pytest tests/test_daemon_service_contract.py -q
python -m pytest tests/test_repo_consistency.py -q
```

Launcher/WebUI contract commands:

```bash
python -m pytest tests/test_buddyswitch_launcher.py -k "model_config or side and model" -q
python -m pytest tests/test_web_management.py -k "side and model" -q
```

Residue commands:

```bash
rg -n "model-config.json" tools/launcher/app_server.py tools/launcher/submit_turn.py tools/launcher/side_thread_lifecycle.py tools/launcher/daemon_core.py tools/launcher/task_sys_runtime.py
rg -n "side_thread_lifecycle\\.start_side_thread" tools/launcher/task_sys_runtime.py buddyswitch-codex tools/launcher/env.sh
rg -n "subparsers\\.add_parser\\(\"start\"" tools/launcher/side_thread_lifecycle.py
rg -n "launcher_submit_turn\\.submit_turn" tools/launcher/task_sys_runtime.py tools/launcher/daemon_core.py
rg -n "thread/settings/update|config/batchWrite" tools/launcher/actor_side_thread.py tools/launcher/side_thread_lifecycle.py buddyswitch-codex tools/launcher/web_management.py
```

Expected residue result:

```text
no hits, except explicitly allowed app_server/parent wrapper/tests
```

Broad verification should run only after focused tests pass and no service-starting test helper shows residual process risk.

## Acceptance Criteria

- New actor instances contain editable `model-config.json`.
- Parent controlled submit reads the latest file on each controlled submit.
- Parent controlled submit sends `thread/settings/update` before the turn when parent config fields exist.
- Side new-thread creation reads the latest file on each creation.
- Side explicit CLI/Web values override file defaults for that new side only.
- Existing side send/cleanup behavior remains lifecycle-owned and does not reload side model config.
- `submit_turn.py`, `side_thread_lifecycle.py`, `app_server.py`, daemon handlers, and Task Sys do not own actor model policy.
- Repo consistency tests prevent reintroducing direct calls or model-config reads in the wrong layer.
- No stale live surface teaches the old architecture.

## Known Risks And Handling

- `thread/settings/updated` notification ordering can race with JSON-RPC response. Handle in `app_server.py` with a dedicated primitive that captures both response and notification.
- Existing tests monkeypatch direct helpers. Update them to patch actor-aware wrappers instead of keeping both call paths.
- `tests/test_repo_consistency.py` currently forbids parent `thread/settings/update`. Narrow the rule rather than deleting it.
- Service-starting launcher tests can leak resources if broadened too early. Use focused tests before broad launcher suites.
- Invalid config should fail loudly at actor-aware boundaries. Do not silently coerce wrong values into Codex defaults.

## Definition Of Done

- All implementation tasks above are complete.
- Focused tests and repository consistency tests pass.
- At least one parent and one side end-to-end contract slice pass.
- Residue scans show no old direct policy paths.
- The HTML architecture memo remains consistent with the implemented code.
- No attach TUI hot-load behavior is claimed in live docs, CLI help, WebUI labels, or tests.
