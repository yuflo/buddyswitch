# Tool Independence Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Runtime code changes must follow `superpowers:test-driven-development`: write and verify each failing test before implementation.

**Goal:** Make env.tool runtime dispatch and payload contracts independent enough that one tool failure cannot break unrelated tools, and the registry/catalog/CLI/service payload surface has one current source of truth.

**Architecture:** Keep the monolithic env.tool runtime, but replace eager service imports with selected-tool lazy loading. Keep `contracts.TOOL_REGISTRY` as the authoritative action and payload source; services validate payload fields from this registry instead of duplicated allowlists. Remove ignored fields directly and expose real fields directly; do not keep compatibility shims or dual behavior.

**Tech Stack:** Python 3.9-compatible runtime code, `scripts/env/tools/**`, `scripts/env/services/**`, `scripts/env/domain/messages.py`, `scripts/env/client.py`, broker/router tests using `pytest`/`unittest`, subprocess import checks under default `python3`.

---

## Source Inputs

Read these before editing runtime code:

- `AGENTS.md`
- `docs/memo/2026-05-19-worktree-independence-review-memo.md`
- `docs/spec/2026-05-19-tool-independence-repair-scope.md`
- `docs/spec/2026-05-19-tool-independence-repair-test-plan.md`
- `scripts/env/domain/messages.py`
- `scripts/env/tools/contracts.py`
- `scripts/env/tools/semantics.py`
- `scripts/env/tools/dispatch.py`
- `scripts/env/tools/router.py`
- `scripts/env/client.py`
- `scripts/env/services/tasks.py`
- `scripts/env/services/tracks.py`
- `scripts/env/services/comments.py`
- `scripts/env/services/artifacts.py`
- `scripts/env/services/buddybox.py`
- `scripts/env/services/context.py`
- `scripts/env/services/evidence.py`
- `scripts/env/services/messages.py`
- `scripts/env/services/search.py`
- `tests/test_env_tool_router.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_task_env_tool.py`
- `tests/test_track_env_tool.py`
- `tests/test_comment_env_tool.py`

## File Change Map

- Modify `scripts/env/domain/messages.py`
  - Make `GetMessage` Python 3.9-safe by using `Optional[dict[str, Any]]` inside `Callable`.

- Modify `scripts/env/tools/contracts.py`
  - Add a public helper that returns registry payload fields for a tool/action.
  - Update comment payload fields to match active comment capability.
  - Keep `TOOL_REGISTRY` as the only authoritative payload source.

- Modify `scripts/env/tools/semantics.py`
  - Update comment capability/action text so `status` filtering is not described as unsupported lifecycle mutation.
  - Add `anchor`, `artifact_revision_id`, `mentions`, and `status` to comment input explanations.

- Modify `scripts/env/tools/dispatch.py`
  - Replace eager service imports with a static string handler-spec map.
  - Load only the selected tool/action handler at dispatch time.
  - Return structured `E_ENV_TOOL_DISPATCH` feedback when the selected handler cannot be loaded.
  - Keep `dispatch_handler_actions()` service-light and registry-aligned.

- Modify `scripts/env/tools/router.py`
  - Keep router imports service-light.
  - Planned code edit: none. If verification shows dispatch feedback lacks top-level `tool` or `action`, set those defaults in `dispatch_env_tool_request` immediately after dispatch returns.

- Modify `scripts/env/client.py`
  - Add optional `--status` to `comment list`.
  - Include status in the dispatched comment list payload only when provided.

- Modify env services that validate payload fields:
  - `scripts/env/services/tasks.py`
  - `scripts/env/services/tracks.py`
  - `scripts/env/services/comments.py`
  - `scripts/env/services/artifacts.py`
  - `scripts/env/services/buddybox.py`
  - `scripts/env/services/context.py`
  - `scripts/env/services/evidence.py`
  - `scripts/env/services/search.py`
  - `scripts/env/services/messages.py`

  Services must validate fields by calling `contracts.payload_fields_for_action(tool, action)`. Do not keep duplicated service allowlists that can drift.

