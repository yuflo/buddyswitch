#!/usr/bin/env python3
"""Contract tests for unified env.tool router dispatch."""

from __future__ import annotations

import copy
import importlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
import env_store  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
_EXPECTED_TOOLS = {"task", "track", "artifact", "buddybox", "context", "evidence", "search"}


class EnvToolRouterTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
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

    def test_active_env_tool_surface_excludes_handoff(self) -> None:
        contracts = importlib.import_module("env.tools.contracts")
        router = importlib.import_module("env.tools.router")
        status_payload = importlib.import_module("turn_runtime")._build_env_tools_desc()

        registry_tools = {row["tool"] for row in contracts.TOOL_REGISTRY}
        self.assertEqual(registry_tools, _EXPECTED_TOOLS)
        self.assertNotIn("handoff", registry_tools)
        self.assertNotIn("track.advance", json.dumps(contracts.operation_semantics(), ensure_ascii=True))

        self.assertEqual(set(router._TOOL_ACTIONS), _EXPECTED_TOOLS)
        self.assertEqual(set(status_payload), _EXPECTED_TOOLS)
        self.assertNotIn("handoff", contracts.compact_tool_affordances())

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
        contracts = importlib.import_module("env.tools.contracts")
        self.assertNotIn("advance", {row["name"] for row in contracts.get_tool_spec("track")["actions"]})

        instance_json = self._instance_json(buddy="pm")
        env_store.create_track("track-router-advance", "Advance", owner_buddy="pm")
        response = self._dispatch_env_tool(
            payload={"tool": "track", "action": "advance", "args": {"track_id": "track-router-advance"}},
            instance_json=instance_json,
            buddy="pm",
            instance_id="inst-dev-example",
        )
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_ENV_TOOL")

    def test_dispatch_handler_coverage_matches_registry_actions(self) -> None:
        contracts = importlib.import_module("env.tools.contracts")
        dispatch = importlib.import_module("env.tools.dispatch")
        router = importlib.import_module("env.tools.router")

        expected: dict[str, set[str]] = {}
        for spec in contracts.TOOL_REGISTRY:
            expected[spec["tool"]] = {action["name"] for action in spec["actions"]}

        dispatch_actions = dispatch.dispatch_handler_actions()
        self.assertEqual(dispatch_actions, expected)
        self.assertEqual({tool: set(actions) for tool, actions in router._TOOL_ACTIONS.items()}, expected)
        self.assertNotIn("handoff", dispatch_actions)

    def test_cli_excludes_handoff_resource_and_track_advance(self) -> None:
        import subprocess

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
