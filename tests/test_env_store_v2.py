import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env_store import create_artifact, create_task, get_artifact, get_task  # noqa: E402


class ArtifactSlotLifecycleTests(unittest.TestCase):
    def _task_path(self, task_id: str) -> Path:
        return ROOT / "buddyswitch" / "objects" / "tasks" / f"{task_id}.json"

    def _artifact_path(self, artifact_id: str) -> Path:
        return ROOT / "buddyswitch" / "objects" / "artifacts" / f"{artifact_id}.json"

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
            skill_id="write-prd",
            slot="prd",
            task_id=task["id"],
            source_run_id="run-seed-v2-revision",
            summary="Initial PRD",
            content={"task_summary": "Initial PRD"},
        )
        second = create_artifact(
            artifact_id="art-task-pm-v2-revision-prd-r2",
            title="PRD revision 2",
            buddy="pm",
            skill_id="write-prd",
            slot="prd",
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