- Modify `tests/test_env_tool_router.py`
  - Add Python 3.9 import tests.
  - Add service-light import tests.
  - Add unrelated-service-failure and selected-service-failure tests.
  - Keep existing registry/CLI coverage tests green.

- Add `tests/test_env_tool_payload_contract.py`
  - Assert registry/catalog/service accepted payload field alignment.

- Modify `tests/test_task_env_tool.py`
  - Add rejections for `task.create` with `buddy` and `active_buddy`.

- Modify `tests/test_track_env_tool.py`
  - Add rejections for `track.update_now` and `track.add_update` with `owner_buddy`.

- Modify `tests/test_env_tool_semantic_contract.py`
  - Add explicit comment payload field assertions.

- Modify `tests/test_comment_env_tool.py`
  - Keep advanced comment field behavior green; add focused assertions only if existing tests do not cover a newly exposed field.

- Modify `buddyswitch/skills/shared/task-tool/SKILL.md`
  - Remove any `task.create` example that sends `buddy` or `active_buddy`.
  - Keep exact payload guidance routed to runtime catalog discovery.

## Phase 1: Python3 Import Compatibility

**Objective:** Default `python3` can import env.tool modules.

**Files:**

- Modify `tests/test_env_tool_router.py`
- Modify `scripts/env/domain/messages.py`

- [ ] **Step 1: Add failing import test**

Add `test_python3_imports_env_tool_modules` to `EnvToolRouterTests`:

```python
def test_python3_imports_env_tool_modules(self) -> None:
    script = """
import sys
from pathlib import Path
root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))
import env.tools.contracts
import env.tools.router
import env.tools.dispatch
print("ok")
"""
    completed = subprocess.run(
        ["python3", "-c", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    self.assertEqual(completed.returncode, 0, msg=completed.stderr)
    self.assertEqual(completed.stdout.strip(), "ok")
```

- [ ] **Step 2: Verify red**

Run:

```bash
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_python3_imports_env_tool_modules -q
```

Expected before implementation: FAIL with `TypeError` from `env.domain.messages.GetMessage`.

- [ ] **Step 3: Make message callable alias Python 3.9-safe**

In `scripts/env/domain/messages.py`, change:

```python
from typing import Any, Callable, TypedDict
```

to:

```python
from typing import Any, Callable, Optional, TypedDict
```

and change:

```python
GetMessage = Callable[[str], dict[str, Any] | None]
```

to:

```python
GetMessage = Callable[[str], Optional[dict[str, Any]]]
```

- [ ] **Step 4: Verify green**

Run:

```bash
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_python3_imports_env_tool_modules -q
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions -q
```

Expected: both pass under default `python3`.

## Phase 2: Service-Light Router And Lazy Dispatch

**Objective:** Importing router/dispatch no longer imports services; selected dispatch loads only the selected service.

**Files:**

- Modify `tests/test_env_tool_router.py`
- Modify `scripts/env/tools/dispatch.py`

- [ ] **Step 1: Add failing service-light import test**

Add `test_env_tool_imports_do_not_load_services`:

```python
def test_env_tool_imports_do_not_load_services(self) -> None:
    script = """
import json
import sys
from pathlib import Path
root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))
import env.tools.contracts
import env.tools.router
import env.tools.dispatch
loaded = sorted(name for name in sys.modules if name.startswith("env.services."))
print(json.dumps(loaded))
"""
    completed = subprocess.run(
        ["python3", "-c", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    self.assertEqual(completed.returncode, 0, msg=completed.stderr)
    self.assertEqual(json.loads(completed.stdout), [])
```

- [ ] **Step 2: Verify red**

Run:

```bash
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_env_tool_imports_do_not_load_services -q
```

Expected before implementation: FAIL because `dispatch.py` imports services eagerly.

- [ ] **Step 3: Replace eager imports with handler specs**

In `scripts/env/tools/dispatch.py`:

- remove all `from env.services import ...` imports;
- import `importlib`;
- define handler specs as module/function strings;
- resolve only selected handlers.

Use this shape:

