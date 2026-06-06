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


class FakeDaemonRuntime:
    def __init__(self, *, result: str = "turn-daemon-1", error: BaseException | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict[str, object]] = []

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
                "text": text,
                "handler_name": handler_name,
                "origin_id": origin_id,
                "interrupt_policy": interrupt_policy,
            }
        )
        if self.error is not None:
            raise self.error
        return {"turn_id": self.result}


class TaskCheckoutHandlerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.daemon_core = load_module(DAEMON_CORE_PATH)
        self.task_checkout_handler = load_module(TASK_CHECKOUT_HANDLER_PATH)
        self.handler = self.task_checkout_handler.TaskCheckoutHandler()

    def _instance(self, temp_root: str) -> dict[str, Any]:
        instance_root = Path(temp_root) / "instances" / "act-dev-daed00000001"
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload: dict[str, Any] = {
            "actor_id": "act-dev-daed00000001",
            "role": "dev",
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
            actor_id="act-dev-daed00000001",
            main_thread_id="thr-main",
        )

    def _completed(
        self,
        *,
        thread_id: str = "thr-main",
        turn_id: str = "turn-user-1",
        status: str = "completed",
        trigger_type: str = "app_server.turn_completed",
    ) -> object:
        params = {
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
            }
        source_context = {
            "method": "turn/completed",
            "thread_id": thread_id,
            "turn_id": turn_id,
            "turn_status": status,
        }
        return self.daemon_core.daemon_triggers.DaemonTrigger(
            source="app_server_notification",
            type=trigger_type,
            target_actor_address={"role_id": "dev", "actor_id": "act-dev-daed00000001"},
            origin_id=turn_id,
            correlation_id=None,
            payload=params,
            source_context=source_context,
        )

    def _patch_view_render(self) -> list[tuple[str, object]]:
        calls: list[tuple[str, object]] = []
        original_view = self.task_checkout_handler.task_management.current_view
        original_render = self.task_checkout_handler.task_tui.render_stop_task_tui

        def fake_current_view(**kwargs: object) -> dict[str, object]:
            calls.append(("view", kwargs))
            return {
                "current_anchor": {"id": "task-1", "status": "active", "progress_summary": "summary"},
                "shelf": [],
                "pending_switch": None,
                "recent_events": [],
                "recent_evidence": [],
                "available_actions": ["checkout"],
                "checkout_cue": {"choices": ["continue", "finish", "block"]},
                "warnings": [],
            }

        def fake_render_stop_task_tui(view: object, previous_turn: object) -> str:
            calls.append(("render", {"view": view, "previous_turn": previous_turn}))
            return "[TASK CHECKOUT]\ntask.checkout next=continue"

        self.addCleanup(setattr, self.task_checkout_handler.task_management, "current_view", original_view)
        self.addCleanup(setattr, self.task_checkout_handler.task_tui, "render_stop_task_tui", original_render)
        self.task_checkout_handler.task_management.current_view = fake_current_view
        self.task_checkout_handler.task_tui.render_stop_task_tui = fake_render_stop_task_tui
        return calls


class TaskCheckoutHandlerFilterTests(TaskCheckoutHandlerTestCase):
    def test_task_checkout_handler_source_has_no_app_server_import(self) -> None:
        source = TASK_CHECKOUT_HANDLER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("import app_server", source)
        self.assertNotIn("handle_notification", source)

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
            missing_thread = self._completed()
            missing_thread.source_context.pop("thread_id")
            missing_turn = self._completed()
            missing_turn.source_context.pop("turn_id")
            missing_status = self._completed()
            missing_status.source_context.pop("turn_status")

            self.assertIsNone(self.task_checkout_handler.completed_turn_for_checkout(object(), state))
            self.assertIsNone(self.task_checkout_handler.completed_turn_for_checkout(missing_thread, state))
            self.assertIsNone(self.task_checkout_handler.completed_turn_for_checkout(missing_turn, state))
            self.assertIsNone(self.task_checkout_handler.completed_turn_for_checkout(missing_status, state))

    def test_task_checkout_origin_turn_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            state = self._state(instance["instance_root"])
            state.record_daemon_origin_turn(
                "turn-daemon-1",
                handler_name="task_checkout",
                origin_turn_id="turn-user-1",
            )

            previous_turn = self.task_checkout_handler.completed_turn_for_checkout(
                self._completed(turn_id="turn-daemon-1"),
                state,
            )

            self.assertIsNone(previous_turn)

    def test_message_available_daemon_origin_turn_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            state = self._state(instance["instance_root"])
            state.record_daemon_origin_turn(
                "turn-daemon-1",
                handler_name="message_available",
                origin_turn_id="msg-1",
            )

            previous_turn = self.task_checkout_handler.completed_turn_for_checkout(
                self._completed(turn_id="turn-daemon-1"),
                state,
            )

            self.assertEqual(
                previous_turn,
                {"thread_id": "thr-main", "turn_id": "turn-daemon-1", "status": "completed"},
            )

    def test_handler_returns_ignored_result_for_ignored_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.daemon_core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            state.record_daemon_origin_turn(
                "turn-daemon-1",
                handler_name="task_checkout",
                origin_turn_id="turn-user-1",
            )
            runtime = FakeDaemonRuntime()

            ignored_triggers = [
                self._completed(thread_id="thr-side"),
                self._completed(status="failed"),
                self._completed(turn_id="turn-daemon-1"),
                self._completed(trigger_type="app_server.turn_failed"),
            ]

            for trigger in ignored_triggers:
                result = self.handler.handle(context, state, runtime, trigger)
                self.assertEqual(result.status, "ignored")

            self.assertEqual(runtime.calls, [])


