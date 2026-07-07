# Actor Model Config Stage 1 Plan: Config Core And Seed

Date: 2026-07-07

## Stage Target

Create the actor-local `model-config.json` core module and seed the default config file for every newly started actor instance.

This stage covers memo Task 1 and Task 2 only. Parent hot-load, side hot-load, app-server settings update, and routing boundary replacement are intentionally left for later stages.

## Current Code Facts

- No `tools/launcher/actor_model_config.py` exists.
- No `tests/test_actor_model_config.py` exists.
- `buddyswitch-codex::start_locked_bootstrap` creates and activates the instance root, then starts runtime services.
- `buddyswitch_instance_activate "${requested_actor_id}" "${requested_role}" "inactive"` writes `instance.json` after `buddyswitch_env_bind_instance` has established the instance paths.
- Existing launcher tests use fake Codex/app-server helpers and inspect `instance_root / "instance.json"` after `instance start`.
- `tools/launcher/app_server.py`, `tools/launcher/submit_turn.py`, `tools/launcher/side_thread_lifecycle.py`, `tools/launcher/daemon_core.py`, and `tools/launcher/task_sys_runtime.py` currently do not mention `model-config.json`.

## Files

Create:

- `tools/launcher/actor_model_config.py`
- `tests/test_actor_model_config.py`

Modify:

- `buddyswitch-codex`
- `tests/test_buddyswitch_launcher.py`
- `docs/spec/2026-07-07-actor-model-config-stage-1-config-core-and-seed.md`

Do not modify in this stage:

- `tools/launcher/app_server.py`
- `tools/launcher/submit_turn.py`
- `tools/launcher/side_thread_lifecycle.py`
- `tools/launcher/task_sys_runtime.py`
- `tools/launcher/daemon_core.py`

## Module Boundary

`actor_model_config.py` owns:

- `model-config.json` filename and path derivation from `instance.json`.
- Default seed payload.
- Schema version 1 validation.
- Loading config from disk.
- Resolving parent and side options.
- Side explicit override merge semantics.
- Side result source metadata.

`buddyswitch-codex` may only call the seed helper during instance creation. It must not parse, validate, or interpret config fields.

Wrong layers must remain free of `model-config.json` references:

- `app_server.py`
- `submit_turn.py`
- `side_thread_lifecycle.py`
- `daemon_core.py`
- `task_sys_runtime.py`

## Development Steps

### Step 1: Write Config Core Failing Tests

Add `tests/test_actor_model_config.py` with focused tests for:

- `model_config_path(instance_json)` returns `instance_json.parent / "model-config.json"`.
- `seed_model_config_if_missing(instance_json)` writes:

```json
{
  "schema_version": 1,
  "parent": {},
  "side": {}
}
```

- Existing config is not overwritten by seeding.
- Missing file resolves as schema version 1 empty defaults in memory without writing.
- Validation rejects:
  - missing or non-`1` `schema_version`
  - non-object `parent`
  - non-object `side`
  - empty `model`
  - invalid `effort`
  - unknown top-level keys
  - unknown keys inside `parent` or `side`
- Parent resolution returns only configured parent fields.
- Side resolution returns file values when no explicit override is supplied.
- Side explicit `model` and `effort` override file values field-by-field.
- Side source metadata distinguishes `actor_config`, `override`, and `codex_default`.

Run:

```bash
python -m pytest tests/test_actor_model_config.py -q
```

Expected before implementation:

```text
ModuleNotFoundError: No module named 'actor_model_config'
```

### Step 2: Implement Config Core

Create `tools/launcher/actor_model_config.py`.

Required public contract:

```python
MODEL_CONFIG_FILENAME = "model-config.json"
VALID_EFFORTS = {"minimal", "low", "medium", "high", "ultra"}

def model_config_path(instance_json: Path) -> Path: ...
def seed_model_config_if_missing(instance_json: Path) -> Path: ...
def load_model_config(instance_json: Path) -> ActorModelConfig: ...
def resolve_parent_options(instance_json: Path) -> ResolvedModelOptions: ...
def resolve_side_options(
    instance_json: Path,
    *,
    explicit_model: str | None = None,
    explicit_effort: str | None = None,
) -> ResolvedModelOptions: ...
def apply_side_source_metadata(payload: Mapping[str, Any], options: ResolvedModelOptions) -> dict[str, Any]: ...
```

Implementation choices:

