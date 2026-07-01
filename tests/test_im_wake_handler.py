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
from env.tool_runtime.actor_profile import ActorAddress  # noqa: E402


@dataclass
class _Context:
    actor_address: ActorAddress


@dataclass
class _Trigger:
    type: str
    target_actor_address: dict[str, str]
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

    def submit_side_triage_prompt(self, prompt: str, **kwargs: Any) -> None:
        self.calls.append({"method": "submit_side_triage_prompt", "prompt": prompt, **kwargs})
        raise AssertionError("IM wake handler must not submit side prompts")

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

    def _actor(self) -> ActorAddress:
        return ActorAddress(role_id="market", actor_id="act-market-test")

    def _trigger(self, actor: ActorAddress | None = None) -> _Trigger:
        target = actor or self._actor()
        return _Trigger(
            type="im.message.created",
            target_actor_address=target.to_payload(),
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
        actor = self._actor()
        runtime = _Runtime()
        handler = im_wake_handler.ImMessageCreatedHandler()

        result = handler.handle(_Context(actor), None, runtime, self._trigger(actor))

        self.assertEqual(result.status, "handled")
        records = self._task_records()
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["source_type"], "im.message.created")
        self.assertEqual(record["source_ref"], {"message_id": "msg-abc123", "conversation_id": "conv-abc123", "event_id": "imev-abc123"})
        self.assertEqual(record["actor_target"], actor.to_payload())
        self.assertEqual(record["inbound_context"]["message_id"], "msg-abc123")
        self.assertEqual(record["status"], "side_processing")
        self.assertEqual(record["active_processor"], "side")
        self.assertEqual(len(runtime.calls), 1)
        self.assertEqual(runtime.calls[0]["method"], "execute_task_sys_instruction")
        self.assertEqual(runtime.calls[0]["instruction"]["type"], "start_side")
        self.assertEqual(runtime.calls[0]["instruction"]["task_id"], record["id"])

    def test_wrong_target_actor_fails(self) -> None:
        handler = im_wake_handler.ImMessageCreatedHandler()
        wrong = ActorAddress(role_id="market", actor_id="act-market-other")

        result = handler.handle(_Context(self._actor()), None, _Runtime(), self._trigger(wrong))

        self.assertEqual(result.status, "failed")
        self.assertIn("wrong target actor", result.message)

    def test_handler_does_not_handle_unrelated_event(self) -> None:
        handler = im_wake_handler.ImMessageCreatedHandler()

        self.assertFalse(handler.handles(_Trigger("example.ready", self._actor().to_payload(), {"message_id": "msg-abc123"})))


if __name__ == "__main__":
    unittest.main()
