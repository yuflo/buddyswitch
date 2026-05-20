# Per-Tool Independence Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Runtime behavior changes must follow `superpowers:test-driven-development`: write and verify the failing test before production code is edited.

**Goal:** Rebuild env.tool so each tool owns its own contract, semantics, CLI, handler mapping, and service entrypoint, with shared runtime modules reduced to service-light discovery, catalog projection, routing, dispatch, and response formatting.

**Architecture:** Replace central hand-written tool tables with repo-local per-tool packages under `scripts/env/tools/<tool>/`. Use generic discovery/catalog/router/dispatch infrastructure that imports only metadata for catalog work and only the selected tool service for dispatch. Delete old central ownership files and service entrypoint modules instead of preserving compatibility shims.

**Tech Stack:** Python 3.9-compatible runtime code, `argparse`, `importlib`, `pkgutil`, `unittest`/`pytest`, AST boundary tests, broker-routed env.tool behavior tests.

---

## Preconditions

Complete and verify `docs/spec/2026-05-19-tool-independence-repair-implementation-plan.md` before starting this rebuild.

Run:

```bash
python3 -m pytest tests/test_env_tool_router.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_payload_contract.py -q
python3 -m pytest tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_comment_env_tool.py -q
git diff --check
```

Expected: all pass.

Do not begin this rebuild while the first repair has relevant env.tool failures.

## Source Inputs

Read these before editing:

- `docs/spec/2026-05-20-per-tool-independence-rebuild-scope.md`
- `docs/spec/2026-05-20-per-tool-independence-rebuild-test-plan.md`
- `scripts/env/tools/contracts.py`
- `scripts/env/tools/semantics.py`
- `scripts/env/tools/dispatch.py`
- `scripts/env/tools/router.py`
- `scripts/env/tools/responses.py`
- `scripts/env/client.py`
- `scripts/turn_runtime.py`
- `scripts/env/services/tasks.py`
- `scripts/env/services/tracks.py`
- `scripts/env/services/artifacts.py`
- `scripts/env/services/buddybox.py`
- `scripts/env/services/context.py`
- `scripts/env/services/evidence.py`
- `scripts/env/services/messages.py`
- `scripts/env/services/comments.py`
- `scripts/env/services/search.py`
- `scripts/env/services/source_refs.py`
- `scripts/env/repos/buddybox_files.py`
- `scripts/env/domain/publication.py`
- `scripts/env/domain/comment_targets.py`
- `scripts/env/domain/artifact_visibility.py`
- `scripts/env/domain/tasks.py`
- `tests/test_env_tool_router.py`
- `tests/test_env_tool_payload_contract.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_env_client_payload_cli.py`
- `tests/test_env_layer_boundaries.py`
- all shipped tool behavior suites under `tests/test_*_env_tool.py`

## Target File Structure

Create:

```text
scripts/env/tools/model.py
scripts/env/tools/discovery.py
scripts/env/tools/catalog.py
scripts/env/tools/cli_helpers.py
scripts/env/domain/source_refs.py
scripts/env/domain/buddybox_workspace.py
tests/test_env_tool_package_independence.py
```

Create these tool packages:

```text
scripts/env/tools/task/__init__.py
scripts/env/tools/task/contract.py
scripts/env/tools/task/semantics.py
scripts/env/tools/task/cli.py
scripts/env/tools/task/handlers.py
scripts/env/tools/task/service.py

scripts/env/tools/track/__init__.py
scripts/env/tools/track/contract.py
scripts/env/tools/track/semantics.py
scripts/env/tools/track/cli.py
scripts/env/tools/track/handlers.py
scripts/env/tools/track/service.py

scripts/env/tools/artifact/__init__.py
scripts/env/tools/artifact/contract.py
scripts/env/tools/artifact/semantics.py
scripts/env/tools/artifact/cli.py
scripts/env/tools/artifact/handlers.py
scripts/env/tools/artifact/service.py

scripts/env/tools/buddybox/__init__.py
scripts/env/tools/buddybox/contract.py
scripts/env/tools/buddybox/semantics.py
scripts/env/tools/buddybox/cli.py
scripts/env/tools/buddybox/handlers.py
scripts/env/tools/buddybox/service.py

scripts/env/tools/context/__init__.py
scripts/env/tools/context/contract.py
scripts/env/tools/context/semantics.py
scripts/env/tools/context/cli.py
scripts/env/tools/context/handlers.py
scripts/env/tools/context/service.py

scripts/env/tools/evidence/__init__.py
scripts/env/tools/evidence/contract.py
scripts/env/tools/evidence/semantics.py
scripts/env/tools/evidence/cli.py
scripts/env/tools/evidence/handlers.py
scripts/env/tools/evidence/service.py

scripts/env/tools/message/__init__.py
scripts/env/tools/message/contract.py
scripts/env/tools/message/semantics.py
scripts/env/tools/message/cli.py
scripts/env/tools/message/handlers.py
scripts/env/tools/message/service.py

scripts/env/tools/comment/__init__.py
scripts/env/tools/comment/contract.py
scripts/env/tools/comment/semantics.py
scripts/env/tools/comment/cli.py
scripts/env/tools/comment/handlers.py
scripts/env/tools/comment/service.py

scripts/env/tools/search/__init__.py
scripts/env/tools/search/contract.py
scripts/env/tools/search/semantics.py
scripts/env/tools/search/cli.py
scripts/env/tools/search/handlers.py
scripts/env/tools/search/service.py
```

Modify:

