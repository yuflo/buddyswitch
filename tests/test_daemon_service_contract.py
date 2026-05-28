#!/usr/bin/env python3
"""Tests for the daemon service handler contract and action gateway."""

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


class FakeActionClient:
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
        instance_root = Path(temp_root) / "instances" / "inst-dev-daemon"
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload: dict[str, Any] = {
            "instance_id": "inst-dev-daemon",
            "buddy": "dev",
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
            instance_id="inst-dev-daemon",
            main_thread_id="thr-main",
        )

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

    def test_dispatch_passes_context_state_actions_and_notification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            client = FakeActionClient()
            notification = self._completed()
            core = self.core

            class RecordingHandler:
                name = "recording"

                def __init__(self) -> None:
                    self.received: dict[str, object] = {}

                def handle_notification(
                    self,
                    context_arg: object,
                    state_arg: object,
                    actions_arg: object,
                    notification_arg: dict[str, object],
                ) -> object:
                    self.received = {
                        "context": context_arg,
                        "state": state_arg,
                        "actions": actions_arg,
                        "notification": notification_arg,
                    }
                    return core.HandlerResult.handled()

            handler = RecordingHandler()

            handled = self.core.dispatch_notification(context, state, client, notification, [handler])

            self.assertTrue(handled)
            self.assertIs(handler.received["context"], context)
            self.assertIs(handler.received["state"], state)
            self.assertIsInstance(handler.received["actions"], self.core.ActionGateway)
            self.assertEqual(handler.received["notification"], notification)

    def test_dispatch_records_declared_failure_under_handler_state_and_continues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            client = FakeActionClient()
            notification = self._completed()
            calls: list[str] = []
            core = self.core

            class FailingHandler:
                name = "first"

                def handle_notification(self, *_args: object) -> object:
                    calls.append(self.name)
                    return core.HandlerResult.failed("declared failure")

            class LaterHandler:
                name = "second"

                def handle_notification(self, *_args: object) -> object:
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
            client = FakeActionClient()
            notification = self._completed()
            calls: list[str] = []
            core = self.core

            class ExplodingHandler:
                name = "exploder"

                def handle_notification(self, *_args: object) -> object:
                    calls.append(self.name)
                    raise RuntimeError("handler exploded")

            class LaterHandler:
                name = "second"

                def handle_notification(self, *_args: object) -> object:
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

    def test_action_gateway_turn_start_uses_main_thread_permissions_and_text_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            client = FakeActionClient(result={"turn": {"id": "turn-daemon-1"}})
            actions = self.core.ActionGateway(context=context, state=state, client=client)

            turn_id = actions.turn_start("daemon prompt", handler_name="fake", origin_turn_id="turn-user-1")

            self.assertEqual(turn_id, "turn-daemon-1")
            self.assertEqual([request["method"] for request in client.requests], ["turn/start"])
            params = client.requests[0]["params"]
            assert isinstance(params, dict)
            self.assertEqual(params["threadId"], "thr-main")
            self.assertEqual(params["permissions"], "buddyswitch-runtime")
            self.assertEqual(params["input"], self.core.app_server.text_input_payload("daemon prompt"))

    def test_action_gateway_records_daemon_origin_and_handler_action_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            client = FakeActionClient(result={"turn": {"id": "turn-daemon-1"}})
            actions = self.core.ActionGateway(context=context, state=state, client=client)

            actions.turn_start("daemon prompt", handler_name="fake", origin_turn_id="turn-user-1")

            saved = json.loads(self.core.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertEqual(saved["daemon_origin_turn_ids"], ["turn-daemon-1"])
            self.assertEqual(saved["handlers"]["fake"]["last_origin_turn_id"], "turn-user-1")
            self.assertEqual(saved["handlers"]["fake"]["last_action_turn_id"], "turn-daemon-1")
            self.assertIsNone(saved["handlers"]["fake"]["last_error"])

    def test_action_gateway_raises_protocol_error_when_turn_id_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            client = FakeActionClient(result={"turn": {}})
            actions = self.core.ActionGateway(context=context, state=state, client=client)

            with self.assertRaises(self.core.app_server.AppServerProtocolError):
                actions.turn_start("daemon prompt", handler_name="fake", origin_turn_id="turn-user-1")

            self.assertEqual(state.payload["daemon_origin_turn_ids"], [])
            self.assertEqual([request["method"] for request in client.requests], ["turn/start"])

    def test_action_gateway_exposes_request_error_without_retry_or_steer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            state = self._state(instance["instance_root"])
            client = FakeActionClient(
                error=self.core.app_server.AppServerRequestError("turn/start", -32000, "active thread"),
            )
            actions = self.core.ActionGateway(context=context, state=state, client=client)

            with self.assertRaises(self.core.app_server.AppServerRequestError):
                actions.turn_start("daemon prompt", handler_name="fake", origin_turn_id="turn-user-1")

            self.assertEqual([request["method"] for request in client.requests], ["turn/start"])
            self.assertNotIn("turn/steer", [request["method"] for request in client.requests])


if __name__ == "__main__":
    unittest.main()
