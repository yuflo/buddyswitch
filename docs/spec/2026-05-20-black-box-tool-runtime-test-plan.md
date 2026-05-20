# Black-Box Tool Runtime Test Plan

Date: 2026-05-20

Source memo: `docs/memo/2026-05-20-black-box-tool-runtime-memo.md`

## Goal

Prove BuddySwitch env.tool has become a black-box tool runtime: the host discovers and invokes a
tool through one public `tool.py` protocol, tool implementations access BuddySwitch state only
through `ToolContext`, and adding or removing a tool does not require host runtime branches or
legacy per-tool surface files.

## Task Confirmation

The current bottleneck is not basic per-tool package independence. The current implementation
already has `scripts/env/tools/<tool>/contract.py`, `semantics.py`, `cli.py`, `handlers.py`, and
`service.py`, but the host runtime still knows that internal layout and tool services still import
BuddySwitch internals directly.

The key problem is the remaining non-black-box boundary:

- host discovery reads `TOOL_SPEC`, `ACTION_SEMANTICS`, and `HANDLER_SPECS` from several per-tool
  files;
- tool services can import `env.repos`, `env.domain`, `env_manifest`, `runtime_kernel`, and sibling
  runtime modules directly;
- CLI/catalog/context/status projections are not all generated from a single protocol object;
- old per-tool public modules would remain future migration burden if they survive the replacement.

The required forward repair is a one-time direct replacement:

- create `scripts/env/tool_runtime/` as the host-owned runtime package;
- expose each tool through exactly one public `scripts/env/tools/<tool>/tool.py`;
- expose the external action input/output protocol through `ToolDefinition`;
- route all state access through `ToolContext`;
- delete old runtime ownership surfaces rather than preserving adapters, fallback registries, or
  old/new dual paths.

## Test Design Rules

- Tests start from functional and architecture requirements, not from current helper functions.
- Behavior tests must exercise public runtime paths: broker dispatch, env.tool registry dispatch,
  generic CLI payload dispatch, runtime catalog projection, and persisted state where mutation is
  expected.
- Behavior tests must preserve the completed clean runtime environment contract: runtime object and
  buddybox writes land under broker-owned state roots, while host-visible workspaces remain safe to
  search and do not expose runtime-state storage projections.
- Architecture tests may inspect files and AST because "single public tool entrypoint", "no direct
  runtime internals", and "legacy surfaces absent" are explicit requirements.
- A temporary probe tool is allowed only when it uses the same public discovery, catalog, CLI, and
  invocation path as shipped tools.
- Tests must fail if a solution keeps old `contract.py`, `semantics.py`, `handlers.py`, `cli.py`, or
  `service.py` files as active runtime surfaces.
- Tests must fail if `env.tools.catalog`, `env.tools.dispatch`, `env.tools.router`,
  `env.tools.responses`, `env.tools.model`, `env.tools.discovery`, or `env.tools.cli_helpers` remain
  as compatibility import aliases.
- Tests must not pass by mocking only the selected implementation. At least one suite must prove the
  real broker and real runtime context still work for shipped tools.

## Functional Requirements

R1. Shipped env.tools remain `artifact`, `buddybox`, `comment`, `context`, `evidence`, `message`,
`search`, `task`, and `track`.

R2. Shipped actions remain:

| Tool | Actions |
| --- | --- |
| `artifact` | `create_revision`, `get`, `update_metadata` |
| `buddybox` | `delete`, `desc`, `list`, `read`, `write` |
| `comment` | `add`, `list` |
| `context` | `get`, `list_sources`, `summarize` |
| `evidence` | `approve_downgrade`, `issue_browser` |
| `message` | `list`, `send` |
| `search` | `open_browser`, `request`, `status` |
| `task` | `archive`, `create`, `get`, `list`, `update` |
| `track` | `add_material`, `add_proof`, `add_update`, `archive`, `create`, `list`, `open`, `update_now` |

R3. Each shipped tool package exposes one public entrypoint: `scripts/env/tools/<tool>/tool.py`.

R4. `tool.py` exports `DEFINITION: ToolDefinition` and `invoke(action, args, context)`.

R5. Tool private implementation files are not host runtime API. Loading catalog/protocol metadata
must not import private implementation modules.

R6. Tool files must not import `env.repos`, `env.domain`, `env_manifest`, `runtime_kernel`, or
sibling `env.tools.<other_tool>` packages. Runtime state access must go through `ToolContext`.

R7. `ToolDefinition` is the only source for externally exposed tool metadata: tool id, title,
description, action ids, input schema, output schema, permission/effect metadata, and durability
metadata.

