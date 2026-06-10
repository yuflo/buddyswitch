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
                "owner_role": "pm",
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
            "buddyswitch/objects/artifacts/art-pm-r1.json",
            {
                "id": "art-pm-r1",
                "kind": "prd",
                "title": "PM PRD",
                "created_by_actor": {"actor_id": "act-pm-clean", "role_id": "pm"},
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
                "created_by_actor": {"actor_id": "act-dev-clean", "role_id": "dev"},
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
                "source_role": "pm",
                "target_role": "dev",
            },
        )
        self._write_taskbox_task(actor_id="act-pm-clean", role="pm", task_id="task-pm")
        self._write_taskbox_task(actor_id="act-dev-clean", role="dev", task_id="task-dev")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _path(self, rel: str) -> Path:
        return self.repo_root / rel

    def _write_json(self, rel: str, payload: dict[str, object]) -> None:
        path = self._path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _instance_workspace(self, *, actor_id: str, role: str) -> Path:
        instance_root = self.shared_root / "instances" / actor_id
        workspace = instance_root / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        (instance_root / "instance.json").write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": role,
                    "status": "active",
                    "instance_root": str(instance_root),
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

    def _write_taskbox_task(self, *, actor_id: str, role: str, task_id: str) -> None:
        taskbox_root = self.shared_root / "instances" / actor_id / "taskbox" / role
        (taskbox_root / "tasks").mkdir(parents=True, exist_ok=True)
        (taskbox_root / "history.md").write_text("", encoding="utf-8")
        self._write_json(
            f"../instances/{actor_id}/taskbox/{role}/tasks/{task_id}.json",
            {
                "id": task_id,
                "owner_actor": {"actor_id": actor_id, "role_id": role},
                "title": f"{role} task",
                "summary": "",
                "status": "active",
                "priority": "normal",
                "track_id": "track-demo",
                "refs": [],
                "created_at": "2026-05-15T00:00:00+00:00",
                "updated_at": "2026-05-15T00:00:00+00:00",
                "closed_at": None,
            },
        )

    def test_cleanup_plan_excludes_handoff_indexing(self) -> None:
        plan = env_cleanup.build_cleanup_plan(
            scope="role",
            role="pm",
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
        )
        self.assertEqual(plan["scope"], "role")
        self.assertIn("art-pm-r1", plan["artifact_object_ids"])
        self.assertNotIn("task_" + "object_ids", plan)
        self.assertNotIn("task_" + "records", plan)
        self.assertNotIn("handoff_object_ids", plan)
        self.assertNotIn("handoff_records", plan)
        self.assertNotIn("handoff_objects", plan.get("counts_by_category", {}))
        self.assertNotIn("task_" + "objects", plan.get("counts_by_category", {}))

    def test_execute_all_data_cleanup_recreates_active_skeleton_only(self) -> None:
        plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            role=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
        )
        result = env_cleanup.execute_cleanup_plan(plan)
        self.assertTrue(result["ok"])

        for directory in (
            "buddyswitch/objects/tracks",
            "buddyswitch/objects/artifacts",
            "buddyswitch/objects/messages",
            "buddyswitch/objects/track-comments",
        ):
            self.assertTrue(self._path(directory).is_dir(), f"missing recreated dir: {directory}")
        self.assertFalse(self._path("buddyswitch/objects" + "/tasks").exists())

    def test_cleanup_plan_includes_message_and_comment_objects(self) -> None:
        """MCT-RUN-003: All-data cleanup plan discovers message and comment objects."""
        self._write_json(
            "buddyswitch/objects/messages/msg-test.json",
            {
                "id": "msg-test",
                "from_actor_address": {"actor_id": "act-pm-clean", "role_id": "pm"},
                "to_actor_address": {"actor_id": "act-dev-clean", "role_id": "dev"},
                "content": "hello",
                "reply_to": None,
                "created_at": "2026-05-17T00:00:00+08:00",
            },
        )
        self._write_json(
            "buddyswitch/objects/track-comments/track-demo/comment-test.json",
            {
                "id": "comment-test",
                "track_id": "track-demo",
                "thread_id": "comment-test",
                "by_actor": {"actor_id": "act-design-clean", "role_id": "design"},
                "content": "looks good",
                "reply_to": None,
                "mentioned_actors": [],
                "status": "open",
                "created_at": "2026-05-17T00:00:00+08:00",
                "resolved_by_actor": None,
                "resolved_at": None,
                "resolution_summary": None,
            },
        )
        plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            role=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
        )
        self.assertIn("message_object_ids", plan)
        self.assertIn("msg-test", plan["message_object_ids"])
        self.assertIn("comment_object_ids", plan)
        self.assertIn("comment-test", plan["comment_object_ids"])

    def test_role_cleanup_deletes_authored_comments_without_mutating_surviving_targets(self) -> None:
        track_path = self._path("buddyswitch/objects/tracks/track-clean-comment.json")
        track_payload = {
            "id": "track-clean-comment",
            "title": "Clean Comment",
            "outcome": "clean comment",
            "owner_role": "pm",
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
            "buddyswitch/objects/track-comments/track-clean-comment/comment-dev-clean.json",
            {
                "id": "comment-dev-clean",
                "track_id": "track-clean-comment",
                "thread_id": "comment-dev-clean",
                "by_actor": {"actor_id": "act-dev-clean", "role_id": "dev"},
                "content": "delete me",
                "reply_to": None,
                "mentioned_actors": [],
                "status": "open",
                "created_at": "2026-05-17T00:00:00+08:00",
                "resolved_by_actor": None,
                "resolved_at": None,
                "resolution_summary": None,
            },
        )
        self._write_json(
            "buddyswitch/objects/track-comments/track-clean-comment/comment-design-keep.json",
            {
                "id": "comment-design-keep",
                "track_id": "track-clean-comment",
                "thread_id": "comment-design-keep",
                "by_actor": {"actor_id": "act-design-clean", "role_id": "design"},
                "content": "keep me",
                "reply_to": None,
                "mentioned_actors": [],
                "status": "open",
                "created_at": "2026-05-17T00:00:01+08:00",
                "resolved_by_actor": None,
                "resolved_at": None,
                "resolution_summary": None,
            },
        )

        plan = env_cleanup.build_cleanup_plan(
            scope="role",
            role="dev",
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
        )
        result = env_cleanup.execute_cleanup_plan(plan)

        self.assertTrue(result["ok"], msg=result)
        self.assertFalse(self._path("buddyswitch/objects/track-comments/track-clean-comment/comment-dev-clean.json").exists())
        self.assertTrue(self._path("buddyswitch/objects/track-comments/track-clean-comment/comment-design-keep.json").exists())
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
                "--role",
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

    def test_role_cleanup_uses_instance_actor_private_owner_boundary(self) -> None:
        pm_workspace = self._instance_workspace(actor_id="act-pm-cleanup", role="pm")
        dev_workspace = self._instance_workspace(actor_id="act-dev-cleanup", role="dev")

        pm_owned = pm_workspace / "private" / "notes" / "draft.md"
        pm_owned.parent.mkdir(parents=True, exist_ok=True)
        pm_owned.write_text("pm-owned", encoding="utf-8")

        dev_owned = dev_workspace / "private" / "notes" / "keep.md"
        dev_owned.parent.mkdir(parents=True, exist_ok=True)
        dev_owned.write_text("dev-owned", encoding="utf-8")

        plan = env_cleanup.build_cleanup_plan(
            scope="role",
            role="pm",
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            shared_root=self.shared_root,
        )
        self.assertIn("path_categories", plan)
        self.assertTrue(
            any(
                category == "actor_private_files"
                for category in plan["path_categories"].values()
            ),
            msg=plan,
        )
        result = env_cleanup.execute_cleanup_plan(plan)
        self.assertTrue(result["ok"], msg=result)
        self.assertFalse(pm_owned.exists())
        self.assertTrue(dev_owned.exists())

        all_data_plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            role=None,
            repo_root=self.repo_root,
            manifest_path=self.manifest_path,
            shared_root=self.shared_root,
        )
        all_data_result = env_cleanup.execute_cleanup_plan(all_data_plan)
        self.assertTrue(all_data_result["ok"], msg=all_data_result)
        self.assertFalse(dev_owned.exists())


if __name__ == "__main__":
    unittest.main()
