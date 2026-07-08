# Actor Model Config Management Interface Forward Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. This plan is for a future implementation pass; it intentionally stops at management interfaces and does not build the WebUI form/card.

**Goal:** Add actor-scoped management interfaces for parent and side `model` / `effort` defaults so WebUI can consume them in a later UI slice and CLI/scripts can manage the same actor-local config that runtime parent and side execution already consume.

**Architecture:** Keep the capability built into the existing actor model config core. Add only thin management adapters: Web HTTP routes in `web_management.py` and an `instance model-config` CLI command in `instance.sh` / `buddyswitch-codex`. Do not add a generic settings service, compatibility path, feature flag, or alternate runtime application path.

**Tech Stack:** Existing Python launcher helpers under `tools/launcher/`, existing bash launcher dispatch in `buddyswitch-codex` and `tools/launcher/instance.sh`, existing Web management HTTP API in `tools/launcher/web_management.py`, existing Python `unittest` coverage.

---

## Upgrade Target

The current runtime application path is already in place:

```text
parent_thread_submit.py -> actor_model_config.resolve_parent_options()
actor_side_thread.py    -> actor_model_config.resolve_side_options()
```

The missing capability for this slice is the management interface path:

```text
future Browser UI -> Web-interface HTTP API -> actor_model_config.py
CLI/script       -> instance model-config  -> actor_model_config.py
```

The upgrade must make actor model config a built-in product capability, not a WebUI-only feature and not scattered file manipulation. The WebUI visual controls are intentionally deferred until the API and CLI management contracts are stable.

## Current Code Evidence

Read before implementation:

- `AGENTS.md`
- all files in `docs/bitter/`
- `docs/arch/web-interface-call-architecture.md`
- `docs/spec/2026-07-07-actor-model-config-stage-overview.md`
- `docs/spec/2026-07-07-actor-model-config-final-acceptance.md`

Confirmed code facts:

- `tools/launcher/actor_model_config.py` owns `model-config.json` pathing from `instance_json`, schema version, section validation, default seed, parent resolve, side resolve, and side source metadata.
- `tools/launcher/actor_model_config.py` only exposes a `seed` command today. It does not expose management read or replace.
- `tools/launcher/parent_thread_submit.py` applies parent config before delegating to `submit_turn.py`.
- `tools/launcher/actor_side_thread.py` applies side config at new side-thread creation time before delegating to `side_thread_lifecycle.py`.
- `tools/launcher/web_management.py` has no model-config route and actor console DTO has no `model_config` projection.
- `tools/launcher/instance.sh` has no `instance model-config` command.
- `tools/launcher/assets/web-management/*` has no actor model defaults UI and remains out of scope for this interface slice.
- `tests/test_repo_consistency.py` already prevents wrong execution layers from reading `model-config.json` and prevents direct side lifecycle start paths from returning.

## Bitter Constraints

This plan applies the `docs/bitter` lessons directly:

- Built-in product interface: the product capability is `actor_model_config.py`; Web and CLI are projections.
- Wrong-boundary narrowness: do not put a narrow Web-specific config special case into `web_management.py`.
- Residue cleanup: live surfaces must teach one current route and one current config model.
- Guarded residue: do not add retired-shape blacklists; construct exact current schema.
- End-to-end contract slice: prove Web/CLI write -> core persisted config -> runtime resolve consumes the same facts.
- Test lifecycle: use focused unit and adapter tests; avoid broad service-starting suites unless process lifecycle is explicitly part of the change.
- Parallel boundary: avoid turning `web_management.py` into the owner of config semantics; keep shared semantics in the core.

## Target Architecture

```text
Management adapters
  Web-interface API adapter ----------------\
  Launcher CLI adapter ---------------------+-> actor_model_config.py

Runtime application adapters
  parent_thread_submit.py ------------------/
  actor_side_thread.py ---------------------/
```

There are two kinds of consumers:

- Management adapters write and read actor defaults.
- Runtime application adapters read and apply actor defaults at the correct execution time.

The adapters are parallel consumers of the core. Management adapters must not call `parent_thread_submit.py` or `actor_side_thread.py`, because those modules have runtime side effects. Runtime application adapters must not expose management write behavior, because they are execution boundaries.

## Module Boundaries