```python
import importlib

HandlerSpec = tuple[str, str]

HANDLER_SPECS_BY_TOOL: dict[str, dict[str, HandlerSpec]] = {
    "task": {
        "create": ("env.services.tasks", "create_task_for_active_buddy"),
        "list": ("env.services.tasks", "list_tasks_for_active_buddy"),
        "get": ("env.services.tasks", "get_task_for_active_buddy"),
        "update": ("env.services.tasks", "update_task_for_active_buddy"),
        "archive": ("env.services.tasks", "archive_task_for_active_buddy"),
    },
    "track": {
        "create": ("env.services.tracks", "create_track_for_pm"),
        "list": ("env.services.tracks", "list_tracks_for_active_buddy"),
        "open": ("env.services.tracks", "open_track_for_active_buddy"),
        "update_now": ("env.services.tracks", "update_now_for_active_buddy"),
        "add_material": ("env.services.tracks", "add_material_to_track"),
        "add_update": ("env.services.tracks", "add_update_to_track"),
        "add_proof": ("env.services.tracks", "add_proof_to_track"),
        "archive": ("env.services.tracks", "archive_track_for_pm"),
    },
    "artifact": {
        "get": ("env.services.artifacts", "get_artifact_for_active_buddy"),
        "create_revision": ("env.services.artifacts", "create_artifact_revision"),
        "update_metadata": ("env.services.artifacts", "update_artifact_metadata"),
    },
    "buddybox": {
        "desc": ("env.services.buddybox", "describe_buddybox_for_active_buddy"),
        "list": ("env.services.buddybox", "list_buddybox_for_active_buddy"),
        "read": ("env.services.buddybox", "read_buddybox_for_active_buddy"),
        "write": ("env.services.buddybox", "write_buddybox_for_active_buddy"),
        "delete": ("env.services.buddybox", "delete_buddybox_for_active_buddy"),
    },
    "context": {
        "get": ("env.services.context", "get_context"),
        "summarize": ("env.services.context", "summarize_context"),
        "list_sources": ("env.services.context", "list_sources"),
    },
    "evidence": {
        "issue_browser": ("env.services.evidence", "issue_browser_for_active_instance"),
        "approve_downgrade": ("env.services.evidence", "approve_downgrade_for_active_instance"),
    },
    "message": {
        "send": ("env.services.messages", "send_message"),
        "list": ("env.services.messages", "list_messages"),
    },
    "comment": {
        "add": ("env.services.comments", "add_comment"),
        "list": ("env.services.comments", "list_comments"),
    },
    "search": {
        "status": ("env.services.search", "status_for_active_instance"),
        "request": ("env.services.search", "request_for_active_instance"),
        "open_browser": ("env.services.search", "open_browser_for_active_instance"),
    },
}


def dispatch_handler_actions() -> dict[str, set[str]]:
    return {tool: set(action_map) for tool, action_map in HANDLER_SPECS_BY_TOOL.items()}


def _load_handler(*, tool: str, action: str) -> Any:
    module_name, function_name = HANDLER_SPECS_BY_TOOL[tool][action]
    module = importlib.import_module(module_name)
    handler = getattr(module, function_name)
    if not callable(handler):
        raise TypeError(f"handler is not callable: {module_name}.{function_name}")
    return handler
```

Do not keep `HANDLERS_BY_TOOL` with imported functions.

- [ ] **Step 4: Return structured selected-load errors**

In `dispatch_registered_env_tool`, load the handler before building context:

```python
    semantic_action = f"{tool}.{action}"
    try:
        handler = _load_handler(tool=tool, action=action)
    except Exception as exc:
        return _runtime_feedback_error(
            tool=tool,
            action=semantic_action,
            active_buddy=active_buddy,
            code="E_ENV_TOOL_DISPATCH",
            message=f"failed to load env tool handler for {semantic_action}: {exc}",
            details={
                "permission_boundary": "env.tool.dispatch",
                "human_summary": "Selected env tool handler could not be loaded.",
                "why_blocked": str(exc),
                "impact": "No handler ran and no runtime state changed.",
                "state_changed": False,
                "retryable": False,
                "retry_guidance": "Fix the selected tool implementation before retrying this action.",
                "allowed_next_actions": ["Use another registered tool that does not depend on this handler."],
            },
        )
```

