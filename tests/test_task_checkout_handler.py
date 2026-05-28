#!/usr/bin/env python3
"""Tests for the daemon task checkout handler."""

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
TASK_CHECKOUT_HANDLER_PATH = ROOT / "tools" / "launcher" / "task_checkout_handler.py"
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


class FakeDaemonClient:
    def __init__(self, *, result: dict[str, object] | None = None, error: BaseException | None = None) -> None:
        self.result = result or {"turn": {"id": "turn-daemon-1"}}
        self.error = error
        self.requests: list[dict[str, object]] = []

    def request(self, method: str, params: dict[str, object] | None) -> dict[str, object]:
        self.requests.append({"method": method, "params": params or {}})
        if self.error is not None:
            raise self.error
        return self.result


class TaskCheckoutHandlerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.daemon_core = load_module(DAEMON_CORE_PATH)
        self.task_checkout_handler = load_module(TASK_CHECKOUT_HANDLER_PATH)
        self.handler = self.task_checkout_handler.TaskCheckoutHandler()

    def _instance(self, temp_root: str) -> dict[str, Any]:
        instance_root = Path(temp_root) / "instances" / "inst-dev-daemon"
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload: dict[str, Any] = {
            "instance_id": "inst-dev-daemon",
            "buddy": "dev",
            "status": "active",
            "instance_root": str(instance_root),
            "workspace_dir": str(instance_root / "workspace"),
            "thread_id": "thr-main",
            "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
        }
        instance_json.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        return {
            "instance_root": instance_root,
            "instance_json": instance_json,
            "payload": payload,
        }

    def _state(self, instance_root: Path) -> Any:
        return self.daemon_core.DaemonState.load(
            instance_root=instance_root,
            instance_id="inst-dev-daemon",
            main_thread_id="thr-main",
        )

    def _completed(self, *, thread_id: str = "thr-main", turn_id: str = "turn-user-1", status: str = "completed") -> dict[str, object]:
        return {
            "method": "turn/completed",
            "params": {
                "threadId": thread_id,
                "turn": {
                    "id": turn_id,
                    "items": [],
                    "itemsView": "summary",
                    "status": status,
                    "error": None,
                    "startedAt": 0,
                    "completedAt": 1 if status != "inProgress" else None,
                    "durationMs": 1 if status != "inProgress" else None,
                },
            },
        }

    def _patch_snapshot_render(self) -> list[tuple[str, object]]:
        calls: list[tuple[str, object]] = []
        original_snapshot = self.task_checkout_handler.task_management.current_snapshot
        original_render = self.task_checkout_handler.task_tui.render_stop_task_tui

        def fake_current_snapshot(**kwargs: object) -> dict[str, object]:
            calls.append(("snapshot", kwargs))
            return {
                "current_task": {"id": "task-1", "status": "active", "summary": "summary"},
                "last_event": None,
                "progress_summary": "summary",
            }

        def fake_render_stop_task_tui(snapshot: object, previous_turn: object) -> str:
            calls.append(("render", {"snapshot": snapshot, "previous_turn": previous_turn}))
            return "[TASK CHECKOUT]\nContinue -> no task update"

        self.addCleanup(setattr, self.task_checkout_handler.task_management, "current_snapshot", original_snapshot)
        self.addCleanup(setattr, self.task_checkout_handler.task_tui, "render_stop_task_tui", original_render)
        self.task_checkout_handler.task_management.current_snapshot = fake_current_snapshot
        self.task_checkout_handler.task_tui.render_stop_task_tui = fake_render_stop_task_tui
        return calls


