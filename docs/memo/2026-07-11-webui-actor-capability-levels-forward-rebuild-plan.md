# WebUI Actor Capability Levels Forward Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace every live actor-level raw model/effort configuration surface with one four-level Parent/Side capability product and a compact matrix editor in Roster Workbench.

**Architecture:** `actor_capability.py` becomes the single product core for the four-level catalog, exact actor-local snapshot schema, validation, persistence, and runtime resolution. CLI, HTTP, WebUI, parent submit, and side creation are projections or consumers of that core; none owns a second catalog or accepts the retired actor model-config payload. The change is a direct replacement with no migration, old route, old file reader, compatibility alias, or dual UI.

**Tech Stack:** Python launcher product core and `unittest`, Bash launcher projection, existing Web management Python HTTP service, vanilla HTML/CSS/JavaScript WebUI, Node `node:test` UI suites, browser smoke at `http://127.0.0.1:8766/`.

---

Date: 2026-07-11
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-webui`
Status: authoritative optimization and implementation plan

## 1. Task Restatement

### Objective

Rebuild actor model defaults as four stable product capability levels shared by Parent and Side:

1. The operator selects one level for Parent and one level for Side.
2. Both roles use the same four-level vocabulary.
3. The main UI shows only level names, concise meaning, selection state, and one Save action.
4. Concrete model and effort values remain inspectable under `Model details`, but are never editable in WebUI.
5. The backend resolves levels through one catalog and persists an exact resolved snapshot.
6. Parent applies its snapshot before the next parent submit.
7. Side applies its snapshot only when a new side thread is created.
8. Every retired actor model-config file, API, CLI, payload editor, validator, state name, and test contract is removed from live surfaces.

The user has confirmed that every old actor is stopped and cleared. This plan therefore performs no data migration and carries no old schema reader.

### End-To-End Contract

```text
operator selects Parent and Side levels in Roster Workbench
  -> one actor-scoped PUT sends only the two level ids
  -> actor_capability validates and atomically stores level + resolved snapshot
  -> next parent submit applies the saved Parent model/effort
  -> next new side thread applies the saved Side model/effort
  -> compact summary and Model details show the canonical saved response