Keep the existing handler execution `except (ValueError, OSError)` block for service-level runtime rejections.

- [ ] **Step 5: Verify service-light green**

Run:

```bash
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_env_tool_imports_do_not_load_services -q
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions -q
```

Expected: pass.

## Phase 3: Failure Isolation Tests

**Objective:** Prove a broken unrelated service does not block healthy tools, and a broken selected service fails locally.

**Files:**

- Modify `tests/test_env_tool_router.py`
- Modify `scripts/env/tools/dispatch.py` if Phase 2 handling is incomplete.

- [ ] **Step 1: Add subprocess helper in router tests**

Add a helper method to `EnvToolRouterTests`:

```python
def _run_router_subprocess_with_blocked_message_service(
    self,
    *,
    instance_json: Path,
    payload: dict[str, object],
    buddy: str = "dev",
) -> subprocess.CompletedProcess[str]:
    payload_json = json.dumps(payload, ensure_ascii=True)
    script = f"""
import importlib.abc
import json
import sys
from pathlib import Path

root = Path({str(ROOT)!r})
sys.path.insert(0, str(root / "scripts"))

class BlockMessages(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "env.services.messages":
            raise RuntimeError("blocked message service import")
        return None

sys.meta_path.insert(0, BlockMessages())

import env_manifest
from env.tools.router import dispatch_env_tool_request

manifest_path = Path({str(MANIFEST)!r})
instance_json = Path({str(instance_json)!r})
instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
payload = json.loads({payload_json!r})
response = dispatch_env_tool_request(
    payload=payload,
    active_buddy={buddy!r},
    instance_id=instance_payload["instance_id"],
    instance_json=instance_json,
    instance_payload=instance_payload,
    manifest=env_manifest.load_manifest(manifest_path),
    manifest_path=manifest_path,
)
print(json.dumps(response, sort_keys=True))
"""
    return subprocess.run(
        ["python3", "-c", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
```

- [ ] **Step 2: Add unrelated-service failure test**

```python
def test_unrelated_service_import_failure_does_not_block_task_tool(self) -> None:
    instance_json = self._instance_json(instance_id="inst-dev-isolation", buddy="dev")
    completed = self._run_router_subprocess_with_blocked_message_service(
        instance_json=instance_json,
        payload={"tool": "task", "action": "list", "args": {}},
        buddy="dev",
    )
    self.assertEqual(completed.returncode, 0, msg=completed.stderr)
    response = json.loads(completed.stdout)
    self.assertTrue(response.get("ok"), msg=response)
    self.assertEqual(response.get("tool"), "task")
    self.assertEqual(response.get("action"), "task.list")
    self.assertIs(response.get("state_changed"), False)
```

- [ ] **Step 3: Add selected-service failure test**

```python
def test_selected_service_import_failure_returns_structured_feedback(self) -> None:
    instance_json = self._instance_json(instance_id="inst-dev-selected-failure", buddy="dev")
    completed = self._run_router_subprocess_with_blocked_message_service(
        instance_json=instance_json,
        payload={"tool": "message", "action": "list", "args": {}},
        buddy="dev",
    )
    self.assertEqual(completed.returncode, 0, msg=completed.stderr)
    response = json.loads(completed.stdout)
    self.assertFalse(response.get("ok"), msg=response)
    self.assertEqual(response.get("tool"), "message")
    self.assertEqual(response.get("action"), "message.list")
    self.assertEqual((response.get("error") or {}).get("code"), "E_ENV_TOOL_DISPATCH")
    self.assertEqual(response.get("permission_boundary"), "env.tool.dispatch")
    self.assertIs(response.get("state_changed"), False)
    self.assertIs(response.get("retryable"), False)
    self.assertIn("blocked message service import", str(response.get("why_blocked")))
```

- [ ] **Step 4: Verify red/green**

Run before implementation if not already implemented:

```bash
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_unrelated_service_import_failure_does_not_block_task_tool -q
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_selected_service_import_failure_returns_structured_feedback -q
```

Expected after Phase 2: both pass.

