#!/usr/bin/env python3
"""Prepare runtime context behavior tests for task-management skill architecture."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_profiles  # noqa: E402
import env_store  # noqa: E402
import turn_runtime  # noqa: E402
from env.tools import contracts as tool_contracts  # noqa: E402
from env_manifest import load_manifest  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
REQUESTS_BY_BUDDY = {
    "market": "做竞品landing page研究",
    "pm": "写PRD并推进交接",
    "design": "输出设计方案",
    "dev": "实现页面",
    "test": "做冒烟测试",
}


class PrepareRuntimeContextTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _session(self, *, buddy: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        return {
            "instance_id": f"instance-{buddy}",
            "active_buddy": buddy,
            "payload": payload or {},
        }

    def _prepare(self, *, buddy: str, request_text: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        with patch.object(turn_runtime, "_load_product_mode_session", return_value=self._session(buddy=buddy, payload=payload)):
            prepared = turn_runtime.prepare_turn_context(request_text, manifest_path=MANIFEST)
        self.assertTrue(prepared["ok"], msg=prepared)
        return prepared

    def _manifest_buddy_order(self) -> list[str]:
        manifest = load_manifest(MANIFEST)
        return [row["id"] for row in manifest.get("buddies", []) if isinstance(row, dict) and isinstance(row.get("id"), str)]

    def test_prepare_returns_runtime_context_for_each_buddy(self) -> None:
        for buddy in self._manifest_buddy_order():
            with self.subTest(buddy=buddy):
                payload = self._prepare(buddy=buddy, request_text=REQUESTS_BY_BUDDY[buddy])
                self.assertIn("runtime_context", payload)
                self.assertIsNone(payload.get("current_task_id"))
                self.assertIsNone(payload.get("task_context"))
                self.assertEqual(payload["runtime_context"]["decision_surface"]["binding_state"]["state"], "unbound")
                run_id = payload["run_envelope"]["run_id"]
                self.assertEqual(payload["context_revision"], f"ctx-{run_id}")

    def test_prepare_runtime_context_capability_boundary_matches_manifest_and_profiles(self) -> None:
        manifest = load_manifest(MANIFEST)
        buddies = {row["id"]: row for row in manifest["buddies"] if isinstance(row, dict)}
        for buddy in self._manifest_buddy_order():
            with self.subTest(buddy=buddy):
                profile = env_profiles.require_env_profile(buddy, manifest_path=MANIFEST, repo_root=ROOT)
                payload = self._prepare(buddy=buddy, request_text=REQUESTS_BY_BUDDY[buddy])
                runtime_context = payload["runtime_context"]
                boundary = runtime_context["capability_boundary"]
                self.assertEqual(runtime_context["active_skill_ids"], buddies[buddy]["skills"])
                self.assertEqual(boundary["allowed_artifact_kinds"], buddies[buddy]["artifact_kinds"])
                self.assertIn("state_write_boundary", boundary)
                self.assertEqual(boundary["project"]["access"], profile["project"]["access"])

    def test_prepare_exposes_tool_requirements_and_persist_payload_hints(self) -> None:
        required_optional = {
            "working_notes",
            "task_id",
            "track_id",
            "artifact_ids",
            "handoff",
            "contributors",
            "tool_evidence",
        }
        for buddy in self._manifest_buddy_order():
            with self.subTest(buddy=buddy):
                profile = env_profiles.require_env_profile(buddy, manifest_path=MANIFEST, repo_root=ROOT)
                payload = self._prepare(buddy=buddy, request_text=REQUESTS_BY_BUDDY[buddy])
                runtime_context = payload["runtime_context"]
                tool_requirements = runtime_context["tool_requirements"]
                self.assertEqual(tool_requirements["browser_cockpit"], profile["tool_capability"]["browser_cockpit"])
                self.assertEqual(
                    tool_requirements["market_research_evidence"],
                    profile["tool_capability"]["market_research_evidence"],
                )
                self.assertEqual(tool_requirements["search"], profile["tool_capability"]["search"])
                hint = runtime_context["persist_payload_hint"]
                self.assertIn("execution_summary", hint["required"])
                self.assertTrue(required_optional.issubset(set(hint["optional"])))
                self.assertNotIn("state_effects", hint["optional"])
                self.assertNotIn("artifacts", hint["optional"])

    def test_prepare_projects_search_capability_boundary_for_each_buddy(self) -> None:
        forbidden_workflow_keys = {
            "default_engine",
            "market_workflow",
            "preferred_backend",
            "route_research",
            "auto_backend",
        }
        for buddy in self._manifest_buddy_order():
            with self.subTest(buddy=buddy):
                profile = env_profiles.require_env_profile(buddy, manifest_path=MANIFEST, repo_root=ROOT)
                expected_search = profile["tool_capability"]["search"]
                payload = self._prepare(buddy=buddy, request_text=REQUESTS_BY_BUDDY[buddy])
                runtime_context = payload["runtime_context"]
                self.assertEqual(runtime_context["tool_requirements"]["search"], expected_search)
                capability = runtime_context["capability_boundary"]["search"]
                self.assertEqual(capability["native_codex_web_search"], "disabled")
                self.assertEqual(capability["browser_cockpit"], expected_search["browser_cockpit"])
                self.assertEqual(capability["search_api"], expected_search["search_api"])
                self.assertEqual(capability["env_tool_source"], "runtime_context.env_tools.search")
                self.assertFalse(forbidden_workflow_keys.intersection(capability))

    def test_prepare_runtime_context_exposes_desc_for_commit_fields(self) -> None:
        payload = self._prepare(buddy="pm", request_text=REQUESTS_BY_BUDDY["pm"])
        desc = payload["runtime_context"]["desc"]
        required_keys = (
            "execution_summary",
            "task_id",
            "track_id",
            "artifact_ids",
            "handoff",
            "contributors",
            "tool_evidence",
        )
        for key in required_keys:
            with self.subTest(key=key):
                self.assertIn(key, desc)
        self.assertNotIn("state_effects.task", desc)
        self.assertNotIn("state_effects.track", desc)
        self.assertNotIn("artifacts", desc)

    def test_prepare_exposes_track_lifecycle_desc_for_pm_and_non_pm(self) -> None:
        pm_payload = self._prepare(buddy="pm", request_text=REQUESTS_BY_BUDDY["pm"])
        pm_desc = pm_payload["runtime_context"]["track_lifecycle_desc"]
        self.assertEqual(pm_desc["owner"], "pm")
        self.assertEqual(pm_desc["allowed_actions"], ["create", "update", "advance", "archive"])
        self.assertTrue(pm_desc["non_create_requires_existing_track"])
        self.assertTrue(pm_desc["handoff_does_not_mutate_track"])

        for buddy in ("market", "design", "dev", "test"):
            with self.subTest(buddy=buddy):
                payload = self._prepare(buddy=buddy, request_text=REQUESTS_BY_BUDDY[buddy])
                lifecycle_desc = payload["runtime_context"]["track_lifecycle_desc"]
                self.assertEqual(lifecycle_desc["owner"], "pm")
                self.assertEqual(lifecycle_desc["allowed_actions"], [])
                self.assertTrue(lifecycle_desc["handoff_does_not_mutate_track"])

    def test_prepare_reports_stale_task_binding_without_repair(self) -> None:
        payload = self._prepare(
            buddy="pm",
            request_text="继续任务",
            payload={"current_task_id": "task-missing"},
        )
        self.assertEqual(payload["runtime_context"]["decision_surface"]["binding_state"]["state"], "stale")
        warnings = payload.get("warnings")
        self.assertIsInstance(warnings, list)
        warning_codes = {row.get("code") for row in warnings if isinstance(row, dict)}
        self.assertIn("W_STALE_TASK_BINDING", warning_codes)
        self.assertIsNone(env_store.get_task("task-missing"))

    def test_prepare_reports_stale_track_binding_without_repair(self) -> None:
        payload = self._prepare(
            buddy="pm",
            request_text="继续track",
            payload={"current_track_id": "track-missing"},
        )
        self.assertEqual(payload["runtime_context"]["decision_surface"]["binding_state"]["state"], "stale")
        warnings = payload.get("warnings")
        self.assertIsInstance(warnings, list)
        warning_codes = {row.get("code") for row in warnings if isinstance(row, dict)}
        self.assertIn("W_STALE_TRACK_BINDING", warning_codes)
        self.assertIsNone(env_store.get_track("track-missing"))

    def test_prepare_projects_direct_id_tool_surface_for_track_artifact_task_handoff(self) -> None:
        payload = self._prepare(buddy="dev", request_text=REQUESTS_BY_BUDDY["dev"])
        env_tools = payload["runtime_context"]["env_tools"]

        self.assertIn("track", env_tools)
        self.assertIn("artifact", env_tools)
        self.assertIn("task", env_tools)
        self.assertIn("handoff", env_tools)

        self.assertIn("join", env_tools["track"]["operations"])
        self.assertEqual(env_tools["artifact"]["payload_fields"]["list"], ["track_id"])
        self.assertIn("list", env_tools["handoff"]["operations"])
        self.assertIn("validate", env_tools["handoff"]["operations"])
        self.assertIn("create", env_tools["handoff"]["operations"])

    def test_prepare_projects_env_tool_semantics_for_each_buddy(self) -> None:
        expected_tools = {row["tool"] for row in tool_contracts.TOOL_REGISTRY}
        expected_actions = {
            row["tool"]: {action["name"] for action in row["actions"]}
            for row in tool_contracts.TOOL_REGISTRY
        }
        expected_operation_semantics = {
            f"{row['tool']}.{action['name']}"
            for row in tool_contracts.TOOL_REGISTRY
            for action in row["actions"]
        }

        for buddy in self._manifest_buddy_order():
            with self.subTest(buddy=buddy):
                payload = self._prepare(buddy=buddy, request_text=REQUESTS_BY_BUDDY[buddy])
                runtime_context = payload["runtime_context"]
                env_tools = runtime_context["env_tools"]
                self.assertEqual(set(env_tools), expected_tools)
                self.assertEqual(set(runtime_context["operation_semantics"]), expected_operation_semantics)
                for tool in sorted(expected_tools):
                    tool_row = env_tools[tool]
                    self.assertIn("action_semantics", tool_row)
                    self.assertEqual(set(tool_row["action_semantics"]), expected_actions[tool])
                    for action in sorted(expected_actions[tool]):
                        semantic = tool_row["action_semantics"][action]
                        self.assertIn("title", semantic)
                        self.assertIn("inputs_explained", semantic)


if __name__ == "__main__":
    unittest.main()
