#!/usr/bin/env python3
"""Cleanup backend tests for active collaboration surfaces."""

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


class CleanupSystemTests(unittest.TestCase):
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
                "owner_buddy": "pm",
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
            "buddyswitch/objects/handoffs/handoff-stale.json",
            {
                "id": "handoff-stale",
                "source_buddy": "pm",
                "target_buddy": "dev",
            },
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _path(self, rel: str) -> Path:
        return self.repo_root / rel

    def _write_json(self, rel: str, payload: dict[str, object]) -> None:
        path = self._path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def test_cleanup_plan_excludes_handoff_indexing(self) -> None:
        plan = env_cleanup.build_cleanup_plan(
            scope="buddy",
            buddy="pm",
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
        )
        self.assertEqual(plan["scope"], "buddy")
        self.assertIn("task-pm", plan["task_object_ids"])
        self.assertIn("art-pm-r1", plan["artifact_object_ids"])
        self.assertNotIn("handoff_object_ids", plan)
        self.assertNotIn("handoff_records", plan)
        self.assertNotIn("handoff_objects", plan.get("counts_by_category", {}))

    def test_execute_all_data_cleanup_recreates_active_skeleton_only(self) -> None:
        plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            buddy=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
        )
        result = env_cleanup.execute_cleanup_plan(plan)
        self.assertTrue(result["ok"])

        for directory in (
            "buddyswitch/objects/tracks",
            "buddyswitch/objects/tasks",
            "buddyswitch/objects/artifacts",
        ):
            self.assertTrue(self._path(directory).is_dir(), f"missing recreated dir: {directory}")

    def test_cleanup_cli_json_reports_active_categories(self) -> None:
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
        self.assertNotIn("handoff_object_ids", payload)
        self.assertNotIn("handoff_records", payload)


if __name__ == "__main__":
    unittest.main()
