import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402

from env_store import (  # noqa: E402
    create_artifact,
    create_comment,
    create_message,
    create_task,
    create_track,
    delete_artifact,
    get_artifact,
    get_comment,
    get_message,
    get_track,
    get_task,
    list_messages,
    list_comments,
    save_message,
    save_comment,
    update_artifact,
    validate_track,
    validate_task,
    validate_message,
    validate_comment,
)
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

_LEGACY_HANDOFF_PRIVATE_PATHS_FIELD = "buddybox_" + "paths"


class ResolveTimeTaskMaterializationTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _task_path(self, task_id: str) -> Path:
        return self._runtime_path(f"buddyswitch/objects/tasks/{task_id}.json")

    def setUp(self) -> None:
        super().setUp()
        self._task_id = "task-dev-resolve-materialization"
        task_path = self._task_path(self._task_id)
        if task_path.exists():
            task_path.unlink()

    def tearDown(self) -> None:
        task_path = self._task_path(self._task_id)
        if task_path.exists():
            task_path.unlink()
        super().tearDown()

    def test_create_task_allows_resolve_time_materialization_without_run(self) -> None:
        task = create_task(
            self._task_id,
            "Resolve-Time Materialization",
            buddy="dev",
        )

        self.assertEqual(task["artifact_ids"], [])
        self.assertEqual(task["artifact_slots"], {})
        self.assertNotIn("run_ids", task)
        self.assertNotIn("latest_run_id", task)

    def test_validate_task_rejects_legacy_run_fields(self) -> None:
        payload = {
            "id": "task-dev-validate-empty-runs",
            "buddy": "dev",
            "title": "Validate Empty Runs",
            "status": "active",
            "track_id": None,
            "artifact_ids": [],
            "artifact_slots": {},
            "run_ids": ["run-old"],
            "latest_run_id": "run-old",
            "summary": "",
            "created_at": "2026-04-22T10:00:00+08:00",
            "updated_at": "2026-04-22T10:00:00+08:00",
        }

        with self.assertRaises(ValueError):
            validate_task(payload)

    def test_create_task_binds_task_and_track_ids_together(self) -> None:
        track = create_track("track-pm-binding-invariant", "PM Binding Invariant")
        task = create_task(
            "task-pm-binding-invariant",
            "PM Binding Invariant",
            buddy="pm",
            track_id=track["id"],
        )

        stored_task = get_task(task["id"])
        stored_track = get_track(track["id"])

        self.assertEqual(stored_task["track_id"], track["id"])
        self.assertIn(task["id"], stored_track["task_ids"])


class ArtifactSlotLifecycleTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _task_path(self, task_id: str) -> Path:
        return self._runtime_path(f"buddyswitch/objects/tasks/{task_id}.json")

    def _artifact_path(self, artifact_id: str) -> Path:
        return self._runtime_path(f"buddyswitch/objects/artifacts/{artifact_id}.json")

    def _cleanup_fixtures(self) -> None:
        for task_id in ("task-pm-v2-slot", "task-pm-v2-revision", "task-pm-v2-move-source", "task-pm-v2-move-dest"):
            path = self._task_path(task_id)
            if path.exists():
                path.unlink()
        for artifact_id in (
            "art-task-pm-v2-revision-prd-r1",
            "art-task-pm-v2-revision-prd-r2",
            "art-task-pm-v2-revision-prd-r3",
            "art-task-pm-v2-move-source-prd-r1",
            "art-task-pm-v2-move-source-prd-r2",
            "art-task-pm-v2-move-dest-prd-r1",
            "art-task-pm-v2-move-dest-prd-r2",
        ):
            path = self._artifact_path(artifact_id)
            if path.exists():
                path.unlink()

    def setUp(self) -> None:
        super().setUp()
        self._cleanup_fixtures()

    def tearDown(self) -> None:
        self._cleanup_fixtures()
        super().tearDown()

    def test_create_task_initializes_artifact_slots(self) -> None:
        task = create_task(
            "task-pm-v2-slot",
            "V2 Slot Task",
            buddy="pm",
        )

        self.assertEqual(task["artifact_slots"], {})
        self.assertNotIn("latest_artifact_id", task)
        stored_task = json.loads(self._task_path(task["id"]).read_text(encoding="utf-8"))
        self.assertEqual(stored_task["artifact_slots"], {})
        self.assertNotIn("latest_artifact_id", stored_task)

    def test_create_artifact_builds_revision_chain_for_same_slot(self) -> None:
        task = create_task(
            "task-pm-v2-revision",
            "V2 Revision Task",
            buddy="pm",
        )

        first = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r1",
            title="PRD revision 1",
            buddy="pm",
            kind="prd",
            task_id=task["id"],
            created_by="test-env-store-v2",
            summary="Initial PRD",
            content={"task_summary": "Initial PRD"},
        )
        second = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r2",
            title="PRD revision 2",
            buddy="pm",
            kind="prd",
            task_id=task["id"],
            created_by="test-env-store-v2",
            summary="Revised PRD",
            content={"task_summary": "Revised PRD"},
        )

        stored_first = get_artifact(first["id"])
        stored_second = get_artifact(second["id"])
        stored_task = get_task(task["id"])
        stored_first_json = json.loads(self._artifact_path(first["id"]).read_text(encoding="utf-8"))
        stored_second_json = json.loads(self._artifact_path(second["id"]).read_text(encoding="utf-8"))
        stored_task_json = json.loads(self._task_path(task["id"]).read_text(encoding="utf-8"))

        self.assertEqual(stored_first["revision"], 1)
        self.assertFalse(stored_first["is_current"])
        self.assertEqual(stored_second["revision"], 2)
        self.assertEqual(stored_second["supersedes_artifact_id"], stored_first["id"])
        self.assertTrue(stored_second["is_current"])
        self.assertEqual(
            stored_task["artifact_slots"]["prd"]["current_artifact_id"],
            stored_second["id"],
        )
        self.assertEqual(stored_task["artifact_slots"]["prd"]["revision_count"], 2)
        self.assertIn("supersedes_artifact_id", stored_first_json)
        self.assertIsNone(stored_first_json["supersedes_artifact_id"])
        self.assertEqual(stored_second_json["supersedes_artifact_id"], stored_first["id"])
        self.assertNotIn("latest_artifact_id", stored_task_json)

    def test_create_artifact_always_registers_new_revision(self) -> None:
        task = create_task(
            "task-pm-v2-revision",
            "V2 Revision Task",
            buddy="pm",
        )

        initial = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r1",
            title="PRD revision 1",
            buddy="pm",
            kind="prd",
            task_id=task["id"],
            created_by="test-env-store-v2",
            summary="Initial PRD",
            content={"task_summary": "Initial PRD"},
        )

        second = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r2",
            title="PRD revision 2",
            buddy="pm",
            kind="prd",
            task_id=task["id"],
            created_by="test-env-store-v2",
            summary="Revised PRD",
            content={"task_summary": "Revised PRD"},
        )

        stored_initial = get_artifact(initial["id"])
        stored_second = get_artifact(second["id"])
        stored_task = get_task(task["id"])
        self.assertFalse(stored_initial["is_current"])
        self.assertTrue(stored_second["is_current"])
        self.assertEqual(stored_task["artifact_slots"]["prd"]["current_artifact_id"], second["id"])
        self.assertEqual(stored_task["artifact_slots"]["prd"]["revision_count"], 2)

    def test_updating_non_current_revision_keeps_slot_head_and_revision_count(self) -> None:
        task = create_task(
            "task-pm-v2-revision",
            "V2 Revision Task",
            buddy="pm",
        )

        first = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r1",
            title="PRD revision 1",
            buddy="pm",
            kind="prd",
            task_id=task["id"],
            created_by="test-env-store-v2",
            summary="Initial PRD",
            content={"task_summary": "Initial PRD"},
        )
        second = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r2",
            title="PRD revision 2",
            buddy="pm",
            kind="prd",
            task_id=task["id"],
            created_by="test-env-store-v2",
            summary="Revised PRD",
            content={"task_summary": "Revised PRD"},
        )

        update_artifact(first["id"], {"summary": "Retouched but still historical"})

        stored_first = get_artifact(first["id"])
        stored_second = get_artifact(second["id"])
        stored_task = get_task(task["id"])

        self.assertFalse(stored_first["is_current"])
        self.assertTrue(stored_second["is_current"])
        self.assertEqual(stored_task["artifact_slots"]["prd"]["current_artifact_id"], stored_second["id"])
        self.assertEqual(stored_task["artifact_slots"]["prd"]["revision_count"], 2)

    def test_deleting_current_revision_promotes_survivor_and_keeps_revision_progression(self) -> None:
        task = create_task(
            "task-pm-v2-revision",
            "V2 Revision Task",
            buddy="pm",
        )

        first = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r1",
            title="PRD revision 1",
            buddy="pm",
            kind="prd",
            task_id=task["id"],
            created_by="test-env-store-v2",
            summary="Initial PRD",
            content={"task_summary": "Initial PRD"},
        )
        second = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r2",
            title="PRD revision 2",
            buddy="pm",
            kind="prd",
            task_id=task["id"],
            created_by="test-env-store-v2",
            summary="Revised PRD",
            content={"task_summary": "Revised PRD"},
        )

        delete_artifact(second["id"])

        promoted_first = get_artifact(first["id"])
        stored_task_after_delete = get_task(task["id"])

        self.assertTrue(promoted_first["is_current"])
        self.assertEqual(stored_task_after_delete["artifact_slots"]["prd"]["current_artifact_id"], first["id"])
        self.assertEqual(stored_task_after_delete["artifact_slots"]["prd"]["revision_count"], 2)

        third = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r3",
            title="PRD revision 3",
            buddy="pm",
            kind="prd",
            task_id=task["id"],
            created_by="test-env-store-v2",
            summary="Third PRD",
            content={"task_summary": "Third PRD"},
        )

        stored_third = get_artifact(third["id"])
        stored_task_after_third = get_task(task["id"])

        self.assertEqual(stored_third["revision"], 3)
        self.assertEqual(stored_third["supersedes_artifact_id"], first["id"])
        self.assertTrue(stored_third["is_current"])
        self.assertFalse(get_artifact(first["id"])["is_current"])
        self.assertEqual(stored_task_after_third["artifact_slots"]["prd"]["current_artifact_id"], third["id"])
        self.assertEqual(stored_task_after_third["artifact_slots"]["prd"]["revision_count"], 3)

    def test_moving_historical_revision_into_occupied_destination_slot_keeps_destination_head(self) -> None:
        source = create_task(
            "task-pm-v2-move-source",
            "V2 Move Source",
            buddy="pm",
        )
        dest = create_task(
            "task-pm-v2-move-dest",
            "V2 Move Dest",
            buddy="pm",
        )

        source_old = create_artifact(
            artifact_id="art-task-pm-v2-move-source-prd-r1",
            title="Source PRD 1",
            buddy="pm",
            kind="prd",
            task_id=source["id"],
            created_by="test-env-store-v2",
            summary="Source old",
            content={"task_summary": "Source old"},
        )
        source_current = create_artifact(
            artifact_id="art-task-pm-v2-move-source-prd-r2",
            title="Source PRD 2",
            buddy="pm",
            kind="prd",
            task_id=source["id"],
            created_by="test-env-store-v2",
            summary="Source current",
            content={"task_summary": "Source current"},
        )
        dest_current = create_artifact(
            artifact_id="art-task-pm-v2-move-dest-prd-r1",
            title="Dest PRD 1",
            buddy="pm",
            kind="prd",
            task_id=dest["id"],
            created_by="test-env-store-v2",
            summary="Dest current",
            content={"task_summary": "Dest current"},
        )

        update_artifact(source_old["id"], {"task_id": dest["id"]})

        moved = get_artifact(source_old["id"])
        dest_current_after = get_artifact(dest_current["id"])
        moved_source_current = get_artifact(source_current["id"])
        dest_task = get_task(dest["id"])
        current_artifacts = [
            artifact
            for artifact in (moved, dest_current_after, moved_source_current)
            if artifact["task_id"] == dest["id"] and artifact["kind"] == "prd" and artifact["is_current"]
        ]

        self.assertFalse(moved["is_current"])
        self.assertTrue(dest_current_after["is_current"])
        self.assertEqual(dest_task["artifact_slots"]["prd"]["current_artifact_id"], dest_current["id"])
        self.assertEqual(dest_task["artifact_slots"]["prd"]["revision_count"], 1)
        self.assertEqual(len(current_artifacts), 1)

    def test_moving_current_revision_into_occupied_destination_slot_promotes_moved_artifact(self) -> None:
        source = create_task(
            "task-pm-v2-move-source",
            "V2 Move Source",
            buddy="pm",
        )
        dest = create_task(
            "task-pm-v2-move-dest",
            "V2 Move Dest",
            buddy="pm",
        )

        source_old = create_artifact(
            artifact_id="art-task-pm-v2-move-source-prd-r1",
            title="Source PRD 1",
            buddy="pm",
            kind="prd",
            task_id=source["id"],
            created_by="test-env-store-v2",
            summary="Source old",
            content={"task_summary": "Source old"},
        )
        source_current = create_artifact(
            artifact_id="art-task-pm-v2-move-source-prd-r2",
            title="Source PRD 2",
            buddy="pm",
            kind="prd",
            task_id=source["id"],
            created_by="test-env-store-v2",
            summary="Source current",
            content={"task_summary": "Source current"},
        )
        dest_current = create_artifact(
            artifact_id="art-task-pm-v2-move-dest-prd-r1",
            title="Dest PRD 1",
            buddy="pm",
            kind="prd",
            task_id=dest["id"],
            created_by="test-env-store-v2",
            summary="Dest current",
            content={"task_summary": "Dest current"},
        )

        update_artifact(source_current["id"], {"task_id": dest["id"]})

        moved = get_artifact(source_current["id"])
        dest_current_after = get_artifact(dest_current["id"])
        dest_task = get_task(dest["id"])
        current_artifacts = [
            artifact
            for artifact in (moved, dest_current_after, get_artifact(source_old["id"]))
            if artifact["task_id"] == dest["id"] and artifact["kind"] == "prd" and artifact["is_current"]
        ]

        self.assertTrue(moved["is_current"])
        self.assertFalse(dest_current_after["is_current"])
        self.assertEqual(dest_task["artifact_slots"]["prd"]["current_artifact_id"], moved["id"])
        self.assertEqual(dest_task["artifact_slots"]["prd"]["revision_count"], 2)
        self.assertEqual(len(current_artifacts), 1)


class TrackStoreContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_validate_track_rejects_current_and_next_buddy(self) -> None:
        payload = {
            "id": "track-legacy-fields",
            "title": "Legacy",
            "status": "active",
            "owner_buddy": "pm",
            "task_ids": [],
            "summary": "",
            "updated_at": "2026-05-15T00:00:00Z",
            "current_buddy": "pm",
            "next_buddy": "dev",
        }
        with self.assertRaises(ValueError):
            validate_track(payload)

    def test_store_rejects_handoff_source_ref_type(self) -> None:
        task = create_task("task-src-ref-reject", "Task", buddy="pm")
        with self.assertRaises(ValueError):
            create_artifact(
                artifact_id="art-src-ref-reject",
                title="Reject handoff source ref",
                buddy="pm",
                kind="prd",
                task_id=task["id"],
                created_by="pm",
                summary="",
                content={"body": "x"},
                source_refs=[{"type": "handoff", "id": "handoff-old"}],
            )


class MessageStoreTests(RuntimeWorkspaceTestMixin, unittest.TestCase):

    def test_create_message_persists_flat_message_without_status(self):
        msg = create_message(from_buddy="design", to_buddy="dev", content="Hello Dev!")
        self.assertTrue(msg["id"].startswith("msg-"))
        self.assertEqual(msg["from_buddy"], "design")
        self.assertEqual(msg["to_buddy"], "dev")
        self.assertEqual(msg["content"], "Hello Dev!")
        self.assertIsNone(msg["reply_to"])
        self.assertIsInstance(msg["created_at"], str)
        self.assertTrue(len(msg["created_at"]) > 0)
        self.assertNotIn("status", msg)
        self.assertNotIn("read_at", msg)
        self.assertNotIn("track_id", msg)
        self.assertNotIn("task_id", msg)
        self.assertNotIn("artifact_id", msg)
        self.assertNotIn("recipients", msg)
        self.assertNotIn("broadcast", msg)

        stored = get_message(msg["id"])
        self.assertIsNotNone(stored)
        self.assertEqual(stored["from_buddy"], "design")
        self.assertEqual(stored["to_buddy"], "dev")
        self.assertNotIn("status", stored)

    def test_create_message_with_reply_to(self):
        msg1 = create_message(from_buddy="pm", to_buddy="dev", content="First")
        msg2 = create_message(from_buddy="dev", to_buddy="pm", content="Reply", reply_to=msg1["id"])
        self.assertEqual(msg2["reply_to"], msg1["id"])

    def test_create_message_rejects_invalid_reply_to(self):
        create_message(from_buddy="pm", to_buddy="dev", content="Seed")
        with self.assertRaises(ValueError):
            create_message(from_buddy="dev", to_buddy="pm", content="Bad", reply_to="not-an-id!")

    def test_validate_message_rejects_forbidden_fields(self):
        with self.assertRaises(ValueError):
            validate_message({
                "id": "msg-test",
                "from_buddy": "pm",
                "to_buddy": "dev",
                "content": "x",
                "reply_to": None,
                "created_at": "2026-05-17T00:00:00Z",
                "status": "unread",
            })

    def test_validate_message_rejects_blank_content(self):
        with self.assertRaises(ValueError):
            validate_message({
                "id": "msg-test",
                "from_buddy": "pm",
                "to_buddy": "dev",
                "content": "   ",
                "reply_to": None,
                "created_at": "2026-05-17T00:00:00Z",
            })

    def test_list_messages_sorts_by_created_at_ascending(self):
        msg1 = create_message(from_buddy="pm", to_buddy="dev", content="First")
        msg2 = create_message(from_buddy="design", to_buddy="dev", content="Second")
        rows = list_messages()
        ids = [row["id"] for row in rows]
        self.assertIn(msg1["id"], ids)
        self.assertIn(msg2["id"], ids)

    def test_save_message_persists(self):
        msg_id = create_message(from_buddy="pm", to_buddy="dev", content="Original")["id"]
        msg = get_message(msg_id)
        msg["content"] = "Updated"
        save_message(msg)
        reloaded = get_message(msg_id)
        self.assertEqual(reloaded["content"], "Updated")