### `tools/launcher/actor_model_config.py`

Owns:

- `model-config.json` schema and default payload.
- Read/validate behavior for persisted config.
- Management DTO construction.
- Full replacement from management request payload.
- Null-to-clear semantics for management requests.
- Atomic file write.
- Parent and side runtime resolve.
- CLI subcommands that operate on `--instance-json`.

Does not own:

- Browser HTTP routing.
- Actor id validation from public routes.
- CLI command UX under `buddyswitch-codex instance`.
- App-server RPC calls.
- Parent turn submission.
- Side-thread creation.
- Model catalog or provider capability discovery.

### `tools/launcher/web_management.py`

Owns:

- Browser-facing HTTP routes.
- Web DTO wrapping and `HttpError` mapping.
- Actor id validation.
- Instance record existence checks.
- Calling `actor_model_config.py` as the core.

Does not own:

- Schema rules.
- Normalization rules.
- Atomic config file writes.
- Runtime application timing.
- Shell command parsing.

### `tools/launcher/instance.sh` and `buddyswitch-codex`

Own:

- Public CLI shape.
- Actor id validation through existing launcher helpers.
- Instance record validation.
- `actor_id -> instance_json` resolution.
- Human output and JSON output for scripts.

Do not own:

- Schema rules.
- File write format.
- Runtime application timing.

### `tools/launcher/assets/web-management/*`

Future slice owns:

- Browser UI rendering and interaction state.
- Calling Web-interface HTTP APIs only.
- Presenting parent and side default values and save state.

Do not own:

- Config file paths.
- Launcher CLI invocation.
- Runtime model application.
- Product truth.

This plan must not modify this directory except through residue checks. The WebUI card, inputs, save state, and interaction polish belong to a follow-up UI implementation plan.

### `tools/launcher/parent_thread_submit.py`

Owns:

- Applying parent model config before BuddySwitch-controlled parent submit.
- Waiting for parent settings update before delegated submit.

Does not own:

- Config management writes.
- Web/CLI DTO semantics.

### `tools/launcher/actor_side_thread.py`

Owns:

- Applying side model config and explicit creation overrides when creating a new side thread.
- Reporting source metadata for the new side thread result.

Does not own:

- Config management writes.
- Existing side-thread mutation.

## Config Semantics

Persisted file shape remains schema version 1:

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

Management read DTO projects missing fields as `null` for interface consumers:

```json
{
  "schema_version": 1,
  "parent": {
    "model": null,
    "effort": null
  },
  "side": {
    "model": "gpt-5.4-mini",
    "effort": "medium"
  },
  "allowed_efforts": ["high", "low", "medium", "minimal", "ultra"],
  "effects": {
    "parent": "applies_before_next_parent_submit",
    "side": "applies_to_new_side_threads_only"
  }
}
```

Management replace request is full replacement:

```json
{
  "parent": {
    "model": "gpt-5.4",
    "effort": "high"
  },
  "side": {
    "model": null,
    "effort": "medium"
  }
}
```

Rules:

- `parent` and `side` sections are required in replace requests.
- Section keys are exactly `model` and `effort`.
- `model` is either `null` or a non-empty trimmed string.
- `effort` is either `null` or one of `minimal`, `low`, `medium`, `high`, `ultra`.
- `null` means clear the actor override and fall back to Codex default.
- Disk payload stores cleared fields by omission, not by writing JSON nulls.
- Unknown top-level or section keys fail before writing.
- Invalid replacement must not mutate the existing file.
- Atomic write uses a temp file in the same directory followed by replace.

Runtime effects:

- Parent config applies before the next BuddySwitch-controlled parent submit.
- Side config applies only when creating a new side thread.
- Existing side threads are not mutated.
- Current active turns are not hot-loaded.

## Public Interface Contract

### CLI

Add:

```text
buddyswitch-codex instance model-config <actor-id> get [--json]
buddyswitch-codex instance model-config <actor-id> set --payload-json <json> [--json]
```

CLI behavior:

- Validate actor id.
- Validate instance record exists.
- Resolve instance JSON with existing launcher helpers.
- Delegate read/replace to `actor_model_config.py`.
- JSON output includes `ok`, `actor_id`, and `model_config`.
- Human output is a compact summary of parent and side defaults.

### Web API

Add:

