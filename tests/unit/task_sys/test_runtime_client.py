"""Tests for the Task Sys-owned daemon mailbox client and CLI."""

from __future__ import annotations

import importlib
import unittest
from pathlib import Path
from typing import Any


from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
CLIENT_PATH = ROOT / "scripts" / "env" / "tool_runtime" / "task_sys_runtime_client.py"
PROTOCOL_PATH = ROOT / "scripts" / "env" / "tool_runtime" / "task_sys_runtime_protocol.py"


def _load_module(path: Path, name: str) -> Any:
    if not path.exists():
        raise AssertionError(f"expected module to exist: {path}")
    del name
    return importlib.reload(importlib.import_module(f"env.tool_runtime.{path.stem}"))


class TaskSysRuntimeClientTests(unittest.TestCase):
    def test_client_and_protocol_modules_exist(self) -> None:
        self.assertTrue(CLIENT_PATH.exists(), CLIENT_PATH)
        self.assertTrue(PROTOCOL_PATH.exists(), PROTOCOL_PATH)

    def test_execute_uses_current_key_and_task_owned_timeout(self) -> None:
        client = _load_module(CLIENT_PATH, "buddyswitch_task_sys_client_execute_test")
        protocol = _load_module(PROTOCOL_PATH, "buddyswitch_task_sys_protocol_client_execute_test")
        calls: list[dict[str, object]] = []
        original = client.daemon_client.request_mailbox
        self.addCleanup(setattr, client.daemon_client, "request_mailbox", original)

        def fake_request(method: str, params: dict[str, object], **kwargs: object) -> dict[str, object]:
            calls.append({"method": method, "params": params, **kwargs})
            return {"ok": True, "result": {"action": "start_parent", "task_id": "task-user-input-client123"}}

        client.daemon_client.request_mailbox = fake_request
        instruction = {"type": "start_parent", "task_id": "task-user-input-client123"}
        root = ROOT / ".tmp-task-client-instance"

        result = client.execute_instruction(instance_root=root, instruction=instruction)

        self.assertEqual(result["task_id"], "task-user-input-client123")
        self.assertEqual(calls[0]["method"], protocol.EXECUTE_INSTRUCTION)
        self.assertEqual(calls[0]["params"], {"instruction": instruction})
        self.assertEqual(calls[0]["response_timeout_seconds"], 65.0)
        self.assertEqual(calls[0]["socket_path"], client.daemon_client.mailbox_socket_path_for_instance_root(root))

    def test_cleanup_uses_current_key_and_maps_mailbox_error(self) -> None:
        client = _load_module(CLIENT_PATH, "buddyswitch_task_sys_client_cleanup_test")
        protocol = _load_module(PROTOCOL_PATH, "buddyswitch_task_sys_protocol_client_cleanup_test")
        calls: list[str] = []
        original = client.daemon_client.request_mailbox
        self.addCleanup(setattr, client.daemon_client, "request_mailbox", original)

        def fake_request(method: str, _params: dict[str, object], **_kwargs: object) -> dict[str, object]:
            calls.append(method)
            return {
                "ok": False,
                "error": {"code": "application_command_error", "message": "cleanup failed", "retriable": False},
            }

        client.daemon_client.request_mailbox = fake_request

        with self.assertRaisesRegex(client.TaskSysRuntimeClientError, "cleanup failed"):
            client.cleanup_side_lease(
                instance_root=ROOT / ".tmp-task-client-instance",
                task_id="task-user-input-cleanup123",
            )
        self.assertEqual(calls, [protocol.CLEANUP_SIDE_LEASE])