R8. `context.get.tool_catalog`, `context.get.operation_semantics`,
`context.summarize.tool_affordances`, `python3 scripts/turn_runtime.py status`, and
`python3 scripts/env/client.py <tool> <action> --payload '<json-object>'` are projections of the
same registry definitions.

R9. Adding a probe tool by adding a package with `tool.py` is enough for discovery, catalog, CLI,
and dispatch. Removing that package removes it from those surfaces without host branch edits.

R10. Dispatch imports only the selected tool private implementation. A broken non-selected tool
does not block healthy selected tool invocation.

R11. Selected tool load or invocation failures return structured env.tool rejection feedback with
`ok=false`, `state_changed=false`, `durability="none"`, `permission_boundary`, `why_blocked`,
`retry_guidance`, and actionable next steps.

R12. Existing behavior for all shipped tool actions remains covered by focused behavior suites.

R13. Shared skills remain decoupled from tool implementation internals and point to runtime
discovery for exact action and payload knowledge.

R14. Final active code and active architecture docs contain no current-runtime references to old
per-tool public modules or old shared env.tools runtime modules.

R15. The black-box runtime preserves the clean runtime environment baseline: `dispatcher` keeps
state-root refresh and status fields, `ToolContext` owns all access to `shared/state`, and tool
packages never derive object or buddybox storage paths from the host-visible workspace.

## Test Matrix

| ID | Requirement | File | Scenario | Main assertions |
| --- | --- | --- | --- | --- |
| BB1 | R1/R2/R3/R4 | `tests/test_black_box_tool_runtime.py` | Shipped tools expose black-box public entrypoints | every shipped tool has `tool.py`; no shipped tool has active `contract.py`, `semantics.py`, `handlers.py`, `cli.py`, or `service.py`; `DEFINITION.id` and actions match required set |
| BB2 | R5/R10 | `tests/test_black_box_tool_runtime.py` | Catalog import stays metadata-only | importing registry and building catalog imports `env.tools.<tool>.tool` but no `env.tools.<tool>._impl` or other private implementation module |
| BB3 | R6 | `tests/test_black_box_tool_runtime.py` | Tool package import boundary | AST scan rejects `env.repos`, `env.domain`, `env_manifest`, `runtime_kernel`, and sibling tool imports anywhere under `scripts/env/tools/<tool>/` |
| BB4 | R6 | `tests/test_black_box_tool_runtime.py` | Tool state mutation boundary | AST scan rejects direct `Path.write_text()`, `Path.unlink()`, write-mode `open()`, and repo write imports in tool packages |
| BB5 | R7/R8 | `tests/test_black_box_tool_runtime.py` | Registry projection is the single source | catalog, operation semantics, payload fields, and CLI action list are generated from `ToolDefinition` |
| BB6 | R9 | `tests/test_black_box_tool_runtime.py` | Probe tool add/delete | temporary `env.tools.probe.tool` appears in registry/CLI/dispatch with no host edits; deleting it removes it after cache invalidation |
| BB7 | R10/R11 | `tests/test_black_box_tool_runtime.py` | Broken non-selected tool does not block selected tool | blocked `message._impl` still allows `task.list`; blocked selected `message._impl` returns structured rejection |
| BB8 | R14 | `tests/test_black_box_tool_runtime.py` | Legacy runtime surfaces are absent | no compatibility modules exist for old shared env.tools runtime files; no old per-tool public module names exist in shipped tool packages |
| CAT1 | R7/R8 | `tests/test_env_tool_response_contract.py` | `context.get` and `turn_runtime status` use the registry | returned `tool_catalog` and `operation_semantics` equal `env.tool_runtime.registry` projections |
| CAT2 | R7/R11 | `tests/test_env_tool_payload_contract.py` | Runtime rejects fields outside input schema | every action rejects an unregistered field without state change |
| CLI1 | R8/R9 | `tests/test_env_client_payload_cli.py` | Generic CLI payload dispatch | every action can be converted into an env.tool envelope through `<tool> <action> --payload` without per-tool CLI modules |
| ROUTE1 | R10/R11 | `tests/test_env_tool_router.py` | Registry selected-tool isolation | dispatching one tool imports only selected private implementation and never sibling implementations |
| REG1 | R12 | Existing `tests/test_*_env_tool.py` suites | Shipped behavior remains intact | task, track, artifact, buddybox, context, evidence, message, comment, and search main paths still pass |
| SKILL1 | R13 | `tests/test_runtime_skills.py` | Skills stay runtime-discovery based | shared skills mention runtime discovery surfaces and do not name `tool.py`, private implementation files, or old module names |
| DOC1 | R14 | `tests/test_repo_consistency.py` | Active docs match black-box runtime | README/current architecture docs describe `env.tool_runtime` and `tool.py`, not old per-tool public module layout |
| CLEAN1 | R15 | `tests/test_clean_runtime_environment.py`, `tests/test_buddy_env_sandbox.py`, `tests/test_env_layer_boundaries.py`, `tests/test_env_layer_end_to_end.py`, `tests/test_runtime_broker.py` | Clean runtime baseline survives black-box replacement | workspace exploration stays clean; generated product config still protects source/state roots; broker status still reports workspace/state roots; env.tool writes still use shared state |
| FULL1 | R1-R15 | full relevant suite | Complete regression | focused architecture, CLI, broker, clean-runtime, behavior, skill, and consistency tests pass together |