## Phase 4: Registry-Backed Payload Field Validation

**Objective:** Remove duplicated service payload allowlists and make `contracts.TOOL_REGISTRY` the payload source used by runtime validation.

**Files:**

- Add `tests/test_env_tool_payload_contract.py`
- Modify `scripts/env/tools/contracts.py`
- Modify service files listed in the file map.

- [ ] **Step 1: Add contract helper tests**

Create `tests/test_env_tool_payload_contract.py` with:

```python
#!/usr/bin/env python3
"""Payload field contract alignment for env.tool actions."""

from __future__ import annotations

import ast
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
from env.tools import contracts  # noqa: E402
from env.tools.router import dispatch_env_tool_request  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"


class EnvToolPayloadContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self) -> Path:
        path = self._runtime_path("instance-payload-contract.json")
        path.write_text(
            json.dumps(
                {
                    "instance_id": "inst-payload-contract",
                    "buddy": "dev",
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "created_at": "2026-05-19T00:00:00Z",
                    "updated_at": "2026-05-19T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _dispatch(self, *, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        instance_json = self._instance_json()
        instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
        return dispatch_env_tool_request(
            payload={"tool": tool, "action": action, "args": args},
            active_buddy="dev",
            instance_id="inst-payload-contract",
            instance_json=instance_json,
            instance_payload=instance_payload,
            manifest=env_manifest.load_manifest(MANIFEST),
            manifest_path=MANIFEST,
        )

    def test_payload_field_helper_matches_registry(self) -> None:
        for tool_spec in contracts.TOOL_REGISTRY:
            tool = tool_spec["tool"]
            for action_spec in tool_spec["actions"]:
                action = action_spec["name"]
                with self.subTest(tool=tool, action=action):
                    self.assertEqual(
                        contracts.payload_fields_for_action(tool, action),
                        set(action_spec.get("payload_fields", [])),
                    )

    def test_runtime_catalog_payload_fields_match_registry_order(self) -> None:
        desc = contracts.env_tools_description()
        for tool_spec in contracts.TOOL_REGISTRY:
            tool = tool_spec["tool"]
            for action_spec in tool_spec["actions"]:
                action = action_spec["name"]
                with self.subTest(tool=tool, action=action):
                    self.assertEqual(
                        desc[tool]["payload_fields"][action],
                        list(action_spec.get("payload_fields", [])),
                    )

    def test_every_action_rejects_unregistered_payload_field_without_state_change(self) -> None:
        for tool_spec in contracts.TOOL_REGISTRY:
            tool = tool_spec["tool"]
            for action_spec in tool_spec["actions"]:
                action = action_spec["name"]
                with self.subTest(tool=tool, action=action):
                    response = self._dispatch(
                        tool=tool,
                        action=action,
                        args={"__unexpected_payload_field__": True},
                    )
                    self.assertFalse(response.get("ok"), msg=response)
                    self.assertIs(response.get("state_changed"), False, msg=response)
                    self.assertIn("__unexpected_payload_field__", json.dumps(response, ensure_ascii=True))

    def test_services_and_message_domain_do_not_define_duplicate_payload_field_sets(self) -> None:
        allowed_names = {"_LEGACY_SOURCE_RUN"}
        service_root = ROOT / "scripts" / "env" / "services"
        violations: list[str] = []
        for path in sorted(service_root.glob("*.py")):
            if path.name == "__init__.py":
                continue
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    name = target.id
                    if name in allowed_names:
                        continue
                    if name.endswith("_FIELDS"):
                        violations.append(f"{path.relative_to(ROOT)}:{node.lineno}: {name}")

        message_domain = ROOT / "scripts" / "env" / "domain" / "messages.py"
        message_tree = ast.parse(message_domain.read_text(encoding="utf-8"), filename=str(message_domain))
        for node in ast.walk(message_tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"_SEND_FIELDS", "_LIST_FIELDS"}:
                    violations.append(f"{message_domain.relative_to(ROOT)}:{node.lineno}: {target.id}")

        self.assertEqual(violations, [], msg="\n".join(violations))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Verify red**

Run:

```bash
python3 -m pytest tests/test_env_tool_payload_contract.py -q
```

Expected before implementation: FAIL because `payload_fields_for_action` does not exist. After adding the helper, this suite must still fail until duplicated service/message-domain field sets are removed and every action rejects `__unexpected_payload_field__`.

- [ ] **Step 3: Add payload helper**

In `scripts/env/tools/contracts.py`, add:

```python
def payload_fields_for_action(tool: str, action: str) -> set[str]:
    spec = get_action_spec(tool, action)
    if spec is None:
        return set()
    return {
        field
        for field in spec.get("payload_fields", [])
        if isinstance(field, str)
    }