- `scripts/env/tools/dispatch.py`
- `scripts/env/tools/router.py`
- `scripts/env/client.py`
- `scripts/turn_runtime.py`
- existing env.tool tests listed in source inputs
- existing runtime skill and repo consistency tests that import `env.tools.contracts`

Delete after callers are updated:

- `scripts/env/tools/contracts.py`
- `scripts/env/tools/semantics.py`
- `scripts/env/services/tasks.py`
- `scripts/env/services/tracks.py`
- `scripts/env/services/artifacts.py`
- `scripts/env/services/buddybox.py`
- `scripts/env/services/context.py`
- `scripts/env/services/evidence.py`
- `scripts/env/services/messages.py`
- `scripts/env/services/comments.py`
- `scripts/env/services/search.py`
- `scripts/env/services/source_refs.py`
- `scripts/env/services/__init__.py`

Remove `scripts/env/services/` if it is empty.

## Shared Interface Contract

Each tool package must expose these metadata modules:

`contract.py`:

```python
from __future__ import annotations

from typing import Any

from env.tools.model import MUTATES_NONE, MUTATES_RUNTIME_OBJECTS

TOOL_ID = "task"
TOOL_SPEC: dict[str, Any] = {
    "tool": TOOL_ID,
    "cli_resource": "task",
    "command": "python3 scripts/env/client.py task <operation>",
    "scope": "...",
    "actions": [
        {
            "name": "list",
            "payload_fields": ["status", "track_id", "limit"],
            "kind": "read",
            "mutates": MUTATES_NONE,
            "required_permission": "task.read",
            "authority": "task.buddy_scope",
            "preconditions": ["active buddy owns task.read permission"],
            "returns": ["tasks"],
        },
    ],
}
```

`semantics.py`:

```python
from __future__ import annotations

from typing import Any

CAPABILITY: dict[str, Any] = {
    "plain_description": "...",
    "when_to_use": ["..."],
    "when_not_to_use": ["..."],
    "capability_boundary": "...",
}

ACTION_SEMANTICS: dict[str, dict[str, Any]] = {
    "list": {
        "use_when": ["..."],
        "do_not_use_when": ["..."],
        "inputs_explained": {"limit": "..."},
        "common_failures": ["..."],
        "success_means": "...",
        "risk_hints": {},
    },
}
```

`handlers.py`:

```python
from __future__ import annotations

HandlerSpec = tuple[str, str]

HANDLER_SPECS: dict[str, HandlerSpec] = {
    "list": ("env.tools.task.service", "list_tasks_for_active_buddy"),
}
```

`cli.py`:

```python
from __future__ import annotations

import argparse
from typing import Any

from env.tools import cli_helpers

TOOL_ID = "task"


def register_cli(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("task", help="Task env tool operations")
    task_sub = parser.add_subparsers(dest="operation", required=True)
    list_parser = task_sub.add_parser("list", help="List active-buddy tasks")
    list_parser.add_argument("--status")
    list_parser.add_argument("--track-id")
    list_parser.add_argument("--limit", type=int)
    list_parser.set_defaults(_env_tool=TOOL_ID, _env_action="list", _env_payload_builder=_list_payload)


def _list_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field in ("status", "track_id", "limit"):
        value = getattr(args, field, None)
        if value is not None:
            payload[field] = value
    return payload
```

`service.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from env.tools import responses as tool_responses


class ServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]
    manifest_path: Path | None
```

Service functions keep the existing function names unless the owning tool package chooses clearer private helper names. Handler specs must point to the final function names.

## Phase 1: Add Failing Independence Tests

**Objective:** Lock the complete rebuild target before runtime edits.

**Files:**

- Create `tests/test_env_tool_package_independence.py`
- Modify `tests/test_env_tool_router.py`
- Modify `tests/test_env_tool_semantic_contract.py`
- Modify `tests/test_env_tool_payload_contract.py`
- Modify `tests/test_env_client_payload_cli.py`
- Modify `tests/test_env_layer_boundaries.py`

- [x] **Step 1: Create package independence test file**

Create `tests/test_env_tool_package_independence.py` with tests from `docs/spec/2026-05-20-per-tool-independence-rebuild-test-plan.md`:

- `test_shipped_tool_packages_own_required_files`
- `test_no_central_tool_ownership_tables_remain`
- `test_tool_packages_do_not_import_sibling_tool_packages`
- `test_public_imports_do_not_load_tool_services`
- `test_catalog_projection_does_not_load_services_repos_or_domains`
- `test_local_probe_tool_package_is_discovered_without_central_edits`
- `test_broken_non_selected_tool_metadata_is_reported_without_blocking_healthy_tool`