## Detailed Test Designs

### BB1: Shipped Tools Expose One Public Entrypoint

Create or replace `tests/test_black_box_tool_runtime.py`.

Assertions:

- `scripts/env/tools/<tool>/tool.py` exists for every shipped tool.
- `scripts/env/tools/<tool>/contract.py`, `semantics.py`, `handlers.py`, `cli.py`, and `service.py`
  do not exist.
- importing `env.tools.<tool>.tool` exposes `DEFINITION` and `invoke`.
- `DEFINITION.id == <tool>`.
- `DEFINITION.actions` equals the action set in R2.
- each action has an object input schema with `additionalProperties` set to `False`.
- each action has an output schema object or canonical result schema reference.

Focused command:

```bash
python3 -m pytest tests/test_black_box_tool_runtime.py::BlackBoxToolRuntimeTests::test_shipped_tools_expose_single_public_entrypoint -q
```

Expected first result before implementation: fail because current shipped packages still expose
`contract.py`, `semantics.py`, `handlers.py`, `cli.py`, and `service.py`.

### BB2: Catalog Import Is Metadata-Only

Use a clean subprocess:

```python
import json
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))

from env.tool_runtime import registry

registry.supported_tools()
registry.env_tools_description()
registry.operation_semantics()

loaded_private = sorted(
    name for name in sys.modules
    if name.startswith("env.tools.") and "._impl" in name
)
print(json.dumps(loaded_private))
```

Assertions:

- subprocess exits 0;
- `loaded_private == []`;
- no loaded module starts with `env.repos.`, `env.domain.`, or `runtime_kernel.`.

Focused command:

```bash
python3 -m pytest tests/test_black_box_tool_runtime.py::BlackBoxToolRuntimeTests::test_registry_catalog_loads_definitions_without_private_implementations -q
```

### BB3: Tool Package Import Boundary

Parse every Python file under `scripts/env/tools/<tool>/`.

Forbidden imports:

- `env.repos`
- `env.domain`
- `env_manifest`
- `runtime_kernel`
- `env.tools.<other_tool>`
- `from env.tools import <other_tool>`
- `env.tools.catalog`, `env.tools.dispatch`, `env.tools.router`, `env.tools.responses`,
  `env.tools.model`, `env.tools.discovery`, `env.tools.cli_helpers`

Allowed imports:

- standard library modules;
- `env.tool_runtime.definition`;
- `env.tool_runtime.context`;
- `env.tool_runtime.results`;
- relative local imports such as `from . import _impl`.

Focused command:

```bash
python3 -m pytest tests/test_black_box_tool_runtime.py::BlackBoxToolRuntimeTests::test_tool_packages_import_only_runtime_sdk_and_local_modules -q
```

### BB4: Tool State Mutation Boundary

Parse AST for direct file mutations and raw repo-style writes under `scripts/env/tools/<tool>/`.

Forbidden patterns:

- `Path.write_text()`
- `Path.write_bytes()`
- `Path.unlink()`
- `open()` calls whose mode includes `w`, `a`, or `x`
- importing any repo module to call write helpers directly
- reading `workspace_dir`, `BUDDYSWITCH_STATE_ROOT`, or hard-coded
  `buddyswitch/objects` / `buddyswitch/local/buddybox` storage paths from tool implementation files

Allowed mutation route:

- methods called on `context.objects`, `context.buddybox`, or `context.browser`.
- host-owned `ToolContext` capability code may call `env.repos`, `env.domain`, and
  `runtime_files` to enforce the state-root-backed clean runtime contract.

Focused command:

```bash
python3 -m pytest tests/test_black_box_tool_runtime.py::BlackBoxToolRuntimeTests::test_tool_packages_mutate_state_only_through_tool_context -q
```

