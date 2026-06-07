#!/usr/bin/env python3
"""Contract tests for registry-based env.tool dispatch."""

from __future__ import annotations

import importlib.abc
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
from env.tool_runtime import registry as tool_registry  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
EXPECTED_TOOLS = {"task", "track", "artifact", "context", "evidence", "search", "message", "comment", "request"}


class EnvToolRouterTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    _CHEAP_ACTION_CASES = (
        ("task", "current", {}, "dev"),
        ("track", "list", {}, "dev"),
        ("artifact", "get", {"artifact_id": "missing-artifact"}, "dev"),
        ("context", "list_sources", {}, "dev"),
        ("evidence", "issue_browser", {}, "dev"),
        ("message", "list", {}, "dev"),
        ("comment", "list", {}, "dev"),
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
        manifest = env_manifest.load_manifest(MANIFEST)
        instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
        return tool_registry.dispatch_env_tool_request(
            payload=payload,
            active_role=role,
            actor_id=actor_id,
            instance_json=instance_json,
            instance_payload=instance_payload,
            manifest=manifest,
            manifest_path=MANIFEST,
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

root = Path({str(ROOT)!r})
sys.path.insert(0, str(root / "scripts"))

class BlockMessageImpl(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "env.tools.message._impl":
            raise RuntimeError("blocked message _impl import")
        return None

sys.meta_path.insert(0, BlockMessageImpl())

import env_manifest
from env.tool_runtime.registry import dispatch_env_tool_request

manifest_path = Path({str(MANIFEST)!r})
instance_json = Path({str(instance_json)!r})
instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
response = dispatch_env_tool_request(
    payload=json.loads({payload_json!r}),
    active_role={role!r},
    actor_id=instance_payload["actor_id"],
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

root = Path({str(ROOT)!r})
sys.path.insert(0, str(root / "scripts"))

class BlockSelectedImpl(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == {blocked_module!r}:
            raise RuntimeError("blocked selected _impl import")
        return None

sys.meta_path.insert(0, BlockSelectedImpl())

import env_manifest
from env.tool_runtime.registry import dispatch_env_tool_request

manifest_path = Path({str(MANIFEST)!r})
instance_json = Path({str(instance_json)!r})
instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
response = dispatch_env_tool_request(
    payload=json.loads({payload_json!r}),
    active_role={role!r},
    actor_id=instance_payload["actor_id"],
    instance_json=instance_json,
    instance_payload=instance_payload,
    manifest=env_manifest.load_manifest(manifest_path),
    manifest_path=manifest_path,
)
loaded = sorted(name for name in sys.modules if name.startswith("env.tools.") and name.endswith("._impl"))
print(json.dumps({{"response": response, "loaded": loaded}}, sort_keys=True))
"""
        return subprocess.run(
            ["python3", "-c", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_registry_surface_matches_expected_tools(self) -> None:
        tools = set(tool_registry.supported_tools())
        self.assertEqual(tools, EXPECTED_TOOLS)
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
            payload={"tool": "task", "action": "current", "args": {}},
            role="dev",
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        response = json.loads(completed.stdout)
        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("tool"), "task")
        self.assertEqual(response.get("action"), "task.current")
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

    def test_role_auth_denies_before_selected_private_impl_import(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-role-deny-before-import", role="dev")
        completed = self._run_router_subprocess_with_blocked_impl(
            instance_json=instance_json,
            payload={
                "tool": "track",
                "action": "create",
                "args": {
                    "track_id": "track-denied",
                    "title": "Denied",
                    "outcome": "x",
                    "appetite": "1d",
                },
            },
            blocked_module="env.tools.track._impl",
            role="dev",
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        response = payload["response"]
        self._assert_role_auth_receipt(
            response,
            required_permission="track.create",
            active_role="dev",
        )
        self.assertNotIn("env.tools.track._impl", payload["loaded"])

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
                    "appetite": "1d",
                },
            },
            blocked_module="env.tools.track._impl",
            role="pm",
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        response = json.loads(completed.stdout)["response"]
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_ENV_TOOL_DISPATCH")
        self.assertEqual(response.get("permission_boundary"), "env.tool.dispatch")
        self.assertIn("blocked selected _impl import", str(response.get("why_blocked")))

    def test_role_auth_denial_precedes_args_shape_validation(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-role-deny-before-payload", role="dev")
        response = self._dispatch_env_tool(
            payload={"tool": "track", "action": "create", "args": "not-an-object"},
            instance_json=instance_json,
            role="dev",
        )
        self._assert_role_auth_receipt(
            response,
            required_permission="track.create",
            active_role="dev",
        )
        self.assertNotEqual((response.get("error") or {}).get("code"), "E_ENV_TOOL_PAYLOAD")

    def test_selected_dispatch_imports_no_sibling_private_impl_modules(self) -> None:
        instance_json = self._instance_json(actor_id="act-dev-selected-impl-import", role="dev")
        for tool, action, args, role in self._CHEAP_ACTION_CASES:
            payload_json = json.dumps({"tool": tool, "action": action, "args": args}, ensure_ascii=True)
            script = f"""
import json
import sys
from pathlib import Path

root = Path({str(ROOT)!r})
sys.path.insert(0, str(root / "scripts"))

import env_manifest
from env.tool_runtime.registry import dispatch_env_tool_request

manifest_path = Path({str(MANIFEST)!r})
instance_json = Path({str(instance_json)!r})
instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
response = dispatch_env_tool_request(
    payload=json.loads({payload_json!r}),
    active_role={role!r},
    actor_id=instance_payload["actor_id"],
    instance_json=instance_json,
    instance_payload=instance_payload,
    manifest=env_manifest.load_manifest(manifest_path),
    manifest_path=manifest_path,
)
loaded = sorted(name for name in sys.modules if name.startswith("env.tools.") and name.endswith("._impl"))
print(json.dumps({{"response": response, "loaded": loaded}}, sort_keys=True))
"""
            completed = subprocess.run(
                ["python3", "-c", script],
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
                expected = f"env.tools.{tool}._impl"
                self.assertIn(expected, loaded, msg=payload)
                self.assertEqual(loaded, [expected], msg=payload)
                if response.get("ok") is not True:
                    self.assertIs(response.get("state_changed"), False, msg=response)


if __name__ == "__main__":
    unittest.main()