Use this shipped tool set:

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
```

Use this required file set:

```python
REQUIRED_TOOL_FILES = {"__init__.py", "contract.py", "semantics.py", "cli.py", "handlers.py", "service.py"}
```

- [x] **Step 2: Update router isolation tests**

In `tests/test_env_tool_router.py`, update service-failure meta-path guards from `env.services.messages` to `env.tools.message.service`.

Add `test_selected_dispatch_imports_no_sibling_tool_services` using the cheapest action list from the test plan.

- [x] **Step 3: Update catalog tests to the target API**

In `tests/test_env_tool_semantic_contract.py` and `tests/test_env_tool_payload_contract.py`, change imports from:

```python
from env.tools import contracts
```

to:

```python
from env.tools import catalog
```

Update references:

```text
contracts.TOOL_REGISTRY -> catalog.tool_specs()
contracts.supported_tools -> catalog.supported_tools
contracts.supported_actions -> catalog.supported_actions
contracts.env_tools_description -> catalog.env_tools_description
contracts.operation_semantics -> catalog.operation_semantics
contracts.payload_fields_for_action -> catalog.payload_fields_for_action
contracts.semantic_contract_errors -> catalog.semantic_contract_errors
contracts.compact_tool_affordances -> catalog.compact_tool_affordances
```

- [x] **Step 4: Update CLI tests**

In `tests/test_env_client_payload_cli.py`, add an assertion that `scripts/env/client.py` does not define any `_dispatch_<tool>` function for the shipped tools.

Keep existing broker payload mapping cases and add any missing flag-based cases:

- `task list --status active --limit 10`
- `track list`
- `context list-sources`
- `buddybox desc`
- `evidence issue-browser`
- `search status`
- `message list --buddy design`
- `comment list --target-type track --target-id track-json --status open`

- [x] **Step 5: Add boundary tests**

In `tests/test_env_layer_boundaries.py`, add:

- `test_tool_package_cross_imports_are_forbidden`
- `test_legacy_env_services_tool_entrypoints_are_removed`

Use AST parsing. Fail on direct sibling tool package imports and any runtime source import of `env.services`.

- [x] **Step 6: Verify red**

Run:

```bash
python3 -m pytest tests/test_env_tool_package_independence.py -q
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_selected_dispatch_imports_no_sibling_tool_services -q
python3 -m pytest tests/test_env_client_payload_cli.py -q
python3 -m pytest tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_tool_package_cross_imports_are_forbidden -q
```

Expected: fail because the current code still has central ownership files and services outside tool packages.

Execution log:

- `python3 -m pytest tests/test_env_tool_package_independence.py -q` -> failed as expected (`15 failed, 1 passed`), with failures on missing per-tool packages and missing `env.tools.catalog`.
- `python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_selected_dispatch_imports_no_sibling_tool_services -q` -> failed as expected (`9 failed, 1 passed`), confirming selected-tool service isolation is not yet implemented.
- `python3 -m pytest tests/test_env_client_payload_cli.py -q` -> failed as expected (`10 failed, 7 passed`), confirming centralized `_dispatch_<tool>` branches still exist and flag mappings are incomplete.
- `python3 -m pytest tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_tool_package_cross_imports_are_forbidden -q` -> failed as expected (`1 failed`), confirming per-tool package structure is not yet present.

## Phase 2: Create Generic Tool Infrastructure

**Objective:** Add service-light shared infrastructure before moving individual tools.

**Files:**

- Create `scripts/env/tools/model.py`
- Create `scripts/env/tools/discovery.py`
- Create `scripts/env/tools/catalog.py`
- Create `scripts/env/tools/cli_helpers.py`
- Modify `scripts/env/tools/__init__.py`

- [x] **Step 1: Create `model.py`**

Move mutation constants from `scripts/env/tools/contracts.py` into `scripts/env/tools/model.py`:

```python
#!/usr/bin/env python3
"""Shared env.tool metadata shapes."""

from __future__ import annotations

from typing import Any, TypedDict

MUTATES_NONE = "none"
MUTATES_RUNTIME_OBJECTS = "runtime_objects"
MUTATES_RUNTIME_FILES = "runtime_files"
MUTATES_BROKER_TOKEN = "broker_token"
MUTATES_BROWSER_SESSION = "browser_session"


class ActionSpec(TypedDict, total=False):
    name: str
    payload_fields: list[str]
    kind: str
    mutates: str
    required_permission: str
    authority: str
    preconditions: list[str]
    returns: list[str]


class ToolSpec(TypedDict, total=False):
    tool: str
    cli_resource: str
    command: str
    scope: str
    actions: list[ActionSpec]


class ToolLoadProblem(TypedDict):
    tool: str
    module: str
    error: str
```

- [x] **Step 2: Create `discovery.py`**

Create repo-local package discovery:

```python
#!/usr/bin/env python3
"""Repo-local env.tool package discovery."""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType
from typing import Any

import env.tools

_SKIP_NAMES = {
    "__pycache__",
    "model",
    "discovery",
    "catalog",
    "cli_helpers",
    "dispatch",
    "responses",
    "router",
}


def discover_tool_ids() -> list[str]:
    ids: list[str] = []
    for info in pkgutil.iter_modules(env.tools.__path__):
        if not info.ispkg or info.name in _SKIP_NAMES or info.name.startswith("_"):
            continue
        ids.append(info.name)
    return sorted(set(ids))


def tool_package_exists(tool: str) -> bool:
    return tool in discover_tool_ids()


def import_tool_module(tool: str, module_name: str) -> ModuleType:
    return importlib.import_module(f"env.tools.{tool}.{module_name}")


def read_module_attr(tool: str, module_name: str, attr_name: str) -> Any:
    module = import_tool_module(tool, module_name)
    return getattr(module, attr_name)
```

- [x] **Step 3: Create `catalog.py`**

Create projections from per-tool packages:

```python
#!/usr/bin/env python3
"""Service-light env.tool catalog projection from per-tool packages."""

from __future__ import annotations

from typing import Any

from env.tools import discovery


def tool_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for tool in discovery.discover_tool_ids():
        spec = load_tool_spec(tool)
        if spec is not None:
            specs.append(spec)
    return specs


def load_tool_spec(tool: str) -> dict[str, Any] | None:
    try:
        spec = discovery.read_module_attr(tool, "contract", "TOOL_SPEC")
    except Exception:
        return None
    if isinstance(spec, dict) and spec.get("tool") == tool:
        return spec
    return None


