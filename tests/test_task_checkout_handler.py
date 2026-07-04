#!/usr/bin/env python3
"""Tests for the daemon task checkout handler."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from itertools import count
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.repos import runtime_files  # noqa: E402

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
        raise AssertionError("task checkout handler must not submit parent prompts")


class TaskCheckoutHandlerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._runtime_tmp = tempfile.TemporaryDirectory()
        runtime_files.set_runtime_root_override(Path(self._runtime_tmp.name))
        self.daemon_core = load_module(DAEMON_CORE_PATH)
        self.task_checkout_handler = load_module(TASK_CHECKOUT_HANDLER_PATH)
        self.handler = self.task_checkout_handler.TaskCheckoutHandler()

    def tearDown(self) -> None:
        runtime_files.reset_runtime_root_override()
        self._runtime_tmp.cleanup()
        super().tearDown()

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
            target_identity_id="act-dev-daed00000001",
            target_role_id="dev",
            origin_id=turn_id,
            correlation_id=None,
            payload=params,
            source_context=source_context,
        )

    def _task_records(self) -> list[dict[str, Any]]:
        tasks_dir = runtime_files.OBJECTS_ROOT / "task-sys" / "tasks"
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(tasks_dir.glob("*.json"))
        ]

    def _assert_no_task_records(self) -> None:
        self.assertEqual(self._task_records(), [])

    def _stub_task_sys_execution(self) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        runtime_module = getattr(self.task_checkout_handler, "task_sys_runtime", None)
        if runtime_module is None:
            return calls
        original_execute = runtime_module.execute_instruction

        def fake_execute(_context: Any, instruction: dict[str, Any]) -> dict[str, Any]:
            calls.append(instruction)
            return {
                "action": instruction["type"],
                "task_id": instruction["task_id"],
                "turn_id": f"turn-checkpoint-{len(calls)}",
            }

        self.addCleanup(setattr, runtime_module, "execute_instruction", original_execute)
        runtime_module.execute_instruction = fake_execute
        return calls


class TaskCheckoutHandlerFilterTests(TaskCheckoutHandlerTestCase):
    def test_task_checkout_handler_source_has_no_app_server_import(self) -> None:
        source = TASK_CHECKOUT_HANDLER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("import app_server", source)
        self.assertNotIn("handle_notification", source)
        self.assertNotIn("submit_turn", source)
        self.assertNotIn("task_management", source)
        self.assertNotIn("task_tui", source)
        self.assertNotIn("[TASK CHECKPOINT]", source)

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

    def test_im_message_created_daemon_origin_turn_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            state = self._state(instance["instance_root"])
            state.record_daemon_origin_turn(
                "turn-daemon-1",
                handler_name="im_message_created",
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
    def test_unbound_completed_turn_does_not_create_task_or_submit_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.daemon_core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            runtime = FakeDaemonRuntime(result="turn-daemon-1")
            executed = self._stub_task_sys_execution()

            result = self.handler.handle(context, state, runtime, self._completed())

            self.assertEqual(result.status, "ignored")
            self.assertEqual(runtime.calls, [])
            self.assertEqual(executed, [])
            self._assert_no_task_records()
            self.assertFalse(state.is_daemon_origin_turn_from("turn-user-1", "task_checkout"))

    def test_unbound_completed_turn_is_not_recorded_as_task_checkout_origin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.daemon_core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            runtime = self.daemon_core.DaemonRuntime(context=context, state=state)
            self._stub_task_sys_execution()

            result = self.handler.handle(context, state, runtime, self._completed())

            self.assertEqual(result.status, "ignored")
            self.assertFalse(state.is_daemon_origin_turn("turn-user-1"))
            self.assertFalse(state.is_daemon_origin_turn_from("turn-checkpoint-1", "task_checkout"))
            self._assert_no_task_records()

    def test_repeated_unbound_completed_turns_do_not_create_task_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.daemon_core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            runtime = FakeDaemonRuntime()
            executed = self._stub_task_sys_execution()

            result = self.handler.handle(context, state, runtime, self._completed())
            result_later = self.handler.handle(
                context,
                state,
                runtime,
                self._completed(turn_id="turn-user-2"),
            )

            self.assertEqual(result.status, "ignored")
            self.assertEqual(result_later.status, "ignored")
            self.assertEqual(runtime.calls, [])
            self.assertEqual(executed, [])
            self._assert_no_task_records()


if __name__ == "__main__":
    unittest.main()
