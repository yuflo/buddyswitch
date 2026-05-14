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


class EnvToolRouterTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(
        self,
        *,
        instance_id: str = "inst-dev-example",
        buddy: str = "dev",
        status: str = "active",
        current_task_id: str | None = None,
        current_track_id: str | None = None,
    ) -> Path:
        instance_json = self._runtime_path("instance.json")
        instance_json.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": status,
                    "current_task_id": current_task_id,
                    "current_track_id": current_track_id,
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
        try:
            router = importlib.import_module("env.tools.router")
        except ModuleNotFoundError:
            self.fail("expected env.tools.router module for Phase 2 env.tool dispatch")
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

    def _seed_task(
        self,
        *,
        task_id: str,
        buddy: str,
        title: str,
        summary: str = "",
    ) -> None:
        env_store.create_task(
            task_id,
            title,
            buddy=buddy,
            track_id=None,
            status="active",
            summary=summary,
            initial_run_id=None,
        )

    def _load_instance(self, instance_json: Path) -> dict[str, object]:
        return json.loads(instance_json.read_text(encoding="utf-8"))

    def _tasks_snapshot(self) -> dict[str, dict[str, object]]:
        rows: dict[str, dict[str, object]] = {}
        tasks_dir = self._runtime_path("buddyswitch/objects/tasks")
        if not tasks_dir.exists():
            return rows
        for path in sorted(tasks_dir.glob("*.json")):
            rows[path.name] = json.loads(path.read_text(encoding="utf-8"))
        return rows

    def test_routes_task_list_through_env_tool_contract(self) -> None:
        instance_json = self._instance_json()
        self._seed_task(task_id="task-dev-visible", buddy="dev", title="Visible")
        self._seed_task(task_id="task-pm-hidden", buddy="pm", title="Hidden")

        response = self._dispatch_env_tool(
            payload={"tool": "task", "action": "list", "args": {}},
            instance_json=instance_json,
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("tool"), "task")
        self.assertEqual(response.get("action"), "task.list")
        tasks = response.get("tasks")
        self.assertIsInstance(tasks, list, msg=response)
        assert isinstance(tasks, list)
        task_ids = {row.get("id") for row in tasks if isinstance(row, dict)}
        self.assertIn("task-dev-visible", task_ids)
        self.assertNotIn("task-pm-hidden", task_ids)

    def test_rejects_malformed_envelope_without_state_mutation(self) -> None:
        instance_json = self._instance_json(current_task_id="task-dev-owned")
        self._seed_task(task_id="task-dev-owned", buddy="dev", title="Owned", summary="baseline")
        before_tasks = copy.deepcopy(self._tasks_snapshot())
        before_instance = self._load_instance(instance_json)

        bad_cases = (
            ("missing_tool", {"action": "list", "args": {}}, "E_ENV_TOOL", "env.tool"),
            ("blank_tool", {"tool": "  ", "action": "list", "args": {}}, "E_ENV_TOOL", "env.tool"),
            ("unknown_tool", {"tool": "unknown", "action": "get", "args": {}}, "E_ENV_TOOL", "env.tool"),
            ("missing_action", {"tool": "task", "args": {}}, "E_ENV_TOOL", "env.tool"),
            ("blank_action", {"tool": "task", "action": " ", "args": {}}, "E_ENV_TOOL", "env.tool"),
            ("unknown_task_action", {"tool": "task", "action": "merge", "args": {}}, "E_ENV_TOOL", "env.tool"),
            ("non_object_args", {"tool": "task", "action": "list", "args": []}, "E_ENV_TOOL_PAYLOAD", "request-payload"),
        )

        for case, payload, error_code, boundary in bad_cases:
            with self.subTest(case=case):
                response = self._dispatch_env_tool(payload=payload, instance_json=instance_json)
                self.assertFalse(response.get("ok"), msg=response)
                error = response.get("error")
                self.assertIsInstance(error, dict, msg=response)
                assert isinstance(error, dict)
                self.assertEqual(error.get("code"), error_code)
                self.assertNotEqual(error.get("code"), "E_ENV_TOOL_ROUTER")
                self.assertEqual(response.get("permission_boundary"), boundary)
                self.assertEqual(self._tasks_snapshot(), before_tasks)
                self.assertEqual(self._load_instance(instance_json), before_instance)

    def test_router_supported_tools_and_actions_match_registry(self) -> None:
        contracts = importlib.import_module("env.tools.contracts")
        router = importlib.import_module("env.tools.router")

        registry = contracts.TOOL_REGISTRY
        expected_tools = {spec["tool"] for spec in registry}
        self.assertEqual(set(router._TOOL_ACTIONS), expected_tools)

        for spec in registry:
            with self.subTest(tool=spec["tool"]):
                expected_actions = {action["name"] for action in spec["actions"]}
                self.assertEqual(set(router._TOOL_ACTIONS[spec["tool"]]), expected_actions)

    def test_dispatch_handler_coverage_matches_registry_actions(self) -> None:
        contracts = importlib.import_module("env.tools.contracts")
        dispatch = importlib.import_module("env.tools.dispatch")
        router = importlib.import_module("env.tools.router")
        registry = contracts.TOOL_REGISTRY

        expected: dict[str, set[str]] = {}
        for spec in registry:
            tool_name = spec["tool"]
            expected[tool_name] = {action["name"] for action in spec["actions"]}

        self.assertIn("join", expected.get("track", set()))
        self.assertIn("list", expected.get("handoff", set()))
        self.assertIn("create", expected.get("handoff", set()))
        self.assertIn("validate", expected.get("handoff", set()))
        self.assertEqual(
            contracts.get_action_spec("artifact", "list").get("payload_fields"),  # type: ignore[union-attr]
            ["track_id"],
        )

        dispatch_actions = dispatch.dispatch_handler_actions()
        self.assertEqual(dispatch_actions, expected)
        self.assertEqual({tool: set(actions) for tool, actions in router._TOOL_ACTIONS.items()}, expected)
        self.assertFalse(hasattr(router, "_TOOL_DISPATCHERS"))

        forbidden_context_actions = {
            "get_track_artifacts",
            "inspect_track_outputs",
            "explain_track_access",
            "validate_sources_available",
        }
        self.assertTrue(forbidden_context_actions.isdisjoint(expected.get("context", set())))
        for actions in expected.values():
            for action in actions:
                self.assertFalse(action.startswith("explain_"), msg=f"unexpected explain action: {action}")

    def test_router_residue_guards_require_dispatch_only_surface(self) -> None:
        importlib.import_module("env.tools.dispatch")

        manager_suffix = "_" + "manager"
        for tool in ("task", "track", "artifact", "context", "binding", "handoff", "run", "evidence", "search"):
            module_name = "env.tools." + tool + manager_suffix
            with self.subTest(module=module_name):
                with self.assertRaises(ModuleNotFoundError):
                    importlib.import_module(module_name)

        tools_dir = ROOT / "scripts" / "env" / "tools"
        forbidden_tokens = (
            "_" + "ACTION" + "_MAP",
            "_" + "router_contract_error",
            "manager" + "_name",
        )
        for path in sorted(tools_dir.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                with self.subTest(path=str(path.relative_to(ROOT)), token=token):
                    self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
