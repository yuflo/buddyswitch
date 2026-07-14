"""Runtime wake handling tests for Central IM."""

from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from tests.support.paths import REPO_ROOT
from tests.support.runtime import RuntimeWorkspaceTestCase

ROOT = REPO_ROOT
HELPER_DIR = ROOT / "tools" / "launcher"
SCRIPTS = ROOT / "scripts"

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

class ImWakeHandlerTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.adapter_calls: list[dict[str, Any]] = []
        original_execute = im_wake_handler.task_sys_daemon_adapter.execute_instruction
        self.addCleanup(
            setattr,
            im_wake_handler.task_sys_daemon_adapter,
            "execute_instruction",
            original_execute,
        )
        im_wake_handler.task_sys_daemon_adapter.execute_instruction = (
            lambda _context, instruction: self.adapter_calls.append(dict(instruction))
            or {"action": instruction["type"], "task_id": instruction["task_id"]}
        )

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
        self.assertEqual(record["status"], "in_progress")
        self.assertEqual(record["execution"]["processor"], "side")
        self.assertEqual(record["task_relation"], {"kind": "independent", "target_task_id": None})
        self.assertNotIn("active_processor", record)
        self.assertEqual(len(self.adapter_calls), 1)
        self.assertEqual(self.adapter_calls[0]["type"], "start_side")
        self.assertEqual(self.adapter_calls[0]["task_id"], record["id"])

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
