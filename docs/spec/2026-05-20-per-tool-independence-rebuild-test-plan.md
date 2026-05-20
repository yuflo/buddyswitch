# Per-Tool Independence Rebuild Test Plan

Date: 2026-05-20

Scope document: `docs/spec/2026-05-20-per-tool-independence-rebuild-scope.md`

## Goal

Prove env.tool per-tool independent development from externally meaningful behavior and architecture boundaries: a tool owns its contract, semantics, CLI, handler mapping, and service entrypoint; shared runtime modules only discover, project, route, and format responses.

## Test Design Rules

- Tests must start from product and architecture requirements, not from private code shortcuts.
- Tests must not assert a mock-only path that would allow broken runtime behavior to pass.
- Positive tests must verify broker/router/CLI behavior and relevant persisted state when state is expected to change.
- Negative tests must verify structured feedback, `state_changed=False`, and no unintended mutation.
- Boundary tests may inspect imports and AST because "no central per-tool ownership" and "no sibling tool imports" are required architecture constraints.
- Tests may create a temporary local probe tool package to prove package discovery, but the probe must exercise the same public catalog/router/CLI discovery path as shipped tools.
- Do not use docs text as proof of runtime behavior.
- Do not keep old tests green by adding compatibility aliases. Update tests to the new runtime API.

## Functional Requirement Model

R1. Shipped tool set is unchanged: task, track, artifact, buddybox, context, evidence, message, comment, and search remain supported.

R2. Each shipped tool owns its contract, semantics, CLI registration, handler specs, and service entrypoint under `scripts/env/tools/<tool>/`.

R3. Shared env.tool infrastructure contains no hand-written per-tool action lists, payload field lists, handler maps, semantic rows, or CLI dispatch branches.

R4. Runtime catalog and operation semantics are generated from per-tool packages and preserve the existing externally visible catalog shape.

R5. Public imports are service-light: importing catalog, router, dispatch, and client does not import any `scripts/env/tools/<tool>/service.py`.

R6. Dispatch is selected-tool only: dispatching one tool imports that tool's service and no sibling tool services.

R7. A broken non-selected tool service does not block healthy selected tool dispatch.

R8. A broken selected tool service returns structured `E_ENV_TOOL_DISPATCH` feedback and does not mutate state.

R9. Catalog generation is resilient to broken non-selected tool metadata: context/catalog discovery reports metadata load errors without crashing unrelated dispatch.

R10. CLI subcommands are registered by tool packages, and CLI operation/action mapping remains aligned with the per-tool contract.

R11. Adding a local probe tool package with contract, semantics, CLI, handler, and service is discovered without editing a central action, semantics, dispatch, or CLI map.

R12. Tool packages do not import sibling tool packages. Shared cross-object behavior lives only in explicit domain modules.

R13. Existing behavior for every shipped env.tool action remains green after ownership moves.

R14. Old central ownership modules and tool service entrypoint modules are removed; no compatibility shims remain.

R15. Runtime skills continue to discover exact action and payload knowledge from `context.get.tool_catalog`.

## Test Matrix