class CommentStoreTests(RuntimeWorkspaceTestMixin, unittest.TestCase):

    def _seed_track(self):
        return create_track("track-cmt-store", "Comment Track")

    def _seed_artifact(self):
        task = create_task("task-cmt-store", "Comment Task", buddy="dev")
        return create_artifact(
            artifact_id="art-cmt-store",
            title="Comment Artifact",
            buddy="dev",
            kind="prd",
            task_id=task["id"],
            created_by="dev",
        )

    def test_create_comment_persists_flat_comment_without_status(self):
        track = self._seed_track()
        cmt = create_comment(
            target_type="track",
            target_id=track["id"],
            author_buddy="design",
            content="Nice track!",
        )
        self.assertTrue(cmt["id"].startswith("comment-"))
        self.assertEqual(cmt["target_type"], "track")
        self.assertEqual(cmt["target_id"], track["id"])
        self.assertEqual(cmt["author_buddy"], "design")
        self.assertEqual(cmt["content"], "Nice track!")
        self.assertIsNone(cmt["reply_to"])
        self.assertIsInstance(cmt["created_at"], str)
        self.assertNotIn("status", cmt)
        self.assertNotIn("resolved", cmt)
        self.assertNotIn("resolved_at", cmt)
        self.assertNotIn("task_id", cmt)
        self.assertNotIn("edit_history", cmt)
        self.assertNotIn("attachment", cmt)

        stored = get_comment(cmt["id"])
        self.assertIsNotNone(stored)
        self.assertEqual(stored["author_buddy"], "design")
        self.assertNotIn("status", stored)

    def test_create_comment_rejects_task_target(self):
        task = create_task("task-cmt-store-reject", "Reject Task Cmt", buddy="dev")
        with self.assertRaises(ValueError):
            create_comment(
                target_type="task",
                target_id=task["id"],
                author_buddy="dev",
                content="No task comments",
            )

    def test_validate_comment_rejects_forbidden_fields(self):
        with self.assertRaises(ValueError):
            validate_comment({
                "id": "comment-test",
                "target_type": "track",
                "target_id": "track-x",
                "author_buddy": "dev",
                "content": "x",
                "reply_to": None,
                "created_at": "2026-05-17T00:00:00Z",
                "status": "open",
            })

    def test_validate_comment_rejects_blank_content(self):
        with self.assertRaises(ValueError):
            validate_comment({
                "id": "comment-test",
                "target_type": "track",
                "target_id": "track-x",
                "author_buddy": "dev",
                "content": "   ",
                "reply_to": None,
                "created_at": "2026-05-17T00:00:00Z",
            })

    def test_track_and_artifact_records_do_not_persist_comment_ids(self):
        track = self._seed_track()
        artifact = self._seed_artifact()

        loaded_track = get_track(track["id"])
        self.assertNotIn("comment_ids", track)
        self.assertNotIn("comment_ids", loaded_track)

        loaded_artifact = get_artifact(artifact["id"])
        self.assertNotIn("comment_ids", artifact)
        self.assertNotIn("comment_ids", loaded_artifact)

    def test_legacy_target_comment_ids_are_ignored_and_stripped_on_save(self):
        track_path = env_store.track_file("track-legacy-comments")
        track_path.parent.mkdir(parents=True, exist_ok=True)
        track_path.write_text(
            json.dumps(
                {
                    "id": "track-legacy-comments",
                    "title": "Legacy Comments",
                    "status": "active",
                    "owner_buddy": "pm",
                    "task_ids": [],
                    "comment_ids": ["comment-stale"],
                    "summary": "",
                    "updated_at": "2026-05-17T00:00:00+08:00",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        loaded = get_track("track-legacy-comments")
        self.assertNotIn("comment_ids", loaded)

        saved = env_store.save_track(loaded)
        self.assertNotIn("comment_ids", saved)
        raw = json.loads(track_path.read_text(encoding="utf-8"))
        self.assertNotIn("comment_ids", raw)

    def test_task_records_do_not_gain_comment_ids(self):
        task = create_task("task-no-comment-ids", "No Comment IDs", buddy="dev")
        self.assertNotIn("comment_ids", task)

    def test_list_comments_sorts_by_created_at_ascending(self):
        track = self._seed_track()
        cmt1 = create_comment(target_type="track", target_id=track["id"], author_buddy="dev", content="First")
        cmt2 = create_comment(target_type="track", target_id=track["id"], author_buddy="design", content="Second")
        rows = list_comments()
        ids = [row["id"] for row in rows]
        self.assertIn(cmt1["id"], ids)
        self.assertIn(cmt2["id"], ids)