```

This sentence is the definition of the product slice. Layer-local tests do not replace it.

## 2. Confirmed Product Decisions

### Four-Level Catalog

The catalog order, ids, labels, mapping, and primary copy are fixed for catalog version `1`:

| Id | Label | Main UI description | Model | Effort |
| --- | --- | --- | --- | --- |
| `fast` | Fast | Responsive, high-strength reasoning | `gpt-5.6-luna` | `xhigh` |
| `balanced` | Balanced | Strong everyday work | `gpt-5.6-terra` | `high` |
| `deep` | Deep | Complex reasoning and coding | `gpt-5.6-sol` | `xhigh` |
| `maximum` | Maximum | Highest capability and cost | `gpt-5.6-sol` | `max` |

`ultra` is intentionally absent. Its model-catalog semantics include automatic task delegation, which overlaps BuddySwitch's Parent/Side orchestration boundary.

### Defaults

```text
Parent = balanced
Side   = fast
```

These defaults are seeded when a new actor instance is created.

### Interaction

- Use the approved C1 quiet matrix in the right-side Roster Workbench rail.
- Keep the saved summary compact: `Parent Balanced`, `Side Fast`.
- `Configure` expands the matrix in the same card.
- Parent and Side are independent radio groups.
- One `Save config` action persists both selections together.
- `Cancel` discards the draft and collapses the matrix.
- `Model details` is collapsed by default and shows canonical model/effort values from the server response.
- Switching actors discards an unsaved capability draft, collapses the editor, and loads the new actor. A draft must never cross actor ids.
- Save failure leaves the editor open, preserves both draft choices, and exposes one inline error.

### Snapshot Semantics

The actor file stores both the selected level and the resolved model/effort used at save time. Runtime reads the snapshot; it does not dynamically re-resolve against a later catalog. A future catalog change therefore cannot silently change an existing actor.

### No Migration And No Compatibility

- Do not read `model-config.json`.
- Do not accept schema version `1` from the retired actor model-config product.
- Do not add a `legacy`, `custom`, or `existing config` fifth state.
- Do not retain `PUT /api/actors/{id}/model-config` as an alias.
- Do not retain `instance model-config` as an alias.
- Do not retain `--payload-json` for actor capabilities.
- Do not keep the raw textarea hidden behind an advanced disclosure.
- Historical files under `docs/memo` remain evidence and are excluded from live-surface residue scans.

### Key Questions Resolved

| Question | Decision |
| --- | --- |
| Where does the four-level meaning live? | Only in `actor_capability.py`; every interface consumes its catalog and canonical DTO. |
| Does the UI send model or effort? | No. It sends exactly two level ids. |
| Can model and effort still be inspected? | Yes, read-only under collapsed `Model details`. |
| Does a catalog update silently change actors? | No. Runtime uses the saved resolved snapshot. |
| Are old actors or old files migrated? | No. They were cleared; missing new config fails closed. |
| Is raw Side creation still a second path? | No. Optional Side override uses one capability level and the same catalog. |
| When does a saved change apply? | Parent before the next submit; Side on the next newly created side thread. |
| Does the capability UI replace conversation content? | No. It stays in the existing right rail and does not touch the message or Markdown pipeline. |
| How is a cross-actor save prevented? | Draft state is bound to actor id and reset on actor selection change. |
| Is a generic provider/model framework introduced? | No. Catalog version 1 is a concrete built-in product definition. |

## 3. Bitter-Lesson Constraints Applied

### Product Core, Then Projections

The built-in product is the capability catalog plus actor-local capability snapshot. HTTP, CLI, WebUI, and runtime hooks project or consume it. `web_management.py`, `instance.sh`, and `app.js` must not define model mappings.

### Correct Narrow Boundary

The stable shared boundary is a capability level id. Raw model and effort are internal resolved output at the Codex RPC edge. Adding another Web-only level map or preserving a direct raw override would be narrow at the wrong boundary.

### Exact Current Contract

Internal product boundaries allow only `fast`, `balanced`, `deep`, and `maximum`. The implementation constructs the exact current schema. It does not accept loose objects and then blacklist known retired keys.

### Behavior Plus Surface Proof

Completion requires both:

- behavior proof that saved levels drive Parent and new Side runtime calls;
- surface proof that live code and tests no longer teach raw actor model-config semantics.

### Test Resource Lifecycle

Launcher integration tests may start persistent services. Run one focused test first, compare process/socket state to baseline, repeat the focused group, and only then run the broad suite. Assertions passing while background services leak is a failed verification.

## 4. Current-System Audit

### Finding 1: The current product boundary exposes implementation details

`tools/launcher/actor_model_config.py` owns a free-form `model` and `effort` schema. It accepts arbitrary non-empty model strings and a stale hardcoded effort allowlist. The WebUI therefore cannot know whether the backend supports a new model/effort combination until save fails.

### Finding 2: The WebUI is a raw API console

`index.html` exposes `Payload - PUT /api/actors/{actor_id}/model-config` and a textarea. `app.js` validates only that input is a JSON object, deliberately accepts unknown future shapes, and summarizes unrecognized data as `Custom payload`. This is incompatible with a four-level product.

### Finding 3: Product semantics leak across adapters

The retired terminology and payload shape appear in:

- `buddyswitch-codex` helper paths and usage;
- `tools/launcher/instance.sh` command parsing and human output;
- `tools/launcher/web_management.py` route naming and DTO fields;
- WebUI state, functions, DOM ids, styles, and tests;
- parent and side runtime adapters;
- repository consistency tests.

A UI-only rewrite would leave the old product alive underneath.

### Finding 4: Side creation is a second raw selection path

`instance side --model/--effort` and the Web side route accept raw creation-time overrides. They are transient rather than persistent, but they still teach a second model-selection vocabulary. Replace them with optional `--capability <level>` / `{ "capability": "deep" }`, resolved through the same catalog.

### Finding 5: Dirty draft ownership is too weak

`syncActorModelConfigFromConsole()` preserves an open dirty draft without binding it to an actor id. During actor switching this can preserve the previous actor's draft long enough to create target ambiguity. The replacement state must bind saved and draft values to the selected actor and reset on selection change.

### Finding 6: Existing correct features are outside the replacement boundary

The following stay structurally and behaviorally unchanged:

- Markdown renderer, sanitization, highlighting, tables, links, and message bubbles;
- direct conversation loading, scroll behavior, new reply state, Send, and Interrupt;
- actor roster grouping, selected highlight, lifecycle operation queue, Stop, Resume, Delete, Clear, and Start;
- Track list, Track detail, Open TUI, Runtime, Task, and Track summary cards;
- `app_server.thread_settings_update()` and `thread_fork()` as internal Codex RPC adapters.

## 5. Target Architecture

### 5.1 Product Core

Create `tools/launcher/actor_capability.py` as the only owner of:

- catalog order and version;
- level labels and descriptions;
- level-to-model/effort mapping;
- Parent and Side defaults;
- `capability-config.json` exact schema;
- validation and atomic persistence;
- canonical product DTO;
- Parent resolution;
- Side resolution and optional capability-level override;
- runtime source/durability metadata.

It must not import HTTP, DOM, Web management, subprocess runners, or shell adapters.

Public API signatures:

- `capability_config_path(instance_json: Path) -> Path`
- `seed_actor_capabilities(instance_json: Path) -> Path`
- `load_actor_capabilities(instance_json: Path) -> ActorCapabilities`
- `replace_actor_capabilities(instance_json: Path, *, parent_level: str, side_level: str) -> ActorCapabilities`
- `describe_actor_capabilities(config: ActorCapabilities) -> dict[str, Any]`
- `resolve_parent_capability(instance_json: Path) -> ResolvedCapability`
- `resolve_side_capability(instance_json: Path, *, explicit_level: str | None = None) -> ResolvedCapability`
- `apply_side_capability_metadata(payload: Mapping[str, Any], resolved: ResolvedCapability) -> dict[str, Any]`

### 5.2 CLI Projection

Create `tools/launcher/actor_capability_cli.py`. It owns only argparse and JSON output. It calls the product core for:

```text
seed --instance-json <path>
get --instance-json <path>
replace --instance-json <path> --parent <level> --side <level>
```

Human-facing launcher commands become:

```bash
./buddyswitch-codex instance capabilities <actor-id> get
./buddyswitch-codex instance capabilities <actor-id> set --parent balanced --side fast
```

### 5.3 HTTP Projection

The actor-scoped route becomes:

```text
GET /api/actors/{actor_id}/capabilities
PUT /api/actors/{actor_id}/capabilities
```

Exact PUT body:

```json
{
  "parent": "balanced",
  "side": "fast"
}
```

The actor console projection uses `console.capabilities`, not `console.model_config`.

Canonical response shape:

```json
{
  "ok": true,
  "actor_id": "act-dev-example",
  "capabilities": {
    "catalog_version": 1,
    "levels": [
      {
        "id": "fast",
        "label": "Fast",
        "description": "Responsive, high-strength reasoning",
        "model": "gpt-5.6-luna",
        "effort": "xhigh"
      },
      {
        "id": "balanced",
        "label": "Balanced",
        "description": "Strong everyday work",
        "model": "gpt-5.6-terra",
        "effort": "high"
      },
      {
        "id": "deep",
        "label": "Deep",
        "description": "Complex reasoning and coding",
        "model": "gpt-5.6-sol",
        "effort": "xhigh"
      },
      {
        "id": "maximum",
        "label": "Maximum",
        "description": "Highest capability and cost",
        "model": "gpt-5.6-sol",
        "effort": "max"
      }
    ],
    "parent": {
      "level": "balanced",
      "model": "gpt-5.6-terra",
      "effort": "high",
      "effect": "applies_before_next_parent_submit"
    },
    "side": {
      "level": "fast",
      "model": "gpt-5.6-luna",
      "effort": "xhigh",
      "effect": "applies_to_new_side_threads_only"
    }
  }
}
```

### 5.4 Persistence

New actor-local file: `capability-config.json`.

Exact seeded payload:

```json
{
  "schema_version": 1,
  "catalog_version": 1,
  "parent": {
    "level": "balanced",
    "model": "gpt-5.6-terra",
    "effort": "high"
  },
  "side": {
    "level": "fast",
    "model": "gpt-5.6-luna",
    "effort": "xhigh"
  }
}
```

The file is written atomically. Missing, malformed, unknown-key, or wrong-schema files fail closed. There is no implicit Codex default and no old file fallback.

### 5.5 Runtime Consumers

Parent:

```text
resolve_parent_capability()
  -> app_server.thread_settings_update(model, effort)
  -> submit_turn.submit_turn()
