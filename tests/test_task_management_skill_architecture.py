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
import env_legacy_store as env_store  # noqa: E402
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

    def _snapshot_json_dir(self, relative_dir: str) -> dict[str, str]:
        root = self._runtime_path(relative_dir)
        if not root.exists():
            return {}
        return {path.name: path.read_text(encoding="utf-8") for path in sorted(root.glob("*.json"))}

    def _assert_publication_rejection_without_state_mutation(
        self,
        *,
        action: str,
        args: dict[str, object],
        field: str,
        before_tracks: dict[str, str],
        before_tasks: dict[str, str],
        before_artifacts: dict[str, str],
    ) -> None:
        rejected = self._dispatch(buddy="pm", tool="task", action=action, args=args)
        self.assertFalse(rejected["ok"], msg=rejected)
        self.assertEqual(rejected.get("permission_boundary"), "request-payload")
        blocked = str(rejected.get("why_blocked"))
        self.assertIn("publication-style payload fields:", blocked)
        self.assertIn(field, blocked)
        self.assertEqual(self._snapshot_json_dir("buddyswitch/objects/tracks"), before_tracks)
        self.assertEqual(self._snapshot_json_dir("buddyswitch/objects/tasks"), before_tasks)
        self.assertEqual(self._snapshot_json_dir("buddyswitch/objects/artifacts"), before_artifacts)

    def test_explicit_task_creates_only_task_objects_without_binding_fields(self) -> None:
        track = env_store.create_track(
            "track-task-arch",
            "Task Arch",
            owner_buddy="pm",
            outcome="Validate private task-only object writes.",
            appetite="1 day",
            now={"next": "Create private tasks", "blocker": None},
        )
        env_store.create_artifact_revision(
            artifact_id="art-pm-task-arch",
            title="Task arch baseline artifact",
            created_by="pm",
            body="draft body",
            template="note",
            summary="artifact should not be touched by task.create",
        )
        before_track = json.loads(env_store.track_file("track-task-arch").read_text(encoding="utf-8"))
        before_artifact = json.loads(env_store.artifact_file("art-pm-task-arch").read_text(encoding="utf-8"))
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

        after_track = json.loads(env_store.track_file("track-task-arch").read_text(encoding="utf-8"))
        after_artifact = json.loads(env_store.artifact_file("art-pm-task-arch").read_text(encoding="utf-8"))
        self.assertEqual(after_track, before_track)
        self.assertEqual(after_artifact, before_artifact)

        task_files = sorted((self._runtime_path("buddyswitch/objects/tasks")).glob("task-pm-task-arch-*.json"))
        self.assertEqual(len(task_files), 3)
        stored_instance = json.loads(self.instance_json.read_text(encoding="utf-8"))
        self.assertNotIn("current_task_id", stored_instance)
        self.assertNotIn("current_track_id", stored_instance)

    def test_task_payload_rejection_leaves_track_and_artifact_state_unchanged(self) -> None:
        env_store.create_track("track-task-arch-reject", "Task arch reject", owner_buddy="pm")
        env_store.create_artifact_revision(
            artifact_id="art-pm-task-arch-reject",
            title="Task arch reject artifact",
            created_by="pm",
            body="draft body",
            template="note",
            summary="artifact baseline",
        )
        before_tracks = self._snapshot_json_dir("buddyswitch/objects/tracks")
        before_tasks = self._snapshot_json_dir("buddyswitch/objects/tasks")
        before_artifacts = self._snapshot_json_dir("buddyswitch/objects/artifacts")

        rejected = self._dispatch(
            buddy="pm",
            tool="task",
            action="create",
            args={
                "task_id": "task-pm-task-arch-reject",
                "title": "Reject publication fields",
                "track_id": "track-task-arch-reject",
                "artifact_ids": ["art-pm-task-arch-reject"],
                "shared_materials": [],
                "close_proof": [],
            },
        )
        self.assertFalse(rejected["ok"], msg=rejected)
        self.assertEqual(rejected.get("permission_boundary"), "request-payload")
        self.assertIn("publication-style payload fields:", str(rejected.get("why_blocked")))

        after_tracks = self._snapshot_json_dir("buddyswitch/objects/tracks")
        after_tasks = self._snapshot_json_dir("buddyswitch/objects/tasks")
        after_artifacts = self._snapshot_json_dir("buddyswitch/objects/artifacts")
        self.assertEqual(after_tracks, before_tracks)
        self.assertEqual(after_tasks, before_tasks)
        self.assertEqual(after_artifacts, before_artifacts)

    def test_context_decision_surface_reports_runless_mode(self) -> None:
        payload = self._dispatch(buddy="pm", tool="context", action="summarize", args={})
        self.assertTrue(payload["ok"], msg=payload)
        self.assertEqual(payload["decision_surface"]["binding_state"]["state"], "runless")
        self.assertFalse(self._runtime_path("runs/raw").exists())
        self.assertFalse(self._runtime_path("buddyswitch/content/runs").exists())

    def test_task_update_track_id_context_changes_only_task_state(self) -> None:
        env_store.create_track("track-task-arch-update-a", "Task arch update A", owner_buddy="pm")
        env_store.create_track("track-task-arch-update-b", "Task arch update B", owner_buddy="pm")
        env_store.create_artifact_revision(
            artifact_id="art-pm-task-arch-update",
            title="Task arch update artifact",
            created_by="pm",
            body="draft body",
            template="note",
            summary="artifact baseline",
        )
        env_store.create_task(
            "task-pm-task-arch-update",
            "Task arch update task",
            buddy="pm",
            track_id="track-task-arch-update-a",
            summary="before update",
            status="active",
            initial_run_id=None,
        )
        before_track_a = json.loads(env_store.track_file("track-task-arch-update-a").read_text(encoding="utf-8"))
        before_track_b = json.loads(env_store.track_file("track-task-arch-update-b").read_text(encoding="utf-8"))
        before_artifact = json.loads(env_store.artifact_file("art-pm-task-arch-update").read_text(encoding="utf-8"))

        updated = self._dispatch(
            buddy="pm",
            tool="task",
            action="update",
            args={
                "task_id": "task-pm-task-arch-update",
                "track_id": "track-task-arch-update-b",
            },
        )
        self.assertTrue(updated["ok"], msg=updated)

        after_track_a = json.loads(env_store.track_file("track-task-arch-update-a").read_text(encoding="utf-8"))
        after_track_b = json.loads(env_store.track_file("track-task-arch-update-b").read_text(encoding="utf-8"))
        after_artifact = json.loads(env_store.artifact_file("art-pm-task-arch-update").read_text(encoding="utf-8"))
        self.assertEqual(after_track_a, before_track_a)
        self.assertEqual(after_track_b, before_track_b)
        self.assertEqual(after_artifact, before_artifact)

        stored_task = env_store.get_task("task-pm-task-arch-update")
        self.assertIsInstance(stored_task, dict)
        assert isinstance(stored_task, dict)
        self.assertEqual(stored_task.get("track_id"), "track-task-arch-update-b")

    def test_task_update_and_archive_reject_publication_payload_fields(self) -> None:
        env_store.create_track("track-task-arch-action-reject", "Task arch action reject", owner_buddy="pm")
        env_store.create_artifact_revision(
            artifact_id="art-pm-task-arch-action-reject",
            title="Task arch action reject artifact",
            created_by="pm",
            body="draft body",
            template="note",
            summary="artifact baseline",
        )
        env_store.create_task(
            "task-pm-task-arch-action-reject",
            "Task arch action reject task",
            buddy="pm",
            track_id="track-task-arch-action-reject",
            summary="before action",
            status="active",
            initial_run_id=None,
        )
        before_tracks = self._snapshot_json_dir("buddyswitch/objects/tracks")
        before_tasks = self._snapshot_json_dir("buddyswitch/objects/tasks")
        before_artifacts = self._snapshot_json_dir("buddyswitch/objects/artifacts")

        field_values: dict[str, object] = {
            "current_artifacts": [],
            "updates": [],
            "source_refs": [],
            "body": "draft body",
            "template": "note",
            "supersedes_artifact_id": "art-pm-task-arch-action-reject",
        }
        for field, value in field_values.items():
            with self.subTest(action="update", field=field):
                self._assert_publication_rejection_without_state_mutation(
                    action="update",
                    args={"task_id": "task-pm-task-arch-action-reject", field: value},
                    field=field,
                    before_tracks=before_tracks,
                    before_tasks=before_tasks,
                    before_artifacts=before_artifacts,
                )

        with self.subTest(action="archive", field="template"):
            self._assert_publication_rejection_without_state_mutation(
                action="archive",
                args={"task_id": "task-pm-task-arch-action-reject", "template": "note"},
                field="template",
                before_tracks=before_tracks,
                before_tasks=before_tasks,
                before_artifacts=before_artifacts,
            )


if __name__ == "__main__":
    unittest.main()