| ID | Requirement | File | Scenario | Main assertions |
| --- | --- | --- | --- | --- |
| PT1 | R1/R2 | `tests/test_env_tool_package_independence.py` | Shipped tool packages exist | every shipped tool has `contract.py`, `semantics.py`, `cli.py`, `handlers.py`, `service.py` |
| PT2 | R2/R3/R14 | `tests/test_env_tool_package_independence.py` | No central ownership remains | no `TOOL_REGISTRY`, `_CAPABILITIES`, `HANDLER_SPECS_BY_TOOL`, `_dispatch_<tool>` branches, or `env.services.<tool>` modules |
| PT3 | R12 | `tests/test_env_tool_package_independence.py` | Tool package import boundaries | no `env.tools.<other_tool>` imports inside a tool package |
| PT4 | R5 | `tests/test_env_tool_package_independence.py` | Public imports are service-light | importing `env.tools.catalog`, `env.tools.router`, `env.tools.dispatch`, and `env.client` loads no `env.tools.*.service` modules |
| PT5 | R5/R6 | `tests/test_env_tool_package_independence.py` | Catalog imports are service-light | building catalog/operation semantics loads contract and semantics modules but no service modules |
| PT6 | R11 | `tests/test_env_tool_package_independence.py` | Local probe tool discovery | a temporary local tool package appears in catalog and can dispatch without central source edits |
| CAT1 | R1/R4 | `tests/test_env_tool_semantic_contract.py` | Catalog preserves shipped tools/actions | generated catalog has same shipped tool/action set and payload fields |
| CAT2 | R4 | `tests/test_env_tool_payload_contract.py` | Payload fields are per-tool source of truth | every action rejects unregistered fields; helper output equals per-tool contract |
| CAT3 | R9 | `tests/test_env_tool_package_independence.py` | Broken non-selected metadata is reported | catalog includes `tool_catalog_errors` or equivalent diagnostics and healthy tool dispatch remains available |
| ROUTE1 | R6/R7 | `tests/test_env_tool_router.py` | Block message service, dispatch `task.list` | response `ok=true`; no message service import required |
| ROUTE2 | R8 | `tests/test_env_tool_router.py` | Block selected message service, dispatch `message.list` | response `ok=false`, `E_ENV_TOOL_DISPATCH`, `state_changed=false` |
| ROUTE3 | R6 | `tests/test_env_tool_router.py` | Selected dispatch loads only selected service | subprocess records service modules imported for each selected tool |
| CLI1 | R10 | `tests/test_env_client_payload_cli.py` | Tool package CLI registers all operations | help output and broker payload mapping match generated contract |
| CLI2 | R10 | `tests/test_env_tool_router.py` | CLI operations align with catalog | operation names from help equal per-tool contract action names after dash/underscore normalization |
| BOUND1 | R12 | `tests/test_env_layer_boundaries.py` | Product couplings stay in domain modules | only allowlisted domain modules perform track/artifact/comment cross-object behavior |
| BOUND2 | R14 | `tests/test_env_layer_boundaries.py` | Old service package is gone | no runtime or tests import `env.services.*`; `scripts/env/services` contains no tool service entrypoints |
| REG1 | R13 | Existing focused suites | Existing env.tool behavior | task, track, artifact, buddybox, context, evidence, message, comment, search tests pass |
| REG2 | R15 | Existing consistency suites | Runtime skills/catalog consistency | runtime skills route exact fields to `context.get.tool_catalog` and do not copy schemas |
| REG3 | R13/R14 | Full suite | Complete regression | `python3 -m pytest -q` and `git diff --check` pass |

## Detailed Test Designs

### PT1: Shipped Tool Packages Exist

Create `tests/test_env_tool_package_independence.py`.

The test defines the shipped tool ids from product requirements:

```python
SHIPPED_TOOLS = {
    "task",
    "track",
    "artifact",
    "buddybox",
    "context",
    "evidence",
    "message",
    "comment",
    "search",
}
REQUIRED_TOOL_FILES = {"__init__.py", "contract.py", "semantics.py", "cli.py", "handlers.py", "service.py"}
```

Assertions:

- `scripts/env/tools/<tool>/` exists for every shipped tool.
- each package contains every required file;
- no required file is empty;
- no extra shipped tool exists outside the discovered tool catalog.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_package_independence.py::EnvToolPackageIndependenceTests::test_shipped_tool_packages_own_required_files -q
```

Expected before implementation: fail because tool packages do not exist yet.

### PT2: Central Ownership Is Removed

Test through source structure because the requirement is architectural ownership.

Assertions:

- `scripts/env/tools/contracts.py` does not exist.
- `scripts/env/tools/semantics.py` does not exist.
- `scripts/env/tools/dispatch.py` does not contain `HANDLER_SPECS_BY_TOOL`.
- `scripts/env/client.py` does not contain `_dispatch_task`, `_dispatch_track`, `_dispatch_artifact`, `_dispatch_context`, `_dispatch_buddybox`, `_dispatch_evidence`, `_dispatch_search`, `_dispatch_message`, or `_dispatch_comment`.
- no Python file under `scripts/env/tools/` defines `TOOL_REGISTRY` outside a per-tool package.
- no Python file under `scripts/env/tools/` defines `_CAPABILITIES` outside a per-tool package.
- no Python file under `scripts/env/tools/` contains handler strings for sibling tools.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_package_independence.py::EnvToolPackageIndependenceTests::test_no_central_tool_ownership_tables_remain -q
```

Expected before implementation: fail on current central files.

### PT3: Tool Packages Do Not Import Sibling Tool Packages

Parse AST for every Python file under `scripts/env/tools/<tool>/`.

Forbidden examples inside `scripts/env/tools/task/**`:

- `from env.tools.track import ...`
- `import env.tools.track.service`
- `from env.tools import track`

Allowed examples:

