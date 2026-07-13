"""Tests for Task Sys side-processing state transitions and tool surface."""

from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.repos import runtime_files  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


def _task_sys() -> Any:
    return importlib.import_module("env.domain.task_sys")


class TaskSysSideProcessingTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _envelope(self) -> dict[str, Any]:
        return {
            "source": {
                "type": "user.input",
                "ref": {"id": "input-1", "surface": "cli"},
            },
            "actor_target": {
                "role_id": "dev",
                "actor_id": self._runtime_actor_id(role="dev", label="act-dev-task-sys-side"),
            },
            "context": {
                "text": "Draft brief",
                "surface": "cli",
            },
        }

    def _task_record(self, task_id: str) -> dict[str, Any]:
        path = runtime_files.OBJECTS_ROOT / "task-sys" / "tasks" / f"{task_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _assert_no_legacy_execution_fields(self, record: dict[str, Any]) -> None:
        for field in ("active_processor", "side_result", "parent_handoff_params", "failure_result", "close_result"):
            with self.subTest(field=field):
                self.assertNotIn(field, record)

    def _move_to_parent_processing(self, task_id: str) -> None:
        task_sys = _task_sys()
        task_sys.record_task_analysis_update(
            task_id,
            {
                "task_desc": "Draft brief",
                "task_relation": {"kind": "independent", "target_task_id": None},
            },
        )
        task_sys.record_side_need_parent(
            task_id,
            {
                "params": {
                    "parent_frame_context": {
                        "next": "Draft in parent.",
                        "task_desc": "Draft brief",
                        "task_relation": {"kind": "independent", "target_task_id": None},
                    },
                    "interrupt": False,
                },
            },
        )
        task_sys.record_parent_handoff_started(task_id)

    def test_record_task_close_closes_side_processing_task_without_parent_handoff(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]

        result = task_sys.record_task_close(
            task_id,
            {
                "summary": "Handled without parent.",
            },
        )

        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result["outcome"], "close")
        record = self._task_record(task_id)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["execution"]["processor"], None)
        self.assertEqual(record["execution"]["handoff"], None)
        self.assertEqual(record["execution"]["result"]["type"], "completion")
        self.assertEqual(record["execution"]["result"]["processor"], "side")
        self.assertEqual(record["execution"]["result"]["summary"], "Handled without parent.")
        self._assert_no_legacy_execution_fields(record)

    def test_side_need_parent_records_handoff_params_without_interrupt_outcome(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]
        task_sys.record_task_analysis_update(
            task_id,
            {
                "task_desc": "Draft brief",
                "task_relation": {"kind": "independent", "target_task_id": None},
            },
        )

        result = task_sys.record_side_need_parent(
            task_id,
            {
                "params": {
                    "parent_frame_context": {
                        "next": "Ask parent to draft the brief.",
                        "task_desc": "Draft brief",
                        "task_relation": {"kind": "independent", "target_task_id": None},
                    },
                    "interrupt": True,
                    "ordering": {"priority": "normal"},
                },
            },
        )

        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result["outcome"], "need_parent")
        record = self._task_record(task_id)
        self.assertEqual(record["status"], "in_progress")
        self.assertEqual(record["execution"]["processor"], None)
        self.assertEqual(
            record["execution"]["handoff"],
            {
                "parent_frame_context": {
                    "next": "Ask parent to draft the brief.",
                    "task_desc": "Draft brief",
                    "task_relation": {"kind": "independent", "target_task_id": None},
                },
                "interrupt": True,
                "ordering": {"priority": "normal"},
                "side_thread_id": None,
                "cleanup": {},
            },
        )
        self.assertIsNone(record["execution"]["result"])
        self._assert_no_legacy_execution_fields(record)

    def test_record_side_result_api_is_retired(self) -> None:
        task_sys = _task_sys()
        self.assertFalse(hasattr(task_sys, "record_side_result"))


if __name__ == "__main__":
    unittest.main()