### BB5: Registry Projection Is the Single Source

Assertions:

- `registry.env_tools_description()[tool]["operations"]` equals action names from
  `registry.get_definition(tool).actions`.
- `registry.operation_semantics()[f"{tool}.{action}"]` comes from the same action definition
  metadata.
- `registry.payload_fields_for_action(tool, action)` equals input schema property keys.
- CLI help action names come from registry definitions and do not require per-tool CLI modules.

Focused command:

```bash
python3 -m pytest tests/test_black_box_tool_runtime.py::BlackBoxToolRuntimeTests::test_registry_projects_catalog_semantics_payload_fields_and_cli_actions_from_definitions -q
```

### BB6: Probe Tool Add/Delete

Create a temporary package at `<tmp>/env_tools_probe/probe/tool.py` with:

- a `ToolDefinition` with `id="probe"`;
- one `ActionDefinition` with `name="ping"`, input property `message`, and output schema
  `{"$ref": "ToolResult"}`;
- `invoke("ping", {"message": "hello"}, context)` returning a canonical read success.

Extend `env.tools.__path__` with the temporary root, invalidate import caches, then assert:

- `registry.supported_tools()` includes `probe`;
- `registry.env_tools_description()["probe"]["payload_fields"]["ping"] == ["message"]`;
- `python3 scripts/env/client.py probe ping --payload '{"message":"hello"}'` can build the broker
  envelope in a patched broker-request test;
- `dispatch_env_tool_request` called with payload `{"tool": "probe", "action": "ping", "args":
  {"message": "hello"}}` returns `ok=true` and `echo=="hello"`.

Remove the temp package from `env.tools.__path__`, invalidate caches, clear registry cache, then
assert `probe` is absent.

Focused command:

```bash
python3 -m pytest tests/test_black_box_tool_runtime.py::BlackBoxToolRuntimeTests::test_probe_tool_add_and_delete_use_only_tool_py_registration -q
```

### BB7: Broken Non-Selected Tool Isolation

Use a meta-path finder in a subprocess:

- block `env.tools.message._impl`;
- dispatch `task.list`;
- dispatch `message.list`.

Assertions:

- `task.list` returns `ok=true`;
- `message.list` returns `ok=false`;
- `message.list` has `error.code == "E_ENV_TOOL_DISPATCH"`;
- `state_changed is False`;
- response has `permission_boundary`, `why_blocked`, `retry_guidance`, and actionable next steps.

Focused command:

```bash
python3 -m pytest tests/test_black_box_tool_runtime.py::BlackBoxToolRuntimeTests::test_broken_non_selected_private_impl_does_not_block_selected_tool -q
```

### BB8: Legacy Runtime Surfaces Are Absent

Assertions:

- these files do not exist:
  - `scripts/env/tools/catalog.py`
  - `scripts/env/tools/cli_helpers.py`
  - `scripts/env/tools/discovery.py`
  - `scripts/env/tools/dispatch.py`
  - `scripts/env/tools/model.py`
  - `scripts/env/tools/responses.py`
  - `scripts/env/tools/router.py`
- no shipped tool package contains:
  - `contract.py`
  - `semantics.py`
  - `handlers.py`
  - `cli.py`
  - `service.py`
- no active Python code imports the deleted modules.

Focused command:

```bash
python3 -m pytest tests/test_black_box_tool_runtime.py::BlackBoxToolRuntimeTests::test_legacy_env_tools_runtime_surfaces_are_removed -q
```

### CAT1: Runtime Discovery Surfaces Use Registry

Modify existing response/turn runtime tests so they import `env.tool_runtime.registry`.

Assertions:

- broker-routed `context.get` returns `tool_catalog == registry.env_tools_description()`;
- broker-routed `context.get` returns `operation_semantics == registry.operation_semantics()`;
- `turn_runtime._build_env_tools_desc() == registry.env_tools_description()`;
- `context.summarize` stays compact and does not include full `tool_catalog`.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_context_get_and_summarize_catalog_scope -q
```

### CAT2: Payload Schema Rejection

Modify `tests/test_env_tool_payload_contract.py` to use the new registry.

Assertions for every action:

- input schema is an object with `additionalProperties=False`;
- payload field helper equals input schema property keys;
- dispatching `{"__unexpected_payload_field__": true}` returns `ok=false`;
- rejection includes the unexpected field name;
- `state_changed is False`.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_payload_contract.py::EnvToolPayloadContractTests::test_every_action_rejects_unregistered_payload_field_without_state_change -q
```

### CLI1: Generic CLI Payload Dispatch

