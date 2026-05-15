#!/usr/bin/env python3
"""Runless task-management architecture contract replacements."""

from __future__ import annotations

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
from env.tools import router as tool_router  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class TaskManagementSkillArchitectureTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        self.manifest = env_manifest.load_manifest(self.manifest_path)
        self.instance_json = self._runtime_path("instance.json")
        self.instance_payload = {
            "instance_id": "inst-pm-task-arch",
            "buddy": "pm",
            "status": "active",
            "workspace_dir": str(self.runtime_root),
        }
        self.instance_json.write_text(json.dumps(self.instance_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _dispatch(self, *, buddy: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        return tool_router.dispatch_env_tool_request(
            payload={"tool": tool, "action": action, "args": args},
            active_buddy=buddy,
            instance_id="inst-pm-task-arch",
            instance_json=self.instance_json,
            instance_payload={**self.instance_payload, "buddy": buddy},
            manifest=self.manifest,
            manifest_path=self.manifest_path,
        )

    def test_explicit_task_creates_only_task_objects_without_binding_fields(self) -> None:
        track = env_store.create_track("track-task-arch", "Task Arch", current_buddy="pm", next_buddy="dev")
        for idx in range(1, 4):
            payload = self._dispatch(
                buddy="pm",
                tool="task",
                action="create",
                args={
                    "task_id": f"task-pm-task-arch-{idx}",
                    "title": f"Task {idx}",
                    "summary": "runless",
                    "track_id": track["id"],
                },
            )
            self.assertTrue(payload["ok"], msg=payload)

        task_files = sorted((self._runtime_path("buddyswitch/objects/tasks")).glob("task-pm-task-arch-*.json"))
        self.assertEqual(len(task_files), 3)
        stored_instance = json.loads(self.instance_json.read_text(encoding="utf-8"))
        self.assertNotIn("current_task_id", stored_instance)
        self.assertNotIn("current_track_id", stored_instance)

    def test_context_decision_surface_reports_runless_mode(self) -> None:
        payload = self._dispatch(buddy="pm", tool="context", action="summarize", args={})
        self.assertTrue(payload["ok"], msg=payload)
        self.assertEqual(payload["decision_surface"]["binding_state"]["state"], "runless")
        self.assertFalse(self._runtime_path("runs/raw").exists())
        self.assertFalse(self._runtime_path("buddyswitch/content/runs").exists())


if __name__ == "__main__":
    unittest.main()
