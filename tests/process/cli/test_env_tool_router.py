"""Contract tests for registry-based env.tool dispatch."""

from __future__ import annotations

import importlib.abc
import json
import subprocess
import sys
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process

ROOT = REPO_ROOT

from buddyswitch.foundation.tool_runtime import registry as tool_registry  # noqa: E402
from tests.support.python import PYTHON  # noqa: E402
from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402

EXPECTED_TOOLS = {"track", "artifact", "context", "demand_sys", "evidence", "search", "message", "task_sys"}


class EnvToolRouterTests(RuntimeWorkspaceTestCase):
    _CHEAP_ACTION_CASES = (
        ("task_sys", "list", {}, "dev"),
        ("demand_sys", "list", {}, "dev"),
        ("track", "list", {}, "dev"),
        ("artifact", "get", {"artifact_id": "missing-artifact"}, "dev"),
        ("context", "list_sources", {}, "dev"),
        ("evidence", "issue_browser", {}, "dev"),
        ("message", "list", {}, "dev"),
        ("track", "list_comments", {"track_id": "missing-track"}, "dev"),
        ("search", "status", {}, "dev"),
    )

    def _instance_json(self, *, actor_id: str = "act-dev-example", role: str = "dev") -> Path:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        path = self._runtime_path("instance.json")
        path.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": role,
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "updated_at": "2026-05-20T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self._seed_active_task_for_instance(
            instance_json=path,
            role=role,
            actor_id=actor_id,
            task_slug=f"{role}-router",
        )
        return path

    def _dispatch_env_tool(
        self,
        *,
        payload: dict[str, object],
        instance_json: Path,
        actor_id: str = "act-dev-example",
        role: str = "dev",
    ) -> dict[str, object]:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
        return tool_registry.dispatch_env_tool_request(
            payload=payload,
            active_role=role,
            actor_id=actor_id,
            instance_json=instance_json,
            instance_payload=instance_payload,
        )

    def _assert_role_auth_receipt(
        self,
        response: dict[str, object],
        *,
        required_permission: str,
        active_role: str,
    ) -> None:
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_TOOL_ROLE_AUTH")
        self.assertEqual(response.get("permission_boundary"), "tool.role_authority")
        self.assertEqual(response.get("category"), "auth_denied")
        self.assertEqual(response.get("auth_source"), "env.tool role-action policy")
        self.assertEqual(response.get("auth_stage"), "pre_dispatch")
        self.assertIs(response.get("executed"), False)
        self.assertEqual(response.get("required_permission"), required_permission)
        self.assertEqual(response.get("active_role"), active_role)
        self.assertEqual(response.get("allowed_roles"), ["pm"])
        self.assertIs(response.get("state_changed"), False)
        self.assertEqual(response.get("durability"), "none")
        why_blocked = str(response.get("why_blocked", ""))
        self.assertIn("role-action policy", why_blocked)
        self.assertNotIn("requires permission", why_blocked)
        self.assertNotIn("owns permission", why_blocked)

    def _run_router_subprocess_with_blocked_message_impl(
        self,
        *,
        instance_json: Path,
        payload: dict[str, object],
        role: str = "dev",
    ) -> subprocess.CompletedProcess[str]:
        payload_json = json.dumps(payload, ensure_ascii=True)
        script = f"""
import importlib.abc
import json
import sys
from pathlib import Path

class BlockMessageImpl(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "buddyswitch.modules.communication.private.adapters.tool._impl":
            raise RuntimeError("blocked message _impl import")
        return None

sys.meta_path.insert(0, BlockMessageImpl())

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.tool_runtime.registry import dispatch_env_tool_request

activate_application()
instance_json = Path({str(instance_json)!r})
instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
response = dispatch_env_tool_request(
    payload=json.loads({payload_json!r}),
    active_role={role!r},
    actor_id=instance_payload["actor_id"],
    instance_json=instance_json,
    instance_payload=instance_payload,
)
print(json.dumps(response, sort_keys=True))
"""
        return run_process(
            [PYTHON, "-c", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def _run_router_subprocess_with_blocked_impl(
        self,
        *,
        instance_json: Path,
        payload: dict[str, object],
        blocked_module: str,
        role: str = "dev",
    ) -> subprocess.CompletedProcess[str]:
        payload_json = json.dumps(payload, ensure_ascii=True)
        script = f"""
import importlib.abc
import json
import sys
from pathlib import Path

class BlockSelectedImpl(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == {blocked_module!r}:
            raise RuntimeError("blocked selected _impl import")
        return None

sys.meta_path.insert(0, BlockSelectedImpl())

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.tool_runtime.registry import dispatch_env_tool_request

activate_application()
instance_json = Path({str(instance_json)!r})
instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
response = dispatch_env_tool_request(
    payload=json.loads({payload_json!r}),
    active_role={role!r},
    actor_id=instance_payload["actor_id"],
    instance_json=instance_json,
    instance_payload=instance_payload,
)
loaded = sorted(
    name
    for name in sys.modules
    if name.endswith("._impl")
    and name.startswith("buddyswitch.modules.demand.private.adapters.tool.")
)
print(json.dumps({{"response": response, "loaded": loaded}}, sort_keys=True))
"""
        return run_process(
            [PYTHON, "-c", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_registry_surface_matches_expected_tools(self) -> None:
        tools = set(tool_registry.supported_tools())
        self.assertEqual(tools, EXPECTED_TOOLS)
        self.assertNotIn("task", tools)
        self.assertNotIn("handoff", tools)

    def test_handoff_tool_is_unsupported(self) -> None:
        instance_json = self._instance_json()
        response = self._dispatch_env_tool(
            payload={"tool": "handoff", "action": "list", "args": {}},
            instance_json=instance_json,
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_ENV_TOOL")
        self.assertEqual(response.get("permission_boundary"), "env.tool")
        self.assertIs(response.get("state_changed"), False)

    def test_dash_action_is_normalized_to_underscore_action_id(self) -> None:
        instance_json = self._instance_json()
        response = self._dispatch_env_tool(
            payload={"tool": "context", "action": "list-sources", "args": {}},
            instance_json=instance_json,
        )
        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("action"), "context.list_sources")

    def test_unrelated_private_impl_import_failure_does_not_block_selected_tool(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-isolation", role="dev")
        completed = self._run_router_subprocess_with_blocked_message_impl(
            instance_json=instance_json,
            payload={"tool": "context", "action": "list_sources", "args": {}},
            role="dev",
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        response = json.loads(completed.stdout)
        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("tool"), "context")
        self.assertEqual(response.get("action"), "context.list_sources")
        self.assertIs(response.get("state_changed"), False)

    def test_selected_private_impl_import_failure_returns_structured_feedback(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-selected-failure", role="dev")
        completed = self._run_router_subprocess_with_blocked_message_impl(
            instance_json=instance_json,
            payload={"tool": "message", "action": "list", "args": {}},
            role="dev",
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
        self.assertIn("blocked message _impl import", str(response.get("why_blocked")))

    def test_track_create_role_policy_allows_dev_to_reach_selected_private_impl_import(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-role-allow-before-import", role="dev")
        completed = self._run_router_subprocess_with_blocked_impl(
            instance_json=instance_json,
            payload={
                "tool": "track",
                "action": "create",
                "args": {
                    "track_id": "track-dev-allowed",
                    "title": "Allowed",
                    "outcome": "x",
                    "now": {"next": "seed", "blocker": None},
                },
            },
            blocked_module="buddyswitch.modules.track.private.adapters.tool._impl",
            role="dev",
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        response = payload["response"]
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_ENV_TOOL_DISPATCH")
        self.assertEqual(response.get("permission_boundary"), "env.tool.dispatch")

    def test_allowed_role_reaches_selected_private_impl_import(self) -> None:
        instance_json = self._instance_json(actor_id="act-pm-role-allow-reaches-import", role="pm")
        completed = self._run_router_subprocess_with_blocked_impl(
            instance_json=instance_json,
            payload={
                "tool": "track",
                "action": "create",
                "args": {
                    "track_id": "track-allowed",
                    "title": "Allowed",
                    "outcome": "x",
                    "now": {"next": "seed", "blocker": None},
                },
            },
            blocked_module="buddyswitch.modules.track.private.adapters.tool._impl",
            role="pm",
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        response = json.loads(completed.stdout)["response"]
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_ENV_TOOL_DISPATCH")
        self.assertEqual(response.get("permission_boundary"), "env.tool.dispatch")
        self.assertIn("blocked selected _impl import", str(response.get("why_blocked")))

    def test_track_create_payload_validation_runs_after_role_policy_allows_dev(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-role-allow-before-payload", role="dev")
        response = self._dispatch_env_tool(
            payload={"tool": "track", "action": "create", "args": "not-an-object"},
            instance_json=instance_json,
            role="dev",
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_ENV_TOOL_PAYLOAD")
        self.assertEqual(response.get("permission_boundary"), "request-payload")

    def test_selected_dispatch_imports_no_sibling_private_impl_modules(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-selected-impl-import", role="dev")
        for tool, action, args, role in self._CHEAP_ACTION_CASES:
            payload_json = json.dumps({"tool": tool, "action": action, "args": args}, ensure_ascii=True)
            script = f"""
import json
import sys
from pathlib import Path

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.tool_runtime.registry import dispatch_env_tool_request

application = activate_application()
registration_by_tool = {{
    registration.definition.id: registration
    for registration in application.tools
}}
registration = registration_by_tool[{tool!r}]
selected_invoke_module = registration.invoke.__module__
expected = f"{{selected_invoke_module.rsplit('.', 1)[0]}}._impl"
component_private_tool_roots = tuple(
    f"{{registration.invoke.__module__.rsplit('.', 1)[0]}}."
    for registration in application.tools
)
instance_json = Path({str(instance_json)!r})
instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
response = dispatch_env_tool_request(
    payload=json.loads({payload_json!r}),
    active_role={role!r},
    actor_id=instance_payload["actor_id"],
    instance_json=instance_json,
    instance_payload=instance_payload,
)
loaded = sorted(
    name
    for name in sys.modules
    if name.endswith("._impl")
    and name.startswith(component_private_tool_roots)
)
print(json.dumps(
    {{"response": response, "loaded": loaded, "expected": expected}},
    sort_keys=True,
))
"""
            completed = run_process(
                [PYTHON, "-c", script],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            payload = json.loads(completed.stdout)
            loaded = payload["loaded"]
            response = payload["response"]
            with self.subTest(tool=tool, action=action):
                expected = payload["expected"]
                self.assertIn(expected, loaded, msg=payload)
                self.assertEqual(loaded, [expected], msg=payload)
                if response.get("ok") is not True:
                    self.assertIs(response.get("state_changed"), False, msg=response)
