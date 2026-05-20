#!/usr/bin/env python3
"""Contract tests for unified env.tool router dispatch."""

from __future__ import annotations

import copy
import importlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
import env_legacy_store as env_store  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
_EXPECTED_TOOLS = {"task", "track", "artifact", "buddybox", "context", "evidence", "search", "message", "comment"}


class EnvToolRouterTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    _CHEAP_ACTION_CASES = (
        ("task", "list", {}, "dev"),
        ("track", "list", {}, "dev"),
        ("artifact", "get", {"artifact_id": "missing-artifact"}, "dev"),
        ("buddybox", "desc", {}, "dev"),
        ("context", "list_sources", {}, "dev"),
        ("evidence", "issue_browser", {}, "dev"),
        ("message", "list", {}, "dev"),
        ("comment", "list", {}, "dev"),
        ("search", "status", {}, "dev"),
    )

    def _instance_json(
        self,
        *,
        instance_id: str = "inst-dev-example",
        buddy: str = "dev",
        status: str = "active",
    ) -> Path:
        instance_json = self._runtime_path("instance.json")
        instance_json.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": status,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "created_at": "2026-05-10T00:00:00Z",
                    "updated_at": "2026-05-10T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _dispatch_env_tool(
        self,
        *,
        payload: dict[str, object],
        instance_json: Path,
        instance_id: str = "inst-dev-example",
        buddy: str = "dev",
    ) -> dict[str, object]:
        router = importlib.import_module("env.tools.router")
        dispatch = getattr(router, "dispatch_env_tool_request", None)
        self.assertTrue(callable(dispatch), msg="expected dispatch_env_tool_request(payload, ...) in env.tools.router")
        manifest = env_manifest.load_manifest(MANIFEST)
        instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
        return dispatch(
            payload=payload,
            active_buddy=buddy,
            instance_id=instance_id,
            instance_json=instance_json,
            instance_payload=instance_payload,
            manifest=manifest,
        )

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
        if fullname == "env.tools.message.service":
            raise RuntimeError("blocked message service import")
        return None

sys.meta_path.insert(0, BlockMessages())

import env_manifest
from env.tools.router import dispatch_env_tool_request

manifest_path = Path({str(MANIFEST)!r})
instance_json = Path({str(instance_json)!r})
instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
response = dispatch_env_tool_request(
    payload=json.loads({payload_json!r}),
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

    def _seed_task(self, *, task_id: str, buddy: str, title: str, summary: str = "") -> None:
        env_store.create_task(task_id, title, buddy=buddy, track_id=None, status="active", summary=summary, initial_run_id=None)

    def _tasks_snapshot(self) -> dict[str, dict[str, object]]:
        rows: dict[str, dict[str, object]] = {}
        tasks_dir = self._runtime_path("buddyswitch/objects/tasks")
        if not tasks_dir.exists():
            return rows
        for path in sorted(tasks_dir.glob("*.json")):
            rows[path.name] = json.loads(path.read_text(encoding="utf-8"))
        return rows

    def _cli_operations_for_resource(self, resource: str) -> set[str]:
        completed = subprocess.run(
            ["python3", "scripts/env/client.py", resource, "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        matched = re.search(r"\{([^}]*)\}", completed.stdout, flags=re.DOTALL)
        self.assertIsNotNone(matched, msg=completed.stdout)
        raw = matched.group(1)
        return {token.strip() for token in raw.split(",") if token.strip()}

    def test_python3_imports_env_tool_modules(self) -> None:
        script = """
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))

import env.tools.catalog
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

    def test_env_tool_imports_do_not_load_services(self) -> None:
        script = """
import json
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))

import env.tools.catalog
import env.tools.router
import env.tools.dispatch