- `from env.tools import responses`
- `from env.tools import catalog`
- `from env.tools.model import MUTATES_NONE`
- `from env.domain import publication`
- `from env.repos import tasks`

Focused command:

```bash
python3 -m pytest tests/test_env_tool_package_independence.py::EnvToolPackageIndependenceTests::test_tool_packages_do_not_import_sibling_tool_packages -q
```

Expected before implementation: fail until package layout exists and imports are clean.

### PT4: Public Imports Are Service-Light

Run a clean subprocess:

```python
script = """
import json
import sys
from pathlib import Path
root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))
import env.client
import env.tools.catalog
import env.tools.dispatch
import env.tools.router
loaded = sorted(name for name in sys.modules if name.startswith("env.tools.") and name.endswith(".service"))
print(json.dumps(loaded))
"""
```

Assertions:

- subprocess exits 0;
- loaded service module list is `[]`.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_package_independence.py::EnvToolPackageIndependenceTests::test_public_imports_do_not_load_tool_services -q
```

Expected before implementation: fail because current modules are not in the target shape.

### PT5: Catalog Projection Is Service-Light

Run a clean subprocess that imports `env.tools.catalog`, calls:

- `supported_tools()`
- `supported_actions(tool)` for every shipped tool
- `env_tools_description()`
- `operation_semantics()`
- `compact_tool_affordances()`

Assertions:

- all calls succeed;
- returned tool/action set equals shipped requirements;
- no loaded module ends with `.service`;
- no loaded module starts with `env.repos.` or `env.domain.`.

This proves catalog generation uses per-tool contract/semantics only, not runtime state or service code.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_package_independence.py::EnvToolPackageIndependenceTests::test_catalog_projection_does_not_load_services_repos_or_domains -q
```

### PT6: Local Probe Tool Discovery Without Central Edits

Create a temporary package directory in the test workspace:

```text
<tmp>/env_tools_probe/probe/
  __init__.py
  contract.py
  semantics.py
  cli.py
  handlers.py
  service.py
```

The probe package exposes one action:

- tool: `probe`
- action: `ping`
- payload fields: `["message"]`
- handler returns `{"ok": True, "tool": "probe", "action": "probe.ping", "echo": <message>}`

The test extends `env.tools.__path__` with `<tmp>/env_tools_probe`, invalidates import caches, then calls public discovery/catalog/router APIs.

Assertions:

- `probe` appears in `catalog.supported_tools()`;
- `catalog.supported_actions("probe") == {"ping"}`;
- `catalog.env_tools_description()["probe"]["payload_fields"]["ping"] == ["message"]`;
- dispatching `{"tool": "probe", "action": "ping", "args": {"message": "hello"}}` returns `ok=true`;
- no source file under `scripts/env/tools/` was edited by the test;
- no central table is required to mention `probe`.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_package_independence.py::EnvToolPackageIndependenceTests::test_local_probe_tool_package_is_discovered_without_central_edits -q
```

This is not a plugin framework requirement. It proves the local package-discovery contract needed for independent tool development.

### CAT1: Catalog Preserves Shipped Tools And Actions

Modify `tests/test_env_tool_semantic_contract.py` to import `env.tools.catalog`.

Assertions:

- supported tool set equals the shipped product set;
- supported actions by tool equal:

```python
{
    "task": {"create", "list", "get", "update", "archive"},
    "track": {"create", "list", "open", "update_now", "add_material", "add_update", "add_proof", "archive"},
    "artifact": {"get", "create_revision", "update_metadata"},
    "buddybox": {"desc", "list", "read", "write", "delete"},
    "context": {"get", "summarize", "list_sources"},
    "evidence": {"issue_browser", "approve_downgrade"},
    "message": {"send", "list"},
    "comment": {"add", "list"},
    "search": {"status", "request", "open_browser"},
}
```

- `catalog.semantic_contract_errors() == []`;
- every action has payload fields, kind, mutation effect, required permission, authority, preconditions, returns, and full action semantics.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
```

### CAT2: Payload Contract Is Per-Tool Source Of Truth

Modify `tests/test_env_tool_payload_contract.py` to import `env.tools.catalog`.

Assertions:

