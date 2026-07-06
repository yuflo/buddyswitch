#!/usr/bin/env python3
"""Tests for instance daemon signal mailbox delivery."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import threading
import unittest
from itertools import count
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MAILBOX_PATH = ROOT / "tools" / "launcher" / "daemon_mailbox.py"
CENTRAL_CORE_PATH = ROOT / "tools" / "launcher" / "central_daemon_core.py"
DAEMON_CLIENT_PATH = ROOT / "scripts" / "env" / "tool_runtime" / "daemon_client.py"
DAEMON_CORE_PATH = ROOT / "tools" / "launcher" / "daemon_core.py"
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


class RecordingTriggerDispatcher:
    def __init__(self, result: dict[str, Any] | None = None) -> None:
        self.result = result or {
            "accepted": True,
            "handled_count": 1,
            "matched_count": 1,
            "handling_status": "handled",
        }
        self.triggers: list[Any] = []

    def __call__(self, trigger: Any) -> dict[str, Any]:
        self.triggers.append(trigger)
        return dict(self.result)


class DaemonMailboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mailbox = load_module(MAILBOX_PATH)
        self.central = load_module(CENTRAL_CORE_PATH)
        self.client = load_module(DAEMON_CLIENT_PATH)
        self.core = load_module(DAEMON_CORE_PATH)

    def _signal(self, *, target_role: str = "dev", target_instance: str = "act-dev-daemon") -> dict[str, Any]:
        return self.mailbox.daemon_signal_envelope(
            signal_id="sig-daemon-mailbox",
            signal_type="example.ready",
            source_identity_id="act-pm-daemon",
            source_role_id="pm",
            target_identity_id=target_instance,
            target_role_id=target_role,
            payload={"message_id": "msg-daemon-mailbox"},
            created_at="2026-05-30T00:00:00Z",
        )

    def test_daemon_signal_envelope_is_generic_and_payload_transparent(self) -> None:
        signal = self._signal()

        self.assertEqual(signal["signal_id"], "sig-daemon-mailbox")
        self.assertEqual(signal["type"], "example.ready")
        self.assertEqual(signal["payload"], {"message_id": "msg-daemon-mailbox"})
        self.assertEqual(signal["source_identity_id"], "act-pm-daemon")
        self.assertEqual(signal["source_role_id"], "pm")
        self.assertEqual(signal["target_identity_id"], "act-dev-daemon")
        self.assertEqual(signal["target_role_id"], "dev")
        for forbidden in ("message_id", "from_actor_address", "to_actor_address", "source_actor_address", "target_actor_address", "from_role", "to_role", "content", "message"):
            self.assertNotIn(forbidden, signal)

    def test_validate_daemon_signal_rejects_legacy_message_event_shape(self) -> None:
        retired_from_field = "from_" + "actor_address"
        retired_to_field = "to_" + "actor_address"
        legacy_event = {
            "type": "example.ready",
            "message_id": "msg-daemon-mailbox",
            retired_from_field: {"role_id": "pm", "actor_id": "act-pm-daemon"},
            retired_to_field: {"role_id": "dev", "actor_id": "act-dev-daemon"},
        }

        with self.assertRaisesRegex(ValueError, "DaemonSignalEnvelope"):
            self.mailbox.validate_daemon_signal(legacy_event)

    def test_validate_daemon_signal_allows_unknown_signal_type_with_object_payload(self) -> None:
        signal = self.mailbox.daemon_signal_envelope(
            signal_id="sig-task-updated",
            signal_type="task.updated",
            source_identity_id="act-pm-daemon",
            source_role_id="pm",
            target_identity_id="act-dev-daemon",
            target_role_id="dev",
            payload={"task_id": "task-1", "state": "ready"},
            created_at="2026-05-30T00:00:00Z",
        )

        self.assertEqual(self.mailbox.validate_daemon_signal(signal), signal)

    def test_signal_deliver_writes_to_mailbox_socket(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = Path(temp_root) / "mailbox.sock"
            dispatcher = RecordingTriggerDispatcher()
            server = self.mailbox.DaemonMailboxServer(
                socket_path=socket_path,
                local_identity_id="act-dev-daemon",
                local_role_id="dev",
                handlers=[],
                trigger_dispatcher=dispatcher,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.close)

            paths = self.central.central_daemon_paths(Path(temp_root) / "shared")
            service = self.central.CentralDaemonService(paths=paths, now=lambda: "2026-05-30T00:00:00Z")
            service.handle(
                "daemon.register",
                {
                    "identity_id": "act-dev-daemon",
                    "role_id": "dev",
                    "endpoint": {"kind": "daemon_mailbox_socket", "socket_path": str(socket_path)},
                },
            )

            result = service.handle("signal.deliver", {"signal": self._signal()})
            server.close()
            thread.join(timeout=2)

            self.assertEqual(result["delivery_status"], "delivered")
            self.assertEqual(result["handling_status"], "handled")
            self.assertEqual(len(dispatcher.triggers), 1)
            self.assertEqual(dispatcher.triggers[0].type, "example.ready")
            self.assertEqual(dispatcher.triggers[0].payload, {"message_id": "msg-daemon-mailbox"})
            self.assertFalse(thread.is_alive())

    def test_signal_deliver_reports_delivery_failed_for_unreachable_mailbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            paths = self.central.central_daemon_paths(Path(temp_root) / "shared")
            service = self.central.CentralDaemonService(paths=paths, now=lambda: "2026-05-30T00:00:00Z")
            service.handle(
                "daemon.register",
                {
                    "identity_id": "act-dev-daemon",
                    "role_id": "dev",
                    "endpoint": {"kind": "daemon_mailbox_socket", "socket_path": str(Path(temp_root) / "missing.sock")},
                },
            )

            result = service.handle("signal.deliver", {"signal": self._signal()})

            self.assertEqual(result["delivery_status"], "delivery_failed")
            registry = service.handle("daemon.registry", {})
            self.assertEqual(registry["actors"][0]["status"], "online")

    def test_signal_deliver_reports_target_not_online(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            paths = self.central.central_daemon_paths(Path(temp_root) / "shared")
            service = self.central.CentralDaemonService(paths=paths, now=lambda: "2026-05-30T00:00:00Z")
            service.handle(
                "daemon.register",
                {
                    "identity_id": "act-dev-daemon",
                    "role_id": "dev",
                    "endpoint": {"kind": "daemon_mailbox_socket", "socket_path": str(Path(temp_root) / "missing.sock")},
                },
            )
            service.handle("daemon.unregister", {"identity_id": "act-dev-daemon", "role_id": "dev"})

            result = service.handle("signal.deliver", {"signal": self._signal()})

            self.assertEqual(result["delivery_status"], "target_not_online")
            self.assertEqual(result["handling_status"], "ignored")

    def test_event_deliver_rejects_legacy_message_event_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            paths = self.central.central_daemon_paths(Path(temp_root) / "shared")
            service = self.central.CentralDaemonService(paths=paths, now=lambda: "2026-05-30T00:00:00Z")
            retired_from_field = "from_" + "actor_address"
            retired_to_field = "to_" + "actor_address"
            legacy_event = {
                "type": "example.ready",
                "message_id": "msg-daemon-mailbox",
                retired_from_field: {"role_id": "pm", "actor_id": "act-pm-daemon"},
                retired_to_field: {"role_id": "dev", "actor_id": "act-dev-daemon"},
            }

            result = service.handle("event.deliver", {"event": legacy_event})

            self.assertEqual(result["delivery_status"], "invalid_signal")
            self.assertEqual(result["handling_status"], "ignored")

    def test_mailbox_rejects_signal_for_other_actor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = Path(temp_root) / "mailbox.sock"
            server = self.mailbox.DaemonMailboxServer(
                socket_path=socket_path,
                local_identity_id="act-design-daemon",
                local_role_id="design",
                handlers=[],
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.close)

            result = self.client.request_mailbox("mailbox.deliver", {"signal": self._signal()}, socket_path=socket_path)
            server.close()
            thread.join(timeout=2)

            self.assertFalse(result["ok"], msg=result)
            self.assertEqual(result["error"]["code"], "wrong_target_actor")

    def test_mailbox_reports_ignored_when_no_handler_handles_signal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = Path(temp_root) / "mailbox.sock"
            dispatcher = RecordingTriggerDispatcher(
                {
                    "accepted": True,
                    "handled_count": 0,
                    "matched_count": 0,
                    "handling_status": "ignored",
                }
            )
            server = self.mailbox.DaemonMailboxServer(
                socket_path=socket_path,
                local_identity_id="act-dev-daemon",
                local_role_id="dev",
                handlers=[],
                trigger_dispatcher=dispatcher,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.close)

            result = self.client.request_mailbox("mailbox.deliver", {"signal": self._signal()}, socket_path=socket_path)
            server.close()
            thread.join(timeout=2)

            self.assertTrue(result["ok"], msg=result)
            self.assertEqual(result["result"]["handling_status"], "ignored")
            self.assertEqual(result["result"]["handled_count"], 0)
            self.assertEqual(len(dispatcher.triggers), 1)

    def test_mailbox_reports_failed_when_handler_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = Path(temp_root) / "mailbox.sock"
            dispatcher = RecordingTriggerDispatcher(
                {
                    "accepted": True,
                    "handled_count": 0,
                    "matched_count": 1,
                    "handling_status": "failed",
                    "handling_error": "handler failed intentionally",
                }
            )
            server = self.mailbox.DaemonMailboxServer(
                socket_path=socket_path,
                local_identity_id="act-dev-daemon",
                local_role_id="dev",
                handlers=[],
                trigger_dispatcher=dispatcher,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.close)

            result = self.client.request_mailbox("mailbox.deliver", {"signal": self._signal()}, socket_path=socket_path)
            server.close()
            thread.join(timeout=2)

            self.assertTrue(result["ok"], msg=result)
            self.assertEqual(result["result"]["handling_status"], "failed")
            self.assertIn("handler failed intentionally", result["result"]["handling_error"])

    def _local_trigger_params(self) -> dict[str, Any]:
        return {
            "identity_id": "act-dev-daemon",
            "role_id": "dev",
            "type": "example.attention_needed",
            "origin_id": "origin-1",
            "correlation_id": "corr-1",
            "payload": {
                "example_id": "example-1",
                "priority": "high",
            },
            "source_context": {
                "sender": "local-side",
                "thread_id": "thr-side-1",
            },
        }

    def test_parent_required_business_method_is_removed(self) -> None:
        server = self.mailbox.DaemonMailboxServer(
            socket_path=Path("/tmp/not-used.sock"),
            local_identity_id="act-dev-daemon",
            local_role_id="dev",
            handlers=[],
        )

        response = server.dispatch(
            {
                "protocol": self.client.MAILBOX_PROTOCOL,
                "request_id": "req-parent-required",
                "method": "mailbox.parent_required",
                "params": self._local_trigger_params(),
            }
        )

        self.assertFalse(response["ok"], msg=response)
        self.assertEqual(response["error"]["code"], "mailbox_unknown_method")

    def test_local_trigger_dispatches_generic_daemon_trigger(self) -> None:
        dispatcher = RecordingTriggerDispatcher()
        server = self.mailbox.DaemonMailboxServer(
            socket_path=Path("/tmp/not-used.sock"),
            local_identity_id="act-dev-daemon",
            local_role_id="dev",
            handlers=[],
            trigger_dispatcher=dispatcher,
        )

        response = server.dispatch(
            {
                "protocol": self.client.MAILBOX_PROTOCOL,
                "request_id": "req-local-trigger",
                "method": "mailbox.local_trigger",
                "params": self._local_trigger_params(),
            }
        )

        self.assertTrue(response["ok"], msg=response)
        self.assertEqual(response["result"]["handling_status"], "handled")
        self.assertEqual(len(dispatcher.triggers), 1)
        trigger = dispatcher.triggers[0]
        self.assertEqual(trigger.source, "mailbox_local_trigger")
        self.assertEqual(trigger.type, "example.attention_needed")
        self.assertEqual(trigger.origin_id, "origin-1")
        self.assertEqual(trigger.correlation_id, "corr-1")
        self.assertEqual(trigger.payload, {"example_id": "example-1", "priority": "high"})
        self.assertEqual(trigger.source_context, {"sender": "local-side", "thread_id": "thr-side-1"})

    def test_local_trigger_defaults_source_context_and_does_not_require_business_fields(self) -> None:
        dispatcher = RecordingTriggerDispatcher()
        server = self.mailbox.DaemonMailboxServer(
            socket_path=Path("/tmp/not-used.sock"),
            local_identity_id="act-dev-daemon",
            local_role_id="dev",
            handlers=[],
            trigger_dispatcher=dispatcher,
        )
        params = {
            "identity_id": "act-dev-daemon",
            "role_id": "dev",
            "type": "example.attention_needed",
            "payload": {"note": "generic local trigger"},
        }

        response = server.dispatch(
            {
                "protocol": self.client.MAILBOX_PROTOCOL,
                "request_id": "req-local-trigger",
                "method": "mailbox.local_trigger",
                "params": params,
            }
        )

        self.assertTrue(response["ok"], msg=response)
        trigger = dispatcher.triggers[0]
        self.assertEqual(trigger.origin_id, None)
        self.assertEqual(trigger.correlation_id, None)
        self.assertEqual(trigger.payload, {"note": "generic local trigger"})
        self.assertEqual(trigger.source_context, {})

    def test_task_sys_mailbox_methods_dispatch_to_concrete_task_sys_handler(self) -> None:
        calls: list[dict[str, Any]] = []

        def task_sys_dispatcher(action: str, params: dict[str, Any]) -> dict[str, Any]:
            calls.append({"action": action, "params": params})
            if action == "execute_instruction":
                instruction = params["instruction"]
                return {"action": instruction["type"], "task_id": instruction["task_id"]}
            if action == "cleanup_side_lease":
                return {"action": "cleanup", "task_id": params["task_id"], "lease_unregistered": True}
            raise AssertionError(action)

        server = self.mailbox.DaemonMailboxServer(
            socket_path=Path("/tmp/not-used.sock"),
            local_identity_id="act-dev-daemon",
            local_role_id="dev",
            handlers=[],
            task_sys_dispatcher=task_sys_dispatcher,
        )
        instruction = {
            "type": "start_side",
            "task_id": "task-user-input-mailbox123",
            "actor_target": {"actor_id": "act-dev-daemon", "role_id": "dev"},
        }

        executed = server.dispatch(
            {
                "protocol": self.client.MAILBOX_PROTOCOL,
                "request_id": "req-task-sys-execute",
                "method": "mailbox.task_sys.execute_instruction",
                "params": {"instruction": instruction},
            }
        )
        cleaned = server.dispatch(
            {
                "protocol": self.client.MAILBOX_PROTOCOL,
                "request_id": "req-task-sys-cleanup",
                "method": "mailbox.task_sys.cleanup_side_lease",
                "params": {"task_id": "task-user-input-mailbox123"},
            }
        )

        self.assertTrue(executed["ok"], msg=executed)
        self.assertEqual(executed["result"], {"action": "start_side", "task_id": "task-user-input-mailbox123"})
        self.assertTrue(cleaned["ok"], msg=cleaned)
        self.assertEqual(cleaned["result"]["lease_unregistered"], True)
        self.assertEqual([call["action"] for call in calls], ["execute_instruction", "cleanup_side_lease"])
        self.assertEqual(calls[0]["params"], {"instruction": instruction})
        self.assertEqual(calls[1]["params"], {"task_id": "task-user-input-mailbox123"})

    def test_daemon_client_task_sys_helpers_call_mailbox_methods(self) -> None:
        calls: list[dict[str, Any]] = []
        original_request_mailbox = self.client.request_mailbox

        def fake_request_mailbox(method: str, params: dict[str, Any], *, socket_path: Path) -> dict[str, Any]:
            calls.append({"method": method, "params": params, "socket_path": socket_path})
            return {
                "protocol": self.client.MAILBOX_PROTOCOL,
                "request_id": "req-test",
                "ok": True,
                "result": {"ok": True, **params},
            }

        self.addCleanup(setattr, self.client, "request_mailbox", original_request_mailbox)
        self.client.request_mailbox = fake_request_mailbox
        instance_root = Path("/tmp/instance-task-sys-mailbox")
        instruction = {
            "type": "start_side",
            "task_id": "task-user-input-mailbox123",
            "actor_target": {"actor_id": "act-dev-daemon", "role_id": "dev"},
        }

        executed = self.client.execute_task_sys_instruction(instance_root=instance_root, instruction=instruction)
        cleaned = self.client.cleanup_task_sys_side_lease(instance_root=instance_root, task_id="task-user-input-mailbox123")

        self.assertEqual(executed["instruction"], instruction)
        self.assertEqual(cleaned["task_id"], "task-user-input-mailbox123")
        self.assertEqual(
            [call["method"] for call in calls],
            ["mailbox.task_sys.execute_instruction", "mailbox.task_sys.cleanup_side_lease"],
        )
        self.assertEqual(
            [call["socket_path"] for call in calls],
            [self.client.mailbox_socket_path_for_instance_root(instance_root)] * 2,
        )

    def test_local_trigger_rejects_wrong_actor_and_invalid_generic_shape_before_dispatch(self) -> None:
        dispatcher = RecordingTriggerDispatcher()
        server = self.mailbox.DaemonMailboxServer(
            socket_path=Path("/tmp/not-used.sock"),
            local_identity_id="act-dev-daemon",
            local_role_id="dev",
            handlers=[],
            trigger_dispatcher=dispatcher,
        )

        def dispatch(params: dict[str, Any]) -> dict[str, Any]:
            return server.dispatch(
                {
                    "protocol": self.client.MAILBOX_PROTOCOL,
                    "request_id": "req-local-trigger",
                    "method": "mailbox.local_trigger",
                    "params": params,
                }
            )

        base = self._local_trigger_params()
        wrong_actor = dict(base)
        wrong_actor["identity_id"] = "act-pm-daemon"
        wrong_actor["role_id"] = "pm"
        empty_type = dict(base)
        empty_type["type"] = " "
        non_object_payload = dict(base)
        non_object_payload["payload"] = ["not", "object"]
        non_object_source_context = dict(base)
        non_object_source_context["source_context"] = "not-object"
        empty_origin = dict(base)
        empty_origin["origin_id"] = ""
        empty_correlation = dict(base)
        empty_correlation["correlation_id"] = ""

        self.assertEqual(dispatch(wrong_actor)["error"]["code"], "wrong_target_actor")
        for params in (empty_type, non_object_payload, non_object_source_context, empty_origin, empty_correlation):
            response = dispatch(params)
            self.assertFalse(response["ok"], msg=response)
            self.assertEqual(response["error"]["code"], "invalid_local_trigger")

        self.assertEqual(dispatcher.triggers, [])

    def test_mailbox_schedule_trigger_registers_instance_local_schedule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-daemon"
            instance_root.mkdir(parents=True, exist_ok=True)
            state = self.core.DaemonState.load(
                instance_root=instance_root,
                actor_id="act-dev-daemon",
                main_thread_id="thr-main",
            )
            server = self.mailbox.DaemonMailboxServer(
                socket_path=Path("/tmp/not-used.sock"),
                local_identity_id="act-dev-daemon",
                local_role_id="dev",
                handlers=[],
                state=state,
                now=lambda: "2026-06-24T00:00:00Z",
            )

            response = server.dispatch(
                {
                    "protocol": self.client.MAILBOX_PROTOCOL,
                    "request_id": "req-schedule",
                    "method": "mailbox.schedule_trigger",
                    "params": {
                        "delay_seconds": 600,
                        "type": "browser.page.expired",
                        "payload": {"target_id": "target-ttl-1"},
                        "source_context": {"owner": "browser"},
                    },
                }
            )

            self.assertTrue(response["ok"], msg=response)
            schedule = response["result"]["schedule"]
            self.assertEqual(schedule["schedule_id"], "schedule-1")
            self.assertEqual(schedule["type"], "browser.page.expired")
            self.assertEqual(schedule["status"], "pending")
            self.assertEqual(schedule["due_at"], "2026-06-24T00:10:00Z")
            saved = json.loads(self.core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["scheduled_trigger_ids"], ["schedule-1"])
            self.assertEqual(saved["scheduled_triggers"]["schedule-1"]["payload"], {"target_id": "target-ttl-1"})

    def test_mailbox_schedule_trigger_upserts_by_schedule_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-daemon"
            instance_root.mkdir(parents=True, exist_ok=True)
            state = self.core.DaemonState.load(
                instance_root=instance_root,
                actor_id="act-dev-daemon",
                main_thread_id="thr-main",
            )
            current_now = {"value": "2026-06-24T00:00:00Z"}
            server = self.mailbox.DaemonMailboxServer(
                socket_path=Path("/tmp/not-used.sock"),
                local_identity_id="act-dev-daemon",
                local_role_id="dev",
                handlers=[],
                state=state,
                now=lambda: current_now["value"],
            )

            request = {
                "protocol": self.client.MAILBOX_PROTOCOL,
                "request_id": "req-schedule",
                "method": "mailbox.schedule_trigger",
                "params": {
                    "delay_seconds": 300,
                    "type": "browser.page.expired",
                    "payload": {"target_id": "target-1"},
                    "source_context": {"owner": "browser", "attempt": 1},
                    "schedule_key": "browser.page.idle:target-1",
                },
            }
            first = server.dispatch(request)
            current_now["value"] = "2026-06-24T00:04:00Z"
            request["params"]["payload"] = {"target_id": "target-1", "refreshed": True}
            request["params"]["source_context"] = {"owner": "browser", "attempt": 2}
            second = server.dispatch(request)

            self.assertTrue(first["ok"], msg=first)
            self.assertTrue(second["ok"], msg=second)
            self.assertEqual(first["result"]["schedule"]["schedule_id"], "schedule-1")
            schedule = second["result"]["schedule"]
            self.assertEqual(schedule["schedule_id"], "schedule-1")
            self.assertEqual(schedule["schedule_key"], "browser.page.idle:target-1")
            self.assertEqual(schedule["due_at"], "2026-06-24T00:09:00Z")
            saved = json.loads(self.core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["scheduled_trigger_ids"], ["schedule-1"])
            self.assertEqual(saved["scheduled_triggers"]["schedule-1"]["payload"], {"target_id": "target-1", "refreshed": True})

    def test_mailbox_schedule_trigger_rejects_invalid_payload_without_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-daemon"
            instance_root.mkdir(parents=True, exist_ok=True)
            state = self.core.DaemonState.load(
                instance_root=instance_root,
                actor_id="act-dev-daemon",
                main_thread_id="thr-main",
            )
            server = self.mailbox.DaemonMailboxServer(
                socket_path=Path("/tmp/not-used.sock"),
                local_identity_id="act-dev-daemon",
                local_role_id="dev",
                handlers=[],
                state=state,
                now=lambda: "2026-06-24T00:00:00Z",
            )

            for params in (
                {"delay_seconds": -1, "type": "browser.page.expired", "payload": {}},
                {"delay_seconds": 600, "type": " ", "payload": {}},
                {"delay_seconds": 600, "type": "browser.page.expired", "payload": []},
                {"delay_seconds": 600, "type": "browser.page.expired", "payload": {}, "source_context": []},
            ):
                with self.subTest(params=params):
                    response = server.dispatch(
                        {
                            "protocol": self.client.MAILBOX_PROTOCOL,
                            "request_id": "req-schedule",
                            "method": "mailbox.schedule_trigger",
                            "params": params,
                        }
                    )

                    self.assertFalse(response["ok"], msg=response)
                    self.assertEqual(response["error"]["code"], "invalid_schedule_trigger")

            self.assertFalse(self.core.daemon_state_file(instance_root).exists())

    def test_daemon_client_schedule_trigger_posts_to_instance_mailbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-daemon"
            instance_root.mkdir(parents=True, exist_ok=True)
            socket_path = self.client.mailbox_socket_path_for_instance_root(instance_root)
            state = self.core.DaemonState.load(
                instance_root=instance_root,
                actor_id="act-dev-daemon",
                main_thread_id="thr-main",
            )
            server = self.mailbox.DaemonMailboxServer(
                socket_path=socket_path,
                local_identity_id="act-dev-daemon",
                local_role_id="dev",
                handlers=[],
                state=state,
                now=lambda: "2026-06-24T00:00:00Z",
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.close)

            result = self.client.schedule_trigger(
                instance_root=instance_root,
                delay_seconds=600,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-ttl-1"},
                source_context={"owner": "browser"},
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(result["schedule"]["schedule_id"], "schedule-1")
            saved = json.loads(self.core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["scheduled_triggers"]["schedule-1"]["payload"], {"target_id": "target-ttl-1"})
            self.assertFalse(thread.is_alive())

    def test_daemon_client_schedule_trigger_posts_optional_schedule_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-daemon"
            instance_root.mkdir(parents=True, exist_ok=True)
            socket_path = self.client.mailbox_socket_path_for_instance_root(instance_root)
            state = self.core.DaemonState.load(
                instance_root=instance_root,
                actor_id="act-dev-daemon",
                main_thread_id="thr-main",
            )
            server = self.mailbox.DaemonMailboxServer(
                socket_path=socket_path,
                local_identity_id="act-dev-daemon",
                local_role_id="dev",
                handlers=[],
                state=state,
                now=lambda: "2026-06-24T00:00:00Z",
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.close)

            result = self.client.schedule_trigger(
                instance_root=instance_root,
                delay_seconds=300,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-1"},
                source_context={"owner": "browser"},
                schedule_key="browser.page.idle:target-1",
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(result["schedule"]["schedule_id"], "schedule-1")
            self.assertEqual(result["schedule"]["schedule_key"], "browser.page.idle:target-1")
            saved = json.loads(self.core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["scheduled_triggers"]["schedule-1"]["schedule_key"], "browser.page.idle:target-1")
            self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