def tool_catalog_errors() -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for tool in discovery.discover_tool_ids():
        try:
            discovery.read_module_attr(tool, "contract", "TOOL_SPEC")
            discovery.read_module_attr(tool, "semantics", "CAPABILITY")
            discovery.read_module_attr(tool, "semantics", "ACTION_SEMANTICS")
        except Exception as exc:
            errors.append({"tool": tool, "module": f"env.tools.{tool}", "error": str(exc)})
    return errors
```

Add the remaining public functions by moving existing projection logic out of `contracts.py` and reading from `tool_specs()` plus each tool's `semantics.py`:

- `supported_tools()`
- `supported_actions(tool)`
- `payload_fields_for_action(tool, action)`
- `env_tools_description()`
- `operation_semantics()`
- `compact_tool_affordances()`
- `semantic_contract_errors()`

Do not import tool `service.py` from this module.

- [x] **Step 4: Create `cli_helpers.py`**

Move JSON payload and operation helpers out of `scripts/env/client.py`:

```python
#!/usr/bin/env python3
"""Shared env.tool CLI argument helpers."""

from __future__ import annotations

import argparse
import json
from typing import Any


def load_json_object(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--payload must be a JSON object string: {exc.msg} at char {exc.pos}") from exc
    if not isinstance(payload, dict):
        raise ValueError("--payload must be a JSON object string")
    return payload


def operation_to_action(operation: str) -> str:
    return operation.replace("-", "_")


def add_payload_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--payload",
        required=True,
        metavar="JSON_OBJECT",
        help="JSON object string to send as env.tool args; do not pass a file path.",
    )