```

- [ ] **Step 4: Replace duplicated service allowlists**

In each service, replace hard-coded allowed field selection with registry-backed selection.

Example for `scripts/env/services/tasks.py`:

```python
from env.tools import contracts as tool_contracts
from env.tools import responses as tool_responses


def _allowed_set(action: str) -> set[str]:
    tool, action_name = action.split(".", 1)
    return tool_contracts.payload_fields_for_action(tool, action_name)
```

Apply the same pattern to:

- `scripts/env/services/tracks.py`
- `scripts/env/services/comments.py`
- `scripts/env/services/artifacts.py`
- `scripts/env/services/buddybox.py`
- `scripts/env/services/context.py`
- `scripts/env/services/evidence.py`
- `scripts/env/services/search.py`

For `scripts/env/domain/messages.py`, replace `_SEND_FIELDS` and `_LIST_FIELDS` with explicit function parameters:

```python
def prepare_send_request(
    *,
    args: dict[str, Any],
    active_buddy: str,
    manifest_buddy_ids: set[str],
    get_message: GetMessage,
    allowed_fields: set[str],
) -> SendRequest:
    unknown = sorted(key for key in args if key not in allowed_fields)
    ...


def prepare_list_request(*, args: dict[str, Any], manifest_buddy_ids: set[str], allowed_fields: set[str]) -> ListRequest:
    unknown = sorted(key for key in args if key not in allowed_fields)
    ...
```

In `scripts/env/services/messages.py`, call those functions with:

```python
allowed_fields=tool_contracts.payload_fields_for_action("message", "send")
```

and:

```python
allowed_fields=tool_contracts.payload_fields_for_action("message", "list")
```

Keep message payload and scope errors in the message domain.

Do not add a second registry or compatibility allowlist.

- [ ] **Step 5: Verify helper tests green**

Run:

```bash
python3 -m pytest tests/test_env_tool_payload_contract.py -q
```

Expected: pass.

## Phase 5: Remove Ignored Task Fields

**Objective:** `task.create` rejects `buddy` and `active_buddy` instead of accepting and ignoring them.

**Files:**

- Modify `tests/test_task_env_tool.py`
- Modify `scripts/env/services/tasks.py` through the registry-backed helper from Phase 4.
- Modify `buddyswitch/skills/shared/task-tool/SKILL.md`

- [ ] **Step 1: Add task rejection tests**

Add:

```python
def test_task_create_rejects_buddy_field_without_state_mutation(self) -> None:
    before_tasks = self._snapshot_json_dir("buddyswitch/objects/tasks")
    instance_json = self._instance_json(instance_id="inst-dev-task-buddy-field", buddy="dev")
    rejected = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-dev-task-buddy-field",
        buddy="dev",
        tool="task",
        action="create",
        args={
            "task_id": "task-dev-reject-buddy",
            "title": "Reject buddy field",
            "summary": "should not create",
            "buddy": "design",
        },
    )
    self.assertFalse(rejected.get("ok"), msg=rejected)
    self.assertEqual(rejected.get("permission_boundary"), "request-payload")
    self.assertIs(rejected.get("state_changed"), False)
    self.assertIn("buddy", str(rejected.get("why_blocked")))
    self.assertEqual(self._snapshot_json_dir("buddyswitch/objects/tasks"), before_tasks)


