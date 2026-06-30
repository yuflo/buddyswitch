#!/usr/bin/env python3
"""Tests for Task Sys checkpoint frames and updates."""

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
from env.tool_runtime import registry as tool_registry  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


def _task_sys() -> Any:
    return importlib.import_module("env.domain.task_sys")


class TaskSysCheckpointTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _envelope(self) -> dict[str, Any]:
        return {
            "source": {
                "type": "app_server.turn_completed",
                "ref": {"thread_id": "thr-main", "turn_id": "turn-user-1", "status": "completed"},
            },
            "actor_target": {
                "role_id": "dev",
                "actor_id": self._runtime_actor_id(role="dev", label="act-dev-task-sys-checkpoint"),
            },
            "context": {"thread_id": "thr-main", "turn_id": "turn-user-1", "status": "completed"},
            "initial_processor": "checkpoint",
        }

    def _task_record(self, task_id: str) -> dict[str, Any]:
        path = runtime_files.OBJECTS_ROOT / "task-sys" / "tasks" / f"{task_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_turn_completed_ingest_creates_checkpoint_frame_instruction(self) -> None:
        task_sys = _task_sys()

        result = task_sys.ingest(self._envelope())

        self.assertTrue(result["ok"], msg=result)
        task_id = result["task_id"]
        record = self._task_record(task_id)
        self.assertEqual(record["status"], "checkpoint")
        self.assertEqual(record["active_processor"], "checkpoint")
        self.assertEqual(record["checkpoint_metadata"]["state"], "awaiting_update")
        instruction = result["instruction"]
        self.assertEqual(instruction["type"], "submit_parent")
        self.assertEqual(instruction["task_id"], task_id)
        frame = instruction["frame"]
        self.assertEqual(frame["kind"], "task_sys.checkpoint")
        self.assertEqual(frame["task_id"], task_id)
        self.assertEqual(frame["completed_turn"], self._envelope()["context"])
        self.assertEqual(frame["current_task_context"], {})
        self.assertEqual(frame["pending_task_context"], [])
        self.assertEqual(
            frame["legal_operations"],
            [
                {
                    "tool": "task_sys",
                    "action": "checkpoint_update",
                    "required_params": ["task_id", "outcome"],
                    "outcomes": ["close", "continue"],
                }
            ],
        )
        self.assertIn("do not recommend", " ".join(frame["constraints"]).lower())

    def test_checkpoint_update_closes_checkpoint_task_and_returns_next_frame(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]

        result = task_sys.record_checkpoint_update(
            task_id,
            {
                "outcome": "close",
                "summary": "Checkpoint acknowledged.",
            },
        )

        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result["outcome"], "close")
        record = self._task_record(task_id)
        self.assertEqual(record["status"], "closed")
        self.assertIsNone(record["active_processor"])
        self.assertEqual(record["checkpoint_metadata"]["last_update"]["summary"], "Checkpoint acknowledged.")
        self.assertEqual(result["frame"]["kind"], "task_sys.checkpoint")
        self.assertEqual(result["frame"]["checkpoint_state"], "closed")

    def test_task_sys_tool_registers_checkpoint_update(self) -> None:
        tool_registry.clear_cache()

        self.assertEqual(tool_registry.supported_actions("task_sys"), {"close", "need_parent", "checkpoint_update"})


if __name__ == "__main__":
    unittest.main()