- `catalog.payload_fields_for_action(tool, action)` equals the action's per-tool contract fields;
- `catalog.env_tools_description()[tool]["payload_fields"][action]` preserves field order;
- every registered action rejects `{"__unexpected_payload_field__": True}` with `state_changed=False`;
- no tool service defines duplicate `_FIELDS` payload allowlists outside its own contract.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_payload_contract.py -q
```

### CAT3: Broken Non-Selected Metadata Is Reported Without Global Crash

Use a clean subprocess and a meta-path finder that raises `RuntimeError("blocked message contract import")` for `env.tools.message.contract`.

Operations:

- call catalog projection for all tools;
- dispatch `task.list`.

Assertions:

- catalog call exits 0;
- catalog output includes a structured diagnostic for `message`;
- `task.list` still returns `ok=true`;
- selecting `message.list` returns structured `E_ENV_TOOL_DISPATCH` or `E_ENV_TOOL_CATALOG` feedback with `state_changed=False`.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_package_independence.py::EnvToolPackageIndependenceTests::test_broken_non_selected_tool_metadata_is_reported_without_blocking_healthy_tool -q
```

### ROUTE1-ROUTE3: Selected-Tool Dispatch Isolation

Update existing router isolation tests from `env.services.messages` to `env.tools.message.service`.

Add a service import recorder subprocess:

```python
loaded = sorted(name for name in sys.modules if name.startswith("env.tools.") and name.endswith(".service"))
```

For each shipped tool, dispatch its cheapest read/status action:

- task: `list`
- track: `list`
- artifact: `get` with a missing id and expect a structured scope error
- buddybox: `desc`
- context: `list_sources`
- evidence: `issue_browser` with a missing target and expect structured scope error
- message: `list`
- comment: `list` with a missing target and expect structured scope error
- search: `status`

Assertions:

- the selected tool's service may be loaded;
- no sibling tool service is loaded;
- structured expected failures still have `state_changed=False`.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_selected_dispatch_imports_no_sibling_tool_services -q
```

### CLI1-CLI2: CLI Is Per-Tool Registered

Modify `tests/test_env_client_payload_cli.py`:

- keep broker mocking for CLI payload mapping;
- verify each resource parser is registered by a tool package;
- verify every CLI operation normalizes to an action in `catalog.supported_actions(tool)`;
- verify every required CLI payload or flag path dispatches the same broker envelope as before.

Add source-boundary assertion:

- `scripts/env/client.py` contains no `_dispatch_<tool>` functions;
- `main()` dispatches through parser defaults or generic tool CLI payload builders.

Focused commands:

```bash
python3 -m pytest tests/test_env_client_payload_cli.py -q
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_cli_operation_maps_align_with_catalog_actions -q
```

### BOUND1: Product Couplings Stay Explicit

Modify `tests/test_env_layer_boundaries.py`.

Assertions:

- direct sibling tool imports are forbidden;
- domain cross-object imports remain allowlisted to:
  - `publication`
  - `comment_targets`
  - `artifact_visibility`
  - `tasks`
  - `source_refs`
  - `buddybox_workspace`
- `track` and `artifact` services may import `env.domain.publication`, not each other;
- `comment` service may import `env.domain.comment_targets`, not track or artifact tool packages;
- `context` service may import catalog and domain/repo helpers, not buddybox tool service.

Focused command:

```bash
python3 -m pytest tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_tool_package_cross_imports_are_forbidden -q
```

### BOUND2: Old Services Package Is Gone

Assertions:

- no runtime Python source imports `env.services`;
- `scripts/env/services` does not contain tool entrypoint files;
- `tests/test_memory_removal_contract.py` imports `env.domain.source_refs`, not `env.services.source_refs`;
- artifact source refs use shared domain validation and buddybox repo logical-name normalization.

Focused command:

```bash
python3 -m pytest tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_legacy_env_services_tool_entrypoints_are_removed -q
```

### REG1: Existing Tool Behavior

Run focused behavior suites:

```bash
python3 -m pytest tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py -q
python3 -m pytest tests/test_buddybox_env_tool.py tests/test_context_binding_env_tool.py -q
python3 -m pytest tests/test_evidence_env_tool.py tests/test_message_env_tool.py tests/test_comment_env_tool.py tests/test_search_env_tool.py -q
```

Expected: pass.

### REG2: Broker, Runtime Status, Skills, And Repo Consistency

Run:

```bash
python3 -m pytest tests/test_runtime_broker.py tests/test_run_env_tool.py tests/test_turn_runtime.py -q
python3 -m pytest tests/test_env_tool_response_contract.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Expected: pass.

### REG3: Full Verification

Run:

```bash
python3 -m pytest -q
git diff --check
```

Expected: pass.

If full suite fails on an unrelated pre-existing failure, record the exact command, failing test, and reason. Do not claim this task complete while any env.tool architecture, CLI, catalog, broker, boundary, or shipped tool behavior test remains red.