```

Side:

```text
resolve_side_capability(explicit_level=None or one level id)
  -> side_thread_lifecycle.start_side_thread(model, model_reasoning_effort)
  -> response includes capability_level, capability_source, capability_durability
```

`side_thread_lifecycle.py` and `app_server.py` may retain internal `model` and `model_reasoning_effort` parameters because those names are required at the Codex RPC boundary. They must not read actor capability files or define the catalog.

### 5.6 WebUI Projection

Saved state:

```javascript
state.actorCapabilityActorId
state.actorCapabilitySaved = { parent: 'balanced', side: 'fast' }
state.actorCapabilityDraft = { parent: 'balanced', side: 'fast' }
state.actorCapabilityCatalog = []
state.actorCapabilityPanelOpen
state.actorCapabilitySaving
state.actorCapabilityStatus
state.actorCapabilityError
```

No JSON text, schema parser, generic payload summary, raw model input, or raw effort input remains.

## 6. File Ownership Map

### Create

- `tools/launcher/actor_capability.py`: product core, catalog, storage, resolution.
- `tools/launcher/actor_capability_cli.py`: argparse/JSON CLI projection.
- `tests/test_actor_capability.py`: product-core behavior and persistence.

### Delete

- `tools/launcher/actor_model_config.py`: retired product and CLI mixture.
- `tests/test_actor_model_config.py`: retired schema tests.

### Modify

- `buddyswitch-codex`: helper path, seed call, usage, Side level override.
- `tools/launcher/env.sh`: pass one Side capability level instead of raw model and effort.
- `tools/launcher/instance.sh`: `capabilities` command and no raw payload parser.
- `tools/launcher/parent_thread_submit.py`: consume Parent capability resolution.
- `tools/launcher/actor_side_thread.py`: consume Side capability resolution and optional level override.
- `tools/launcher/side_thread_lifecycle.py`: keep runtime selection transport while removing retired model-config result metadata.
- `tools/launcher/web_management.py`: capability routes, console projection, Side capability override.
- `tools/launcher/assets/web-management/index.html`: quiet matrix and details disclosure.
- `tools/launcher/assets/web-management/app.js`: typed level draft state and save flow.
- `tools/launcher/assets/web-management/styles.css`: compact matrix styling.
- `tests/test_parent_thread_submit.py`: Parent capability runtime contract.
- `tests/test_actor_side_thread.py`: Side capability runtime contract.
- `tests/test_side_thread_lifecycle.py`: current Side lifecycle result contract without retired model-config metadata.
- `tests/test_task_sys_runtime_executor.py`: capability-backed Parent execution contract.
- `tests/test_buddyswitch_launcher.py`: seed, CLI, Side override, and end-to-end RPC contract.
- `tests/test_web_management.py`: HTTP and console capability projection.
- `tests/web_management_ui_state.test.js`: typed UI state and save behavior.
- `tests/web_management_ui_contract.test.js`: matrix markup and preserved feature contract.
- `tests/test_repo_consistency.py`: current-boundary and residue checks.

### Historical Evidence Only

Existing `docs/memo/*model-config*` files are not runtime surfaces and are not rewritten. This new plan supersedes them for implementation.

## 7. Implementation Strategy

Do not commit an intermediate state where both products are live or where frontend and backend routes disagree. Use TDD inside the worktree, but make the production replacement one atomic vertical-slice commit after focused and end-to-end verification are green.

## 8. Implementation Tasks

### Task 1: Lock The New Product Contract With Failing Core Tests

**Files:**
- Create: `tests/test_actor_capability.py`
- Reference: `tools/launcher/actor_model_config.py`

- [x] **Step 1: Write the exact catalog and default snapshot tests**

```python
def test_catalog_v1_has_exact_order_and_mapping(self) -> None:
    self.assertEqual(
        [
            (row.id, row.label, row.model, row.effort)
            for row in actor_capability.CAPABILITY_LEVELS
        ],
        [
            ("fast", "Fast", "gpt-5.6-luna", "xhigh"),
            ("balanced", "Balanced", "gpt-5.6-terra", "high"),
            ("deep", "Deep", "gpt-5.6-sol", "xhigh"),
            ("maximum", "Maximum", "gpt-5.6-sol", "max"),
        ],
    )

def test_seed_writes_balanced_parent_and_fast_side_snapshot(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root:
        instance_json = self._instance_json(Path(temp_root))
        path = actor_capability.seed_actor_capabilities(instance_json)
        self.assertEqual(
            json.loads(path.read_text(encoding="utf-8")),
            {
                "schema_version": 1,
                "catalog_version": 1,
                "parent": {
                    "level": "balanced",
                    "model": "gpt-5.6-terra",
                    "effort": "high",
                },
                "side": {
                    "level": "fast",
                    "model": "gpt-5.6-luna",
                    "effort": "xhigh",
                },
            },
        )
```

- [x] **Step 2: Write exact replacement, validation, and no-fallback tests**

Required cases:

```text
replace deep/maximum writes one exact snapshot
invalid level fails before disk mutation
unknown top-level or section key fails
missing capability-config.json fails
wrong schema_version fails
retired model-config.json alone is ignored and load still fails
describe_actor_capabilities returns catalog + parent + side + effects
```

- [x] **Step 3: Write exact runtime resolution tests**

```python
def test_parent_and_side_resolve_saved_snapshots(self) -> None:
    parent = actor_capability.resolve_parent_capability(self.instance_json)
    side = actor_capability.resolve_side_capability(self.instance_json)
    self.assertEqual((parent.level, parent.model, parent.effort), ("balanced", "gpt-5.6-terra", "high"))
    self.assertEqual((side.level, side.model, side.effort), ("fast", "gpt-5.6-luna", "xhigh"))

def test_side_explicit_level_uses_same_catalog(self) -> None:
    side = actor_capability.resolve_side_capability(self.instance_json, explicit_level="deep")
    self.assertEqual((side.level, side.model, side.effort, side.source), ("deep", "gpt-5.6-sol", "xhigh", "override"))
```

- [x] **Step 4: Run the new core test and verify red**

Run:

```bash
python3 -m unittest tests.test_actor_capability -v
```

Expected: FAIL because `actor_capability` does not exist.

### Task 2: Replace The Product Core And Runtime Consumers

**Files:**
- Create: `tools/launcher/actor_capability.py`
- Create: `tools/launcher/actor_capability_cli.py`
- Delete: `tools/launcher/actor_model_config.py`
- Modify: `tools/launcher/parent_thread_submit.py`
- Modify: `tools/launcher/actor_side_thread.py`
- Modify: `tests/test_parent_thread_submit.py`
- Modify: `tests/test_actor_side_thread.py`

- [x] **Step 1: Define the catalog and exact product types**

Use these constants and immutable types:

```python
CAPABILITY_CONFIG_FILENAME = "capability-config.json"
SCHEMA_VERSION = 1
CATALOG_VERSION = 1
DEFAULT_PARENT_LEVEL = "balanced"
DEFAULT_SIDE_LEVEL = "fast"

@dataclass(frozen=True)
class CapabilityProfile:
    id: str
    label: str
    description: str
    model: str
    effort: str

CAPABILITY_LEVELS = (
    CapabilityProfile("fast", "Fast", "Responsive, high-strength reasoning", "gpt-5.6-luna", "xhigh"),
    CapabilityProfile("balanced", "Balanced", "Strong everyday work", "gpt-5.6-terra", "high"),
    CapabilityProfile("deep", "Deep", "Complex reasoning and coding", "gpt-5.6-sol", "xhigh"),
    CapabilityProfile("maximum", "Maximum", "Highest capability and cost", "gpt-5.6-sol", "max"),
)

@dataclass(frozen=True)
class CapabilitySnapshot:
    level: str
    model: str
    effort: str

@dataclass(frozen=True)
class ActorCapabilities:
    schema_version: int
    catalog_version: int
    parent: CapabilitySnapshot
    side: CapabilitySnapshot

@dataclass(frozen=True)
class ResolvedCapability:
    level: str
    model: str
    effort: str
    source: str
    catalog_version: int
```

- [x] **Step 2: Implement exact construction, load, replace, and atomic write**

The only accepted replacement inputs are `parent_level` and `side_level`. Build snapshots from the catalog; do not accept model or effort arguments.

Use these exact construction and persistence functions:

```python
_PROFILE_BY_ID = {profile.id: profile for profile in CAPABILITY_LEVELS}
_TOP_LEVEL_KEYS = {"schema_version", "catalog_version", "parent", "side"}
_SNAPSHOT_KEYS = {"level", "model", "effort"}

class ActorCapabilityError(RuntimeError):
    """Raised when actor capabilities cannot be loaded, validated, or saved."""

def capability_config_path(instance_json: Path) -> Path:
    return instance_json.parent / CAPABILITY_CONFIG_FILENAME

def _profile_for_level(level: str, field_name: str) -> CapabilityProfile:
    if not isinstance(level, str) or not level.strip():
        raise ActorCapabilityError(f"{field_name} must be a non-empty string")
    normalized = level.strip()
    profile = _PROFILE_BY_ID.get(normalized)
    if profile is None:
        allowed = ", ".join(profile.id for profile in CAPABILITY_LEVELS)
        raise ActorCapabilityError(f"{field_name} must be one of: {allowed}")
    return profile

def _snapshot_for_level(level: str, field_name: str) -> CapabilitySnapshot:
    profile = _profile_for_level(level, field_name)
    return CapabilitySnapshot(level=profile.id, model=profile.model, effort=profile.effort)

def _disk_payload(config: ActorCapabilities) -> dict[str, Any]:
    def section(snapshot: CapabilitySnapshot) -> dict[str, str]:
        return {"level": snapshot.level, "model": snapshot.model, "effort": snapshot.effort}

    return {
        "schema_version": config.schema_version,
        "catalog_version": config.catalog_version,
        "parent": section(config.parent),
        "side": section(config.side),
    }

def _config_for_levels(parent_level: str, side_level: str) -> ActorCapabilities:
    return ActorCapabilities(
        schema_version=SCHEMA_VERSION,
        catalog_version=CATALOG_VERSION,
        parent=_snapshot_for_level(parent_level, "parent"),
        side=_snapshot_for_level(side_level, "side"),
    )

def seed_actor_capabilities(instance_json: Path) -> Path:
    path = capability_config_path(instance_json)
    if path.exists():
        return path
    config = _config_for_levels(DEFAULT_PARENT_LEVEL, DEFAULT_SIDE_LEVEL)
    _atomic_write_json(path, _disk_payload(config))
    return path

def _load_snapshot(path: Path, value: Any, section_name: str) -> CapabilitySnapshot:
    if not isinstance(value, dict):
        raise ActorCapabilityError(f"{path}: {section_name} must be an object")
    if set(value) != _SNAPSHOT_KEYS:
        raise ActorCapabilityError(f"{path}: {section_name} must contain exactly: effort, level, model")
    level = value.get("level")
    model = value.get("model")
    effort = value.get("effort")
    _profile_for_level(level, f"{section_name}.level")
    if not isinstance(model, str) or not model.strip():
        raise ActorCapabilityError(f"{path}: {section_name}.model must be a non-empty string")
    if not isinstance(effort, str) or not effort.strip():
        raise ActorCapabilityError(f"{path}: {section_name}.effort must be a non-empty string")
    return CapabilitySnapshot(level=level.strip(), model=model.strip(), effort=effort.strip())

def load_actor_capabilities(instance_json: Path) -> ActorCapabilities:
    path = capability_config_path(instance_json)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ActorCapabilityError(f"{path}: capability config is missing") from exc
    except json.JSONDecodeError as exc:
        raise ActorCapabilityError(f"{path}: invalid JSON: {exc}") from exc
    except OSError as exc:
        raise ActorCapabilityError(f"{path}: failed to read capability config: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != _TOP_LEVEL_KEYS:
        raise ActorCapabilityError(f"{path}: capability config has an invalid shape")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ActorCapabilityError(f"{path}: schema_version must be {SCHEMA_VERSION}")
    catalog_version = payload.get("catalog_version")
    if type(catalog_version) is not int or catalog_version < 1:
        raise ActorCapabilityError(f"{path}: catalog_version must be a positive integer")
    return ActorCapabilities(
        schema_version=SCHEMA_VERSION,
        catalog_version=catalog_version,
        parent=_load_snapshot(path, payload.get("parent"), "parent"),
        side=_load_snapshot(path, payload.get("side"), "side"),
    )

def replace_actor_capabilities(
    instance_json: Path,
    *,
    parent_level: str,
    side_level: str,
) -> ActorCapabilities:
    config = _config_for_levels(parent_level, side_level)
    _atomic_write_json(capability_config_path(instance_json), _disk_payload(config))
    return config
```

Retain the proven temporary-file, `fsync`, and `os.replace` atomic-write sequence from the retired core, renamed to raise `ActorCapabilityError` and to use `CAPABILITY_CONFIG_FILENAME`.

- [x] **Step 3: Implement the canonical product description**

`describe_actor_capabilities()` returns catalog rows and both saved sections. `effects` are added per section as specified in Section 5.3.

```python
def describe_actor_capabilities(config: ActorCapabilities) -> dict[str, Any]:
    def catalog_row(profile: CapabilityProfile) -> dict[str, str]:
        return {
            "id": profile.id,
            "label": profile.label,
            "description": profile.description,
            "model": profile.model,
            "effort": profile.effort,
        }

    def selection(snapshot: CapabilitySnapshot, effect: str) -> dict[str, str]:
        return {
            "level": snapshot.level,
            "model": snapshot.model,
            "effort": snapshot.effort,
            "effect": effect,
        }

    return {
        "catalog_version": config.catalog_version,
        "levels": [catalog_row(profile) for profile in CAPABILITY_LEVELS],
        "parent": selection(config.parent, "applies_before_next_parent_submit"),
        "side": selection(config.side, "applies_to_new_side_threads_only"),
    }

def resolve_parent_capability(instance_json: Path) -> ResolvedCapability:
    config = load_actor_capabilities(instance_json)
    return ResolvedCapability(
        level=config.parent.level,
        model=config.parent.model,
        effort=config.parent.effort,
        source="actor_config",
        catalog_version=config.catalog_version,
    )

def resolve_side_capability(
    instance_json: Path,
    *,
    explicit_level: str | None = None,
) -> ResolvedCapability:
    config = load_actor_capabilities(instance_json)
    if explicit_level is None:
        snapshot = config.side
        source = "actor_config"
        catalog_version = config.catalog_version
    else:
        snapshot = _snapshot_for_level(explicit_level, "explicit_level")
        source = "override"
        catalog_version = CATALOG_VERSION
    return ResolvedCapability(
        level=snapshot.level,
        model=snapshot.model,
        effort=snapshot.effort,
        source=source,
        catalog_version=catalog_version,
    )

def apply_side_capability_metadata(
    payload: Mapping[str, Any],
    resolved: ResolvedCapability,
) -> dict[str, Any]:
    result = dict(payload)
    result["model"] = resolved.model
    result["model_reasoning_effort"] = resolved.effort
    result["capability_level"] = resolved.level
    result["capability_source"] = resolved.source
    result["capability_durability"] = "thread_fork_only"
    return result
```

- [x] **Step 4: Implement the CLI adapter**

`actor_capability_cli.py` imports the core and exposes only `seed`, `get`, and `replace`. `replace` requires `--parent` and `--side`; it has no JSON payload argument.

- [x] **Step 5: Rewire Parent submit**

Replace the old import and resolve call with:

```python
import actor_capability

try:
    resolved = actor_capability.resolve_parent_capability(instance_json)
except actor_capability.ActorCapabilityError as exc:
    raise ParentThreadSubmitError(f"parent capability invalid: {exc}") from exc

app_server.thread_settings_update(
    socket_path,
    thread_id,
    model=resolved.model,
    effort=resolved.effort,
)
```

There is no empty/default branch because every current actor has one exact seeded snapshot.

- [x] **Step 6: Rewire Side creation**

Change `start_actor_side_thread()` to accept `capability_level: str | None = None`. Resolve it through `resolve_side_capability()` and pass only the resolved model/effort to `side_thread_lifecycle.start_side_thread()`.

```python
resolved = actor_capability.resolve_side_capability(
    instance_json,
    explicit_level=capability_level,
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
    model=resolved.model,
    model_reasoning_effort=resolved.effort,
)
return actor_capability.apply_side_capability_metadata(payload, resolved)
```

- [x] **Step 7: Replace runtime tests**

Parent tests prove Balanced resolves to Terra/high before submit. Side tests prove saved Fast resolves to Luna/xhigh and explicit Deep resolves to Sol/xhigh. Missing files fail before any RPC call.

- [x] **Step 8: Delete the retired core and run focused tests**

Run:

```bash
python3 -m unittest \
  tests.test_actor_capability \
  tests.test_parent_thread_submit \
  tests.test_actor_side_thread \
  -v
```

Expected: PASS; no test imports `actor_model_config`.

### Task 3: Replace Launcher Seeding, CLI, And Side Override Vocabulary

**Files:**
- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/instance.sh`
- Modify: `tests/test_buddyswitch_launcher.py`

- [x] **Step 1: Write failing launcher tests for the new command**

Required command contracts:

```bash
./buddyswitch-codex instance capabilities act-pm-demo get --json
./buddyswitch-codex instance capabilities act-pm-demo set --parent deep --side maximum --json
./buddyswitch-codex instance side act-pm-demo --text "Explore" --capability deep --json
```

Tests assert the new file payload, public DTO, and `thread/fork` RPC model/effort.

- [x] **Step 2: Replace helper wiring and creation seed**

Rename `MODEL_CONFIG_HELPER` to `ACTOR_CAPABILITY_CLI_HELPER`, point it to `actor_capability_cli.py`, and seed `capability-config.json` immediately after actor activation.

- [x] **Step 3: Replace instance command parsing**

`instance capabilities set` accepts exactly:

```text
--parent <fast|balanced|deep|maximum>
--side <fast|balanced|deep|maximum>
--json
```

The core validates values. Shell parses presence only.

- [x] **Step 4: Replace transient Side override**

Remove `--model` and `--effort` from public Side parsing. Add one optional `--capability`. Existing side-thread continuation rejects `--capability` because it applies only to creation.

- [x] **Step 5: Update human output**

Human `capabilities get` prints actor id, Parent level, Side level, and resolved details. It does not print or request a JSON payload.

- [x] **Step 6: Run focused launcher tests**

Run individual methods first, then the focused class group. Expected: creation writes the new file; get/set round-trip; invalid level leaves the file unchanged; Side Deep forks Sol/xhigh.

### Task 4: Replace The Web API And Actor Console Projection

**Files:**
- Modify: `tools/launcher/web_management.py`
- Modify: `tests/test_web_management.py`

- [x] **Step 1: Write failing product API tests**

Add tests for:

```text
GET /api/actors/{id}/capabilities returns canonical DTO
PUT exact level body rewrites the snapshot and runtime sees it
PUT unknown field returns 400 and preserves disk
PUT invalid level returns 400 and preserves disk
GET missing/malformed capability file returns 409
write failure returns 502 CAPABILITY_CONFIG_WRITE_FAILED
actor console exposes capabilities and no model_config field
```

- [x] **Step 2: Replace route parsing and handlers**

Use `_parse_actor_capabilities_path()`, `_read_actor_capabilities()`, and `_replace_actor_capabilities()`. The route is actor scoped and delegates every product decision to `actor_capability`.

- [x] **Step 3: Make PUT shape exact**

Reject any top-level key outside `parent` and `side`; require both values to be strings. Pass both level ids to the core in one call.

- [x] **Step 4: Replace console projection**

Return:

```python
"capabilities": self._read_actor_capabilities(actor_id)["capabilities"]
```

Do not expose `model_config` beside it.

- [x] **Step 5: Replace Side Web override**

The new-side body accepts optional `capability`; it rejects `model` and `effort` as unknown fields. Existing-side continuation rejects `capability` before command execution.

- [x] **Step 6: Run Web API tests**

Run:

```bash
python3 -m unittest tests.test_web_management.WebManagementProductApiTests -v
python3 -m unittest tests.test_web_management.WebManagementHTTPActionTests -v
```

Expected: PASS with only the capability route and level-based Side override.

### Task 5: Replace WebUI State With Typed Capability Drafts

**Files:**
- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tests/web_management_ui_state.test.js`

- [x] **Step 1: Replace old UI tests with failing level-state tests**

Required behavior tests:

```text
console capabilities initialize saved and draft levels
opening the editor preserves the selected actor id
changing one radio marks the card Unsaved
Cancel restores both saved levels and closes
Save PUTs {parent, side} to /capabilities
successful save uses the canonical response and closes
failed save preserves the draft and remains open
actor switch discards prior draft and binds new actor capabilities
model details render canonical model and effort read-only
```

- [x] **Step 2: Replace state fields**

Remove every `actorModelConfig*` state field. Add the exact `actorCapability*` fields listed in Section 5.6.

- [x] **Step 3: Add pure typed helpers**

Implement and export:

```javascript
function buildActorCapabilitiesUrl(actorId) {
  return '/api/actors/' + encodeURIComponent(actorId) + '/capabilities';
}

function capabilitySelectionFromConsole(actorConsole) {
  const capabilities = actorConsole && actorConsole.capabilities;
  return {
    parent: capabilities && capabilities.parent ? capabilities.parent.level : '',
    side: capabilities && capabilities.side ? capabilities.side.level : '',
  };
}

function sameCapabilitySelection(left, right) {
  return Boolean(left && right && left.parent === right.parent && left.side === right.side);
}
```

Add focused helpers for sync, select, cancel, save, summary, and details rendering. No JSON parser participates in capability editing.

- [x] **Step 4: Bind draft ownership to actor id**

When `selectedActorId` changes, reset panel, saved/draft values, status, and error before applying the new console response. A stale response must still obey the existing request-id/AbortController guard.

- [x] **Step 5: Implement one PUT save path**

The request body is always:

```javascript
JSON.stringify({
  parent: state.actorCapabilityDraft.parent,
  side: state.actorCapabilityDraft.side,
})
```

On success, replace `state.actorConsole.capabilities` with the canonical response and collapse. On failure, retain the draft.

- [x] **Step 6: Run UI state tests**

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected: PASS, including existing Markdown message tests.

### Task 6: Replace The Payload Card With The Approved Quiet Matrix

**Files:**
- Modify: `tools/launcher/assets/web-management/index.html`
- Modify: `tools/launcher/assets/web-management/styles.css`
- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tests/web_management_ui_contract.test.js`

- [x] **Step 1: Write the failing DOM contract**

Require:

```text
actor-capability-card
actor-capability-toggle
actor-capability-status
actor-capability-parent-summary
actor-capability-side-summary
actor-capability-panel
actor-capability-matrix
actor-capability-details
actor-capability-cancel
actor-capability-save
```

Forbid raw payload textarea ids and raw model/effort form controls.

- [x] **Step 2: Replace the right-rail card markup**

Use one `fieldset` per Parent/Side radio group or an equivalently accessible matrix with labels that associate each radio to both role and level. Keep summary rows and the existing `next`/`new` effect tags.

- [x] **Step 3: Add collapsed model details**

Use native `<details>` and `<summary>Model details</summary>`. Render model and effort as read-only text. Do not place the details content in a second card.

- [x] **Step 4: Add compact matrix styling**

Use the approved quiet treatment:

- one border around the card;
- row separators, not nested cards;
- fixed role columns;
- 16px radio targets with larger clickable cells;
- pale green only in selected cells;
- 7px or smaller radii;
- stable dimensions at desktop and narrow widths;
- no gradients, decorative blobs, or marketing copy.

- [x] **Step 5: Preserve the rest of Roster Workbench**

Do not move or rename message, Markdown, lifecycle, Track, Runtime, Task, or Open TUI elements. The capability card remains between Selected teammate and Runtime.

- [x] **Step 6: Run static and contract checks**

Run:

```bash
node --check tools/launcher/assets/web-management/app.js
node tests/web_management_ui_contract.test.js
```

Expected: PASS with no payload editor contract.

### Task 7: Enforce One Vocabulary And Remove Live Residue

**Files:**
- Modify: `tests/test_repo_consistency.py`
- Scan: all production and current tests listed in Section 6

- [x] **Step 1: Replace consistency tests with current-boundary rules**

Add narrow live-surface scans that fail on:

```text
actor_model_config
model-config.json
/model-config
instance model-config
actorModelConfig
actor-model-config
allowed_efforts
VALID_EFFORTS
--payload-json in the capabilities command
--model or --effort in public instance side parsing
```

Do not scan historical `docs/memo` files.

- [x] **Step 2: Prove adapters do not duplicate the catalog**

Scan `web_management.py`, `instance.sh`, `buddyswitch-codex`, and WebUI assets for the four concrete model slugs and effort mapping. Expected: no hits outside `actor_capability.py` and tests that verify the core.

- [x] **Step 3: Prove internal RPC layers do not read storage**

`app_server.py`, `submit_turn.py`, `side_thread_lifecycle.py`, daemon code, and task runtime must not mention `capability-config.json` or call load/replace product functions.

- [x] **Step 4: Run exact scans**

```bash
rg -n "actor_model_config|model-config\\.json|/model-config|instance model-config|actorModelConfig|actor-model-config|allowed_efforts|VALID_EFFORTS" \
  buddyswitch-codex \
  tools/launcher \
  tests/test_actor_capability.py \
  tests/test_parent_thread_submit.py \
  tests/test_actor_side_thread.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_web_management.py \
  tests/web_management_ui_state.test.js \
  tests/web_management_ui_contract.test.js \
  tests/test_repo_consistency.py
```

Expected: no hits except string fragments intentionally split inside negative scan tests.

- [x] **Step 5: Run repository consistency tests**

```bash
python3 -m unittest tests.test_repo_consistency -v
```

Expected: PASS.

### Task 8: Verify The Full User Loop And Preserve Existing Features

**Files:**
- Verify all files in Section 6

- [x] **Step 1: Capture process baseline**

```bash
ps -axo pid,command | rg "buddyswitch|app-server|runtime_broker|fake_codex" || true
```

Save the output for comparison after service-starting tests.

- [x] **Step 2: Run focused backend suites**

```bash
python3 -m unittest \
  tests.test_actor_capability \
  tests.test_parent_thread_submit \
  tests.test_actor_side_thread \
  -v
```

- [x] **Step 3: Run launcher and Web management suites**

```bash
python3 -m unittest tests.test_buddyswitch_launcher -v
python3 -m unittest tests.test_web_management -v
```

- [x] **Step 4: Recheck process and socket residue**

Compare the same `ps` filter and inspect temporary runtime sockets. No test-owned process or socket may remain.

- [x] **Step 5: Run frontend and consistency suites**

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
python3 -m unittest tests.test_repo_consistency -v
```

- [x] **Step 6: Run the broad Python suite after lifecycle proof and record baseline exceptions**

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Acceptance for this scoped rebuild: all task-owned and directly affected suites pass, host resources return to baseline, and unrelated repository failures are recorded rather than repaired or hidden in this change. The broad run exposed six existing non-green modules whose failing boundaries are outside this capability rebuild; see the execution record below.

- [x] **Step 7: Start the live product from this worktree**

```bash
./buddyswitch-codex web --port 8766
```

Confirm the process command and static assets resolve from `/Users/chen/Dev/buddyswitch/.worktrees/fea-webui` before trusting the browser result.

- [x] **Step 8: Run one real browser acceptance flow**

```text
Start one actor
select it in Active
open Capability level
set Parent Deep and Side Maximum
confirm Unsaved state and one Save action
save and confirm compact summary
open Model details and confirm Sol/xhigh plus Sol/max
send one Parent message and verify thread/settings/update used Sol/xhigh
start one new Side thread and verify thread/fork used Sol/max
switch actors while a draft is dirty and confirm the draft does not follow
render a Markdown reply with list, quote, code fence, table, link, and inline code
Stop and Delete remain bound to the selected actor
```

- [x] **Step 9: Check live API and persisted state**

```bash
curl --noproxy '*' -fsS http://127.0.0.1:8766/api/actors/<actor-id>/capabilities
```

Inspect the actor's `capability-config.json` through the owning launcher/test path. The API, file snapshot, Parent RPC, and Side RPC must agree.

- [x] **Step 10: Commit the atomic replacement**

```bash
git add \
  buddyswitch-codex \
  tools/launcher \
  tests \
  docs/memo/2026-07-11-webui-actor-capability-levels-forward-rebuild-plan.md
git commit -m "Rebuild actor model defaults as capability levels"
```

Do not commit `.superpowers/` prototype session state.

## 9. Acceptance Matrix

| Requirement | Owning proof |
| --- | --- |
| Exactly four levels and approved mappings | `tests/test_actor_capability.py` catalog test |
| Parent Balanced and Side Fast creation defaults | core seed test + launcher start integration test |
| One product core owns catalog and persistence | consistency import/catalog scans |
| No old actor migration or fallback | missing-file and retired-file negative tests |
| Snapshot does not silently re-resolve | persistence/resolution tests read stored model/effort |
| Parent applies before next submit | Parent unit test + launcher RPC integration |
| Side applies only to new side threads | Side unit test + launcher/Web route tests |
| Side override uses capability vocabulary | CLI and Web Side tests |
| WebUI has quiet matrix and one Save | DOM contract + UI state tests + browser smoke |
| Model details are hidden and read-only | DOM contract + UI render test + browser smoke |
| Draft cannot cross actors | UI state regression test + browser smoke |
| Save failure preserves draft | UI state test |
| Markdown and direct conversation remain intact | existing UI Markdown state/contract tests + browser smoke |
| Lifecycle roster/actions remain intact | existing lifecycle tests + browser smoke |
| No retired live semantics | exact `rg` scan + repo consistency tests |
| No service leakage from verification | before/after process and socket baseline |

## 10. Explicit Non-Goals

- Dynamic provider discovery from `~/.codex/models_cache.json`.
- A generic model registry or provider plugin system.
- Automatic upgrade of saved actors when a future catalog changes.
- An advanced/custom raw model mode.
- Old actor migration, import, or compatibility aliases.
- Changes to Codex app-server RPC names or payload requirements.
- Redesign of Markdown, direct conversation, lifecycle queue, Tracks, Runtime, Task, or Open TUI.
- Broad splitting or bundling of the existing `app.js` outside the capability slice.

## 11. Risks And Controls

### Risk: Fast with xhigh may be read as lowest latency

Control: copy says `Responsive, high-strength reasoning`, not `lowest latency`. The hidden details show Luna/xhigh exactly.

### Risk: Snapshot and catalog can diverge after a future code release

Control: runtime intentionally trusts the saved snapshot. Catalog upgrades require a separate explicit product decision; no silent resolution is allowed.

### Risk: Right rail becomes too tall

Control: saved state remains compact; the matrix exists only while Configure is open. Runtime and Task remain below it and return immediately after Save/Cancel.

### Risk: Large WebUI state file invites unrelated changes

Control: modify only capability-specific state/helpers/render/bindings and keep the existing pure helper test pattern. Do not reformat or reorganize unrelated code.

### Risk: The backend and frontend cutover temporarily disagree

Control: no intermediate production commit. Complete and verify the vertical slice before the atomic commit.

## 12. Definition Of Done

The task is complete only when all statements are true:

1. New actors seed only `capability-config.json` with Parent Balanced and Side Fast snapshots.
2. The approved four mappings exist in exactly one production catalog.
3. WebUI and CLI accept only capability levels for actor configuration.
4. New Side overrides, when used, accept one capability level rather than raw model/effort.
5. Parent and new Side runtime calls use the saved or explicitly selected resolved snapshot.
6. The quiet matrix is integrated into Roster Workbench and model details are collapsed/read-only.
7. Actor switching, failures, and save state cannot target the wrong actor.
8. Markdown, direct conversation, lifecycle, roster, and Track tests remain green.
9. Narrow live-surface scans find no retired actor model-config semantics.
10. Focused, browser, persisted-state, and process-lifecycle verification pass; broad-suite baseline exceptions are explicit and were not introduced or masked by this change.

## 13. Execution Record

Implemented and reviewed on 2026-07-11 in `/Users/chen/Dev/buddyswitch/.worktrees/fea-webui`.

- The capability core, CLI, launcher seeding, Parent/Side runtime consumers, Web API, console projection, and typed Roster Workbench matrix are one forward-only path.
- The retired core, file reader, route, CLI vocabulary, raw textarea state, Side metadata vocabulary, and compatibility aliases are removed.
- Focused capability/runtime tests, 8 launcher capability scenarios, all 81 Web management tests, both frontend suites, and all 58 repository consistency tests pass.
- Two independent final read-only reviews approved the implementation with no remaining Critical or Important findings.
- Live `http://127.0.0.1:8766/` acceptance covered Start feedback, Active selection, Deep/Maximum save, saved-vs-draft summary, read-only details, dirty actor switching, full Markdown rendering, Stop progression, Stopped grouping, and exact-target Delete confirmation.
- The live API and `capability-config.json` agreed on Deep = `gpt-5.6-sol` / `xhigh` and Maximum = `gpt-5.6-sol` / `max`; the real Parent session recorded `thread_settings_applied` with Sol/xhigh and the real Side start returned Sol/max.
- Browser-created smoke actors were stopped and deleted after verification. The final 8766 process is owned by this worktree and the roster is clean.

Repository-wide note: the single-process `unittest discover` run is not a usable green gate in this checkout because existing unrelated tests leak product-mode environment across modules. An isolated 91-module run passed 85 modules; the six non-green modules are outside this diff (`test_black_box_tool_runtime`, `test_browser_cockpit_proxy`, `test_buddyswitch_launcher` service-test hang, `test_im_delivery` standalone import path, `test_runtime_skills`, and `test_task_sys_checkpoint`). The changed product boundary and all directly affected suites are green; no unrelated production or test files were changed to mask those baseline failures.