Modify `tests/test_env_client_payload_cli.py`.

Assertions:

- `python3 scripts/env/client.py --help` lists all shipped tool ids from registry;
- `python3 scripts/env/client.py <tool> --help` lists action names from registry;
- `python3 scripts/env/client.py <tool> <action> --payload '<json-object>'` sends broker params
  `{"tool": tool, "action": action, "args": parsed_payload}`;
- file-path payload shortcuts are rejected;
- malformed JSON and non-object JSON are rejected before broker dispatch.

Focused command:

```bash
python3 -m pytest tests/test_env_client_payload_cli.py -q
```

### REG1: Shipped Tool Behavior

Run existing behavior suites after migration:

```bash
python3 -m pytest \
  tests/test_task_env_tool.py \
  tests/test_track_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_buddybox_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_evidence_env_tool.py \
  tests/test_message_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_search_env_tool.py \
  -q
```

Expected final result: all pass through the new `env.tool_runtime.registry` dispatch path and
`ToolContext`.

### CLEAN1: Clean Runtime Baseline Survives

Run the clean-runtime regression suites after the dispatcher, context, and buddybox migrations.

Assertions:

- broker `ping` and `status` still expose `runtime_workspace_root`, `runtime_state_root`, and
  `env_store_root`;
- `BUDDYSWITCH_STATE_ROOT` still refreshes `runtime_files` roots inside broker dispatch and is
  restored after dispatch;
- runtime object and buddybox writes through env.tool create files under `shared/state`, not under
  the host-visible workspace;
- host-visible workspaces still omit `buddyswitch/objects/**` and active buddybox storage
  projections;
- context and buddybox responses do not guide users to direct storage paths.

Focused command:

```bash
python3 -m pytest \
  tests/test_clean_runtime_environment.py \
  tests/test_buddy_env_sandbox.py \
  tests/test_env_layer_boundaries.py \
  tests/test_env_layer_end_to_end.py \
  tests/test_runtime_broker.py \
  -q
```

### SKILL1 and DOC1: Active Guidance Has No Runtime Residue

Assertions:

- shared skills mention `context.get.tool_catalog`, `context.get.operation_semantics`,
  `context.summarize.tool_affordances`, or `python3 scripts/turn_runtime.py status`;
- shared skills do not mention `contract.py`, `semantics.py`, `handlers.py`, `service.py`,
  `TOOL_SPEC`, `ACTION_SEMANTICS`, `HANDLER_SPECS`, or private `_impl.py`;
- active README/current architecture docs name `scripts/env/tool_runtime/*.py` and
  `scripts/env/tools/<tool>/tool.py`;
- active README/current architecture docs do not describe deleted old runtime files as current
  architecture.

Focused command:

```bash
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

## Required Verification Commands

Focused architecture and contract verification:

```bash
python3 -m pytest \
  tests/test_black_box_tool_runtime.py \
  tests/test_env_tool_payload_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_env_client_payload_cli.py \
  tests/test_env_tool_router.py \
  -q
```

Focused shipped behavior verification:

```bash
python3 -m pytest \
  tests/test_task_env_tool.py \
  tests/test_track_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_buddybox_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_evidence_env_tool.py \
  tests/test_message_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_search_env_tool.py \
  -q
```

Runtime integration and guidance verification:

```bash
python3 -m pytest \
  tests/test_runtime_broker.py \
  tests/test_turn_runtime.py \
  tests/test_runless_runtime_contract.py \
  tests/test_clean_runtime_environment.py \
  tests/test_buddy_env_sandbox.py \
  tests/test_env_layer_boundaries.py \
  tests/test_env_layer_end_to_end.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  -q
```

Repository hygiene:

```bash
git diff --check
rg -n 'env\.tools\.(catalog|cli_helpers|discovery|dispatch|model|responses|router)|TOOL_SPEC|ACTION_SEMANTICS|HANDLER_SPECS|scripts/env/tools/.*/(contract|semantics|handlers|cli|service)\.py' \
  scripts tests README.md docs/memo/buddyswitch-parallel-modular-architecture.md -S
```

Expected final hygiene result: no active code or active architecture guide references the old
runtime modules. Historical specs and memos may mention old files as source context or deletion
targets, but they must not be imported as active runtime guidance.

## Completion Gate

The task is not complete until:

- the new architecture tests pass;
- every shipped tool behavior suite passes through the new runtime;
- active docs and skills describe only the black-box runtime;
- clean runtime environment regressions still pass;
- deleted old module names are rejected by tests;
- no compatibility import alias, fallback registry, or old/new dual path remains.
