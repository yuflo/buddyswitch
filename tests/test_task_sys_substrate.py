#!/usr/bin/env python3
"""Tests for the minimal task sys substrate."""

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


class TaskSysSubstrateTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _envelope(self, *, initial_processor: str | None = None) -> dict[str, Any]:
        envelope: dict[str, Any] = {
            "source": {
                "type": "user.input",
                "ref": {"id": "input-1", "surface": "cli"},
            },
            "actor_target": {
                "role_id": "dev",
                "actor_id": self._runtime_actor_id(role="dev", label="act-dev-task-sys"),
            },
            "context": {
                "text": "Draft brief",
                "surface": "cli",
            },
        }
        if initial_processor is not None:
            envelope["initial_processor"] = initial_processor
        return envelope

    def _task_record_path(self, task_id: str) -> Path:
        return runtime_files.OBJECTS_ROOT / "task-sys" / "tasks" / f"{task_id}.json"

    def test_ingest_persists_task_record_and_returns_start_side_instruction(self) -> None:
        task_sys = _task_sys()
        envelope = self._envelope()

        result = task_sys.ingest(envelope)

        self.assertTrue(result.get("ok"), msg=result)
        task_id = result.get("task_id")
        self.assertIsInstance(task_id, str, msg=result)
        assert isinstance(task_id, str)
        self.assertTrue(task_id.startswith("task-"), msg=task_id)
        record_path = self._task_record_path(task_id)
        self.assertTrue(record_path.exists(), msg=record_path)
        persisted = json.loads(record_path.read_text(encoding="utf-8"))
        self.assertEqual(result.get("task"), persisted)
        self.assertEqual(persisted["id"], task_id)
        self.assertEqual(persisted["source_type"], "user.input")
        self.assertEqual(persisted["source_ref"], {"id": "input-1", "surface": "cli"})
        self.assertEqual(persisted["actor_target"], envelope["actor_target"])
        self.assertEqual(persisted["inbound_context"], envelope["context"])
        self.assertEqual(persisted["status"], "side_processing")
        self.assertEqual(persisted["active_processor"], "side")
        self.assertIsNone(persisted["parent_handoff_params"])
        self.assertEqual(persisted["checkpoint_metadata"], {})
        self.assertIsInstance(persisted.get("created_at"), str)
        self.assertIsInstance(persisted.get("updated_at"), str)

        instruction = result.get("instruction")
        self.assertIsInstance(instruction, dict, msg=result)
        assert isinstance(instruction, dict)
        self.assertEqual(instruction["type"], "start_side")
        self.assertEqual(instruction["task_id"], task_id)
        self.assertEqual(instruction["actor_target"], envelope["actor_target"])
        frame = instruction.get("frame")
        self.assertIsInstance(frame, dict, msg=instruction)
        assert isinstance(frame, dict)
        self.assertEqual(frame["kind"], "task_sys.side_frame")
        self.assertEqual(frame["task_id"], task_id)
        self.assertEqual(frame["source"], {"type": "user.input", "ref": {"id": "input-1", "surface": "cli"}})
        self.assertEqual(frame["actor_target"], envelope["actor_target"])
        self.assertEqual(frame["context"], envelope["context"])

    def test_ingest_can_record_without_actor_action(self) -> None:
        task_sys = _task_sys()

        result = task_sys.ingest(self._envelope(initial_processor="none"))

        self.assertTrue(result.get("ok"), msg=result)
        task_id = result.get("task_id")
        self.assertIsInstance(task_id, str, msg=result)
        assert isinstance(task_id, str)
        persisted = json.loads(self._task_record_path(task_id).read_text(encoding="utf-8"))
        self.assertEqual(persisted["status"], "closed")
        self.assertIsNone(persisted["active_processor"])
        instruction = result.get("instruction")
        self.assertIsInstance(instruction, dict, msg=result)
        assert isinstance(instruction, dict)
        self.assertEqual(instruction["type"], "no_actor_action")
        self.assertEqual(instruction["task_id"], task_id)
        self.assertEqual(instruction["actor_target"], self._envelope()["actor_target"])

    def test_parent_runtime_instruction_shapes_are_task_traceable(self) -> None:
        task_sys = _task_sys()
        actor_target = self._envelope()["actor_target"]
        frame = {
            "kind": "task_sys.parent_frame",
            "task_id": "task-user-input-123456abcdef",
            "context": {"text": "Draft brief"},
        }

        submit = task_sys.runtime_instruction(
            "submit_parent",
            task_id="task-user-input-123456abcdef",
            actor_target=actor_target,
            frame=frame,
        )
        interrupt = task_sys.runtime_instruction(
            "interrupt_submit_parent",
            task_id="task-user-input-123456abcdef",
            actor_target=actor_target,
            frame=frame,
        )

        self.assertEqual(submit["type"], "submit_parent")
        self.assertEqual(interrupt["type"], "interrupt_submit_parent")
        for instruction in (submit, interrupt):
            with self.subTest(instruction=instruction["type"]):
                self.assertEqual(instruction["task_id"], "task-user-input-123456abcdef")
                self.assertEqual(instruction["actor_target"], actor_target)
                self.assertEqual(instruction["frame"], frame)

        with self.assertRaisesRegex(ValueError, "runtime instruction"):
            task_sys.runtime_instruction(
                "side_interrupt",
                task_id="task-user-input-123456abcdef",
                actor_target=actor_target,
                frame=frame,
            )

    def test_parent_instruction_from_need_parent_task_stays_parent_ready_until_runtime_start(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]
        task_sys.record_side_result(
            task_id,
            {
                "outcome": "need_parent",
                "params": {
                    "parent_frame_context": {"next": "Draft the brief in parent."},
                    "relation": "User input requires main-thread work.",
                    "interrupt": True,
                    "ordering": {"priority": "normal"},
                },
            },
        )

        instruction = task_sys.parent_handoff_instruction(task_id)

        self.assertEqual(instruction["type"], "interrupt_submit_parent")
        self.assertEqual(instruction["task_id"], task_id)
        self.assertEqual(instruction["actor_target"], self._envelope()["actor_target"])
        frame = instruction.get("frame")
        self.assertIsInstance(frame, dict, msg=instruction)
        assert isinstance(frame, dict)
        self.assertEqual(frame["kind"], "task_sys.parent_frame")
        self.assertEqual(frame["task_id"], task_id)
        self.assertEqual(frame["source"], {"type": "user.input", "ref": {"id": "input-1", "surface": "cli"}})
        self.assertEqual(frame["inbound_context"], self._envelope()["context"])
        self.assertEqual(frame["side_result"]["outcome"], "need_parent")
        self.assertEqual(
            frame["parent_handoff_params"],
            {
                "parent_frame_context": {"next": "Draft the brief in parent."},
                "relation": "User input requires main-thread work.",
                "interrupt": True,
                "ordering": {"priority": "normal"},
            },
        )
        persisted = json.loads(self._task_record_path(task_id).read_text(encoding="utf-8"))
        self.assertEqual(persisted["status"], "needs_parent")
        self.assertIsNone(persisted["active_processor"])

    def test_record_parent_handoff_started_marks_parent_processing(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]
        task_sys.record_side_result(
            task_id,
            {
                "outcome": "need_parent",
                "params": {
                    "parent_frame_context": {"next": "Draft the brief in parent."},
                    "relation": "User input requires main-thread work.",
                    "interrupt": True,
                },
            },
        )

        result = task_sys.record_parent_handoff_started(task_id)

        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result["task_id"], task_id)
        persisted = json.loads(self._task_record_path(task_id).read_text(encoding="utf-8"))
        self.assertEqual(persisted["status"], "parent_processing")
        self.assertEqual(persisted["active_processor"], "parent")

    def test_parent_instruction_rejects_non_parent_ready_task(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]

        with self.assertRaisesRegex(ValueError, "needs_parent"):
            task_sys.parent_handoff_instruction(task_id)

    def test_ingest_rejects_invalid_envelope_shapes(self) -> None:
        task_sys = _task_sys()
        valid = self._envelope()
        cases = (
            ({}, "source"),
            ({**valid, "source": "user.input"}, "source"),
            ({**valid, "source": {"ref": {"id": "input-1"}}}, "source.type"),
            ({**valid, "source": {"type": "user.input"}}, "source.ref"),
            ({**valid, "actor_target": {"role_id": "dev"}}, "actor_target.actor_id"),
            ({**valid, "actor_target": {"actor_id": valid["actor_target"]["actor_id"]}}, "actor_target.role_id"),
            ({**valid, "context": "Draft brief"}, "context"),
            ({**valid, "initial_processor": "parent"}, "initial_processor"),
        )
        for payload, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(ValueError, expected):
                    task_sys.ingest(payload)

    def test_task_sys_substrate_has_no_daemon_or_taskbox_dependencies(self) -> None:
        source = (ROOT / "scripts" / "env" / "domain" / "task_sys.py").read_text(encoding="utf-8")

        for forbidden in (
            "daemon_core",
            "daemon_client",
            "app_server",
            "tools.launcher",
            "task_management",
            "taskbox",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
