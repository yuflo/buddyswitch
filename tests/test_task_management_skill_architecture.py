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
from env.tool_runtime import registry as tool_router  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class TaskManagementSkillArchitectureTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        self.manifest = env_manifest.load_manifest(self.manifest_path)
        self.instance_root = self._runtime_path("instances/inst-pm-task-arch")
        self.instance_json = self.instance_root / "instance.json"
        self.instance_payload = {
            "instance_id": "inst-pm-task-arch",
            "buddy": "pm",
            "status": "active",
            "instance_root": str(self.instance_root),
            "workspace_dir": str(self.runtime_root),
        }
        (self.instance_root / "taskbox" / "pm" / "tasks").mkdir(parents=True, exist_ok=True)
        (self.instance_root / "taskbox" / "pm" / "history.md").write_text("", encoding="utf-8")
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

    def _task_file(self, task_id: str, *, buddy: str = "pm") -> Path:
        return self.instance_root / "taskbox" / buddy / "tasks" / f"{task_id}.json"

    def _history_file(self, *, buddy: str = "pm") -> Path:
        return self.instance_root / "taskbox" / buddy / "history.md"

    def _seed_taskbox_task(self, *, task_id: str, track_id: str | None, buddy: str = "pm") -> None:
        self._task_file(task_id, buddy=buddy).write_text(
            json.dumps(
                {
                    "id": task_id,
                    "owner_buddy": buddy,
                    "title": "Seed task",
                    "summary": "before update",
                    "status": "active",
                    "priority": "normal",
                    "track_id": track_id,
                    "refs": [],
                    "created_at": "2026-05-23T12:00:00+08:00",
                    "updated_at": "2026-05-23T12:00:00+08:00",
                    "closed_at": None,
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _assert_publication_rejection_without_state_mutation(
        self,
        *,
        action: str,
        args: dict[str, object],
        field: str,
        before_tracks: dict[str, str],
        before_artifacts: dict[str, str],
    ) -> None:
        rejected = self._dispatch(buddy="pm", tool="task", action=action, args=args)
        self.assertFalse(rejected["ok"], msg=rejected)
        self.assertEqual(rejected.get("permission_boundary"), "request-payload")
        blocked = str(rejected.get("why_blocked"))
        self.assertIn("publication-style payload fields:", blocked)
        self.assertIn(field, blocked)
        self.assertEqual(self._snapshot_json_dir("buddyswitch/objects/tracks"), before_tracks)
        self.assertEqual(self._snapshot_json_dir("buddyswitch/objects/artifacts"), before_artifacts)

    def _snapshot_json_dir(self, relative_dir: str) -> dict[str, str]:
        root = self._runtime_path(relative_dir)
        if not root.exists():
            return {}
        return {path.name: path.read_text(encoding="utf-8") for path in sorted(root.glob("*.json"))}

    def test_task_tool_and_skill_describe_instance_local_taskbox_contract(self) -> None:
        skill_text = (ROOT / "buddyswitch" / "skills" / "shared" / "task-tool" / "SKILL.md").read_text(encoding="utf-8").lower()
        self.assertIn("instance-local", skill_text)
        self.assertIn("taskbox", skill_text)
        self.assertIn("priority", skill_text)
        self.assertIn("history", skill_text)
        self.assertIn("do not edit taskbox files or runtime state files directly", skill_text)
        self.assertIn("env.tool", skill_text)

        catalog = tool_router.env_tools_description()["task"]
        self.assertIn("taskbox", str(catalog["object_model"]).lower())
        self.assertIn("history", catalog["operations"])
        self.assertIn("priority", catalog["payload_fields"]["create"])
        self.assertIn("refs", catalog["payload_fields"]["create"])
        self.assertIn("priority", catalog["payload_fields"]["update"])
        self.assertIn("refs", catalog["payload_fields"]["update"])

    def test_explicit_task_creates_only_taskbox_state_without_binding_fields(self) -> None:
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
                    "track_id": str(track["id"]),
                    "priority": "high" if idx == 1 else "normal",
                },
            )
            self.assertTrue(payload["ok"], msg=payload)

        after_track = json.loads(env_store.track_file("track-task-arch").read_text(encoding="utf-8"))
        after_artifact = json.loads(env_store.artifact_file("art-pm-task-arch").read_text(encoding="utf-8"))
        self.assertEqual(after_track, before_track)
        self.assertEqual(after_artifact, before_artifact)
        self.assertEqual(
            sorted(path.stem for path in (self.instance_root / "taskbox" / "pm" / "tasks").glob("task-pm-task-arch-*.json")),
            ["task-pm-task-arch-1", "task-pm-task-arch-2", "task-pm-task-arch-3"],
        )
        history_text = self._history_file().read_text(encoding="utf-8")
        self.assertIn("task.create task-pm-task-arch-1", history_text)
        stored_instance = json.loads(self.instance_json.read_text(encoding="utf-8"))
        self.assertNotIn("current_task_id", stored_instance)
        self.assertNotIn("current_track_id", stored_instance)

    def test_context_decision_surface_reports_runless_mode(self) -> None:
        payload = self._dispatch(buddy="pm", tool="context", action="summarize", args={})
        self.assertTrue(payload["ok"], msg=payload)
        self.assertEqual(payload["decision_surface"]["binding_state"]["state"], "runless")
        self.assertFalse(self._runtime_path("runs/raw").exists())
        self.assertFalse(self._runtime_path("buddyswitch/content/runs").exists())

    def test_task_update_track_id_context_changes_only_taskbox_task_state(self) -> None:
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
        self._seed_taskbox_task(task_id="task-pm-task-arch-update", track_id="track-task-arch-update-a")
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

        stored_task = json.loads(self._task_file("task-pm-task-arch-update").read_text(encoding="utf-8"))
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
        self._seed_taskbox_task(task_id="task-pm-task-arch-action-reject", track_id="track-task-arch-action-reject")
        before_tracks = self._snapshot_json_dir("buddyswitch/objects/tracks")
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
                    before_artifacts=before_artifacts,
                )

        with self.subTest(action="archive", field="template"):
            self._assert_publication_rejection_without_state_mutation(
                action="archive",
                args={"task_id": "task-pm-task-arch-action-reject", "template": "note"},
                field="template",
                before_tracks=before_tracks,
                before_artifacts=before_artifacts,
            )