```http
GET /api/actors/{actor_id}/model-config
PUT /api/actors/{actor_id}/model-config
```

Web behavior:

- Validate actor id.
- Require an existing instance record.
- Return `404 NOT_FOUND` if the actor instance record is missing.
- Return `400 INVALID_REQUEST` for malformed PUT payloads.
- Return `409 MODEL_CONFIG_INVALID` when an existing persisted config cannot be loaded for read.
- Return `502 MODEL_CONFIG_WRITE_FAILED` for filesystem write failures.
- Return the same `model_config` DTO shape as CLI JSON output.

Actor console:

- Include `model_config` in `/api/actors/{actor_id}/console` by using the same read projection.
- Do not make console GET write or seed config.

### Deferred WebUI Consumer

The WebUI card and controls are not part of this slice. The only WebUI-facing requirement here is that the Web-interface API and actor console DTO expose a stable contract that a later UI task can consume without file-path knowledge or CLI calls.

Deferred UI behavior:

- Read initial values from `actorConsole.model_config` or `GET /api/actors/{actor_id}/model-config`.
- Write with `PUT /api/actors/{actor_id}/model-config`.
- Treat empty model/effort controls as `null`.
- Never call CLI and never construct file paths.

## End-To-End Contract Sentence

An interface client writes parent and side defaults through Web API or CLI -> the adapter validates public shape and replaces actor config through `actor_model_config.py` -> Web API and CLI reads show the same defaults -> parent runtime resolve and side runtime resolve consume the same persisted facts at their execution boundaries.

This sentence is the acceptance target. Component tests do not replace it.

## Implementation Plan

### Task 1: Extend Actor Model Config Core

Files:

- Modify `tools/launcher/actor_model_config.py`
- Modify `tests/test_actor_model_config.py`

Steps:

1. Add failing tests for management DTO projection.
   - Missing config returns `parent.model = null`, `parent.effort = null`, `side.model = null`, `side.effort = null`.
   - `allowed_efforts` is sorted and includes exactly the current effort enum.
   - `effects.parent` and `effects.side` use the current runtime semantics.

2. Add failing tests for full replacement.
   - Replacement trims strings.
   - Replacement writes only non-null keys to disk.
   - Replacement output DTO projects cleared values as null.
   - Existing `resolve_parent_options()` and `resolve_side_options()` read the replaced values.

3. Add failing tests for invalid replacement.
   - Unknown top-level key fails.
   - Missing `parent` or `side` fails.
   - Unknown section key fails.
   - Empty model string fails.
   - Invalid effort fails.
   - Existing file remains unchanged after failure.

4. Implement core functions with these public signatures:
   - `read_management_payload(instance_json: Path) -> dict[str, Any]`
   - `replace_management_payload(instance_json: Path, payload: Mapping[str, Any]) -> dict[str, Any]`

5. Add `actor_model_config.py` subcommands:

```text
get --instance-json <path>
replace --instance-json <path> --payload-json <json>
```

6. Run focused verification:

```bash
python3 -m unittest tests.test_actor_model_config
```

Expected result:

```text
OK
```

### Task 2: Add Launcher CLI Adapter

Files:

- Modify `tools/launcher/instance.sh`
- Modify `buddyswitch-codex`
- Modify `tests/test_buddyswitch_launcher.py`

Steps:

1. Add usage text for `instance model-config`.

2. Add `buddyswitch_instance_model_config()` in `tools/launcher/instance.sh`.

3. Dispatch `model-config` in `buddyswitch_instance_main()`.

4. Implement get path:

```text
validate actor id
validate instance record
bind instance
python3 actor_model_config.py get --instance-json "$BUDDYSWITCH_INSTANCE_JSON"
```

5. Implement set path:

```text
validate actor id
validate instance record
bind instance
python3 actor_model_config.py replace --instance-json "$BUDDYSWITCH_INSTANCE_JSON" --payload-json "$payload_json"
```

6. Add launcher tests:
   - `instance model-config <actor> get --json` returns default null DTO for a seeded instance.
   - `instance model-config <actor> set --payload-json '{"parent":{"model":"gpt-5.4","effort":"high"},"side":{"model":"gpt-5.4-mini","effort":"medium"}}' --json` writes `model-config.json`.
   - CLI get after set returns the same DTO.
   - Invalid payload exits non-zero and does not mutate the file.
   - Unknown model-config option exits 2.