loaded = sorted(name for name in sys.modules if name.startswith("env.tools.") and name.endswith(".service"))
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

    def test_selected_dispatch_imports_no_sibling_tool_services(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-selected-service-import", buddy="dev")
        for tool, action, args, buddy in self._CHEAP_ACTION_CASES:
            payload_json = json.dumps({"tool": tool, "action": action, "args": args}, ensure_ascii=True)
            script = f"""
import json
import sys
from pathlib import Path

root = Path({str(ROOT)!r})
sys.path.insert(0, str(root / "scripts"))

import env_manifest
from env.tools.router import dispatch_env_tool_request

manifest_path = Path({str(MANIFEST)!r})
instance_json = Path({str(instance_json)!r})
instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
response = dispatch_env_tool_request(
    payload=json.loads({payload_json!r}),
    active_buddy={buddy!r},
    instance_id=instance_payload["instance_id"],
    instance_json=instance_json,
    instance_payload=instance_payload,
    manifest=env_manifest.load_manifest(manifest_path),
    manifest_path=manifest_path,
)
loaded = sorted(name for name in sys.modules if name.startswith("env.tools.") and name.endswith(".service"))
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
                expected = f"env.tools.{tool}.service"
                self.assertIn(expected, loaded, msg=payload)
                self.assertEqual(loaded, [expected], msg=payload)
                if response.get("ok") is not True:
                    self.assertIs(response.get("state_changed"), False, msg=response)

    def test_active_env_tool_surface_excludes_handoff(self) -> None:
        tool_catalog = importlib.import_module("env.tools.catalog")
        status_payload = importlib.import_module("turn_runtime")._build_env_tools_desc()

        registry_tools = set(tool_catalog.supported_tools())
        self.assertEqual(registry_tools, _EXPECTED_TOOLS)
        self.assertNotIn("handoff", registry_tools)
        self.assertNotIn("track.advance", json.dumps(tool_catalog.operation_semantics(), ensure_ascii=True))

        self.assertEqual(set(status_payload), _EXPECTED_TOOLS)
        self.assertNotIn("handoff", tool_catalog.compact_tool_affordances())

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

    def test_track_advance_is_not_registered(self) -> None:
        tool_catalog = importlib.import_module("env.tools.catalog")
        track_spec = tool_catalog.get_tool_spec("track")
        self.assertIsInstance(track_spec, dict)
        assert isinstance(track_spec, dict)
        self.assertNotIn("advance", {row["name"] for row in track_spec["actions"]})

        instance_json = self._instance_json(buddy="pm")
        env_store.create_track(
            "track-router-advance",
            "Advance",
            owner_buddy="pm",
            outcome="Advance outcome",
            appetite="1 day",
            now={"next": "next", "blocker": None},
        )
        response = self._dispatch_env_tool(
            payload={"tool": "track", "action": "advance", "args": {"track_id": "track-router-advance"}},
            instance_json=instance_json,
            buddy="pm",
            instance_id="inst-dev-example",
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_ENV_TOOL")

    def test_dispatch_handler_coverage_matches_registry_actions(self) -> None:
        tool_catalog = importlib.import_module("env.tools.catalog")
        dispatch = importlib.import_module("env.tools.dispatch")
        turn_runtime = importlib.import_module("turn_runtime")

        expected: dict[str, set[str]] = {}
        for spec in tool_catalog.tool_specs():
            expected[spec["tool"]] = {action["name"] for action in spec["actions"]}

        dispatch_actions = dispatch.dispatch_handler_actions()
        self.assertEqual(dispatch_actions, expected)
        runtime_desc = turn_runtime._build_env_tools_desc()
        self.assertEqual(set(runtime_desc), set(expected))
        for tool, actions in expected.items():
            with self.subTest(tool=tool):
                self.assertEqual(set(runtime_desc[tool]["operations"]), actions)
                self.assertEqual(set(runtime_desc[tool]["payload_fields"]), actions)
                self.assertEqual(set(runtime_desc[tool]["action_semantics"]), actions)
        self.assertNotIn("handoff", dispatch_actions)

    def test_cli_operation_maps_align_with_catalog_actions(self) -> None:
        tool_catalog = importlib.import_module("env.tools.catalog")
        for spec in tool_catalog.tool_specs():
            tool = spec["tool"]
            cli_resource = spec["cli_resource"]
            expected_actions = {action["name"] for action in spec["actions"]}
            cli_ops = self._cli_operations_for_resource(cli_resource)
            normalized = {name.replace("-", "_") for name in cli_ops}
            with self.subTest(tool=tool):
                self.assertEqual(normalized, expected_actions)

    def test_comment_list_cli_help_includes_status_filter(self) -> None:
        completed = subprocess.run(
            ["python3", "scripts/env/client.py", "comment", "list", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("--status", completed.stdout)

    def test_artifact_router_surface_uses_revision_actions(self) -> None:
        tool_catalog = importlib.import_module("env.tools.catalog")
        artifact_spec = tool_catalog.get_tool_spec("artifact")
        self.assertIsInstance(artifact_spec, dict)
        assert isinstance(artifact_spec, dict)

        actions = {row["name"] for row in artifact_spec["actions"]}
        self.assertEqual(
            actions,
            {"get", "create_revision", "update_metadata"},
        )

        payload_fields = {row["name"]: set(row.get("payload_fields", [])) for row in artifact_spec["actions"]}
        self.assertIn("template", payload_fields["create_revision"])
        self.assertIn("body", payload_fields["create_revision"])
        self.assertNotIn("published_to_track", payload_fields["create_revision"])
        self.assertNotIn("task_id", payload_fields["create_revision"])
        self.assertNotIn("kind", payload_fields["create_revision"])
        self.assertNotIn("content", payload_fields["create_revision"])

    def test_cli_exposes_final_track_operations_without_handoff(self) -> None:
        handoff = subprocess.run(
            ["python3", "scripts/env/client.py", "handoff", "list"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(handoff.returncode, 0)

        help_out = subprocess.run(
            ["python3", "scripts/env/client.py", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(help_out.returncode, 0, msg=help_out.stderr)
        self.assertNotIn("handoff", help_out.stdout)

        track_help = subprocess.run(
            ["python3", "scripts/env/client.py", "track", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(track_help.returncode, 0, msg=track_help.stderr)
        self.assertNotIn("advance", track_help.stdout)
        self.assertIn("open", track_help.stdout)
        self.assertIn("add-material", track_help.stdout)
        self.assertIn("add-proof", track_help.stdout)

        artifact_help = subprocess.run(
            ["python3", "scripts/env/client.py", "artifact", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(artifact_help.returncode, 0, msg=artifact_help.stderr)
        self.assertNotIn("publish", artifact_help.stdout)
        self.assertNotIn("archive", artifact_help.stdout)

    def test_comment_resolve_and_reopen_are_absent_from_active_surfaces(self) -> None:
        tool_catalog = importlib.import_module("env.tools.catalog")
        dispatch = importlib.import_module("env.tools.dispatch")

        self.assertEqual(tool_catalog.supported_actions("comment"), {"add", "list"})
        self.assertEqual(dispatch.dispatch_handler_actions().get("comment"), {"add", "list"})
        self.assertNotIn("resolve", self._cli_operations_for_resource("comment"))
        self.assertNotIn("reopen", self._cli_operations_for_resource("comment"))

        instance_json = self._instance_json(buddy="pm")
        for action in ("resolve", "reopen"):
            payload = self._dispatch_env_tool(
                payload={"tool": "comment", "action": action, "args": {"thread_id": "thread-1"}},
                instance_json=instance_json,
                buddy="pm",
            )
            with self.subTest(action=action):
                self.assertFalse(payload.get("ok"), msg=payload)
                self.assertEqual((payload.get("error") or {}).get("code"), "E_ENV_TOOL")
                self.assertEqual(payload.get("permission_boundary"), "env.tool")

    def test_cli_payload_help_requires_inline_json_object_string(self) -> None:
        import subprocess

        payload_help_cases = [
            ["task", "create", "--help"],
            ["track", "add-material", "--help"],
            ["artifact", "create-revision", "--help"],
            ["buddybox", "write", "--help"],
            ["message", "send", "--help"],
            ["comment", "add", "--help"],
        ]

        for args in payload_help_cases:
            with self.subTest(args=args):
                completed = subprocess.run(
                    ["python3", "scripts/env/client.py", *args],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, msg=completed.stderr)
                self.assertIn("--payload JSON_OBJECT", completed.stdout)
                self.assertIn("JSON object string", completed.stdout)
                self.assertNotIn("--payload PAYLOAD", completed.stdout)
                self.assertNotIn("payload file", completed.stdout.lower())

    def test_rejects_malformed_envelope_without_state_mutation(self) -> None:
        instance_json = self._instance_json()
        self._seed_task(task_id="task-dev-owned", buddy="dev", title="Owned", summary="baseline")
        before_tasks = copy.deepcopy(self._tasks_snapshot())

        bad_cases = (
            {"action": "list", "args": {}},
            {"tool": "unknown", "action": "get", "args": {}},
            {"tool": "task", "action": "merge", "args": {}},
            {"tool": "task", "action": "list", "args": []},
        )

        for payload in bad_cases:
            response = self._dispatch_env_tool(payload=payload, instance_json=instance_json)
            with self.subTest(payload=payload):
                self.assertFalse(response.get("ok"), msg=response)
                self.assertIs(response.get("state_changed"), False)
                self.assertEqual(self._tasks_snapshot(), before_tasks)


if __name__ == "__main__":
    unittest.main()
