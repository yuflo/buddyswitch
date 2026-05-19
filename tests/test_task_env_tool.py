#!/usr/bin/env python3
"""Task env.tool tests for private task model."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_legacy_store as env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class TaskEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _snapshot_json_dir(self, relative_dir: str) -> dict[str, str]:
        root = self._runtime_path(relative_dir)
        if not root.exists():
            return {}
        return {path.name: path.read_text(encoding="utf-8") for path in sorted(root.glob("*.json"))}

    def _instance_json(self, *, instance_id: str, buddy: str) -> Path:
        path = self._runtime_path(f"instance-{instance_id}.json")
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "updated_at": "2026-05-17T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _assert_publication_field_rejected_without_state_mutation(
        self,
        *,
        instance_json: Path,
        instance_id: str,
        buddy: str,
        action: str,
        args: dict[str, object],
        field: str,
        before_tracks: dict[str, str],
        before_tasks: dict[str, str],
        before_artifacts: dict[str, str],
    ) -> None:
        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy=buddy,
            tool="task",
            action=action,
            args=args,
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(rejected.get("permission_boundary"), "request-payload")
        blocked = str(rejected.get("why_blocked"))
        self.assertIn("publication-style payload fields:", blocked)
        self.assertIn(field, blocked)
        self.assertEqual(self._snapshot_json_dir("buddyswitch/objects/tracks"), before_tracks)
        self.assertEqual(self._snapshot_json_dir("buddyswitch/objects/tasks"), before_tasks)
        self.assertEqual(self._snapshot_json_dir("buddyswitch/objects/artifacts"), before_artifacts)

    def _dispatch(self, *, instance_json: Path, instance_id: str, buddy: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-task-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "instance_id": instance_id,
                "active_buddy": buddy,
                "tool": tool,
                "action": action,
                "args": args,
            },
            "deadline_ms": 35000,
        }
        envelope = runtime_broker.dispatch_runtime_request(
            request=request,
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertIsInstance(envelope, dict)
        assert isinstance(envelope, dict)
        if envelope.get("ok") is True:
            result = envelope.get("result")
            self.assertIsInstance(result, dict, msg=envelope)
            assert isinstance(result, dict)
            return result
        error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
        payload: dict[str, object] = {
            "ok": False,
            "error": {
                "code": error.get("code"),
                "message": error.get("message"),
                "retriable": error.get("retriable"),
            },
        }
        for key, value in envelope.items():
            if key in {"protocol", "request_id", "ok", "error"}:
                continue
            payload[key] = value
        return payload

    def _create_track(self) -> None:
        pm_instance = self._instance_json(instance_id="inst-pm-task", buddy="pm")
        created = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-task",
            buddy="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-task-private",
                "title": "Private hint",
                "outcome": "outcome",
                "appetite": "1 day",
                "now": {"next": "x", "blocker": None},
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

    def test_task_track_id_hint_does_not_mutate_track(self) -> None:
        self._create_track()
        before = env_store.get_track("track-task-private")
        self.assertIsInstance(before, dict)

        dev_instance = self._instance_json(instance_id="inst-dev-task", buddy="dev")
        created = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-task",
            buddy="dev",
            tool="task",
            action="create",
            args={
                "task_id": "task-dev-private",
                "title": "Private task",
                "track_id": "track-task-private",
                "summary": "hint only",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        after = env_store.get_track("track-task-private")
        self.assertEqual(before, after)

    def test_task_get_rejects_foreign_private_task(self) -> None:
        self._create_track()
        dev_instance = self._instance_json(instance_id="inst-dev-task", buddy="dev")
        self.assertTrue(
            self._dispatch(
                instance_json=dev_instance,
                instance_id="inst-dev-task",
                buddy="dev",
                tool="task",
                action="create",
                args={
                    "task_id": "task-dev-private-2",
                    "title": "Private task",
                    "summary": "private",
                },
            ).get("ok")
        )

        pm_instance = self._instance_json(instance_id="inst-pm-task", buddy="pm")
        denied = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-task",
            buddy="pm",
            tool="task",
            action="get",
            args={"task_id": "task-dev-private-2"},
        )
        self.assertFalse(denied.get("ok"), msg=denied)
        self.assertEqual(denied.get("permission_boundary"), "task.buddy_scope")

    def test_task_rows_omit_artifact_linkage_fields(self) -> None:
        dev_instance = self._instance_json(instance_id="inst-dev-task", buddy="dev")
        created = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-task",
            buddy="dev",
            tool="task",
            action="create",
            args={"task_id": "task-dev-no-art", "title": "No artifact fields", "summary": "x"},
        )
        self.assertTrue(created.get("ok"), msg=created)

        one = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-task",
            buddy="dev",
            tool="task",
            action="get",
            args={"task_id": "task-dev-no-art"},
        )
        many = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-task",
            buddy="dev",
            tool="task",
            action="list",
            args={},
        )
        self.assertTrue(one.get("ok"), msg=one)
        self.assertTrue(many.get("ok"), msg=many)
        row = one["task"]
        encoded = json.dumps(row, ensure_ascii=True)
        self.assertNotIn("artifact_ids", encoded)
        self.assertNotIn("artifact" + "_slots", encoded)
        self.assertNotIn("current_artifacts", encoded)
        self.assertNotIn("shared_materials", encoded)

    def test_task_track_id_hint_does_not_mutate_track_state(self) -> None:
        env_store.create_track("track-task-hint-envtool", "Track Hint Env Tool", owner_buddy="pm")
        env_store.create_artifact_revision(
            artifact_id="art-dev-track-hint-envtool",
            title="Track hint artifact",
            created_by="dev",
            body="draft body",
            template="note",
            summary="artifact should stay untouched",
        )
        before_track = json.loads(env_store.track_file("track-task-hint-envtool").read_text(encoding="utf-8"))
        before_artifact = json.loads(env_store.artifact_file("art-dev-track-hint-envtool").read_text(encoding="utf-8"))
        instance_json = self._instance_json(instance_id="inst-dev-task", buddy="dev")

        created = self._dispatch(
            instance_json=instance_json,
            tool="task",
            action="create",
            args={
                "task_id": "task-dev-track-hint-envtool",
                "title": "Track hint task",
                "track_id": "track-task-hint-envtool",
            },
            instance_id="inst-dev-task",
            buddy="dev",
        )
        self.assertTrue(created.get("ok"), msg=created)

        after_track = json.loads(env_store.track_file("track-task-hint-envtool").read_text(encoding="utf-8"))
        after_artifact = json.loads(env_store.artifact_file("art-dev-track-hint-envtool").read_text(encoding="utf-8"))
        self.assertEqual(after_track, before_track)
        self.assertEqual(after_artifact, before_artifact)

        stored_task = env_store.get_task("task-dev-track-hint-envtool")
        self.assertIsInstance(stored_task, dict)
        assert isinstance(stored_task, dict)
        self.assertEqual(stored_task.get("track_id"), "track-task-hint-envtool")
        self.assertNotIn("artifact_ids", stored_task)
        self.assertNotIn("artifact_slots", stored_task)

    def test_task_rejects_publication_style_payload_without_state_mutation(self) -> None:
        env_store.create_track("track-task-pub-reject", "Task pub reject track", owner_buddy="pm")
        env_store.create_artifact_revision(
            artifact_id="art-dev-pub-reject",
            title="Publication guard artifact",
            created_by="dev",
            body="draft body",
            template="note",
            summary="artifact baseline",
        )
        before_tracks = self._snapshot_json_dir("buddyswitch/objects/tracks")
        before_tasks = self._snapshot_json_dir("buddyswitch/objects/tasks")
        before_artifacts = self._snapshot_json_dir("buddyswitch/objects/artifacts")

        instance_json = self._instance_json(instance_id="inst-dev-task", buddy="dev")
        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-task",
            buddy="dev",
            tool="task",
            action="create",
            args={
                "task_id": "task-dev-pub-reject",
                "title": "Reject publication payload",
                "track_id": "track-task-pub-reject",
                "artifact_id": "art-dev-pub-reject",
                "published_to_track": "track-task-pub-reject",
                "shared_materials": [],
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(rejected.get("permission_boundary"), "request-payload")
        self.assertIn("publication-style payload fields:", str(rejected.get("why_blocked")))

        after_tracks = self._snapshot_json_dir("buddyswitch/objects/tracks")
        after_tasks = self._snapshot_json_dir("buddyswitch/objects/tasks")
        after_artifacts = self._snapshot_json_dir("buddyswitch/objects/artifacts")
        self.assertEqual(after_tracks, before_tracks)
        self.assertEqual(after_tasks, before_tasks)
        self.assertEqual(after_artifacts, before_artifacts)

    def test_task_rejects_remaining_publication_style_fields_without_state_mutation(self) -> None:
        env_store.create_track("track-task-pub-remaining", "Task pub remaining track", owner_buddy="pm")
        env_store.create_artifact_revision(
            artifact_id="art-dev-pub-remaining",
            title="Publication remaining guard artifact",
            created_by="dev",
            body="draft body",
            template="note",
            summary="artifact baseline",
        )
        before_tracks = self._snapshot_json_dir("buddyswitch/objects/tracks")
        before_tasks = self._snapshot_json_dir("buddyswitch/objects/tasks")
        before_artifacts = self._snapshot_json_dir("buddyswitch/objects/artifacts")
        instance_json = self._instance_json(instance_id="inst-dev-task", buddy="dev")

        field_values: dict[str, object] = {
            "current_artifacts": [],
            "updates": [],
            "source_refs": [],
            "body": "draft body",
            "template": "note",
            "supersedes_artifact_id": "art-dev-pub-remaining",
        }
        for index, (field, value) in enumerate(field_values.items(), start=1):
            with self.subTest(action="create", field=field):
                self._assert_publication_field_rejected_without_state_mutation(
                    instance_json=instance_json,
                    instance_id="inst-dev-task",
                    buddy="dev",
                    action="create",
                    args={
                        "task_id": f"task-dev-pub-remaining-{index}",
                        "title": f"Reject publication payload {index}",
                        "track_id": "track-task-pub-remaining",
                        field: value,
                    },
                    field=field,
                    before_tracks=before_tracks,
                    before_tasks=before_tasks,
                    before_artifacts=before_artifacts,
                )

    def test_task_update_track_id_change_does_not_mutate_track_or_artifact_state(self) -> None:
        env_store.create_track("track-task-update-context-a", "Task update context A", owner_buddy="pm")
        env_store.create_track("track-task-update-context-b", "Task update context B", owner_buddy="pm")
        env_store.create_artifact_revision(
            artifact_id="art-dev-task-update-context",
            title="Task update context artifact",
            created_by="dev",
            body="draft body",
            template="note",
            summary="artifact baseline",
        )
        env_store.create_task(
            "task-dev-track-update-context",
            "Track update context task",
            buddy="dev",
            track_id="track-task-update-context-a",
            status="active",
            summary="before update",
            initial_run_id=None,
        )
        before_track_a = json.loads(env_store.track_file("track-task-update-context-a").read_text(encoding="utf-8"))
        before_track_b = json.loads(env_store.track_file("track-task-update-context-b").read_text(encoding="utf-8"))
        before_artifact = json.loads(env_store.artifact_file("art-dev-task-update-context").read_text(encoding="utf-8"))
        instance_json = self._instance_json(instance_id="inst-dev-task", buddy="dev")

        updated = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-task",
            buddy="dev",
            tool="task",
            action="update",
            args={
                "task_id": "task-dev-track-update-context",
                "track_id": "track-task-update-context-b",
            },
        )
        self.assertTrue(updated.get("ok"), msg=updated)

        after_track_a = json.loads(env_store.track_file("track-task-update-context-a").read_text(encoding="utf-8"))
        after_track_b = json.loads(env_store.track_file("track-task-update-context-b").read_text(encoding="utf-8"))
        after_artifact = json.loads(env_store.artifact_file("art-dev-task-update-context").read_text(encoding="utf-8"))
        self.assertEqual(after_track_a, before_track_a)
        self.assertEqual(after_track_b, before_track_b)
        self.assertEqual(after_artifact, before_artifact)

        stored_task = env_store.get_task("task-dev-track-update-context")
        self.assertIsInstance(stored_task, dict)
        assert isinstance(stored_task, dict)
        self.assertEqual(stored_task.get("track_id"), "track-task-update-context-b")

    def test_task_update_and_archive_reject_publication_fields_without_state_mutation(self) -> None:
        env_store.create_track("track-task-action-pub-reject", "Task action pub reject track", owner_buddy="pm")
        env_store.create_artifact_revision(
            artifact_id="art-dev-action-pub-reject",
            title="Task action pub reject artifact",
            created_by="dev",
            body="draft body",
            template="note",
            summary="artifact baseline",
        )
        env_store.create_task(
            "task-dev-action-pub-reject",
            "Task action pub reject",
            buddy="dev",
            track_id="track-task-action-pub-reject",
            status="active",
            summary="before action",
            initial_run_id=None,
        )
        before_tracks = self._snapshot_json_dir("buddyswitch/objects/tracks")
        before_tasks = self._snapshot_json_dir("buddyswitch/objects/tasks")
        before_artifacts = self._snapshot_json_dir("buddyswitch/objects/artifacts")
        instance_json = self._instance_json(instance_id="inst-dev-task", buddy="dev")

        field_values: dict[str, object] = {
            "current_artifacts": [],
            "updates": [],
            "source_refs": [],
            "body": "draft body",
            "template": "note",
            "supersedes_artifact_id": "art-dev-action-pub-reject",
        }
        for field, value in field_values.items():
            with self.subTest(action="update", field=field):
                self._assert_publication_field_rejected_without_state_mutation(
                    instance_json=instance_json,
                    instance_id="inst-dev-task",
                    buddy="dev",
                    action="update",
                    args={"task_id": "task-dev-action-pub-reject", field: value},
                    field=field,
                    before_tracks=before_tracks,
                    before_tasks=before_tasks,
                    before_artifacts=before_artifacts,
                )

        with self.subTest(action="archive", field="body"):
            self._assert_publication_field_rejected_without_state_mutation(
                instance_json=instance_json,
                instance_id="inst-dev-task",
                buddy="dev",
                action="archive",
                args={"task_id": "task-dev-action-pub-reject", "body": "draft body"},
                field="body",
                before_tracks=before_tracks,
                before_tasks=before_tasks,
                before_artifacts=before_artifacts,
            )


if __name__ == "__main__":
    unittest.main()