class TaskCheckoutHandlerFilterTests(TaskCheckoutHandlerTestCase):
    def test_completed_main_thread_user_turn_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            state = self._state(instance["instance_root"])

            previous_turn = self.task_checkout_handler.completed_turn_for_checkout(self._completed(), state)

            self.assertEqual(
                previous_turn,
                {"thread_id": "thr-main", "turn_id": "turn-user-1", "status": "completed"},
            )

    def test_other_thread_completed_turn_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            state = self._state(instance["instance_root"])

            previous_turn = self.task_checkout_handler.completed_turn_for_checkout(
                self._completed(thread_id="thr-side"),
                state,
            )

            self.assertIsNone(previous_turn)

    def test_non_completed_statuses_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            state = self._state(instance["instance_root"])

            self.assertIsNone(self.task_checkout_handler.completed_turn_for_checkout(self._completed(status="failed"), state))
            self.assertIsNone(self.task_checkout_handler.completed_turn_for_checkout(self._completed(status="interrupted"), state))
            self.assertIsNone(self.task_checkout_handler.completed_turn_for_checkout(self._completed(status="inProgress"), state))

    def test_missing_notification_fields_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            state = self._state(instance["instance_root"])

            self.assertIsNone(self.task_checkout_handler.completed_turn_for_checkout({"method": "turn/completed"}, state))
            self.assertIsNone(
                self.task_checkout_handler.completed_turn_for_checkout(
                    {"method": "turn/completed", "params": {}},
                    state,
                )
            )
            self.assertIsNone(
                self.task_checkout_handler.completed_turn_for_checkout(
                    {"method": "turn/completed", "params": {"threadId": "thr-main", "turn": {"status": "completed"}}},
                    state,
                )
            )
            self.assertIsNone(
                self.task_checkout_handler.completed_turn_for_checkout(
                    {"method": "turn/completed", "params": {"turn": {"id": "turn-user-1", "status": "completed"}}},
                    state,
                )
            )

    def test_daemon_origin_turn_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            state = self._state(instance["instance_root"])
            state.record_daemon_origin_turn("turn-daemon-1")

            previous_turn = self.task_checkout_handler.completed_turn_for_checkout(
                self._completed(turn_id="turn-daemon-1"),
                state,
            )

            self.assertIsNone(previous_turn)


class TaskCheckoutHandlerSendTests(TaskCheckoutHandlerTestCase):
    def test_accepted_completed_turn_sends_one_turn_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.daemon_core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            calls = self._patch_snapshot_render()
            client = FakeDaemonClient(result={"turn": {"id": "turn-daemon-1"}})

            sent = self.handler.handle_notification(context, state, client, self._completed())

            self.assertTrue(sent)
            self.assertEqual([request["method"] for request in client.requests], ["turn/start"])
            params = client.requests[0]["params"]
            assert isinstance(params, dict)
            self.assertEqual(params["threadId"], "thr-main")
            self.assertEqual(params["permissions"], "buddyswitch-runtime")
            input_payload = params["input"]
            assert isinstance(input_payload, list)
            prompt = input_payload[0]["text"]
            self.assertTrue(prompt.startswith("[TASK CHECKOUT]"))
            self.assertNotIn("[TASK CONTEXT]", prompt)
            self.assertNotIn("[USER INPUT]", prompt)
            self.assertEqual([name for name, _payload in calls], ["snapshot", "render"])
            self.assertTrue(state.is_daemon_origin_turn("turn-daemon-1"))
            saved = json.loads(self.daemon_core.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertEqual(saved["handlers"]["task_checkout"]["last_origin_turn_id"], "turn-user-1")
            self.assertEqual(saved["handlers"]["task_checkout"]["last_checkout_turn_id"], "turn-daemon-1")
            self.assertIsNone(saved["handlers"]["task_checkout"]["last_error"])

    def test_missing_turn_id_records_error_and_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.daemon_core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            self._patch_snapshot_render()
            client = FakeDaemonClient(result={"turn": {}})

            sent = self.handler.handle_notification(context, state, client, self._completed())

            self.assertFalse(sent)
            saved = json.loads(self.daemon_core.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertEqual(saved["last_error"]["origin_turn_id"], "turn-user-1")
            self.assertEqual(saved["last_error"]["handler"], "task_checkout")
            self.assertIn("turn/start did not return a turn id", saved["last_error"]["message"])
            self.assertEqual(saved["handlers"]["task_checkout"]["last_error"]["origin_turn_id"], "turn-user-1")

    def test_turn_start_failure_records_error_without_retry_or_steer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.daemon_core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            self._patch_snapshot_render()
            client = FakeDaemonClient(
                error=self.task_checkout_handler.app_server.AppServerRequestError("turn/start", -32000, "active thread"),
            )

            sent = self.handler.handle_notification(context, state, client, self._completed())

            self.assertFalse(sent)
            self.assertEqual([request["method"] for request in client.requests], ["turn/start"])
            saved = json.loads(self.daemon_core.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertEqual(saved["last_error"]["origin_turn_id"], "turn-user-1")
            self.assertEqual(saved["last_error"]["handler"], "task_checkout")
            self.assertIn("turn/start failed", saved["last_error"]["message"])
            self.assertFalse(state.is_daemon_origin_turn("turn-user-1"))

            client.error = None
            client.result = {"turn": {"id": "turn-daemon-2"}}
            sent_later = self.handler.handle_notification(
                context,
                state,
                client,
                self._completed(turn_id="turn-user-2"),
            )
            self.assertTrue(sent_later)
            self.assertEqual([request["method"] for request in client.requests], ["turn/start", "turn/start"])
            self.assertNotIn("turn/steer", [request["method"] for request in client.requests])


if __name__ == "__main__":
    unittest.main()
