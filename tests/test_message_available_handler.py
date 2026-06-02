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
    def __init__(
        self,
        *,
        activity: dict[str, object] | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.activity = activity or {"status": "idle", "active_turn_id": None}
        self.error = error
        self.calls: list[dict[str, object]] = []

    def parent_activity(self) -> dict[str, object]:
        self.calls.append({"method": "parent_activity"})
        return self.activity

    def submit_parent_prompt(self, text: str, *, handler_name: str, origin_id: str | None) -> str:
        self.calls.append(
            {
                "method": "submit_parent_prompt",
                "text": text,
                "handler_name": handler_name,
                "origin_id": origin_id,
            }
        )
        if self.error is not None:
            raise self.error
        return "turn-message-read"

    def start_or_reuse_side_triage(self, text: str, *, handler_name: str, origin_id: str | None) -> dict[str, object]:
        self.calls.append(
            {
                "method": "start_or_reuse_side_triage",
                "text": text,
                "handler_name": handler_name,
                "origin_id": origin_id,
            }
        )
        if self.error is not None:
            raise self.error
        return {"action": "start", "side_thread_id": "thr-side-1", "turn_id": "turn-side-1"}

    def require_side_thread(self, side_thread_id: str) -> dict[str, object]:
        self.calls.append({"method": "require_side_thread", "side_thread_id": side_thread_id})
        if self.error is not None:
            raise self.error
        return {"thread_id": side_thread_id, "parent_thread_id": "thr-main", "status": "open"}

    def interrupt_and_submit_parent_prompt(self, text: str, *, handler_name: str, origin_id: str | None) -> dict[str, object]:
        self.calls.append(
            {
                "method": "interrupt_and_submit_parent_prompt",
                "text": text,
                "handler_name": handler_name,
                "origin_id": origin_id,
            }
        )
        if self.error is not None:
            raise self.error
        return {"interrupted_turn_id": "turn-main-1", "turn_id": "turn-parent-message"}


class MessageAvailableHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.daemon_core = load_module(DAEMON_CORE_PATH)
        self.handler_module = load_module(HANDLER_PATH)
        self.handler = self.handler_module.MessageAvailableHandler()

    def _instance(self, temp_root: str) -> dict[str, Any]:
        instance_root = Path(temp_root) / "instances" / "act-dev-daemon"
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload = {
            "actor_id": "act-dev-daemon",
            "role": "dev",
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
            actor_id="act-dev-daemon",
            main_thread_id="thr-main",
        )
        return {"context": context, "state": state}

    def _signal(
        self,
        *,
        signal_type: str = "message.available",
        to_role: str = "dev",
        to_instance: str = "act-dev-daemon",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "signal_id": "sig-readable",
            "type": signal_type,
            "source_actor_address": {"role_id": "pm", "actor_id": "act-pm-daemon"},
            "target_actor_address": {"role_id": to_role, "actor_id": to_instance},
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
                self._signal(to_role="design", to_instance="act-design-daemon"),
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

    def test_message_available_handler_routes_idle_parent_to_parent_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            actions = FakeActionGateway()
            signal = self._signal()

            self.assertTrue(self.handler.handles(signal))
            result = self.handler.handle_signal(instance["context"], instance["state"], actions, signal)

            self.assertEqual(result.status, "handled")
            self.assertEqual([call["method"] for call in actions.calls], ["parent_activity", "submit_parent_prompt"])
            call = actions.calls[1]
            self.assertEqual(call["handler_name"], "message_available")
            self.assertEqual(call["origin_id"], "msg-readable")
            prompt = call["text"]
            self.assertIsInstance(prompt, str)
            self.assertIn("[MESSAGE AVAILABLE]", prompt)
            self.assertIn("native", prompt.lower())
            self.assertNotIn("message_id: msg-readable", prompt)
            self.assertIn("message__list", prompt)
            self.assertIn("message__conversation", prompt)
            self.assertNotIn("Fallback CLI", prompt)
            self.assertNotIn("python3 scripts/env/client.py", prompt)
            self.assertNotIn("message list --payload", prompt)
            self.assertNotIn("message.list", prompt)
            self.assertNotIn("content", prompt)
            self.assertNotIn("message body", prompt.lower())

    def test_message_available_handler_routes_running_parent_to_side_triage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            actions = FakeActionGateway(activity={"status": "running", "active_turn_id": "turn-main-1"})

            result = self.handler.handle_signal(instance["context"], instance["state"], actions, self._signal())

            self.assertEqual(result.status, "handled")
            self.assertEqual([call["method"] for call in actions.calls], ["parent_activity", "start_or_reuse_side_triage"])
            call = actions.calls[1]
            self.assertEqual(call["handler_name"], "message_available")
            self.assertEqual(call["origin_id"], "msg-readable")
            prompt = call["text"]
            self.assertIsInstance(prompt, str)
            self.assertIn("[MESSAGE TRIAGE]", prompt)
            self.assertIn("message__list", prompt)
            self.assertIn("message__conversation", prompt)
            self.assertIn("message__send", prompt)
            self.assertIn("parent is required", prompt.lower())
            self.assertNotIn("codex-remote", prompt)

    def test_message_available_handler_fails_when_parent_activity_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            actions = FakeActionGateway(activity={"status": "unavailable", "error": "app-server down"})

            result = self.handler.handle_signal(instance["context"], instance["state"], actions, self._signal())

            self.assertEqual(result.status, "failed")
            self.assertIn("app-server down", result.message)
            self.assertEqual([call["method"] for call in actions.calls], ["parent_activity"])

    def test_message_available_handler_records_failed_parent_submit_as_handler_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            actions = FakeActionGateway(error=RuntimeError("submit failed"))

            result = self.handler.handle_signal(instance["context"], instance["state"], actions, self._signal())

            self.assertEqual(result.status, "failed")
            self.assertIn("submit failed", result.message)

    def test_parent_required_request_validates_side_and_interrupts_then_submits_parent_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            actions = FakeActionGateway()

            result = self.handler.handle_parent_required(
                instance["context"],
                instance["state"],
                actions,
                {
                    "message_id": "msg-readable",
                    "parent_thread_id": "thr-main",
                    "side_thread_id": "thr-side-1",
                    "reason": "parent is required",
                },
            )

            self.assertEqual(result["status"], "handled")
            self.assertEqual(result["side_thread_id"], "thr-side-1")
            self.assertEqual(result["interrupted_turn_id"], "turn-main-1")
            self.assertEqual(result["turn_id"], "turn-parent-message")
            self.assertEqual(
                [call["method"] for call in actions.calls],
                ["require_side_thread", "interrupt_and_submit_parent_prompt"],
            )
            prompt = actions.calls[1]["text"]
            self.assertIn("[MESSAGE AVAILABLE]", prompt)
            self.assertIn("message__list", prompt)

    def test_parent_required_request_reports_side_validation_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            actions = FakeActionGateway(error=RuntimeError("side not registered"))

            result = self.handler.handle_parent_required(
                instance["context"],
                instance["state"],
                actions,
                {
                    "message_id": "msg-readable",
                    "parent_thread_id": "thr-main",
                    "side_thread_id": "thr-side-unknown",
                    "reason": "parent is required",
                },
            )

            self.assertEqual(result["status"], "failed")
            self.assertIn("side not registered", result["message"])


if __name__ == "__main__":
    unittest.main()