7. Run focused verification:

```bash
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_instance_start_seeds_model_config_default_schema
python3 -m unittest tests.test_buddyswitch_launcher -k model_config
```

Expected result:

```text
OK
```

If the local `unittest` version does not support `-k`, run the explicitly named model-config tests added in this task.

### Task 3: Add Web API Adapter

Files:

- Modify `tools/launcher/web_management.py`
- Modify `tests/test_web_management.py`

Steps:

1. Import `actor_model_config` in `web_management.py`.

2. Add a route parser for:

```text
/api/actors/{actor_id}/model-config
```

3. Add private helpers with these signatures:
   - `_instance_json_for_actor(self, actor_id: str) -> Path`
   - `_read_actor_model_config(self, actor_id: str) -> dict[str, Any]`
   - `_replace_actor_model_config(self, actor_id: str, body: bytes) -> dict[str, Any]`

4. Keep Web route behavior thin:
   - It validates actor id.
   - It verifies the instance record exists.
   - It maps exceptions to HTTP errors.
   - It delegates schema and write behavior to `actor_model_config.py`.

5. Include `model_config` in `_actor_console()` by calling `_read_actor_model_config(actor_id)["model_config"]`.

6. Add Web API tests:
   - GET route returns default null DTO.
   - PUT route replaces config and returns DTO.
   - GET after PUT returns the same DTO.
   - Actor console includes `model_config` as an interface projection for a future WebUI slice.
   - Invalid actor id is 400.
   - Missing actor instance is 404.
   - Invalid PUT payload is 400 and preserves the previous file.

7. Add an end-to-end adapter/core test:

```text
PUT /api/actors/act-pm-demo/model-config
  -> actor_model_config.resolve_parent_options(instance_json)
  -> actor_model_config.resolve_side_options(instance_json)
```

Expected:

- Parent resolve returns the PUT parent values.
- Side resolve returns the PUT side values.

8. Run focused verification:

```bash
python3 -m unittest tests.test_web_management.WebManagementProductApiTests
python3 -m unittest tests.test_web_management.WebManagementHTTPActionTests
```

Expected result:

```text
OK
```

### Task 4: Add Residue And Boundary Gates

Files:

- Modify `tests/test_repo_consistency.py`

Steps:

1. Extend live-surface scans to enforce that Browser UI does not know config file paths in this interface slice:

```bash
rg -n "model-config\\.json" tools/launcher/assets/web-management
```

Expected: no output.

2. Extend scans to keep execution layers read-only through core:

```bash
rg -n "model-config\\.json" tools/launcher/app_server.py tools/launcher/submit_turn.py tools/launcher/side_thread_lifecycle.py tools/launcher/daemon_core.py tools/launcher/task_sys_runtime.py
```

Expected: no output.

3. Extend scans to prevent persistent side config write paths outside the core:

```bash
rg -n "PersistModelSelection|UpdateModel|config/batchWrite|thread/settings/update" tools/launcher/actor_side_thread.py tools/launcher/side_thread_lifecycle.py tools/launcher/web_management.py
```

Expected: no output except existing test assertions if the scan target includes tests. The repo consistency test must target production files for this gate.

4. Add a gate that Web API uses actor route shape, not instance route shape:

```bash
rg -n "/api/instances/.*/model-config|/api/instances/.*model-config" tools/launcher/web_management.py
```

Expected: no output.

5. Add a temporary interface-slice gate that WebUI assets do not yet expose the model config controls:

```bash
rg -n "model-config|parent-model|side-model|parent-effort|side-effort" tools/launcher/assets/web-management
```

Expected: no output.

6. Run verification:

```bash
python3 -m unittest tests.test_repo_consistency
```

Expected result:

```text
OK
```

### Task 5: Focused End-To-End Acceptance

Files:

- Modify `tests/test_actor_model_config.py`
- Modify `tests/test_web_management.py`
- Modify `tests/test_buddyswitch_launcher.py`
- Modify `tests/test_parent_thread_submit.py` only if existing assertions need the management DTO values.
- Modify `tests/test_actor_side_thread.py` only if existing assertions need the management DTO values.

Acceptance tests:

