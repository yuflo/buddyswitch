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
        self.shared_root = Path(self._tmp.name)
        self.repo_root = self.shared_root / "state"
        self.repo_root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.repo_root / "buddyswitch" / "manifest.toml"
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "buddyswitch" / "manifest.toml", self.manifest_path)

        self._write_json(
            "buddyswitch/objects/tracks/track-demo.json",
            {
                "id": "track-demo",
                "title": "Demo",
                "outcome": "Cleanup fixture",
                "owner_buddy": "pm",
                "state": "active",
                "health": "ok",
                "appetite": "1 day",
                "now": {"next": "fixture", "blocker": None},
                "shared_materials": [],
                "updates": [],
                "close_proof": [],
                "created_at": "2026-05-15T00:00:00+00:00",
                "updated_at": "2026-05-15T00:00:00+00:00",
                "archived_at": None,
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
                "created_at": "2026-05-15T00:00:00+00:00",
                "updated_at": "2026-05-15T00:00:00+00:00",
            },
        )
        self._write_json(
            "buddyswitch/objects/artifacts/art-pm-r1.json",
            {
                "id": "art-pm-r1",
                "kind": "prd",
                "title": "PM PRD",
                "created_by": "pm",
                "published_to_track": None,
                "publication_role": None,
                "summary": "",
                "content": {"body": "x"},
                "revision": 1,
                "source_refs": [],
                "supersedes_artifact_id": None,
                "is_current": True,
                "created_at": "2026-05-15T00:00:00+00:00",
                "updated_at": "2026-05-15T00:00:00+00:00",
            },
        )
        self._write_json(
            "buddyswitch/objects/artifacts/art-dev-r1.json",
            {
                "id": "art-dev-r1",
                "kind": "implementation-report",
                "title": "DEV report",
                "created_by": "dev",
                "published_to_track": None,
                "publication_role": None,
                "summary": "",
                "content": {"body": "x"},
                "revision": 1,
                "source_refs": [],
                "supersedes_artifact_id": None,
                "is_current": True,
                "created_at": "2026-05-15T00:00:00+00:00",
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

    def _instance_workspace(self, *, instance_id: str, buddy: str) -> Path:
        instance_root = self.shared_root / "instances" / instance_id
        workspace = instance_root / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        (instance_root / "instance.json").write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": "active",
                    "workspace_dir": str(workspace),
                    "browser_port": None,
                    "updated_at": "2026-05-19T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return workspace

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
            "buddyswitch/objects/messages",
            "buddyswitch/objects/comments",
        ):
            self.assertTrue(self._path(directory).is_dir(), f"missing recreated dir: {directory}")

    def test_cleanup_plan_includes_message_and_comment_objects(self) -> None:
        """MCT-RUN-003: All-data cleanup plan discovers message and comment objects."""
        self._write_json(
            "buddyswitch/objects/messages/msg-test.json",
            {"id": "msg-test", "from_buddy": "pm", "to_buddy": "dev", "content": "hello", "reply_to": None, "created_at": "2026-05-17T00:00:00+08:00"},
        )
        self._write_json(
            "buddyswitch/objects/comments/comment-test.json",
            {"id": "comment-test", "target_type": "track", "target_id": "track-demo", "author_buddy": "design", "content": "looks good", "reply_to": None, "created_at": "2026-05-17T00:00:00+08:00"},
        )
        plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            buddy=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
        )
        self.assertIn("message_object_ids", plan)
        self.assertIn("msg-test", plan["message_object_ids"])
        self.assertIn("comment_object_ids", plan)
        self.assertIn("comment-test", plan["comment_object_ids"])

    def test_buddy_cleanup_deletes_authored_comments_without_mutating_surviving_targets(self) -> None:
        track_path = self._path("buddyswitch/objects/tracks/track-clean-comment.json")
        track_payload = {
            "id": "track-clean-comment",
            "title": "Clean Comment",
            "outcome": "clean comment",
            "owner_buddy": "pm",
            "state": "active",
            "health": "ok",
            "appetite": "1 day",
            "now": {"next": "clean", "blocker": None},
            "shared_materials": [],
            "updates": [],
            "close_proof": [],
            "created_at": "2026-05-17T00:00:00+08:00",
            "updated_at": "2026-05-17T00:00:00+08:00",
            "archived_at": None,
        }
        self._write_json("buddyswitch/objects/tracks/track-clean-comment.json", track_payload)
        self._write_json(
            "buddyswitch/objects/comments/comment-dev-clean.json",
            {
                "id": "comment-dev-clean",
                "target_type": "track",
                "target_id": "track-clean-comment",
                "author_buddy": "dev",
                "content": "delete me",
                "reply_to": None,
                "created_at": "2026-05-17T00:00:00+08:00",
            },
        )
        self._write_json(
            "buddyswitch/objects/comments/comment-design-keep.json",
            {
                "id": "comment-design-keep",
                "target_type": "track",
                "target_id": "track-clean-comment",
                "author_buddy": "design",
                "content": "keep me",
                "reply_to": None,
                "created_at": "2026-05-17T00:00:01+08:00",
            },
        )

        plan = env_cleanup.build_cleanup_plan(
            scope="buddy",
            buddy="dev",
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
        )
        result = env_cleanup.execute_cleanup_plan(plan)

        self.assertTrue(result["ok"], msg=result)
        self.assertFalse(self._path("buddyswitch/objects/comments/comment-dev-clean.json").exists())
        self.assertTrue(self._path("buddyswitch/objects/comments/comment-design-keep.json").exists())
        self.assertEqual(json.loads(track_path.read_text(encoding="utf-8")), track_payload)

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

    def test_buddy_cleanup_uses_instance_buddybox_owner_boundary(self) -> None:
        pm_workspace = self._instance_workspace(instance_id="inst-pm-cleanup", buddy="pm")
        dev_workspace = self._instance_workspace(instance_id="inst-dev-cleanup", buddy="dev")

        pm_owned = pm_workspace / "buddyswitch" / "local" / "buddybox" / "pm" / "notes" / "draft.md"
        pm_owned.parent.mkdir(parents=True, exist_ok=True)
        pm_owned.write_text("pm-owned", encoding="utf-8")

        pm_workspace_dev_file = pm_workspace / "buddyswitch" / "local" / "buddybox" / "dev" / "notes" / "keep.md"
        pm_workspace_dev_file.parent.mkdir(parents=True, exist_ok=True)
        pm_workspace_dev_file.write_text("dev-owned", encoding="utf-8")

        dev_workspace_pm_file = dev_workspace / "buddyswitch" / "local" / "buddybox" / "pm" / "notes" / "keep.md"
        dev_workspace_pm_file.parent.mkdir(parents=True, exist_ok=True)
        dev_workspace_pm_file.write_text("pm-in-dev-workspace", encoding="utf-8")

        plan = env_cleanup.build_cleanup_plan(
            scope="buddy",
            buddy="pm",
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            shared_root=self.shared_root,
        )
        self.assertIn("path_categories", plan)
        self.assertTrue(
            any(
                category == "buddybox_private_files"
                for category in plan["path_categories"].values()
            ),
            msg=plan,
        )
        result = env_cleanup.execute_cleanup_plan(plan)
        self.assertTrue(result["ok"], msg=result)
        self.assertFalse(pm_owned.exists())
        self.assertTrue(pm_workspace_dev_file.exists())
        self.assertTrue(dev_workspace_pm_file.exists())


if __name__ == "__main__":
    unittest.main()
