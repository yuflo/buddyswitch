#!/usr/bin/env python3
"""Tests for daemon-side message.available signal handler."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from itertools import count
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DAEMON_CORE_PATH = ROOT / "tools" / "launcher" / "daemon_core.py"
HANDLER_PATH = ROOT / "tools" / "launcher" / "message_available_handler.py"
MODULE_COUNTER = count()


def load_module(path: Path) -> Any:
    if not path.exists():
        raise AssertionError(f"expected module to exist: {path}")
    module_name = f"buddyswitch_{path.stem}_{next(MODULE_COUNTER)}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeActionGateway:
    def __init__(self, *, error: BaseException | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, object]] = []

    def submit_turn(self, text: str, *, handler_name: str, origin_turn_id: str | None) -> str:
        self.calls.append(
            {
                "text": text,
                "handler_name": handler_name,
                "origin_turn_id": origin_turn_id,
            }
        )
        if self.error is not None:
            raise self.error
        return "turn-message-read"


class MessageAvailableHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.daemon_core = load_module(DAEMON_CORE_PATH)
        self.handler_module = load_module(HANDLER_PATH)
        self.handler = self.handler_module.MessageAvailableHandler()

    def _instance(self, temp_root: str) -> dict[str, Any]:
        instance_root = Path(temp_root) / "instances" / "inst-dev-daemon"
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload = {
            "instance_id": "inst-dev-daemon",
            "buddy": "dev",
            "status": "active",
            "instance_root": str(instance_root),
            "workspace_dir": str(workspace_dir),
            "thread_id": "thr-main",
            "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
        }
        instance_json.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        context = self.daemon_core.load_daemon_context(instance_json)
        state = self.daemon_core.DaemonState.load(
            instance_root=instance_root,
            instance_id="inst-dev-daemon",
            main_thread_id="thr-main",
        )
        return {"context": context, "state": state}

    def _signal(
        self,
        *,
        signal_type: str = "message.available",
        to_buddy: str = "dev",
        to_instance: str = "inst-dev-daemon",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "signal_id": "sig-readable",
            "type": signal_type,
            "source_actor_address": {"buddy_id": "pm", "instance_id": "inst-pm-daemon"},
            "target_actor_address": {"buddy_id": to_buddy, "instance_id": to_instance},
            "payload": {"message_id": "msg-readable"} if payload is None else payload,
            "created_at": "2026-05-30T00:00:00Z",
        }

    def test_message_available_handler_ignores_non_message_available_signals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            actions = FakeActionGateway()
            signal = self._signal(signal_type="task.updated", payload={"task_id": "task-1"})

            self.assertFalse(self.handler.handles(signal))
            result = self.handler.handle_signal(instance["context"], instance["state"], actions, signal)

            self.assertEqual(result.status, "ignored")
            self.assertEqual(actions.calls, [])

    def test_message_available_handler_rejects_signal_for_other_actor_address(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            actions = FakeActionGateway()

            result = self.handler.handle_signal(
                instance["context"],
                instance["state"],
                actions,
                self._signal(to_buddy="design", to_instance="inst-design-daemon"),
            )

            self.assertEqual(result.status, "failed")
            self.assertIn("wrong target actor", result.message)
            self.assertEqual(actions.calls, [])

    def test_message_available_handler_rejects_missing_payload_message_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            actions = FakeActionGateway()

            result = self.handler.handle_signal(
                instance["context"],
                instance["state"],
                actions,
                self._signal(payload={}),
            )

            self.assertEqual(result.status, "failed")
            self.assertIn("message_id", result.message)
            self.assertEqual(actions.calls, [])

    def test_message_available_handler_submits_read_prompt_through_action_gateway(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            actions = FakeActionGateway()
            signal = self._signal()

            self.assertTrue(self.handler.handles(signal))
            result = self.handler.handle_signal(instance["context"], instance["state"], actions, signal)

            self.assertEqual(result.status, "handled")
            self.assertEqual(len(actions.calls), 1)
            call = actions.calls[0]
            self.assertEqual(call["handler_name"], "message_available")
            self.assertEqual(call["origin_turn_id"], "msg-readable")
            prompt = call["text"]
            self.assertIsInstance(prompt, str)
            self.assertIn("[MESSAGE AVAILABLE]", prompt)
            self.assertNotIn("message_id: msg-readable", prompt)
            self.assertIn("message__list", prompt)
            self.assertIn("message__conversation", prompt)
            self.assertIn("message list --payload '{}'", prompt)
            self.assertNotIn("message.list", prompt)
            self.assertNotIn("content", prompt)
            self.assertNotIn("message body", prompt.lower())

    def test_message_available_handler_records_failed_submit_turn_as_handler_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            actions = FakeActionGateway(error=RuntimeError("submit failed"))

            result = self.handler.handle_signal(instance["context"], instance["state"], actions, self._signal())

            self.assertEqual(result.status, "failed")
            self.assertIn("submit failed", result.message)


if __name__ == "__main__":
    unittest.main()