```

- [x] **Step 5: Verify infrastructure imports**

Run:

```bash
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "scripts"))
import env.tools.model
import env.tools.discovery
import env.tools.catalog
import env.tools.cli_helpers
print("ok")
PY
```

Expected: prints `ok`.

## Phase 3: Split Contracts And Semantics Into Tool Packages

**Objective:** Move all action and semantic ownership from central files into per-tool packages.

**Files:**

- Create each `scripts/env/tools/<tool>/__init__.py`
- Create each `scripts/env/tools/<tool>/contract.py`
- Create each `scripts/env/tools/<tool>/semantics.py`
- Modify `scripts/env/tools/catalog.py`

- [x] **Step 1: Create all package directories**

Create the nine package directories listed in the target file structure.

Each `__init__.py` must be service-light:

```python
"""<tool> env.tool package."""
```

Do not import `service`, `handlers`, `contract`, or `semantics` in `__init__.py`.

- [x] **Step 2: Move contract rows**

For each tool, copy exactly one row from the current `TOOL_REGISTRY` into that tool's `contract.py` as `TOOL_SPEC`.

Use this exact map:

| Tool | Source row in `contracts.py` | Destination |
| --- | --- | --- |
| task | row with `"tool": "task"` | `scripts/env/tools/task/contract.py` |
| track | row with `"tool": "track"` | `scripts/env/tools/track/contract.py` |
| artifact | row with `"tool": "artifact"` | `scripts/env/tools/artifact/contract.py` |
| buddybox | row with `"tool": "buddybox"` | `scripts/env/tools/buddybox/contract.py` |
| context | row with `"tool": "context"` | `scripts/env/tools/context/contract.py` |
| evidence | row with `"tool": "evidence"` | `scripts/env/tools/evidence/contract.py` |
| message | row with `"tool": "message"` | `scripts/env/tools/message/contract.py` |
| comment | row with `"tool": "comment"` | `scripts/env/tools/comment/contract.py` |
| search | row with `"tool": "search"` | `scripts/env/tools/search/contract.py` |

Replace mutation constant imports with imports from `env.tools.model`.

- [x] **Step 3: Move semantic rows**

For each tool, copy exactly one capability row and all action semantic rows from the current `_CAPABILITIES` entry in `scripts/env/tools/semantics.py` into that tool's `semantics.py`.

Use these destination symbols:

```python
CAPABILITY: dict[str, Any] = {...}
ACTION_SEMANTICS: dict[str, dict[str, Any]] = {...}
```

The keys of `ACTION_SEMANTICS` must exactly match that tool's contract action names.

- [x] **Step 4: Complete `catalog.py` projections**

Implement `catalog.env_tools_description()` with the existing output shape:

```python
{
    tool: {
        "scope": ...,
        "command": ...,
        "operations": [...],
        "payload_fields": {action: [...]},
        "action_semantics": {action: {...}},
    }
}
```

Implement `catalog.operation_semantics()` with the existing machine-readable shape:

```python
{
    "task.list": {
        "kind": "read",
        "mutates": "none",
        "required_permission": "task.read",
        "authority": "task.buddy_scope",
        "requires": [...],
        "returns": [...],
        "risk_hints": {...},
    }
}
```

Implement `catalog.compact_tool_affordances()` from each tool's `CAPABILITY`.

Implement `catalog.semantic_contract_errors()`:

- error if a discovered tool has no contract;
- error if a discovered tool has no semantics;
- error if action names differ between contract and semantics;
- error if required fields are missing from any semantic action row.

- [x] **Step 5: Verify catalog red/green subset**

Run:

```bash
python3 -m pytest tests/test_env_tool_package_independence.py::EnvToolPackageIndependenceTests::test_shipped_tool_packages_own_required_files -q
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
```

Expected after this phase: package file test passes; semantic contract tests may still fail until tests import `catalog` and old central files are removed.

## Phase 4: Move Handler Specs And Services Into Tool Packages

**Objective:** A selected tool dispatch loads only that tool's handler and service.

**Files:**

- Create all `handlers.py`
- Create all `service.py`
- Modify imports inside moved service files
- Modify `scripts/env/tools/dispatch.py`

- [x] **Step 1: Move handler specs**

Create each `handlers.py` from the existing central `HANDLER_SPECS_BY_TOOL` rows.

Use this exact destination map:

| Tool | Destination handler specs |
| --- | --- |
| task | `{"create": ("env.tools.task.service", "create_task_for_active_buddy"), "list": ("env.tools.task.service", "list_tasks_for_active_buddy"), "get": ("env.tools.task.service", "get_task_for_active_buddy"), "update": ("env.tools.task.service", "update_task_for_active_buddy"), "archive": ("env.tools.task.service", "archive_task_for_active_buddy")}` |
| track | `{"create": ("env.tools.track.service", "create_track_for_pm"), "list": ("env.tools.track.service", "list_tracks_for_active_buddy"), "open": ("env.tools.track.service", "open_track_for_active_buddy"), "update_now": ("env.tools.track.service", "update_now_for_active_buddy"), "add_material": ("env.tools.track.service", "add_material_to_track"), "add_update": ("env.tools.track.service", "add_update_to_track"), "add_proof": ("env.tools.track.service", "add_proof_to_track"), "archive": ("env.tools.track.service", "archive_track_for_pm")}` |
| artifact | `{"get": ("env.tools.artifact.service", "get_artifact_for_active_buddy"), "create_revision": ("env.tools.artifact.service", "create_artifact_revision"), "update_metadata": ("env.tools.artifact.service", "update_artifact_metadata")}` |
| buddybox | `{"desc": ("env.tools.buddybox.service", "describe_buddybox_for_active_buddy"), "list": ("env.tools.buddybox.service", "list_buddybox_for_active_buddy"), "read": ("env.tools.buddybox.service", "read_buddybox_for_active_buddy"), "write": ("env.tools.buddybox.service", "write_buddybox_for_active_buddy"), "delete": ("env.tools.buddybox.service", "delete_buddybox_for_active_buddy")}` |
| context | `{"get": ("env.tools.context.service", "get_context"), "summarize": ("env.tools.context.service", "summarize_context"), "list_sources": ("env.tools.context.service", "list_sources")}` |
| evidence | `{"issue_browser": ("env.tools.evidence.service", "issue_browser_for_active_instance"), "approve_downgrade": ("env.tools.evidence.service", "approve_downgrade_for_active_instance")}` |
| message | `{"send": ("env.tools.message.service", "send_message"), "list": ("env.tools.message.service", "list_messages")}` |
| comment | `{"add": ("env.tools.comment.service", "add_comment"), "list": ("env.tools.comment.service", "list_comments")}` |
| search | `{"status": ("env.tools.search.service", "status_for_active_instance"), "request": ("env.tools.search.service", "request_for_active_instance"), "open_browser": ("env.tools.search.service", "open_browser_for_active_instance")}` |

- [x] **Step 2: Move service files**

Move each service file into its tool package:

```text
scripts/env/services/tasks.py -> scripts/env/tools/task/service.py
scripts/env/services/tracks.py -> scripts/env/tools/track/service.py
scripts/env/services/artifacts.py -> scripts/env/tools/artifact/service.py
scripts/env/services/buddybox.py -> scripts/env/tools/buddybox/service.py
scripts/env/services/context.py -> scripts/env/tools/context/service.py
scripts/env/services/evidence.py -> scripts/env/tools/evidence/service.py
scripts/env/services/messages.py -> scripts/env/tools/message/service.py
scripts/env/services/comments.py -> scripts/env/tools/comment/service.py
scripts/env/services/search.py -> scripts/env/tools/search/service.py
```

In each moved service, replace:

```python
from env.tools import contracts as tool_contracts
```

with either:

```python
from env.tools import catalog as tool_catalog
```

or an own-tool contract import:

```python
from env.tools.task import contract as tool_contract
```

Use own-tool contract imports for service payload validation where possible. Use `catalog` only for context output that needs full runtime catalog.

- [x] **Step 3: Extract source refs domain**

Move:

```text
scripts/env/services/source_refs.py -> scripts/env/domain/source_refs.py
```

Update artifact service:

```python
from env.domain import source_refs as source_ref_domain
```

Update tests:

```python
from env.domain import source_refs
```

- [x] **Step 4: Extract buddybox workspace descriptor domain**

Create `scripts/env/domain/buddybox_workspace.py`.

Move service-light helper logic shared by context and buddybox:

- manifest buddy id normalization if needed by descriptors;
- `build_buddybox_desc`;
- private workspace descriptor construction that does not read private file content.

Update:

- `scripts/env/tools/buddybox/service.py` imports `env.domain.buddybox_workspace`;
- `scripts/env/tools/context/service.py` imports `env.domain.buddybox_workspace`;
- context service no longer imports buddybox tool service.

- [x] **Step 5: Rewrite generic dispatch**

Replace `scripts/env/tools/dispatch.py` with generic selected-tool loading.

Required behavior:

- no central `HANDLER_SPECS_BY_TOOL`;
- `dispatch_handler_actions()` builds `{tool: set(actions)}` from each tool's `handlers.HANDLER_SPECS`;
- `_load_handler(tool, action)` imports only `env.tools.<tool>.handlers`, then the selected handler function module;
- selected handler load failure returns structured `E_ENV_TOOL_DISPATCH`;
- no sibling service modules are imported.

Required function signatures:

```python
def dispatch_handler_actions() -> dict[str, set[str]]: ...

