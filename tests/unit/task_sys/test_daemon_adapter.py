"""Tests for the Task Sys-owned daemon application-command adapter."""

from __future__ import annotations

import importlib
import unittest
from pathlib import Path
from typing import Any


from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
ADAPTER_PATH = ROOT / "tools" / "launcher" / "task_sys_daemon_adapter.py"
PROTOCOL_PATH = ROOT / "scripts" / "env" / "tool_runtime" / "task_sys_runtime_protocol.py"


def _load_module(path: Path, name: str) -> Any:
    if not path.exists():
        raise AssertionError(f"expected module to exist: {path}")
    del name
    module_name = f"env.tool_runtime.{path.stem}" if path == PROTOCOL_PATH else path.stem
    return importlib.reload(importlib.import_module(module_name))


class TaskSysDaemonAdapterTests(unittest.TestCase):
    def test_adapter_and_protocol_modules_exist(self) -> None:
        self.assertTrue(ADAPTER_PATH.exists(), ADAPTER_PATH)
        self.assertTrue(PROTOCOL_PATH.exists(), PROTOCOL_PATH)

    def test_command_handlers_use_only_current_protocol_keys(self) -> None:
        adapter = _load_module(ADAPTER_PATH, "buddyswitch_task_sys_adapter_test")
        protocol = _load_module(PROTOCOL_PATH, "buddyswitch_task_sys_protocol_test")
        context = object()

        handlers = adapter.command_handlers(context)

        self.assertEqual(set(handlers), {protocol.EXECUTE_INSTRUCTION, protocol.CLEANUP_SIDE_LEASE})
        self.assertTrue(all(callable(handler) for handler in handlers.values()))

    def test_execute_command_validates_payload_and_delegates_to_runtime(self) -> None:
        adapter = _load_module(ADAPTER_PATH, "buddyswitch_task_sys_adapter_execute_test")
        protocol = _load_module(PROTOCOL_PATH, "buddyswitch_task_sys_protocol_execute_test")
        context = object()
        instruction = {"type": "start_parent", "task_id": "task-controlled-inbound-adapter123"}
        calls: list[tuple[object, dict[str, object]]] = []
        original = adapter.task_sys_runtime.execute_instruction
        self.addCleanup(setattr, adapter.task_sys_runtime, "execute_instruction", original)
        adapter.task_sys_runtime.execute_instruction = lambda runtime_context, value: (
            calls.append((runtime_context, value))
            or {"action": value["type"], "task_id": value["task_id"]}
        )

        result = adapter.command_handlers(context)[protocol.EXECUTE_INSTRUCTION]({"instruction": instruction})

        self.assertEqual(result, {"action": "start_parent", "task_id": "task-controlled-inbound-adapter123"})
        self.assertEqual(calls, [(context, instruction)])
        with self.assertRaisesRegex(ValueError, "instruction must be an object"):
            adapter.command_handlers(context)[protocol.EXECUTE_INSTRUCTION]({"instruction": "invalid"})

    def test_cleanup_command_validates_task_id_and_delegates_to_runtime(self) -> None:
        adapter = _load_module(ADAPTER_PATH, "buddyswitch_task_sys_adapter_cleanup_test")
        protocol = _load_module(PROTOCOL_PATH, "buddyswitch_task_sys_protocol_cleanup_test")
        context = object()
        calls: list[tuple[object, str]] = []
        original = adapter.task_sys_runtime.cleanup_side_lease
        self.addCleanup(setattr, adapter.task_sys_runtime, "cleanup_side_lease", original)
        adapter.task_sys_runtime.cleanup_side_lease = lambda runtime_context, task_id: (
            calls.append((runtime_context, task_id))
            or {"task_id": task_id, "lease_unregistered": True}
        )

        result = adapter.command_handlers(context)[protocol.CLEANUP_SIDE_LEASE](
            {"task_id": "task-controlled-inbound-cleanup123"}
        )

        self.assertTrue(result["lease_unregistered"])
        self.assertEqual(calls, [(context, "task-controlled-inbound-cleanup123")])
        with self.assertRaisesRegex(ValueError, "task_id"):
            adapter.command_handlers(context)[protocol.CLEANUP_SIDE_LEASE]({"task_id": ""})

    def test_progress_check_handler_owns_only_turn_completed_notifications(self) -> None:
        adapter = _load_module(ADAPTER_PATH, "buddyswitch_task_sys_adapter_progress_test")
        handler = adapter.TaskSysProgressCheckHandler()

        completed = type("Trigger", (), {"type": "app_server.turn_completed"})()
        message = type("Trigger", (), {"type": "im.message.created"})()

        self.assertEqual(handler.name, "task_sys_progress_check")
        self.assertTrue(handler.handles(completed))
        self.assertFalse(handler.handles(message))