- Use `@dataclass(frozen=True)` for resolved options.
- Trim configured strings after validation.
- Missing file returns empty parent/side config without creating a file.
- Seed writes JSON with `ensure_ascii=True`, `indent=2`, and a trailing newline.
- Unknown keys fail by allowlist, not retired-structure blacklist.
- Invalid config raises `ActorModelConfigError` with a clear path and field reason.
- Missing side values use source `codex_default`, not `parent_thread`.
- `apply_side_source_metadata(...)` preserves lifecycle payload fields but overwrites `model_source`, `model_reasoning_effort_source`, and `model_config_durability` to actor-boundary source names.

Run:

```bash
python -m pytest tests/test_actor_model_config.py -q
```

Expected after implementation:

```text
passed
```

### Step 3: Write Instance Seed Failing Test

Add a focused launcher test in `tests/test_buddyswitch_launcher.py`:

```text
test_instance_start_seeds_model_config_default_schema
```

The test must:

- Start a fake service instance using `_start_service_instance(...)`.
- Assert the command returns zero.
- Assert `ctx["instance_root"] / "model-config.json"` exists.
- Assert its JSON payload equals:

```json
{
  "schema_version": 1,
  "parent": {},
  "side": {}
}
```

- Assert `instance.json` does not contain `model`, `effort`, `parent`, `side`, or `model_config`.

Run:

```bash
python -m pytest tests/test_buddyswitch_launcher.py -k "model_config" -q
```

Expected before launcher implementation:

```text
failed
```

### Step 4: Seed During Locked Start Bootstrap

Modify `buddyswitch-codex`:

- Add `MODEL_CONFIG_HELPER="${REPO_ROOT}/tools/launcher/actor_model_config.py"`.
- Include the helper in the launcher missing-helper check.
- In `start_locked_bootstrap`, after `buddyswitch_instance_activate "${requested_actor_id}" "${requested_role}" "inactive"` succeeds and before service startup, run:

```bash
python3 "${MODEL_CONFIG_HELPER}" seed --instance-json "$(buddyswitch_instance_json_path "${requested_actor_id}")"
```

The shell layer must only call the helper. It must not inspect or mutate config JSON fields.

Add a small CLI to `actor_model_config.py`:

```text
actor_model_config.py seed --instance-json <path>
```

The CLI prints a compact JSON result with:

```json
{
  "ok": true,
  "path": "<path>"
}
```

### Step 5: Run Focused Stage Verification

Run:

```bash
python -m pytest tests/test_actor_model_config.py -q
python -m pytest tests/test_buddyswitch_launcher.py -k "model_config" -q
```

Expected:

```text
passed
```

### Step 6: Run Stage Residue Scan

Run:

```bash
rg -n "model-config.json" tools/launcher/app_server.py tools/launcher/submit_turn.py tools/launcher/side_thread_lifecycle.py tools/launcher/daemon_core.py tools/launcher/task_sys_runtime.py
```

Expected:

```text
no output
```

## Stage Acceptance

Stage 1 is accepted only when:

- `tests/test_actor_model_config.py` proves path, seed, validation, parent resolve, side resolve, and source metadata behavior.
- Launcher start seeds `model-config.json` with schema version 1 defaults.
- `instance.json` remains free of model config fields.
- The wrong-layer residue scan has no hits.
- This stage doc is updated with the exact test and scan results.

## Completion Notes

- Added `tools/launcher/actor_model_config.py` with model-config pathing, default seeding, schema version 1 validation, parent/side resolution, side override source metadata, and a `seed --instance-json` CLI.
- Added `tests/test_actor_model_config.py` covering path, seed, missing-file defaults, validation, parent resolution, side override precedence, and metadata source terms.
- Added `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_seeds_model_config_default_schema`.
- Updated `buddyswitch-codex::start_locked_bootstrap` to call the actor model config seed helper after `instance.json` activation and before runtime service startup.

## Test Results

Red checks:

```bash
python -m pytest tests/test_actor_model_config.py -q
```

Result:

```text
ModuleNotFoundError: No module named 'actor_model_config'
```

```bash
python -m pytest tests/test_buddyswitch_launcher.py -k "model_config" -q
```

Result:

```text
FAILED tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_seeds_model_config_default_schema
AssertionError: False is not true
```

Green checks:

```bash
python -m pytest tests/test_actor_model_config.py -q
```

Result:

```text
8 passed, 8 subtests passed in 0.02s
```

```bash
python -m pytest tests/test_buddyswitch_launcher.py -k "model_config" -q
```

Result:

```text
1 passed, 210 deselected in 2.49s
```

## Residue Scan Results

Command:

```bash
rg -n "model-config.json" tools/launcher/app_server.py tools/launcher/submit_turn.py tools/launcher/side_thread_lifecycle.py tools/launcher/daemon_core.py tools/launcher/task_sys_runtime.py
```

Result:

```text
no output
```

## Remaining Risk

Parent hot-load and side hot-load are intentionally not implemented in this stage.