def test_task_create_rejects_active_buddy_field_without_state_mutation(self) -> None:
    before_tasks = self._snapshot_json_dir("buddyswitch/objects/tasks")
    instance_json = self._instance_json(instance_id="inst-dev-task-active-buddy-field", buddy="dev")
    rejected = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-dev-task-active-buddy-field",
        buddy="dev",
        tool="task",
        action="create",
        args={
            "task_id": "task-dev-reject-active-buddy",
            "title": "Reject active buddy field",
            "summary": "should not create",
            "active_buddy": "pm",
        },
    )
    self.assertFalse(rejected.get("ok"), msg=rejected)
    self.assertEqual(rejected.get("permission_boundary"), "request-payload")
    self.assertIs(rejected.get("state_changed"), False)
    self.assertIn("active_buddy", str(rejected.get("why_blocked")))
    self.assertEqual(self._snapshot_json_dir("buddyswitch/objects/tasks"), before_tasks)
```

- [ ] **Step 2: Verify red**

Run:

```bash
python3 -m pytest tests/test_task_env_tool.py::TaskEnvToolTests::test_task_create_rejects_buddy_field_without_state_mutation -q
python3 -m pytest tests/test_task_env_tool.py::TaskEnvToolTests::test_task_create_rejects_active_buddy_field_without_state_mutation -q
```

Expected before implementation: FAIL because the service accepts these fields.

- [ ] **Step 3: Remove task field acceptance**

Ensure `scripts/env/services/tasks.py` no longer includes `buddy` or `active_buddy` in any create allowlist. With Phase 4, no separate change should be needed beyond deleting old constants.

- [ ] **Step 4: Remove stale skill example**

In `buddyswitch/skills/shared/task-tool/SKILL.md`, remove any example payload containing `"buddy"` or `"active_buddy"`. Keep text that says exact payload fields come from `context.get.tool_catalog['task']`.

- [ ] **Step 5: Verify green**

Run:

```bash
python3 -m pytest tests/test_task_env_tool.py -q
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py::RepoConsistencyTests::test_skill_and_contract_texts_do_not_copy_payload_field_or_schema_tables -q
```

Expected: pass.

## Phase 6: Track And Comment Payload Drift Cleanup

**Objective:** Reject non-contract track owner payload fields and expose real comment fields.

**Files:**

- Modify `tests/test_track_env_tool.py`
- Modify `tests/test_env_tool_semantic_contract.py`
- Modify `tests/test_env_tool_router.py`
- Modify `scripts/env/tools/contracts.py`
- Modify `scripts/env/tools/semantics.py`
- Modify `scripts/env/services/tracks.py`
- Modify `scripts/env/services/comments.py`
- Modify `scripts/env/client.py`

- [ ] **Step 1: Add track owner-field tests**

In `tests/test_track_env_tool.py`, add tests matching PC5 and PC6 from the test plan. Snapshot the track JSON file before dispatch and assert it is byte-for-byte unchanged after rejection.

- [ ] **Step 2: Verify red**

Run:

```bash
python3 -m pytest tests/test_track_env_tool.py::TrackEnvToolTests::test_update_now_rejects_owner_buddy_without_state_mutation -q
python3 -m pytest tests/test_track_env_tool.py::TrackEnvToolTests::test_add_update_rejects_owner_buddy_without_state_mutation -q
```

Expected before implementation: FAIL because the rejection message is the special immutable-field branch rather than unsupported field, or because allowed fields still drift from registry.

- [ ] **Step 3: Remove owner_buddy from track service acceptance**

In `scripts/env/services/tracks.py`:

- delete `_UPDATE_NOW_FIELDS` and `_ADD_UPDATE_FIELDS` if Phase 4 has not already removed the old constants;
- delete the `if "owner_buddy" in args:` branches in `update_now_for_active_buddy`;
- delete the `if "owner_buddy" in args:` branch in `add_update_to_track`;
- delete the dead `if "owner_buddy" in args:` branch in `create_track_for_pm`;
- rely on `_require_fields` to reject it as an unsupported payload field.

- [ ] **Step 4: Add comment payload registry test**

In `tests/test_env_tool_semantic_contract.py`, add:

```python
def test_comment_payload_fields_match_active_comment_capability(self) -> None:
    desc = contracts.env_tools_description()
    comment_fields = desc["comment"]["payload_fields"]
    self.assertEqual(
        comment_fields["add"],
        ["target_type", "target_id", "content", "reply_to", "artifact_revision_id", "anchor", "mentions"],
    )
    self.assertEqual(comment_fields["list"], ["target_type", "target_id", "status"])