class TaskCheckoutHandlerSendTests(TaskCheckoutHandlerTestCase):
    def test_accepted_completed_turn_uses_runtime_submit_parent_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.daemon_core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            calls = self._patch_view_render()
            runtime = FakeDaemonRuntime(result="turn-daemon-1")

            result = self.handler.handle(context, state, runtime, self._completed())

            self.assertEqual(result.status, "handled")
            self.assertEqual(len(runtime.calls), 1)
            self.assertEqual(runtime.calls[0]["handler_name"], "task_checkout")
            self.assertEqual(runtime.calls[0]["origin_id"], "turn-user-1")
            self.assertEqual(runtime.calls[0]["interrupt_policy"], "none")
            prompt = runtime.calls[0]["text"]
            assert isinstance(prompt, str)
            self.assertTrue(prompt.startswith("[TASK CHECKOUT]"))
            self.assertNotIn("[TASK CONTEXT]", prompt)
            self.assertNotIn("[USER INPUT]", prompt)
            self.assertEqual([name for name, _payload in calls], ["view", "render"])
            view_payload = calls[0][1]
            self.assertEqual(
                view_payload.get("active_actor"),
                {"actor_id": "act-dev-daed00000001", "role_id": "dev"},
            )

    def test_task_checkout_state_uses_standard_runtime_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.daemon_core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            self._patch_view_render()
            runtime = self.daemon_core.DaemonRuntime(context=context, state=state)
            original_submit_turn = self.daemon_core.launcher_submit_turn.submit_turn

            def fake_submit_turn(*, socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, object]:
                return {"action": "start", "turn_id": "turn-daemon-1"}

            self.addCleanup(setattr, self.daemon_core.launcher_submit_turn, "submit_turn", original_submit_turn)
            self.daemon_core.launcher_submit_turn.submit_turn = fake_submit_turn

            result = self.handler.handle(context, state, runtime, self._completed())

            self.assertEqual(result.status, "handled")
            self.assertTrue(state.is_daemon_origin_turn("turn-daemon-1"))
            saved = json.loads(self.daemon_core.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertEqual(saved["handlers"]["task_checkout"]["last_origin_turn_id"], "turn-user-1")
            self.assertEqual(saved["handlers"]["task_checkout"]["last_runtime_turn_id"], "turn-daemon-1")
            self.assertIsNone(saved["handlers"]["task_checkout"]["last_error"])
            self.assertNotIn("last_" + "action" + "_turn_id", saved["handlers"]["task_checkout"])
            self.assertNotIn("last_checkout_turn_id", saved["handlers"]["task_checkout"])

    def test_missing_turn_id_records_error_and_returns_failed_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.daemon_core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            self._patch_view_render()
            runtime = self.daemon_core.DaemonRuntime(context=context, state=state)
            original_submit_turn = self.daemon_core.launcher_submit_turn.submit_turn

            def fake_submit_turn(*, socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, object]:
                return {"action": "start"}

            self.addCleanup(setattr, self.daemon_core.launcher_submit_turn, "submit_turn", original_submit_turn)
            self.daemon_core.launcher_submit_turn.submit_turn = fake_submit_turn

            result = self.handler.handle(context, state, runtime, self._completed())

            self.assertEqual(result.status, "failed")
            self.assertIn("submit_turn did not return a turn id", result.message)

    def test_submit_turn_failure_returns_failed_handler_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.daemon_core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            self._patch_view_render()
            runtime = FakeDaemonRuntime(
                error=self.task_checkout_handler.launcher_submit_turn.SubmitTurnError("submit_turn failed: active thread"),
            )

            result = self.handler.handle(context, state, runtime, self._completed())

            self.assertEqual(result.status, "failed")
            self.assertIn("submit_turn failed", result.message)
            self.assertEqual(len(runtime.calls), 1)
            self.assertFalse(state.is_daemon_origin_turn("turn-user-1"))

            runtime.error = None
            runtime.result = "turn-daemon-2"
            result_later = self.handler.handle(
                context,
                state,
                runtime,
                self._completed(turn_id="turn-user-2"),
            )
            self.assertEqual(result_later.status, "handled")
            self.assertEqual(len(runtime.calls), 2)


if __name__ == "__main__":
    unittest.main()
