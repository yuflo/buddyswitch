#!/usr/bin/env python3
"""Task-management architecture contract tests."""

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
        self.actor_id = self._runtime_actor_id(role="pm", label="act-pm-task-arch")
        self.instance_root = self._runtime_path(f"instances/{self.actor_id}")
        self.instance_json = self.instance_root / "instance.json"
        self.instance_payload = {
            "actor_id": self.actor_id,
            "role": "pm",
            "status": "active",
            "instance_root": str(self.instance_root),
            "workspace_dir": str(self.runtime_root),
        }
        (self.instance_root / "taskbox" / "pm" / "tasks").mkdir(parents=True, exist_ok=True)
        (self.instance_root / "taskbox" / "pm" / "history.md").write_text("", encoding="utf-8")
        self.instance_json.write_text(json.dumps(self.instance_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _dispatch(self, *, role: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        actor_id = self._runtime_actor_id(role=role, label="act-pm-task-arch")
        return tool_router.dispatch_env_tool_request(
            payload={"tool": tool, "action": action, "args": args},
            active_role=role,
            actor_id=actor_id,
            instance_json=self.instance_json,
            instance_payload={**self.instance_payload, "actor_id": actor_id, "role": role},
            manifest=self.manifest,
            manifest_path=self.manifest_path,
        )

    def _task_file(self, task_id: str, *, role: str = "pm") -> Path:
        return self.instance_root / "taskbox" / role / "tasks" / f"{task_id}.json"

    def _history_file(self, *, role: str = "pm") -> Path:
        return self.instance_root / "taskbox" / role / "history.md"

    def _snapshot_json_dir(self, relative_dir: str) -> dict[str, str]:
        root = self._runtime_path(relative_dir)
        if not root.exists():
            return {}
        return {path.name: path.read_text(encoding="utf-8") for path in sorted(root.glob("*.json"))}

    def test_task_management_skill_and_catalog_are_new_surface_only(self) -> None:
        skill_path = ROOT / "buddyswitch" / "skills" / "shared" / "task-management" / "SKILL.md"
        self.assertTrue(skill_path.exists(), msg=skill_path)
        self.assertFalse((ROOT / "buddyswitch" / "skills" / "shared" / "task-tool" / "SKILL.md").exists())
        skill_text = skill_path.read_text(encoding="utf-8")
        lowered = skill_text.lower()
        self.assertIn("instance-local", lowered)
        self.assertIn("taskbox", lowered)
        self.assertIn("env.tool", lowered)
        for heading in (
            "## Continue Current Task",
            "## Create New Task",
            "## Switch Task",
            "## Confirm Pending Switch",
            "## Mark Done / Blocked",
            "## Tool Reference",
        ):
            self.assertIn(heading, skill_text)
        for old_action in ("task.list", "task.get", "task.update", "task.archive", "task.history"):
            self.assertNotIn(old_action, skill_text)
        self.assertNotIn("additionalProperties", skill_text)
        self.assertNotIn('"required"', skill_text)

        skill_ids = {row.get("id") for row in self.manifest.get("skills", []) if isinstance(row, dict)}
        self.assertIn("task-management", skill_ids)
        self.assertNotIn("task-tool", skill_ids)
        for role in self.manifest.get("roles", []):
            assert isinstance(role, dict)
            skills = set(role.get("skills", []))
            with self.subTest(role=role.get("id")):
                self.assertIn("task-management", skills)
                self.assertNotIn("task-tool", skills)

        catalog = tool_router.env_tools_description()["task"]
        self.assertEqual(set(catalog["operations"]), {"current", "propose", "confirm"})
        self.assertIn("taskbox", str(catalog["object_model"]).lower())
        propose_schema = tool_router.get_action_definition("task", "propose").input_schema
        self.assertIn("body", propose_schema["properties"]["task"]["properties"])
        self.assertIn("target", catalog["payload_fields"]["propose"])

    def test_task_propose_start_creates_only_taskbox_state_without_binding_fields(self) -> None:
        env_store.create_track(
            "track-task-arch",
            "Task Arch",
            owner_role="pm",
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
            summary="artifact should not be touched by task.propose",
        )
        before_track = json.loads(env_store.track_file("track-task-arch").read_text(encoding="utf-8"))
        before_artifact = json.loads(env_store.artifact_file("art-pm-task-arch").read_text(encoding="utf-8"))

        payload = self._dispatch(
            role="pm",
            tool="task",
            action="propose",
            args={
                "type": "start",
                "task": {
                    "title": "Task Arch",
                    "summary": "runless",
                    "body": "Detailed private task body.",
                    "priority": "high",
                    "track_id": "track-task-arch",
                    "refs": [],
                },
                "reason": "User introduced private task work.",
                "evidence": "User request.",
            },
        )
        self.assertTrue(payload["ok"], msg=payload)

        after_track = json.loads(env_store.track_file("track-task-arch").read_text(encoding="utf-8"))
        after_artifact = json.loads(env_store.artifact_file("art-pm-task-arch").read_text(encoding="utf-8"))
        self.assertEqual(after_track, before_track)
        self.assertEqual(after_artifact, before_artifact)
        stored_task = json.loads(self._task_file("task-0001-task-arch").read_text(encoding="utf-8"))
        self.assertEqual(stored_task.get("body"), "Detailed private task body.")
        self.assertEqual(stored_task.get("track_id"), "track-task-arch")
        self.assertIn("task.create task-0001-task-arch", self._history_file().read_text(encoding="utf-8"))
        stored_instance = json.loads(self.instance_json.read_text(encoding="utf-8"))
        self.assertNotIn("current_task_id", stored_instance)
        self.assertNotIn("current_track_id", stored_instance)

    def test_context_decision_surface_names_new_task_actions(self) -> None:
        payload = self._dispatch(role="pm", tool="context", action="get", args={})
        self.assertTrue(payload["ok"], msg=payload)
        operation_semantics = payload["operation_semantics"]
        self.assertIn("task.current", operation_semantics)
        self.assertIn("task.propose", operation_semantics)
        self.assertIn("task.confirm", operation_semantics)
        self.assertNotIn("task.list", operation_semantics)
        self.assertNotIn("task.update", operation_semantics)
        self.assertEqual(payload["decision_surface"]["binding_state"]["state"], "runless")

    def test_task_propose_rejects_publication_payload_fields_without_shared_mutation(self) -> None:
        env_store.create_track("track-task-arch-action-reject", "Task arch action reject", owner_role="pm")
        env_store.create_artifact_revision(
            artifact_id="art-pm-task-arch-action-reject",
            title="Task arch action reject artifact",
            created_by="pm",
            body="draft body",
            template="note",
            summary="artifact baseline",
        )
        before_tracks = self._snapshot_json_dir("buddyswitch/objects/tracks")
        before_artifacts = self._snapshot_json_dir("buddyswitch/objects/artifacts")
        before_history = self._history_file().read_text(encoding="utf-8")

        for field, value in {"visibility": "public", "template": "note", "source_refs": []}.items():
            with self.subTest(field=field):
                rejected = self._dispatch(
                    role="pm",
                    tool="task",
                    action="propose",
                    args={
                        "type": "start",
                        "task": {
                            "title": "Reject publication field",
                            "body": "Body.",
                            field: value,
                        },
                        "reason": "Bad payload.",
                        "evidence": "Bad payload.",
                    },
                )
                self.assertFalse(rejected["ok"], msg=rejected)
                self.assertIs(rejected.get("state_changed"), False)
                self.assertIn("publication-style payload fields", str(rejected.get("why_blocked")))
                self.assertEqual(self._snapshot_json_dir("buddyswitch/objects/tracks"), before_tracks)
                self.assertEqual(self._snapshot_json_dir("buddyswitch/objects/artifacts"), before_artifacts)
                self.assertEqual(self._history_file().read_text(encoding="utf-8"), before_history)


if __name__ == "__main__":
    unittest.main()
