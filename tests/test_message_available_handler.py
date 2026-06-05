#!/usr/bin/env python3
"""Tests for daemon-side message trigger handler."""

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


class FakeDaemonRuntime:
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

    def submit_parent_prompt(
        self,
        text: str,
        *,
        handler_name: str,
        origin_id: str | None,
        interrupt_policy: str,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "method": "submit_parent_prompt",
                "text": text,
                "handler_name": handler_name,
                "origin_id": origin_id,
                "interrupt_policy": interrupt_policy,
            }
        )
        if self.error is not None:
            raise self.error
        payload: dict[str, object] = {"turn_id": "turn-parent-message"}
        if interrupt_policy == "before_submit":
            payload["interrupted_turn_id"] = "turn-main-1"
        return payload

    def submit_side_triage_prompt(self, text: str, *, handler_name: str, origin_id: str | None) -> dict[str, object]:
        self.calls.append(
            {
                "method": "submit_side_triage_prompt",
                "text": text,
                "handler_name": handler_name,
                "origin_id": origin_id,
            }
        )
        if self.error is not None:
            raise self.error
        return {"action": "start", "side_thread_id": "thr-side-1", "turn_id": "turn-side-1"}


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

    def _trigger(
        self,
        *,
        trigger_type: str = "message.available",
        to_role: str = "dev",
        to_instance: str = "act-dev-daemon",
        payload: dict[str, Any] | None = None,
        source_context: dict[str, Any] | None = None,
    ) -> object:
        context_payload = (
            {
                "signal_id": "sig-readable",
                "source_actor_address": {"role_id": "pm", "actor_id": "act-pm-readable"},
                "created_at": "2026-06-03T00:00:00Z",
            }
            if source_context is None
            else source_context
        )
        return self.daemon_core.daemon_triggers.DaemonTrigger(
            source="mailbox_cross_actor_signal" if trigger_type == "message.available" else "mailbox_local_trigger",
            type=trigger_type,
            target_actor_address={"role_id": to_role, "actor_id": to_instance},
            origin_id="sig-readable",
            correlation_id=None,
            payload={"message_id": "msg-readable"} if payload is None else payload,
            source_context=context_payload,
        )

    def test_message_handler_source_uses_unified_trigger_interface_and_clean_runtime(self) -> None:
        source = HANDLER_PATH.read_text(encoding="utf-8")

        self.assertIn("def handle(", source)
        self.assertNotIn("handle_signal", source)
        self.assertNotIn("handle_parent_required", source)
        self.assertNotIn("require_side_thread", source)
        self.assertNotIn("message." + "parent_required", source)
        self.assertNotIn("mailbox.local_trigger", source)
        self.assertNotIn("interrupt_and_submit_parent_prompt", source)
        self.assertNotIn("start_or_reuse_side_triage", source)

    def test_message_available_handler_ignores_unknown_trigger_types(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            runtime = FakeDaemonRuntime()
            trigger = self._trigger(trigger_type="task.updated", payload={"task_id": "task-1"})

            self.assertFalse(self.handler.handles(trigger))
            result = self.handler.handle(instance["context"], instance["state"], runtime, trigger)

            self.assertEqual(result.status, "ignored")
            self.assertEqual(runtime.calls, [])

    def test_message_available_handler_rejects_trigger_for_other_actor_address(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            runtime = FakeDaemonRuntime()

            result = self.handler.handle(
                instance["context"],
                instance["state"],
                runtime,
                self._trigger(to_role="design", to_instance="act-design-daemon"),
            )

            self.assertEqual(result.status, "failed")
            self.assertIn("wrong target actor", result.message)
            self.assertEqual(runtime.calls, [])

    def test_message_available_handler_rejects_missing_payload_message_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            runtime = FakeDaemonRuntime()

            result = self.handler.handle(instance["context"], instance["state"], runtime, self._trigger(payload={}))

            self.assertEqual(result.status, "failed")
            self.assertIn("message_id", result.message)
            self.assertEqual(runtime.calls, [])

    def test_message_available_handler_routes_idle_parent_to_parent_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            runtime = FakeDaemonRuntime()
            trigger = self._trigger()

            self.assertTrue(self.handler.handles(trigger))
            result = self.handler.handle(instance["context"], instance["state"], runtime, trigger)

            self.assertEqual(result.status, "handled")
            self.assertEqual([call["method"] for call in runtime.calls], ["parent_activity", "submit_parent_prompt"])
            call = runtime.calls[1]
            self.assertEqual(call["handler_name"], "message_available")
            self.assertEqual(call["origin_id"], "msg-readable")
            self.assertEqual(call["interrupt_policy"], "none")
            prompt = call["text"]
            self.assertIsInstance(prompt, str)
            self.assertIn("[MESSAGE AVAILABLE]", prompt)
            self.assertIn("msg-readable", prompt)
            self.assertIn('From: {"actor_id": "act-pm-readable", "role_id": "pm"}', prompt)
            self.assertIn('To: {"actor_id": "act-dev-daemon", "role_id": "dev"}', prompt)
            self.assertIn("message__get", prompt)
            self.assertIn("message__conversation", prompt)
            self.assertIn("message__send", prompt)
            self.assertIn("message__mark", prompt)
            self.assertNotIn("message__" + "list", prompt)
            self.assertNotIn("Fallback CLI", prompt)
            self.assertNotIn("python3 scripts/env/client.py", prompt)
            self.assertNotIn("message body", prompt.lower())

    def test_message_available_handler_routes_running_parent_to_side_triage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            runtime = FakeDaemonRuntime(activity={"status": "running", "active_turn_id": "turn-main-1"})

            result = self.handler.handle(instance["context"], instance["state"], runtime, self._trigger())

            self.assertEqual(result.status, "handled")
            self.assertEqual([call["method"] for call in runtime.calls], ["parent_activity", "submit_side_triage_prompt"])
            call = runtime.calls[1]
            self.assertEqual(call["handler_name"], "message_available")
            self.assertEqual(call["origin_id"], "msg-readable")
            prompt = call["text"]
            self.assertIsInstance(prompt, str)
            self.assertIn("[MESSAGE TRIAGE]", prompt)
            self.assertIn("msg-readable", prompt)
            self.assertIn('From: {"actor_id": "act-pm-readable", "role_id": "pm"}', prompt)
            self.assertIn('To: {"actor_id": "act-dev-daemon", "role_id": "dev"}', prompt)
            self.assertIn("message__get", prompt)
            self.assertIn("message__conversation", prompt)
            self.assertIn("message__send", prompt)
            self.assertIn("message__mark", prompt)
            self.assertNotIn("message__" + "list", prompt)
            self.assertNotIn("mailbox.local_trigger", prompt)
            self.assertNotIn("message." + "parent_required", prompt)
            self.assertNotIn("parent_thread_id", prompt)
            self.assertNotIn("side_thread_id", prompt)
            self.assertNotIn("codex-remote", prompt)

    def test_parent_required_prompt_renderer_is_message_owned(self) -> None:
        prompt = self.handler_module.message_rules.render_parent_required_prompt(
            "msg-readable",
            {"role_id": "pm", "actor_id": "act-pm-readable"},
            {"role_id": "dev", "actor_id": "act-dev-daemon"},
            "Requires parent context.",
        )

        self.assertIn("[MESSAGE NEEDS PARENT]", prompt)
        self.assertIn("Requires parent context.", prompt)
        self.assertIn("message__get", prompt)
        self.assertIn("message__conversation", prompt)
        self.assertIn("message__send", prompt)
        self.assertIn("message__mark", prompt)
        self.assertNotIn("message__" + "list", prompt)
        self.assertNotIn("message." + "parent_required", prompt)
        self.assertNotIn("mailbox.local_trigger", prompt)

    def test_message_available_handler_fails_when_parent_activity_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            runtime = FakeDaemonRuntime(activity={"status": "unavailable", "error": "app-server down"})

            result = self.handler.handle(instance["context"], instance["state"], runtime, self._trigger())

            self.assertEqual(result.status, "failed")
            self.assertIn("app-server down", result.message)
            self.assertEqual([call["method"] for call in runtime.calls], ["parent_activity"])

    def test_message_available_handler_records_failed_parent_submit_as_handler_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            runtime = FakeDaemonRuntime(error=RuntimeError("submit failed"))

            result = self.handler.handle(instance["context"], instance["state"], runtime, self._trigger())

            self.assertEqual(result.status, "failed")
            self.assertIn("submit failed", result.message)

    def test_parent_required_trigger_is_no_longer_a_message_handler_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            runtime = FakeDaemonRuntime()
            trigger = self._trigger(
                trigger_type="message." + "parent_required",
                payload={"message_id": "msg-readable", "reason": "parent is required"},
                source_context={"side_thread_id": "thr-side-1"},
            )

            self.assertFalse(self.handler.handles(trigger))
            result = self.handler.handle(instance["context"], instance["state"], runtime, trigger)

            self.assertEqual(result.status, "ignored")
            self.assertEqual(runtime.calls, [])


if __name__ == "__main__":
    unittest.main()