1. CLI set -> core resolve:

```text
instance model-config act-pm-demo set --payload-json '{"parent":{"model":"gpt-5.4","effort":"high"},"side":{"model":"gpt-5.4-mini","effort":"medium"}}'
actor_model_config.resolve_parent_options(instance_json) -> model "gpt-5.4", effort "high"
actor_model_config.resolve_side_options(instance_json) -> model "gpt-5.4-mini", effort "medium"
```

2. Web PUT -> CLI get:

```text
PUT /api/actors/act-pm-demo/model-config
instance model-config act-pm-demo get --json
```

3. Web PUT -> runtime resolve:

```text
PUT /api/actors/act-pm-demo/model-config
parent_thread_submit sees parent values
actor_side_thread sees side values
```

4. Side non-retroactivity:

```text
existing side-thread send with model config present
  -> no thread/fork
  -> no thread/settings/update
  -> no model metadata in send payload
```

Verification command:

```bash
python3 -m unittest \
  tests.test_actor_model_config \
  tests.test_parent_thread_submit \
  tests.test_actor_side_thread \
  tests.test_web_management \
  tests.test_buddyswitch_launcher \
  tests.test_repo_consistency
```

Expected result:

```text
Python unittest output ends with OK.
```

## Live Surface Residue Scan

Run after implementation:

```bash
rg -n "model-config\\.json" tools/launcher/assets/web-management
rg -n "model-config\\.json" tools/launcher/app_server.py tools/launcher/submit_turn.py tools/launcher/side_thread_lifecycle.py tools/launcher/daemon_core.py tools/launcher/task_sys_runtime.py
rg -n "/api/instances/.*/model-config|/api/instances/.*model-config" tools/launcher/web_management.py
rg -n "model-config|parent-model|side-model|parent-effort|side-effort" tools/launcher/assets/web-management
rg -n "side_thread_lifecycle\\.start_side_thread" tools/launcher/task_sys_runtime.py buddyswitch-codex tools/launcher/env.sh
rg -n "launcher_submit_turn\\.submit_turn" tools/launcher/task_sys_runtime.py tools/launcher/daemon_core.py
```

Expected:

```text
no output
```

## Non-Goals

- No model catalog.
- No provider capability discovery.
- No role policy engine.
- No generic settings framework.
- No feature flag.
- No old/new dual Web route.
- No WebUI card, inputs, save button, or frontend state in this slice.
- No WebUI direct file access.
- No runtime hot-load for active turns.
- No retroactive mutation of existing side threads.
- No `config/batchWrite` or persistent Codex app config write path.

## Key Risks And Controls

### Risk: Web API becomes the product owner

Control:

- Web API only maps HTTP to `actor_model_config.py`.
- Schema validation and write format stay in the core.

### Risk: CLI and Web drift into two semantics

Control:

- Both adapters call the same core functions.
- Acceptance includes Web PUT -> CLI get and CLI set -> Web GET.

### Risk: Null clearing creates a second disk schema

Control:

- Null is request/DTO semantics only.
- Disk stores cleared fields by omission.
- Existing `load_model_config()` continues to accept only current schema.

### Risk: Runtime layers start managing config

Control:

- Keep `parent_thread_submit.py` and `actor_side_thread.py` as runtime application adapters only.
- Keep repo consistency scans over runtime layers.

### Risk: Tests start long-lived services unnecessarily

Control:

- Prefer temp instance records and fake command runners.
- Do not use broad service-starting launcher tests for this slice.
- If a test starts app-server, browser, daemon, or runtime broker, add explicit process cleanup and residual checks before scaling.

## Definition Of Done

The task is done only when:

1. `actor_model_config.py` owns management read and replace semantics.
2. CLI `instance model-config` reads and writes through the core.
3. Web API `GET/PUT /api/actors/{actor_id}/model-config` reads and writes through the core.
4. Actor console projects `model_config` for the future WebUI consumer.
5. Runtime application paths remain unchanged in responsibility and continue consuming core resolve functions.
6. Invalid config replacement does not mutate the existing file.
7. Focused Python tests pass.
8. Live-surface residue scans return no output.
9. No WebUI control implementation is included in this interface slice.
10. No compatibility route, feature flag, duplicate schema, or alternate runtime application path remains.
