import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env_store import (  # noqa: E402
    create_artifact,
    create_task,
    create_track,
    delete_artifact,
    get_artifact,
    get_track,
    get_task,
    update_artifact,
    validate_task,
)
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


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
            initial_run_id=None,
        )

        self.assertEqual(task["run_ids"], [])
        self.assertIsNone(task["latest_run_id"])

    def test_validate_task_allows_empty_run_ids_when_latest_run_is_null(self) -> None:
        payload = {
            "id": "task-dev-validate-empty-runs",
            "buddy": "dev",
            "title": "Validate Empty Runs",
            "status": "active",
            "track_id": None,
            "artifact_ids": [],
            "artifact_slots": {},
            "run_ids": [],
            "latest_run_id": None,
            "summary": "",
            "created_at": "2026-04-22T10:00:00+08:00",
            "updated_at": "2026-04-22T10:00:00+08:00",
        }

        normalized = validate_task(payload)

        self.assertEqual(normalized["run_ids"], [])
        self.assertIsNone(normalized["latest_run_id"])

    def test_create_task_binds_task_and_track_ids_together(self) -> None:
        track = create_track("track-pm-binding-invariant", "PM Binding Invariant")
        task = create_task(
            "task-pm-binding-invariant",
            "PM Binding Invariant",
            buddy="pm",
            track_id=track["id"],
            initial_run_id="run-seed-pm-binding-invariant",
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
            initial_run_id="run-seed-v2-slot",
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
            initial_run_id="run-seed-v2-revision",
        )

        first = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r1",
            title="PRD revision 1",
            buddy="pm",
            kind="prd",
            task_id=task["id"],
            source_run_id="run-seed-v2-revision",
            summary="Initial PRD",
            content={"task_summary": "Initial PRD"},
        )
        second = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r2",
            title="PRD revision 2",
            buddy="pm",
            kind="prd",
            task_id=task["id"],
            source_run_id="run-seed-v2-revision-2",
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
            initial_run_id="run-seed-v2-revision",
        )

        initial = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r1",
            title="PRD revision 1",
            buddy="pm",
            kind="prd",
            task_id=task["id"],
            source_run_id="run-seed-v2-revision",
            summary="Initial PRD",
            content={"task_summary": "Initial PRD"},
        )

        second = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r2",
            title="PRD revision 2",
            buddy="pm",
            kind="prd",
            task_id=task["id"],
            source_run_id="run-seed-v2-revision-2",
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
            initial_run_id="run-seed-v2-revision",
        )

        first = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r1",
            title="PRD revision 1",
            buddy="pm",
            kind="prd",
            task_id=task["id"],
            source_run_id="run-seed-v2-revision",
            summary="Initial PRD",
            content={"task_summary": "Initial PRD"},
        )
        second = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r2",
            title="PRD revision 2",
            buddy="pm",
            kind="prd",
            task_id=task["id"],
            source_run_id="run-seed-v2-revision-2",
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
            initial_run_id="run-seed-v2-revision",
        )

        first = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r1",
            title="PRD revision 1",
            buddy="pm",
            kind="prd",
            task_id=task["id"],
            source_run_id="run-seed-v2-revision",
            summary="Initial PRD",
            content={"task_summary": "Initial PRD"},
        )
        second = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r2",
            title="PRD revision 2",
            buddy="pm",
            kind="prd",
            task_id=task["id"],
            source_run_id="run-seed-v2-revision-2",
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
            source_run_id="run-seed-v2-revision-3",
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
            initial_run_id="run-seed-v2-move-source",
        )
        dest = create_task(
            "task-pm-v2-move-dest",
            "V2 Move Dest",
            buddy="pm",
            initial_run_id="run-seed-v2-move-dest",
        )

        source_old = create_artifact(
            artifact_id="art-task-pm-v2-move-source-prd-r1",
            title="Source PRD 1",
            buddy="pm",
            kind="prd",
            task_id=source["id"],
            source_run_id="run-seed-v2-move-source",
            summary="Source old",
            content={"task_summary": "Source old"},
        )
        source_current = create_artifact(
            artifact_id="art-task-pm-v2-move-source-prd-r2",
            title="Source PRD 2",
            buddy="pm",
            kind="prd",
            task_id=source["id"],
            source_run_id="run-seed-v2-move-source-2",
            summary="Source current",
            content={"task_summary": "Source current"},
        )
        dest_current = create_artifact(
            artifact_id="art-task-pm-v2-move-dest-prd-r1",
            title="Dest PRD 1",
            buddy="pm",
            kind="prd",
            task_id=dest["id"],
            source_run_id="run-seed-v2-move-dest",
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
            initial_run_id="run-seed-v2-move-source",
        )
        dest = create_task(
            "task-pm-v2-move-dest",
            "V2 Move Dest",
            buddy="pm",
            initial_run_id="run-seed-v2-move-dest",
        )

        source_old = create_artifact(
            artifact_id="art-task-pm-v2-move-source-prd-r1",
            title="Source PRD 1",
            buddy="pm",
            kind="prd",
            task_id=source["id"],
            source_run_id="run-seed-v2-move-source",
            summary="Source old",
            content={"task_summary": "Source old"},
        )
        source_current = create_artifact(
            artifact_id="art-task-pm-v2-move-source-prd-r2",
            title="Source PRD 2",
            buddy="pm",
            kind="prd",
            task_id=source["id"],
            source_run_id="run-seed-v2-move-source-2",
            summary="Source current",
            content={"task_summary": "Source current"},
        )
        dest_current = create_artifact(
            artifact_id="art-task-pm-v2-move-dest-prd-r1",
            title="Dest PRD 1",
            buddy="pm",
            kind="prd",
            task_id=dest["id"],
            source_run_id="run-seed-v2-move-dest",
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
