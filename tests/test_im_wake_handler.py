#!/usr/bin/env python3
"""Runtime wake handling tests for Central IM."""

from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HELPER_DIR = ROOT / "tools" / "launcher"
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import im_wake_handler  # noqa: E402
from env.repos import runtime_files  # noqa: E402


@dataclass
class _Context:
    actor_id: str
    role: str


@dataclass
class _Trigger:
    type: str
    target_identity_id: str
    target_role_id: str
    payload: dict[str, str]


class _Runtime:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def parent_activity(self) -> dict[str, str]:
        self.calls.append({"method": "parent_activity"})
        raise AssertionError("IM wake handler must not inspect parent activity")

    def submit_parent_prompt(self, prompt: str, **kwargs: Any) -> None:
        self.calls.append({"method": "submit_parent_prompt", "prompt": prompt, **kwargs})
        raise AssertionError("IM wake handler must not submit parent prompts")

    def execute_task_sys_instruction(self, instruction: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"method": "execute_task_sys_instruction", "instruction": instruction})
        return {"action": instruction["type"], "task_id": instruction["task_id"]}


class ImWakeHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.runtime_root = Path(self._tmp_dir.name)
        runtime_files.set_runtime_root_override(self.runtime_root)

    def tearDown(self) -> None:
        runtime_files.reset_runtime_root_override()
        self._tmp_dir.cleanup()
        super().tearDown()

    def _identity_route(self) -> dict[str, str]:
        return {"identity_id": "act-market-test", "role_id": "market"}

    def _trigger(self, route: dict[str, str] | None = None) -> _Trigger:
        target = route or self._identity_route()
        return _Trigger(
            type="im.message.created",
            target_identity_id=target["identity_id"],
            target_role_id=target["role_id"],
            payload={
                "message_id": "msg-abc123",
                "conversation_id": "conv-abc123",
                "event_id": "imev-abc123",
            },
        )

    def _task_records(self) -> list[dict[str, Any]]:
        tasks_dir = runtime_files.OBJECTS_ROOT / "task-sys" / "tasks"
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(tasks_dir.glob("*.json"))
        ]

    def test_im_message_ingests_task_without_parent_or_side_prompt(self) -> None:
        route = self._identity_route()
        runtime = _Runtime()
        handler = im_wake_handler.ImMessageCreatedHandler()

        result = handler.handle(_Context(actor_id=route["identity_id"], role=route["role_id"]), None, runtime, self._trigger(route))

        self.assertEqual(result.status, "handled")
        records = self._task_records()
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["source_type"], "im.message.created")
        self.assertEqual(record["source_ref"], {"message_id": "msg-abc123", "conversation_id": "conv-abc123", "event_id": "imev-abc123"})
        self.assertEqual(record["actor_target"], {"actor_id": route["identity_id"], "role_id": route["role_id"]})
        self.assertEqual(record["inbound_context"]["message_id"], "msg-abc123")
        self.assertEqual(record["status"], "side_processing")
        self.assertEqual(record["active_processor"], "side")
        self.assertEqual(len(runtime.calls), 1)
        self.assertEqual(runtime.calls[0]["method"], "execute_task_sys_instruction")
        self.assertEqual(runtime.calls[0]["instruction"]["type"], "start_side")
        self.assertEqual(runtime.calls[0]["instruction"]["task_id"], record["id"])

    def test_wrong_target_actor_fails(self) -> None:
        handler = im_wake_handler.ImMessageCreatedHandler()
        wrong = {"identity_id": "act-market-other", "role_id": "market"}

        route = self._identity_route()
        result = handler.handle(_Context(actor_id=route["identity_id"], role=route["role_id"]), None, _Runtime(), self._trigger(wrong))

        self.assertEqual(result.status, "failed")
        self.assertIn("wrong target identity", result.message)

    def test_handler_does_not_handle_unrelated_event(self) -> None:
        handler = im_wake_handler.ImMessageCreatedHandler()

        self.assertFalse(handler.handles(_Trigger("example.ready", "act-market-test", "market", {"message_id": "msg-abc123"})))


if __name__ == "__main__":
    unittest.main()