```

- [ ] **Step 5: Verify red**

Run:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_comment_payload_fields_match_active_comment_capability -q
```

Expected before implementation: FAIL because registry omits active comment fields.

- [ ] **Step 6: Update comment registry and semantics**

In `scripts/env/tools/contracts.py`:

- change `comment.add` payload fields to:

```python
["target_type", "target_id", "content", "reply_to", "artifact_revision_id", "anchor", "mentions"]
```

- change `comment.list` payload fields to:

```python
["target_type", "target_id", "status"]
```

In `scripts/env/tools/semantics.py`, update comment action `inputs_explained` and common failures so the newly exposed fields are described as active capability, not hidden service options.

- [ ] **Step 7: Add comment CLI status**

In `scripts/env/client.py`:

- add `comment_list.add_argument("--status")`;
- include `status` in `_dispatch_comment` list payload only when provided:

```python
payload = {"target_type": args.target_type, "target_id": args.target_id}
if isinstance(args.status, str) and args.status.strip():
    payload["status"] = args.status.strip()
return _dispatch_env_tool("comment", action, payload)
```

- [ ] **Step 8: Verify green**

Run:

```bash
python3 -m pytest tests/test_track_env_tool.py -q
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
python3 -m pytest tests/test_comment_env_tool.py -q
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_cli_operation_maps_align_with_registry_actions -q
```

Expected: pass.

## Phase 7: Full Tool Surface Verification

**Objective:** Prove the complete task is done, not just the first failure.

**Files:**

- No new production files expected.
- Modify tests only if verification identifies an uncovered requirement from the test plan.

- [ ] **Step 1: Run focused tool contract suites**

```bash
python3 -m pytest tests/test_env_tool_router.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_payload_contract.py -q
```

Expected: pass.

- [ ] **Step 2: Run affected behavior suites**

```bash
python3 -m pytest tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_comment_env_tool.py -q
python3 -m pytest tests/test_message_env_tool.py tests/test_artifact_env_tool.py tests/test_buddybox_env_tool.py -q
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_evidence_env_tool.py tests/test_search_env_tool.py -q
```

Expected: pass.

- [ ] **Step 3: Run broker/CLI/boundary consistency**

```bash
python3 -m pytest tests/test_env_client_payload_cli.py tests/test_runtime_broker.py -q
python3 -m pytest tests/test_env_layer_boundaries.py tests/test_repo_consistency.py tests/test_runtime_skills.py -q
```

Expected: pass.

- [ ] **Step 4: Run full suite and diff check**

```bash
python3 -m pytest -q
git diff --check
```

Expected: pass.

If full suite failure is unrelated to this task, record the exact failing test, command output summary, and why the focused coverage still proves this repair. Do not claim full completion if a relevant tool test remains red.

## Final Acceptance Checklist

- [ ] `python3` is still Python 3.9.x or the documented default launcher interpreter, and env.tool tests pass under it.
- [ ] `env.tools.router` import is service-light.
- [ ] `env.tools.dispatch` import is service-light.
- [ ] Unrelated service import failure does not block `task.list`.
- [ ] Selected service import failure returns `E_ENV_TOOL_DISPATCH`.
- [ ] `dispatch_handler_actions()` matches `contracts.TOOL_REGISTRY`.
- [ ] Runtime status/catalog payload fields match registry.
- [ ] CLI operations match registry.
- [ ] `task.create` rejects `buddy` and `active_buddy`.
- [ ] `track.update_now` and `track.add_update` reject `owner_buddy`.
- [ ] Comment registry exposes active comment fields.
- [ ] Existing tool behavior suites pass.
- [ ] Skill docs no longer show stale task owner payload fields.
- [ ] No compatibility shim, fallback registry, or dual dispatch path remains.
- [ ] `git diff --check` passes.
