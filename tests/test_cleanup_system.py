#!/usr/bin/env python3
"""Runless cleanup backend and CLI tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_cleanup  # noqa: E402


class CleanupSystemRunlessTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.repo_root = Path(self._tmp.name) / "state"
        self.repo_root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.repo_root / "buddyswitch" / "manifest.toml"
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "buddyswitch" / "manifest.toml", self.manifest_path)

        self._write_json(
            "buddyswitch/objects/tracks/track-demo.json",
            {
                "id": "track-demo",
                "title": "Demo",
                "summary": "",
                "status": "active",
                "current_buddy": "pm",
                "next_buddy": "dev",
                "task_ids": ["task-pm", "task-dev"],
                "updated_at": "2026-05-15T00:00:00+00:00",
            },
        )
        self._write_json(
            "buddyswitch/objects/tasks/task-pm.json",
            {
                "id": "task-pm",
                "buddy": "pm",
                "title": "PM task",
                "summary": "",
                "status": "active",
                "track_id": "track-demo",
                "artifact_ids": ["art-pm-r1"],
                "artifact_slots": {},
                "created_at": "2026-05-15T00:00:00+00:00",
                "updated_at": "2026-05-15T00:00:00+00:00",
            },
        )
        self._write_json(
            "buddyswitch/objects/tasks/task-dev.json",
            {
                "id": "task-dev",
                "buddy": "dev",
                "title": "DEV task",
                "summary": "",
                "status": "active",
                "track_id": "track-demo",
                "artifact_ids": ["art-dev-r1"],
                "artifact_slots": {},
                "created_at": "2026-05-15T00:00:00+00:00",
                "updated_at": "2026-05-15T00:00:00+00:00",
            },
        )
        self._write_json(
            "buddyswitch/objects/artifacts/art-pm-r1.json",
            {
                "id": "art-pm-r1",
                "task_id": "task-pm",
                "buddy": "pm",
                "kind": "prd",
                "title": "PM PRD",
                "summary": "",
                "content": {"body": "x"},
                "revision": 1,
                "created_by": "pm",
                "source_refs": [],
                "is_current": True,
                "updated_at": "2026-05-15T00:00:00+00:00",
            },
        )
        self._write_json(
            "buddyswitch/objects/artifacts/art-dev-r1.json",
            {
                "id": "art-dev-r1",
                "task_id": "task-dev",
                "buddy": "dev",
                "kind": "implementation-report",
                "title": "DEV report",
                "summary": "",
                "content": {"body": "x"},
                "revision": 1,
                "created_by": "dev",
                "source_refs": [],
                "is_current": True,
                "updated_at": "2026-05-15T00:00:00+00:00",
            },
        )
        self._write_json(
            "buddyswitch/objects/handoffs/handoff-pm-dev.json",
            {
                "id": "handoff-pm-dev",
                "source_buddy": "pm",
                "target_buddy": "dev",
                "track_id": "track-demo",
                "source_task_id": "task-pm",
                "artifact_ids": ["art-pm-r1"],
                "buddybox_paths": ["pm/notes.md"],
                "reason": "implement",
                "context": "",
                "status": "proposed",
                "created_at": "2026-05-15T00:00:00+00:00",
                "updated_at": "2026-05-15T00:00:00+00:00",
            },
        )
        self._write_json(
            "buddyswitch/objects/memories/mem-pm.json",
            {
                "id": "mem-pm",
                "buddy": "pm",
                "kind": "decision",
                "title": "PM memory",
                "summary": "summary",
                "content": {"body": "x"},
                "source_refs": [],
                "status": "active",
                "created_at": "2026-05-15T00:00:00+00:00",
                "updated_at": "2026-05-15T00:00:00+00:00",
            },
        )
        self._write_text("buddyswitch/content/buddybox/pm/notes.md", "# pm\n")
        self._write_text("buddyswitch/content/buddybox/dev/report.txt", "dev\n")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _path(self, rel: str) -> Path:
        return self.repo_root / rel

    def _write_json(self, rel: str, payload: dict[str, object]) -> None:
        path = self._path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _write_text(self, rel: str, content: str) -> None:
        path = self._path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_buddy_cleanup_plan_targets_owned_runless_state_only(self) -> None:
        plan = env_cleanup.build_cleanup_plan(
            scope="buddy",
            buddy="pm",
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
        )
        self.assertEqual(plan["scope"], "buddy")
        self.assertIn("task-pm", plan["task_object_ids"])
        self.assertNotIn("task-dev", plan["task_object_ids"])
        self.assertIn("art-pm-r1", plan["artifact_object_ids"])
        self.assertNotIn("art-dev-r1", plan["artifact_object_ids"])
        self.assertIn("handoff-pm-dev", plan["handoff_object_ids"])
        self.assertNotIn("memory_object_ids", plan)
        self.assertIn("buddyswitch/content/buddybox/pm/notes.md", plan["delete_paths"])
        self.assertNotIn("buddyswitch/objects/memories/mem-pm.json", plan["delete_paths"])
        self.assertNotIn("buddyswitch/content/buddybox/dev/report.txt", plan["delete_paths"])

    def test_execute_all_data_cleanup_removes_runless_state_and_recreates_skeleton(self) -> None:
        plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            buddy=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
        )
        result = env_cleanup.execute_cleanup_plan(plan)
        self.assertTrue(result["ok"])

        self.assertFalse(self._path("buddyswitch/objects/tasks/task-pm.json").exists())
        self.assertFalse(self._path("buddyswitch/objects/tasks/task-dev.json").exists())
        self.assertFalse(self._path("buddyswitch/objects/artifacts/art-pm-r1.json").exists())
        self.assertFalse(self._path("buddyswitch/objects/handoffs/handoff-pm-dev.json").exists())
        self.assertTrue(self._path("buddyswitch/objects/memories/mem-pm.json").exists())
        self.assertFalse(self._path("buddyswitch/content/buddybox/pm/notes.md").exists())
        self.assertFalse(self._path("buddyswitch/content/buddybox/dev/report.txt").exists())

        for directory in (
            "buddyswitch/objects/tracks",
            "buddyswitch/objects/tasks",
            "buddyswitch/objects/artifacts",
            "buddyswitch/objects/handoffs",
            "buddyswitch/content/buddybox",
        ):
            self.assertTrue(self._path(directory).is_dir(), f"missing recreated skeleton dir: {directory}")

    def test_cleanup_cli_json_reports_runless_deletes(self) -> None:
        completed = subprocess.run(
            [
                "python3",
                str(ROOT / "scripts" / "env_cleanup.py"),
                "--repo-root",
                str(self.repo_root),
                "--manifest",
                str(self.manifest_path),
                "--buddy",
                "pm",
                "--json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertIn("buddyswitch/content/buddybox/pm/notes.md", payload["delete_paths"])
        self.assertNotIn("buddyswitch/content/runs", json.dumps(payload, ensure_ascii=True))
        self.assertNotIn("runs/raw", json.dumps(payload, ensure_ascii=True))


if __name__ == "__main__":
    unittest.main()
