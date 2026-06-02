#!/usr/bin/env python3
"""Tests for unified daemon trigger normalization and routing."""

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
TRIGGERS_PATH = ROOT / "tools" / "launcher" / "daemon_triggers.py"
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


class RecordingHandler:
    name = "recording"

    def __init__(self) -> None:
        self.handled: list[Any] = []

    def handles(self, trigger: Any) -> bool:
        return trigger.type == "message.available"

    def handle(self, _context: object, _state: object, _actions: object, trigger: Any) -> object:
        self.handled.append(trigger)
        import daemon_core

        return daemon_core.HandlerResult.handled()


class FailingHandler:
    name = "failing"

    def handles(self, trigger: Any) -> bool:
        return trigger.type == "message.available"

    def handle(self, _context: object, _state: object, _actions: object, _trigger: Any) -> object:
        import daemon_core

        return daemon_core.HandlerResult.failed("handler failed intentionally")


class InvalidReturnHandler:
    name = "invalid_return"

    def handles(self, trigger: Any) -> bool:
        return trigger.type == "message.available"

    def handle(self, _context: object, _state: object, _actions: object, _trigger: Any) -> object:
        return object()


class IgnoringHandler:
    name = "ignoring"

    def handles(self, trigger: Any) -> bool:
        return trigger.type == "task.updated"

    def handle(self, *_args: object) -> object:
        raise AssertionError("ignored handler must not be called")


class DaemonTriggerRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.triggers = load_module(TRIGGERS_PATH)
        self.daemon_core = load_module(DAEMON_CORE_PATH)

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

    def _actor_address(self) -> dict[str, str]:
        return {"role_id": "dev", "actor_id": "act-dev-daemon"}

    def _trigger(self, *, trigger_type: str = "message.available") -> Any:
        return self.triggers.DaemonTrigger(
            source="mailbox_cross_actor_signal",
            type=trigger_type,
            target_actor_address=self._actor_address(),
            origin_id="sig-readable",
            correlation_id="corr-readable",
            payload={"message_id": "msg-readable"},
            source_context={"signal_id": "sig-readable"},
        )

    def test_daemon_trigger_preserves_core_fields(self) -> None:
        trigger = self._trigger()

        self.assertEqual(trigger.source, "mailbox_cross_actor_signal")
        self.assertEqual(trigger.type, "message.available")
        self.assertEqual(trigger.target_actor_address, self._actor_address())
        self.assertEqual(trigger.origin_id, "sig-readable")
        self.assertEqual(trigger.correlation_id, "corr-readable")
        self.assertEqual(trigger.payload, {"message_id": "msg-readable"})
        self.assertEqual(trigger.source_context, {"signal_id": "sig-readable"})

    def test_app_server_turn_completed_notification_normalizes_to_daemon_trigger(self) -> None:
        notification = {
            "method": "turn/completed",
            "params": {
                "threadId": "thr-main",
                "turn": {"id": "turn-user-1", "status": "completed"},
            },
        }

        trigger = self.triggers.normalize_app_server_notification(
            notification,
            target_actor_address=self._actor_address(),
        )

        self.assertEqual(trigger.source, "app_server_notification")
        self.assertEqual(trigger.type, "app_server.turn_completed")
        self.assertEqual(trigger.target_actor_address, self._actor_address())
        self.assertEqual(trigger.origin_id, "turn-user-1")
        self.assertEqual(trigger.payload, notification["params"])
        self.assertEqual(
            trigger.source_context,
            {
                "method": "turn/completed",
                "thread_id": "thr-main",
                "turn_id": "turn-user-1",
                "turn_status": "completed",
            },
        )

    def test_cross_actor_signal_normalizes_to_daemon_trigger(self) -> None:
        signal = {
            "signal_id": "sig-readable",
            "type": "message.available",
            "source_actor_address": {"role_id": "pm", "actor_id": "act-pm-daemon"},
            "target_actor_address": self._actor_address(),
            "payload": {"message_id": "msg-readable"},
            "created_at": "2026-05-30T00:00:00Z",
        }

        trigger = self.triggers.normalize_cross_actor_signal(signal)

        self.assertEqual(trigger.source, "mailbox_cross_actor_signal")
        self.assertEqual(trigger.type, "message.available")
        self.assertEqual(trigger.target_actor_address, self._actor_address())
        self.assertEqual(trigger.origin_id, "sig-readable")
        self.assertEqual(trigger.payload, {"message_id": "msg-readable"})
        self.assertEqual(
            trigger.source_context,
            {
                "signal_id": "sig-readable",
                "source_actor_address": {"role_id": "pm", "actor_id": "act-pm-daemon"},
                "created_at": "2026-05-30T00:00:00Z",
            },
        )

    def test_trigger_router_dispatches_only_through_unified_handler_interface(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            handler = RecordingHandler()

            result = self.daemon_core.dispatch_trigger(
                instance["context"],
                instance["state"],
                actions=object(),
                trigger=self._trigger(),
                handlers=[IgnoringHandler(), handler],
            )

            self.assertEqual(result["matched_count"], 1)
            self.assertEqual(result["handled_count"], 1)
            self.assertEqual(result["handling_status"], "handled")
            self.assertEqual(handler.handled, [self._trigger()])
            saved = json.loads(self.daemon_core.daemon_state_file(instance["context"].instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["handlers"]["recording"]["last_result"], "handled")
            self.assertEqual(saved["handlers"]["recording"]["last_origin_turn_id"], "sig-readable")

    def test_trigger_router_reports_handler_failures_and_invalid_returns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)

            result = self.daemon_core.dispatch_trigger(
                instance["context"],
                instance["state"],
                actions=object(),
                trigger=self._trigger(),
                handlers=[FailingHandler(), InvalidReturnHandler()],
            )

            self.assertEqual(result["matched_count"], 2)
            self.assertEqual(result["handled_count"], 0)
            self.assertEqual(result["handling_status"], "failed")
            self.assertIn("handler failed intentionally", result["handling_error"])
            self.assertIn("handler returned invalid result", result["handling_error"])
            saved = json.loads(self.daemon_core.daemon_state_file(instance["context"].instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["handlers"]["failing"]["last_result"], "failed")
            self.assertEqual(saved["handlers"]["invalid_return"]["last_result"], "failed")

    def test_trigger_router_source_has_no_legacy_entry_method_calls(self) -> None:
        import inspect

        source = inspect.getsource(self.daemon_core.dispatch_trigger)

        self.assertNotIn("handle_notification", source)
        self.assertNotIn("handle_signal", source)
        self.assertNotIn("handle_parent_required", source)


if __name__ == "__main__":
    unittest.main()