def dispatch_registered_env_tool(
    *,
    tool: str,
    action: str,
    args: dict[str, Any],
    active_buddy: str,
    instance_id: str,
    instance_json: Path,
    instance_payload: dict[str, Any],
    manifest: dict[str, Any],
    manifest_path: Path | None = None,
) -> dict[str, Any]: ...
```

Keep `_runtime_feedback_error` and `_service_context` behavior from the current dispatch module.

- [x] **Step 6: Verify selected service isolation**

Run:

```bash
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_selected_dispatch_imports_no_sibling_tool_services -q
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_unrelated_service_import_failure_does_not_block_task_tool -q
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_selected_service_import_failure_returns_structured_feedback -q
```

Expected: pass.

## Phase 5: Move CLI Ownership Into Tool Packages

**Objective:** The top-level CLI contains no tool-specific operation branches.

**Files:**

- Create all `cli.py`
- Modify `scripts/env/client.py`
- Modify `tests/test_env_client_payload_cli.py`

- [x] **Step 1: Create per-tool CLI modules**

Move parser and payload builder ownership from `scripts/env/client.py` into each tool's `cli.py`.

Use this exact operation map:

| Tool | CLI operations |
| --- | --- |
| task | `create`, `list`, `get`, `update`, `archive` |
| track | `create`, `list`, `open`, `update-now`, `add-material`, `add-update`, `add-proof`, `archive` |
| artifact | `get`, `create-revision`, `update-metadata` |
| context | `get`, `summarize`, `list-sources` |
| buddybox | `desc`, `list`, `read`, `write`, `delete` |
| evidence | `issue-browser`, `approve-downgrade` |
| message | `send`, `list` |
| comment | `add`, `list` |
| search | `status`, `request`, `open-browser` |

Every leaf parser must set:

```python
parser.set_defaults(
    _env_tool="<tool>",
    _env_action="<action_with_underscores>",
    _env_payload_builder=<callable>,
)
```

For JSON payload operations, use:

```python
def _json_payload(args: argparse.Namespace) -> dict[str, Any]:
    return cli_helpers.load_json_object(args.payload)
```

- [x] **Step 2: Rewrite `scripts/env/client.py`**

Keep only generic responsibilities:

- broker request helper;
- error payload helper;
- top-level parser creation;
- loop over discovered tool packages and call each package's `cli.register_cli(subparsers)`;
- generic payload dispatch using parser defaults.

The final `main()` shape must be:

```python
def main() -> int:
    try:
        args = _parse_args()
        tool = getattr(args, "_env_tool", None)
        action = getattr(args, "_env_action", None)
        payload_builder = getattr(args, "_env_payload_builder", None)
        if not isinstance(tool, str) or not isinstance(action, str) or not callable(payload_builder):
            raise ValueError("selected CLI operation is not registered as an env.tool action")
        payload = _dispatch_env_tool(tool, action, payload_builder(args))
    except Exception as exc:
        print(json.dumps(_error_payload("E_ENV_CLI", str(exc)), ensure_ascii=True, indent=2))
        return 1

    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if payload.get("ok") is True else 1
