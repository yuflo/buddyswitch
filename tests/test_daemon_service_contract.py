#!/usr/bin/env python3
"""Tests for the daemon service handler contract and runtime."""

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
MODULE_COUNTER = count()


def load_daemon_core() -> Any:
    module_name = f"buddyswitch_daemon_core_service_{next(MODULE_COUNTER)}"
    spec = importlib.util.spec_from_file_location(module_name, DAEMON_CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec for {DAEMON_CORE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeRuntimeClient:
    def __init__(self, *, result: dict[str, object] | None = None, error: BaseException | None = None) -> None:
        self.result = result or {"turn": {"id": "turn-daemon-1"}}
        self.error = error
        self.requests: list[dict[str, object]] = []

    def request(self, method: str, params: dict[str, object] | None) -> dict[str, object]:
        self.requests.append({"method": method, "params": params or {}})
        if self.error is not None:
            raise self.error
        return self.result


class DaemonServiceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.core = load_daemon_core()

    def _instance(self, temp_root: str) -> dict[str, Any]:
        instance_root = Path(temp_root) / "instances" / "act-dev-daed00000001"
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload: dict[str, Any] = {
            "actor_id": "act-dev-daed00000001",
            "role": "dev",
            "status": "active",
            "instance_root": str(instance_root),
            "workspace_dir": str(workspace_dir),
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
        return self.core.DaemonState.load(
            instance_root=instance_root,
            actor_id="act-dev-daed00000001",
            main_thread_id="thr-main",
        )

    def _saved_state(self, instance_root: Path) -> dict[str, Any]:
        return json.loads(self.core.daemon_state_file(instance_root).read_text(encoding="utf-8"))

    def _runtime_records(self, instance_root: Path) -> list[dict[str, Any]]:
        saved = self._saved_state(instance_root)
        runtime_call_ids = saved.get("daemon_runtime_call_ids", [])
        runtime_calls = saved.get("daemon_runtime_calls", {})
        return [runtime_calls[runtime_call_id] for runtime_call_id in runtime_call_ids]

    def _completed(self, *, turn_id: str = "turn-user-1") -> dict[str, object]:
        return {
            "method": "turn/completed",
            "params": {
                "threadId": "thr-main",
                "turn": {
                    "id": turn_id,
                    "status": "completed",
                },
            },
        }

    def test_handler_result_has_explicit_statuses(self) -> None:
        ignored = self.core.HandlerResult.ignored()
        handled = self.core.HandlerResult.handled()
        failed = self.core.HandlerResult.failed("boom")

        self.assertEqual(ignored.status, "ignored")
        self.assertIsNone(ignored.message)
        self.assertEqual(handled.status, "handled")
        self.assertIsNone(handled.message)
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.message, "boom")

    def test_daemon_runtime_replaces_action_gateway_without_alias(self) -> None:
        self.assertTrue(hasattr(self.core, "DaemonRuntime"))
        self.assertTrue(hasattr(self.core, "DaemonHandler"))
        self.assertFalse(hasattr(self.core, "Action" + "Gateway"))

    def test_dispatch_passes_context_state_runtime_and_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            client = FakeRuntimeClient()
            notification = self._completed()
            core = self.core

            class RecordingHandler:
                name = "recording"

                def __init__(self) -> None:
                    self.received: dict[str, object] = {}

                def handles(self, trigger: object) -> bool:
                    return getattr(trigger, "type", None) == "app_server.turn_completed"

                def handle(
                    self,
                    context_arg: object,
                    state_arg: object,
                    runtime_arg: object,
                    trigger_arg: object,
                ) -> object:
                    self.received = {
                        "context": context_arg,
                        "state": state_arg,
                        "runtime": runtime_arg,
                        "trigger": trigger_arg,
                    }
                    return core.HandlerResult.handled()

            handler = RecordingHandler()

            handled = self.core.dispatch_notification(context, state, client, notification, [handler])

            self.assertTrue(handled)
            self.assertIs(handler.received["context"], context)
            self.assertIs(handler.received["state"], state)
            self.assertIsInstance(handler.received["runtime"], self.core.DaemonRuntime)
            trigger = handler.received["trigger"]
            self.assertEqual(getattr(trigger, "type"), "app_server.turn_completed")
            self.assertEqual(getattr(trigger, "origin_id"), "turn-user-1")

    def test_dispatch_records_declared_failure_under_handler_state_and_continues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            client = FakeRuntimeClient()
            notification = self._completed()
            calls: list[str] = []
            core = self.core

            class FailingHandler:
                name = "first"

                def handles(self, trigger: object) -> bool:
                    return getattr(trigger, "type", None) == "app_server.turn_completed"

                def handle(self, *_args: object) -> object:
                    calls.append(self.name)
                    return core.HandlerResult.failed("declared failure")

            class LaterHandler:
                name = "second"

                def handles(self, trigger: object) -> bool:
                    return getattr(trigger, "type", None) == "app_server.turn_completed"

                def handle(self, *_args: object) -> object:
                    calls.append(self.name)
                    return core.HandlerResult.handled()

            handled = self.core.dispatch_notification(context, state, client, notification, [FailingHandler(), LaterHandler()])

            self.assertTrue(handled)
            self.assertEqual(calls, ["first", "second"])
            saved = json.loads(self.core.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertIsNone(saved["last_error"])
            self.assertEqual(saved["handlers"]["first"]["last_result"], "failed")
            self.assertEqual(saved["handlers"]["first"]["last_error"]["message"], "declared failure")
            self.assertEqual(saved["handlers"]["first"]["last_error"]["origin_turn_id"], "turn-user-1")
            self.assertEqual(saved["handlers"]["second"]["last_result"], "handled")
            self.assertIsNone(saved["handlers"]["second"]["last_error"])

    def test_dispatch_records_exception_under_handler_state_and_continues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            client = FakeRuntimeClient()
            notification = self._completed()
            calls: list[str] = []
            core = self.core

            class ExplodingHandler:
                name = "exploder"

                def handles(self, trigger: object) -> bool:
                    return getattr(trigger, "type", None) == "app_server.turn_completed"

                def handle(self, *_args: object) -> object:
                    calls.append(self.name)
                    raise RuntimeError("handler exploded")

            class LaterHandler:
                name = "second"

                def handles(self, trigger: object) -> bool:
                    return getattr(trigger, "type", None) == "app_server.turn_completed"

                def handle(self, *_args: object) -> object:
                    calls.append(self.name)
                    return core.HandlerResult.handled()

            handled = self.core.dispatch_notification(context, state, client, notification, [ExplodingHandler(), LaterHandler()])

            self.assertTrue(handled)
            self.assertEqual(calls, ["exploder", "second"])
            saved = json.loads(self.core.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertIsNone(saved["last_error"])
            self.assertEqual(saved["handlers"]["exploder"]["last_result"], "failed")
            self.assertEqual(saved["handlers"]["exploder"]["last_error"]["message"], "handler exploded")
            self.assertEqual(saved["handlers"]["exploder"]["last_error"]["origin_turn_id"], "turn-user-1")

    def test_submit_parent_prompt_none_delegates_to_launcher_submit_turn(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            runtime = self.core.DaemonRuntime(context=context, state=state)
            calls: list[dict[str, object]] = []
            original_submit_turn = self.core.launcher_submit_turn.submit_turn

            def fake_submit_turn(*, socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, object]:
                calls.append(
                    {
                        "socket_path": socket_path,
                        "thread_id": thread_id,
                        "text": text,
                        "permissions": permissions,
                    }
                )
                return {"action": "start", "turn_id": "turn-daemon-1"}

            self.addCleanup(setattr, self.core.launcher_submit_turn, "submit_turn", original_submit_turn)
            self.core.launcher_submit_turn.submit_turn = fake_submit_turn

            result = runtime.submit_parent_prompt(
                "daemon prompt",
                handler_name="fake",
                origin_id="turn-user-1",
                interrupt_policy="none",
            )

            self.assertEqual(result, {"turn_id": "turn-daemon-1"})
            self.assertEqual(
                calls,
                [
                    {
                        "socket_path": context.socket_path,
                        "thread_id": "thr-main",
                        "text": "daemon prompt",
                        "permissions": "buddyswitch-runtime",
                    }
                ],
            )

    def test_submit_parent_prompt_none_records_daemon_origin_and_handler_action_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            runtime = self.core.DaemonRuntime(context=context, state=state)
            original_submit_turn = self.core.launcher_submit_turn.submit_turn

            def fake_submit_turn(*, socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, object]:
                return {"action": "start", "turn_id": "turn-daemon-1"}

            self.addCleanup(setattr, self.core.launcher_submit_turn, "submit_turn", original_submit_turn)
            self.core.launcher_submit_turn.submit_turn = fake_submit_turn

            runtime.submit_parent_prompt(
                "daemon prompt",
                handler_name="fake",
                origin_id="turn-user-1",
                interrupt_policy="none",
            )

            saved = json.loads(self.core.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertEqual(saved["daemon_origin_turn_ids"], ["turn-daemon-1"])
            self.assertEqual(saved["daemon_origin_turns"]["turn-daemon-1"]["handler_name"], "fake")
            self.assertEqual(saved["daemon_origin_turns"]["turn-daemon-1"]["origin_turn_id"], "turn-user-1")
            self.assertEqual(saved["daemon_origin_turns"]["turn-daemon-1"]["turn_id"], "turn-daemon-1")
            self.assertRegex(saved["daemon_origin_turns"]["turn-daemon-1"]["created_at"], r"^\d{4}-\d{2}-\d{2}T")
            self.assertEqual(saved["handlers"]["fake"]["last_origin_turn_id"], "turn-user-1")
            self.assertEqual(saved["handlers"]["fake"]["last_runtime_turn_id"], "turn-daemon-1")
            self.assertIsNone(saved["handlers"]["fake"]["last_error"])

    def test_submit_parent_prompt_none_raises_launcher_submit_turn_error_when_no_turn_id_is_returned(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            runtime = self.core.DaemonRuntime(context=context, state=state)
            original_submit_turn = self.core.launcher_submit_turn.submit_turn

            def fake_submit_turn(*, socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, object]:
                return {"action": "start"}

            self.addCleanup(setattr, self.core.launcher_submit_turn, "submit_turn", original_submit_turn)
            self.core.launcher_submit_turn.submit_turn = fake_submit_turn

            with self.assertRaises(self.core.launcher_submit_turn.SubmitTurnError):
                runtime.submit_parent_prompt(
                    "daemon prompt",
                    handler_name="fake",
                    origin_id="turn-user-1",
                    interrupt_policy="none",
                )

            self.assertEqual(state.payload["daemon_origin_turn_ids"], [])
            state_path = self.core.daemon_state_file(instance["instance_root"])
            if state_path.exists():
                saved = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertNotIn("fake", saved["handlers"])

    def test_submit_parent_prompt_none_exposes_launcher_submit_turn_error_without_retry_or_steer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            runtime = self.core.DaemonRuntime(context=context, state=state)
            original_submit_turn = self.core.launcher_submit_turn.submit_turn

            def fake_submit_turn(*, socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, object]:
                raise self.core.launcher_submit_turn.SubmitTurnError("submit_turn failed: active thread")

            self.addCleanup(setattr, self.core.launcher_submit_turn, "submit_turn", original_submit_turn)
            self.core.launcher_submit_turn.submit_turn = fake_submit_turn

            with self.assertRaises(self.core.launcher_submit_turn.SubmitTurnError):
                runtime.submit_parent_prompt(
                    "daemon prompt",
                    handler_name="fake",
                    origin_id="turn-user-1",
                    interrupt_policy="none",
                )

            self.assertEqual(state.payload["daemon_origin_turn_ids"], [])

    def test_parent_activity_reports_idle_running_and_unavailable_from_local_app_server(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            runtime = self.core.DaemonRuntime(context=context, state=state)
            calls: list[dict[str, object]] = []
            original_thread_read = self.core.app_server.thread_read
            original_active_turn_id = self.core.app_server.active_turn_id

            def idle_thread_read(socket_path: Path, thread_id: str, *, include_turns: bool = False) -> dict[str, object]:
                calls.append({"helper": "thread_read", "socket_path": socket_path, "thread_id": thread_id, "include_turns": include_turns})
                return {"thread": {"id": thread_id, "status": {"type": "idle"}}}

            def running_thread_read(socket_path: Path, thread_id: str, *, include_turns: bool = False) -> dict[str, object]:
                calls.append({"helper": "thread_read", "socket_path": socket_path, "thread_id": thread_id, "include_turns": include_turns})
                return {"thread": {"id": thread_id, "status": {"type": "active", "activeFlags": []}}}

            def fake_active_turn_id(socket_path: Path, thread_id: str) -> str:
                calls.append({"helper": "active_turn_id", "socket_path": socket_path, "thread_id": thread_id})
                return "turn-main-1"

            self.addCleanup(setattr, self.core.app_server, "thread_read", original_thread_read)
            self.addCleanup(setattr, self.core.app_server, "active_turn_id", original_active_turn_id)
            self.core.app_server.thread_read = idle_thread_read

            self.assertEqual(runtime.parent_activity(), {"status": "idle", "active_turn_id": None})

            self.core.app_server.thread_read = running_thread_read
            self.core.app_server.active_turn_id = fake_active_turn_id
            self.assertEqual(runtime.parent_activity(), {"status": "running", "active_turn_id": "turn-main-1"})

            def failing_thread_read(*_args: object, **_kwargs: object) -> dict[str, object]:
                raise self.core.app_server.AppServerUnavailableError("app-server down")

            self.core.app_server.thread_read = failing_thread_read
            unavailable = runtime.parent_activity()
            self.assertEqual(unavailable["status"], "unavailable")
            self.assertIn("app-server down", unavailable["error"])
            self.assertEqual(calls[0]["helper"], "thread_read")

    def test_submit_parent_prompt_before_submit_interrupts_then_submits_and_records_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            runtime = self.core.DaemonRuntime(context=context, state=state)
            submit_calls: list[dict[str, object]] = []
            interrupt_calls: list[dict[str, object]] = []
            original_submit_turn = self.core.launcher_submit_turn.submit_turn
            original_interrupt_turn = self.core.app_server.interrupt_turn

            def fake_submit_turn(*, socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, object]:
                submit_calls.append({"socket_path": socket_path, "thread_id": thread_id, "text": text, "permissions": permissions})
                return {"action": "start", "turn_id": "turn-daemon-1"}

            def fake_interrupt_turn(socket_path: Path, thread_id: str) -> dict[str, object]:
                interrupt_calls.append({"socket_path": socket_path, "thread_id": thread_id})
                return {"ok": True, "turn_id": "turn-main-1"}

            self.addCleanup(setattr, self.core.launcher_submit_turn, "submit_turn", original_submit_turn)
            self.addCleanup(setattr, self.core.app_server, "interrupt_turn", original_interrupt_turn)
            self.core.launcher_submit_turn.submit_turn = fake_submit_turn
            self.core.app_server.interrupt_turn = fake_interrupt_turn

            result = runtime.submit_parent_prompt(
                "parent prompt",
                handler_name="message_available",
                origin_id="msg-1",
                interrupt_policy="before_submit",
            )

            self.assertEqual(result["interrupted_turn_id"], "turn-main-1")
            self.assertEqual(result["turn_id"], "turn-daemon-1")
            self.assertEqual(interrupt_calls, [{"socket_path": context.socket_path, "thread_id": "thr-main"}])
            self.assertEqual(submit_calls[0]["thread_id"], "thr-main")
            records = self._runtime_records(instance["instance_root"])
            self.assertEqual([record["runtime_method"] for record in records], ["parent_interrupt", "parent_submit"])
            self.assertEqual(records[0]["interrupted_turn_id"], "turn-main-1")
            self.assertEqual(records[1]["turn_id"], "turn-daemon-1")
            self.assertEqual(records[1]["handler_name"], "message_available")
            self.assertEqual(records[1]["origin_id"], "msg-1")
            self.assertEqual(records[1]["status"], "succeeded")
            saved = self._saved_state(instance["instance_root"])
            self.assertEqual(saved["daemon_origin_turn_ids"], ["turn-daemon-1"])

    def test_submit_parent_prompt_ensure_stopped_idle_submits_without_interrupt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            runtime = self.core.DaemonRuntime(context=context, state=state)
            submit_calls: list[dict[str, object]] = []
            interrupt_calls: list[dict[str, object]] = []
            thread_read_calls: list[dict[str, object]] = []
            original_submit_turn = self.core.launcher_submit_turn.submit_turn
            original_interrupt_turn = self.core.app_server.interrupt_turn
            original_thread_read = self.core.app_server.thread_read

            def fake_submit_turn(*, socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, object]:
                submit_calls.append({"socket_path": socket_path, "thread_id": thread_id, "text": text, "permissions": permissions})
                return {"action": "start", "turn_id": "turn-daemon-1"}

            def fake_interrupt_turn(socket_path: Path, thread_id: str) -> dict[str, object]:
                interrupt_calls.append({"socket_path": socket_path, "thread_id": thread_id})
                return {"ok": True, "turn_id": "turn-main-1"}

            def fake_thread_read(socket_path: Path, thread_id: str, *, include_turns: bool = False) -> dict[str, object]:
                thread_read_calls.append({"socket_path": socket_path, "thread_id": thread_id, "include_turns": include_turns})
                return {"thread": {"id": thread_id, "status": "idle"}}

            self.addCleanup(setattr, self.core.launcher_submit_turn, "submit_turn", original_submit_turn)
            self.addCleanup(setattr, self.core.app_server, "interrupt_turn", original_interrupt_turn)
            self.addCleanup(setattr, self.core.app_server, "thread_read", original_thread_read)
            self.core.launcher_submit_turn.submit_turn = fake_submit_turn
            self.core.app_server.interrupt_turn = fake_interrupt_turn
            self.core.app_server.thread_read = fake_thread_read

            result = runtime.submit_parent_prompt(
                "parent prompt",
                handler_name="message_mark",
                origin_id="msg-1",
                interrupt_policy="ensure_stopped",
            )

            self.assertEqual(result, {"turn_id": "turn-daemon-1"})
            self.assertEqual(interrupt_calls, [])
            self.assertEqual(len(thread_read_calls), 1)
            self.assertEqual(submit_calls[0]["thread_id"], "thr-main")
            records = self._runtime_records(instance["instance_root"])
            self.assertEqual([record["runtime_method"] for record in records], ["parent_submit"])
            self.assertEqual(records[0]["turn_id"], "turn-daemon-1")
            self.assertEqual(records[0]["handler_name"], "message_mark")
            self.assertEqual(records[0]["origin_id"], "msg-1")
            self.assertEqual(records[0]["status"], "succeeded")

    def test_submit_parent_prompt_ensure_stopped_running_interrupts_waits_then_submits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            runtime = self.core.DaemonRuntime(context=context, state=state)
            submit_calls: list[dict[str, object]] = []
            interrupt_calls: list[dict[str, object]] = []
            thread_statuses = iter(("active", "idle"))
            original_submit_turn = self.core.launcher_submit_turn.submit_turn
            original_interrupt_turn = self.core.app_server.interrupt_turn
            original_thread_read = self.core.app_server.thread_read
            original_active_turn_id = self.core.app_server.active_turn_id

            def fake_submit_turn(*, socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, object]:
                submit_calls.append({"socket_path": socket_path, "thread_id": thread_id, "text": text, "permissions": permissions})
                return {"action": "start", "turn_id": "turn-daemon-1"}

            def fake_interrupt_turn(socket_path: Path, thread_id: str) -> dict[str, object]:
                interrupt_calls.append({"socket_path": socket_path, "thread_id": thread_id})
                return {"ok": True, "turn_id": "turn-main-1"}

            def fake_thread_read(socket_path: Path, thread_id: str, *, include_turns: bool = False) -> dict[str, object]:
                return {"thread": {"id": thread_id, "status": next(thread_statuses)}}

            def fake_active_turn_id(socket_path: Path, thread_id: str) -> str | None:
                return "turn-main-1"

            self.addCleanup(setattr, self.core.launcher_submit_turn, "submit_turn", original_submit_turn)
            self.addCleanup(setattr, self.core.app_server, "interrupt_turn", original_interrupt_turn)
            self.addCleanup(setattr, self.core.app_server, "thread_read", original_thread_read)
            self.addCleanup(setattr, self.core.app_server, "active_turn_id", original_active_turn_id)
            self.core.launcher_submit_turn.submit_turn = fake_submit_turn
            self.core.app_server.interrupt_turn = fake_interrupt_turn
            self.core.app_server.thread_read = fake_thread_read
            self.core.app_server.active_turn_id = fake_active_turn_id

            result = runtime.submit_parent_prompt(
                "parent prompt",
                handler_name="message_mark",
                origin_id="msg-1",
                interrupt_policy="ensure_stopped",
            )

            self.assertEqual(result["interrupted_turn_id"], "turn-main-1")
            self.assertEqual(result["turn_id"], "turn-daemon-1")
            self.assertEqual(interrupt_calls, [{"socket_path": context.socket_path, "thread_id": "thr-main"}])
            self.assertEqual(submit_calls[0]["thread_id"], "thr-main")
            records = self._runtime_records(instance["instance_root"])
            self.assertEqual([record["runtime_method"] for record in records], ["parent_interrupt", "parent_submit"])
            self.assertEqual(records[0]["status"], "succeeded")
            self.assertEqual(records[0]["interrupted_turn_id"], "turn-main-1")
            self.assertEqual(records[1]["status"], "succeeded")
            self.assertEqual(records[1]["turn_id"], "turn-daemon-1")

    def test_submit_parent_prompt_ensure_stopped_no_active_turn_race_waits_then_submits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            runtime = self.core.DaemonRuntime(context=context, state=state)
            submit_calls: list[dict[str, object]] = []
            thread_statuses = iter(("active", "idle"))
            active_turn_ids = iter((None, None))
            original_submit_turn = self.core.launcher_submit_turn.submit_turn
            original_thread_read = self.core.app_server.thread_read
            original_active_turn_id = self.core.app_server.active_turn_id

            def fake_submit_turn(*, socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, object]:
                submit_calls.append({"socket_path": socket_path, "thread_id": thread_id, "text": text, "permissions": permissions})
                return {"action": "start", "turn_id": "turn-daemon-1"}

            def fake_thread_read(socket_path: Path, thread_id: str, *, include_turns: bool = False) -> dict[str, object]:
                return {"thread": {"id": thread_id, "status": next(thread_statuses)}}

            def fake_active_turn_id(socket_path: Path, thread_id: str) -> str | None:
                return next(active_turn_ids)

            self.addCleanup(setattr, self.core.launcher_submit_turn, "submit_turn", original_submit_turn)
            self.addCleanup(setattr, self.core.app_server, "thread_read", original_thread_read)
            self.addCleanup(setattr, self.core.app_server, "active_turn_id", original_active_turn_id)
            self.core.launcher_submit_turn.submit_turn = fake_submit_turn
            self.core.app_server.thread_read = fake_thread_read
            self.core.app_server.active_turn_id = fake_active_turn_id

            result = runtime.submit_parent_prompt(
                "parent prompt",
                handler_name="message_mark",
                origin_id="msg-1",
                interrupt_policy="ensure_stopped",
            )

            self.assertEqual(result["turn_id"], "turn-daemon-1")
            self.assertNotIn("interrupted_turn_id", result)
            self.assertEqual(submit_calls[0]["thread_id"], "thr-main")
            records = self._runtime_records(instance["instance_root"])
            self.assertEqual([record["runtime_method"] for record in records], ["parent_interrupt", "parent_submit"])
            self.assertEqual(records[0]["status"], "failed")
            self.assertIn("no active in-progress turn", records[0]["error"])
            self.assertEqual(records[1]["status"], "succeeded")
            self.assertEqual(records[1]["turn_id"], "turn-daemon-1")

    def test_submit_parent_prompt_ensure_stopped_timeout_fails_without_submit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            runtime = self.core.DaemonRuntime(context=context, state=state)
            interrupt_calls: list[dict[str, object]] = []
            submit_calls: list[dict[str, object]] = []
            original_submit_turn = self.core.launcher_submit_turn.submit_turn
            original_interrupt_turn = self.core.app_server.interrupt_turn
            original_thread_read = self.core.app_server.thread_read
            original_active_turn_id = self.core.app_server.active_turn_id
            original_sleep = self.core.time.sleep

            def fake_submit_turn(*, socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, object]:
                submit_calls.append({"socket_path": socket_path, "thread_id": thread_id, "text": text, "permissions": permissions})
                return {"action": "start", "turn_id": "turn-daemon-1"}

            def fake_interrupt_turn(socket_path: Path, thread_id: str) -> dict[str, object]:
                interrupt_calls.append({"socket_path": socket_path, "thread_id": thread_id})
                return {"ok": True, "turn_id": "turn-main-1"}

            def fake_thread_read(socket_path: Path, thread_id: str, *, include_turns: bool = False) -> dict[str, object]:
                return {"thread": {"id": thread_id, "status": "active"}}

            def fake_active_turn_id(socket_path: Path, thread_id: str) -> str | None:
                return "turn-main-1"

            def fake_sleep(_seconds: float) -> None:
                return None

            self.addCleanup(setattr, self.core.launcher_submit_turn, "submit_turn", original_submit_turn)
            self.addCleanup(setattr, self.core.app_server, "interrupt_turn", original_interrupt_turn)
            self.addCleanup(setattr, self.core.app_server, "thread_read", original_thread_read)
            self.addCleanup(setattr, self.core.app_server, "active_turn_id", original_active_turn_id)
            self.addCleanup(setattr, self.core.time, "sleep", original_sleep)
            self.core.launcher_submit_turn.submit_turn = fake_submit_turn
            self.core.app_server.interrupt_turn = fake_interrupt_turn
            self.core.app_server.thread_read = fake_thread_read
            self.core.app_server.active_turn_id = fake_active_turn_id
            self.core.time.sleep = fake_sleep

            with self.assertRaisesRegex(RuntimeError, "parent thread .* did not become idle"):
                runtime.submit_parent_prompt(
                    "parent prompt",
                    handler_name="message_mark",
                    origin_id="msg-1",
                    interrupt_policy="ensure_stopped",
                )

            self.assertEqual(interrupt_calls, [{"socket_path": context.socket_path, "thread_id": "thr-main"}])
            self.assertEqual(submit_calls, [])
            records = self._runtime_records(instance["instance_root"])
            self.assertEqual([record["runtime_method"] for record in records], ["parent_interrupt"])
            self.assertEqual(records[0]["status"], "succeeded")

    def test_submit_parent_prompt_rejects_invalid_interrupt_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            runtime = self.core.DaemonRuntime(context=context, state=state)

            with self.assertRaisesRegex(ValueError, "interrupt_policy"):
                runtime.submit_parent_prompt(
                    "parent prompt",
                    handler_name="message_available",
                    origin_id="msg-1",
                    interrupt_policy="after_submit",
                )

    def test_submit_parent_prompt_before_submit_records_submit_failure_after_successful_interrupt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            runtime = self.core.DaemonRuntime(context=context, state=state)
            original_submit_turn = self.core.launcher_submit_turn.submit_turn
            original_interrupt_turn = self.core.app_server.interrupt_turn

            def fake_interrupt_turn(socket_path: Path, thread_id: str) -> dict[str, object]:
                return {"ok": True, "turn_id": "turn-main-1"}

            def fake_submit_turn(*, socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, object]:
                raise self.core.launcher_submit_turn.SubmitTurnError("submit failed after interrupt")

            self.addCleanup(setattr, self.core.launcher_submit_turn, "submit_turn", original_submit_turn)
            self.addCleanup(setattr, self.core.app_server, "interrupt_turn", original_interrupt_turn)
            self.core.launcher_submit_turn.submit_turn = fake_submit_turn
            self.core.app_server.interrupt_turn = fake_interrupt_turn

            with self.assertRaisesRegex(self.core.launcher_submit_turn.SubmitTurnError, "submit failed"):
                runtime.submit_parent_prompt(
                    "parent prompt",
                    handler_name="message_available",
                    origin_id="msg-1",
                    interrupt_policy="before_submit",
                )

            records = self._runtime_records(instance["instance_root"])
            self.assertEqual([record["runtime_method"] for record in records], ["parent_interrupt", "parent_submit"])
            self.assertEqual(records[0]["status"], "succeeded")
            self.assertEqual(records[0]["interrupted_turn_id"], "turn-main-1")
            self.assertEqual(records[1]["status"], "failed")
            self.assertIn("submit failed after interrupt", records[1]["error"])
            self.assertEqual(state.payload["daemon_origin_turn_ids"], [])

    def test_submit_side_triage_prompt_starts_or_reuses_side_and_records_runtime_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            runtime = self.core.DaemonRuntime(context=context, state=state)
            calls: list[dict[str, object]] = []
            original_side_start = self.core.app_server.side_start
            original_input_turn = self.core.app_server.input_turn

            def fake_side_start(
                socket_path: Path,
                parent_thread_id: str,
                text: str,
                *,
                workspace_dir: Path,
                shared_project_workspace_dir: Path,
                permissions: str,
            ) -> dict[str, object]:
                calls.append(
                    {
                        "helper": "side_start",
                        "socket_path": socket_path,
                        "parent_thread_id": parent_thread_id,
                        "text": text,
                        "workspace_dir": workspace_dir,
                        "shared_project_workspace_dir": shared_project_workspace_dir,
                        "permissions": permissions,
                    }
                )
                return {"action": "start", "side_thread_id": "thr-side-1", "turn_id": "turn-side-1"}

            def fake_input_turn(socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, object]:
                calls.append({"helper": "input_turn", "socket_path": socket_path, "thread_id": thread_id, "text": text, "permissions": permissions})
                return {"action": "start", "turn_id": "turn-side-2"}

            self.addCleanup(setattr, self.core.app_server, "side_start", original_side_start)
            self.addCleanup(setattr, self.core.app_server, "input_turn", original_input_turn)
            self.core.app_server.side_start = fake_side_start
            self.core.app_server.input_turn = fake_input_turn

            started = runtime.submit_side_triage_prompt("triage prompt", handler_name="message_available", origin_id="msg-1")
            reused = runtime.submit_side_triage_prompt("follow up", handler_name="message_available", origin_id="msg-2")

            self.assertEqual(started["side_thread_id"], "thr-side-1")
            self.assertEqual(reused["side_thread_id"], "thr-side-1")
            self.assertEqual(reused["action"], "send")
            self.assertEqual([call["helper"] for call in calls], ["side_start", "input_turn"])
            self.assertEqual(calls[0]["workspace_dir"], context.workspace_dir)
            self.assertEqual(calls[0]["shared_project_workspace_dir"], context.project_workspace_dir)
            self.assertEqual(calls[0]["permissions"], "buddyswitch-runtime")
            records = self._runtime_records(instance["instance_root"])
            self.assertEqual([record["runtime_method"] for record in records], ["side_start", "side_send"])
            self.assertEqual([record["side_thread_id"] for record in records], ["thr-side-1", "thr-side-1"])
            payload = json.loads(instance["instance_json"].read_text(encoding="utf-8"))
            self.assertEqual(payload["side_threads"][0]["thread_id"], "thr-side-1")

    def test_daemon_runtime_handler_facing_surface_is_exactly_clean_runtime_methods(self) -> None:
        public_methods = {
            name
            for name, value in vars(self.core.DaemonRuntime).items()
            if callable(value) and not name.startswith("_")
        }
        self.assertEqual(
            public_methods,
            {
                "parent_activity",
                "submit_parent_prompt",
                "submit_side_triage_prompt",
            },
        )

    def test_daemon_runtime_handler_facing_surface_excludes_old_action_names(self) -> None:
        for old_name in (
            "submit_turn",
            "interrupt_parent",
            "interrupt_and_submit_parent_prompt",
            "start_side_triage",
            "send_side_triage",
            "start_or_reuse_side_triage",
            "require_side_thread",
            "close_side_triage",
        ):
            self.assertFalse(hasattr(self.core.DaemonRuntime, old_name), old_name)


if __name__ == "__main__":
    unittest.main()
