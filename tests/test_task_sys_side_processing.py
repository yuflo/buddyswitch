#!/usr/bin/env python3
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
from env.tool_runtime import registry as tool_registry  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


def _task_sys() -> Any:
    return importlib.import_module("env.domain.task_sys")


class _TaskSysToolContext(dict):
    def __init__(self) -> None:
        super().__init__(
            active_actor={"actor_id": "act-dev-task-sys-side", "role_id": "dev"},
            active_role="dev",
        )
        self.daemon = self
        self.instructions: list[dict[str, Any]] = []

    def execute_task_sys_instruction(self, instruction: dict[str, Any]) -> dict[str, Any]:
        self.instructions.append(instruction)
        return {"action": instruction["type"], "task_id": instruction["task_id"], "turn_id": "turn-parent-1"}

    def submit_parent_prompt(self, *_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("task_sys.need_parent must not submit raw parent prompts")


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

    def test_side_close_marks_task_closed_without_parent_handoff(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]

        result = task_sys.record_side_result(
            task_id,
            {
                "outcome": "close",
                "summary": "Handled without parent.",
            },
        )

        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result["outcome"], "close")
        record = self._task_record(task_id)
        self.assertEqual(record["status"], "closed")
        self.assertIsNone(record["active_processor"])
        self.assertIsNone(record["parent_handoff_params"])
        self.assertEqual(record["side_result"]["outcome"], "close")
        self.assertEqual(record["side_result"]["summary"], "Handled without parent.")

    def test_side_need_parent_records_handoff_params_without_interrupt_outcome(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]

        result = task_sys.record_side_result(
            task_id,
            {
                "outcome": "need_parent",
                "params": {
                    "parent_frame_context": {"next": "Ask parent to draft the brief."},
                    "relation": "User input requires main-thread work.",
                    "interrupt": True,
                    "ordering": {"priority": "normal"},
                },
            },
        )

        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result["outcome"], "need_parent")
        record = self._task_record(task_id)
        self.assertEqual(record["status"], "needs_parent")
        self.assertIsNone(record["active_processor"])
        self.assertEqual(
            record["parent_handoff_params"],
            {
                "parent_frame_context": {"next": "Ask parent to draft the brief."},
                "relation": "User input requires main-thread work.",
                "interrupt": True,
                "ordering": {"priority": "normal"},
            },
        )
        self.assertEqual(record["side_result"]["outcome"], "need_parent")

    def test_side_result_rejects_interrupt_as_outcome(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]

        with self.assertRaisesRegex(ValueError, "side result outcome"):
            task_sys.record_side_result(task_id, {"outcome": "interrupt"})

    def test_task_sys_tool_registers_only_close_and_need_parent_side_results(self) -> None:
        tool_registry.clear_cache()

        actions = tool_registry.supported_actions("task_sys")

        self.assertIn("checkpoint_update", actions)
        self.assertEqual(actions - {"checkpoint_update"}, {"close", "need_parent"})

    def test_task_sys_need_parent_tool_executes_parent_instruction_via_daemon_context(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]
        impl = importlib.import_module("env.tools.task_sys._impl")
        context = _TaskSysToolContext()

        result = impl.invoke(
            action="need_parent",
            args={
                "task_id": task_id,
                "params": {
                    "parent_frame_context": {"next": "Draft in parent."},
                    "relation": "Side needs parent work.",
                    "interrupt": False,
                },
            },
            context=context,
        )

        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result["outcome"], "need_parent")
        self.assertEqual(result["task_status"], "parent_processing")
        self.assertEqual(result["parent_runtime"]["action"], "submit_parent")
        self.assertEqual(len(context.instructions), 1)
        instruction = context.instructions[0]
        self.assertEqual(instruction["type"], "submit_parent")
        self.assertEqual(instruction["task_id"], task_id)
        self.assertEqual(instruction["frame"]["kind"], "task_sys.parent_frame")
        record = self._task_record(task_id)
        self.assertEqual(record["status"], "parent_processing")
        self.assertEqual(record["active_processor"], "parent")


if __name__ == "__main__":
    unittest.main()