```

Do not keep `_dispatch_task`, `_dispatch_track`, `_dispatch_artifact`, `_dispatch_context`, `_dispatch_buddybox`, `_dispatch_evidence`, `_dispatch_search`, `_dispatch_message`, or `_dispatch_comment`.

- [x] **Step 3: Verify CLI behavior**

Run:

```bash
python3 -m pytest tests/test_env_client_payload_cli.py -q
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_cli_operation_maps_align_with_catalog_actions -q
```

Expected: pass.

## Phase 6: Update Router And Runtime Catalog Consumers

**Objective:** All runtime callers use the new generic catalog, not old central contracts.

**Files:**

- Modify `scripts/env/tools/router.py`
- Modify `scripts/env/tools/dispatch.py`
- Modify `scripts/env/tools/catalog.py`
- Modify `scripts/env/tools/responses.py` only if import paths reference old contracts
- Modify `scripts/env/tools/context/service.py`
- Modify `scripts/turn_runtime.py`
- Modify tests importing `env.tools.contracts`

- [x] **Step 1: Rewrite router registration lookup**

In `scripts/env/tools/router.py`, replace module-load `_TOOL_ACTIONS` with calls to `catalog`.

Required behavior:

- unsupported tool rejection uses `catalog.supported_tools()`;
- selected action validation uses `catalog.supported_actions(tool)`;
- if selected tool package exists but its contract cannot load, return structured `E_ENV_TOOL_CATALOG` feedback with `state_changed=False`;
- response still sets top-level `tool` and semantic `action` where applicable.

- [x] **Step 2: Update context catalog output**

In `scripts/env/tools/context/service.py`, replace:

```python
"tool_catalog": tool_contracts.env_tools_description(),
"operation_semantics": tool_contracts.operation_semantics(),
```

with:

```python
"tool_catalog": tool_catalog.env_tools_description(),
"operation_semantics": tool_catalog.operation_semantics(),
"tool_catalog_errors": tool_catalog.tool_catalog_errors(),
```

Do not import any sibling tool service.

- [x] **Step 3: Update runtime status**

In `scripts/turn_runtime.py`, replace old contract imports with:

```python
from env.tools import catalog as tool_catalog
```

Update runtime status construction to call `tool_catalog.env_tools_description()`.

If status includes operation semantics, source it from `tool_catalog.operation_semantics()`.

- [x] **Step 4: Update tests to catalog**

Replace all runtime test imports:

```python
from env.tools import contracts as tool_contracts
```

with:

```python
from env.tools import catalog as tool_catalog
```

Use `rg "env.tools import contracts|tool_contracts|TOOL_REGISTRY|contracts\\." tests scripts` until no production caller remains.

- [x] **Step 5: Verify catalog and router**

Run:

```bash
python3 -m pytest tests/test_env_tool_package_independence.py::EnvToolPackageIndependenceTests::test_catalog_projection_does_not_load_services_repos_or_domains -q
python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_env_tool_payload_contract.py -q
python3 -m pytest tests/test_env_tool_router.py -q
```

Expected: pass after remaining imports are updated.

## Phase 7: Delete Old Central Ownership And Legacy Services

**Objective:** Remove the old path, not preserve it.

**Files:**

- Delete `scripts/env/tools/contracts.py`
- Delete `scripts/env/tools/semantics.py`
- Delete `scripts/env/services/*.py`
- Delete `scripts/env/services/__init__.py`
- Modify tests and docs references only where tests execute runtime imports

- [x] **Step 1: Confirm no runtime imports remain**

Run:

```bash
rg -n "env\\.tools import contracts|env\\.tools\\.contracts|env\\.tools import semantics|env\\.tools\\.semantics|env\\.services" scripts tests
```

Expected before deletion: no matches in runtime code. Matches in historical docs are acceptable and must not be imported.

- [x] **Step 2: Delete old files**

Delete:

```text
scripts/env/tools/contracts.py
scripts/env/tools/semantics.py
scripts/env/services/tasks.py
scripts/env/services/tracks.py
scripts/env/services/artifacts.py
scripts/env/services/buddybox.py
scripts/env/services/context.py
scripts/env/services/evidence.py
scripts/env/services/messages.py
scripts/env/services/comments.py
scripts/env/services/search.py
scripts/env/services/source_refs.py
scripts/env/services/__init__.py
```

Remove the `scripts/env/services/` directory if it contains no tracked files.

- [x] **Step 3: Verify old path is gone**

Run:

```bash
python3 -m pytest tests/test_env_tool_package_independence.py::EnvToolPackageIndependenceTests::test_no_central_tool_ownership_tables_remain -q
python3 -m pytest tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_legacy_env_services_tool_entrypoints_are_removed -q
```

Expected: pass.

## Phase 8: Boundary And Product Coupling Cleanup

**Objective:** Keep real cross-object workflows explicit and remove accidental tool-to-tool coupling.

**Files:**

- Modify `scripts/env/domain/source_refs.py`
- Modify `scripts/env/domain/buddybox_workspace.py`
- Modify `scripts/env/tools/artifact/service.py`
- Modify `scripts/env/tools/buddybox/service.py`
- Modify `scripts/env/tools/context/service.py`
- Modify `scripts/env/tools/comment/service.py`
- Modify `scripts/env/tools/track/service.py`
- Modify `tests/test_env_layer_boundaries.py`

- [x] **Step 1: Share buddybox logical-name validation**

In `scripts/env/domain/source_refs.py`, call `env.repos.buddybox_files.normalize_logical_name` or the existing canonical repo helper for buddybox logical-name normalization.

Preserve source refs semantics:

- buddybox source refs are provenance only;
- they never grant read access;
- they store `private_to_buddy`;
- they reject buddy prefixes and traversal.

- [x] **Step 2: Keep publication in domain**

Confirm `scripts/env/tools/track/service.py` uses:

```python
from env.domain import publication as publication_domain
```

and does not import `env.tools.artifact`.

Confirm artifact service does not import track tool package.

- [x] **Step 3: Keep comment target readability in domain**

Confirm `scripts/env/tools/comment/service.py` uses:

```python
from env.domain import comment_targets as comment_target_domain
```

and does not import track or artifact tool packages.

- [x] **Step 4: Verify boundaries**

Run:

```bash
python3 -m pytest tests/test_env_layer_boundaries.py -q
```

Expected: pass.

## Phase 9: Focused Behavior Regression

**Objective:** Prove moved ownership did not change shipped tool behavior.

**Files:**

- Modify tool services only if behavior tests expose import-path mistakes or move regressions.

- [x] **Step 1: Run task, track, artifact**

```bash
python3 -m pytest tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py -q
```

Expected: pass.

- [x] **Step 2: Run buddybox and context**

```bash
python3 -m pytest tests/test_buddybox_env_tool.py tests/test_context_binding_env_tool.py -q
```

Expected: pass.

- [x] **Step 3: Run evidence, message, comment, search**

```bash
python3 -m pytest tests/test_evidence_env_tool.py tests/test_message_env_tool.py tests/test_comment_env_tool.py tests/test_search_env_tool.py -q
```

Expected: pass.

- [x] **Step 4: Run router, payload, semantic, CLI suites**

```bash
python3 -m pytest tests/test_env_tool_router.py tests/test_env_tool_payload_contract.py tests/test_env_tool_semantic_contract.py tests/test_env_client_payload_cli.py -q
```

Expected: pass.

## Phase 10: Runtime, Skill, And Full Verification

**Objective:** Prove the complete env.tool surface remains coherent.

**Files:**

- Modify only files required by failing verification.

- [x] **Step 1: Run broker and runtime status tests**

```bash
python3 -m pytest tests/test_runtime_broker.py tests/test_run_env_tool.py tests/test_turn_runtime.py -q
```

Expected: pass.

- [x] **Step 2: Run response, skill, and repo consistency tests**

```bash
python3 -m pytest tests/test_env_tool_response_contract.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Expected: pass.

- [x] **Step 3: Run architecture independence tests**

```bash
python3 -m pytest tests/test_env_tool_package_independence.py tests/test_env_layer_boundaries.py -q
```

Expected: pass.

- [x] **Step 4: Run full suite and diff check**

```bash
python3 -m pytest -q
git diff --check
```

Expected: pass.

Do not claim completion if any env.tool architecture, catalog, CLI, broker, boundary, skill, or shipped tool behavior test remains red.

Execution log (this run):

- Phase 2 Step 5:
  - `python3 - <<'PY' ... import env.tools.model/discovery/catalog/cli_helpers ... PY` -> `ok`
- Phase 3 Step 5:
  - `python3 -m pytest tests/test_env_tool_package_independence.py::EnvToolPackageIndependenceTests::test_shipped_tool_packages_own_required_files -q` -> passed
  - `python3 -m pytest tests/test_env_tool_semantic_contract.py -q` -> passed
- Phase 4 Step 6:
  - `python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_selected_dispatch_imports_no_sibling_tool_services -q` -> passed
  - `python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_unrelated_service_import_failure_does_not_block_task_tool -q` -> passed
  - `python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_selected_service_import_failure_returns_structured_feedback -q` -> passed
- Phase 5 Step 3:
  - `python3 -m pytest tests/test_env_client_payload_cli.py -q` -> passed
  - `python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_cli_operation_maps_align_with_catalog_actions -q` -> passed
- Phase 6 Step 5:
  - `python3 -m pytest tests/test_env_tool_package_independence.py::EnvToolPackageIndependenceTests::test_catalog_projection_does_not_load_services_repos_or_domains -q` -> passed
  - `python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_env_tool_payload_contract.py -q` -> passed
  - `python3 -m pytest tests/test_env_tool_router.py -q` -> passed
- Phase 7 Step 1:
  - `rg -n "env\.tools import contracts|env\.tools\.contracts|env\.tools import semantics|env\.tools\.semantics|env\.services" scripts tests`
  - result: no runtime code matches; only test scanner literals remained.
- Phase 7 Step 3:
  - `python3 -m pytest tests/test_env_tool_package_independence.py::EnvToolPackageIndependenceTests::test_no_central_tool_ownership_tables_remain -q` -> passed
  - `python3 -m pytest tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_legacy_env_services_tool_entrypoints_are_removed -q` -> passed
- Phase 8 Step 4:
  - `python3 -m pytest tests/test_env_layer_boundaries.py -q` -> passed
- User-required verification set:
  - `python3 -m pytest tests/test_env_tool_package_independence.py tests/test_env_layer_boundaries.py -q` -> `21 passed, 9 subtests passed`
  - `python3 -m pytest tests/test_env_tool_router.py tests/test_env_tool_payload_contract.py tests/test_env_tool_semantic_contract.py tests/test_env_client_payload_cli.py -q` -> `34 passed, 220 subtests passed`
  - `python3 -m pytest tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_buddybox_env_tool.py tests/test_context_binding_env_tool.py tests/test_evidence_env_tool.py tests/test_message_env_tool.py tests/test_comment_env_tool.py tests/test_search_env_tool.py -q` -> `108 passed, 81 subtests passed`
  - `python3 -m pytest tests/test_runtime_broker.py tests/test_run_env_tool.py tests/test_turn_runtime.py tests/test_env_tool_response_contract.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q` -> `78 passed, 112 subtests passed`
- Full suite:
  - first `python3 -m pytest -q` run exposed launcher smoke mismatch (`search status --query` legacy args); fixed test smoke command to `search status`.
  - final `python3 -m pytest -q` -> `510 passed, 529 subtests passed`
  - `git diff --check` -> passed

## Final Acceptance Checklist

- [x] Current shipped tools and actions are unchanged.
- [x] Every shipped tool has `contract.py`, `semantics.py`, `cli.py`, `handlers.py`, and `service.py`.
- [x] No central `TOOL_REGISTRY` remains.
- [x] No central `_CAPABILITIES` or central action semantic table remains.
- [x] No central `HANDLER_SPECS_BY_TOOL` remains.
- [x] `scripts/env/client.py` has no per-tool `_dispatch_<tool>` branches.
- [x] `scripts/env/tools/contracts.py` is deleted.
- [x] `scripts/env/tools/semantics.py` is deleted.
- [x] `scripts/env/services` no longer contains tool entrypoints.
- [x] Public catalog/router/dispatch/client imports are service-light.
- [x] Dispatching a selected tool imports no sibling tool service.
- [x] Broken non-selected tool service does not block healthy selected dispatch.
- [x] Broken selected tool service returns structured `E_ENV_TOOL_DISPATCH` feedback.
- [x] Broken non-selected tool metadata is reported without crashing healthy dispatch.
- [x] Tool packages do not import sibling tool packages.
- [x] Product cross-object behavior stays in explicit domain modules.
- [x] A temporary local probe tool package is discovered without central source edits.
- [x] Runtime catalog and operation semantics are generated from per-tool packages.
- [x] CLI operations are registered from per-tool packages and align with catalog actions.
- [x] Existing shipped tool behavior suites pass.
- [x] Runtime broker, status, response, skill, repo consistency, and boundary suites pass.
- [x] Full `python3 -m pytest -q` passes.
- [x] `git diff --check` passes.
