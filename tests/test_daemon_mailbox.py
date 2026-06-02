#!/usr/bin/env python3
"""Tests for instance daemon signal mailbox delivery."""

from __future__ import annotations

import importlib.util
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


class RecordingSignalHandler:
    name = "recording"

    def __init__(self) -> None:
        self.signals: list[dict[str, Any]] = []

    def handles(self, signal: dict[str, Any]) -> bool:
        return signal.get("type") == "message.available"

    def handle_signal(self, _context: object, _state: object, _actions: object, signal: dict[str, Any]) -> object:
        self.signals.append(signal)
        return {"status": "handled"}


class IgnoringSignalHandler:
    name = "ignoring"

    def handles(self, signal: dict[str, Any]) -> bool:
        return False

    def handle_signal(self, _context: object, _state: object, _actions: object, signal: dict[str, Any]) -> object:
        raise AssertionError("ignored handler must not be called")


class FailedSignalHandler:
    name = "failed"

    def handles(self, signal: dict[str, Any]) -> bool:
        return True

    def handle_signal(self, _context: object, _state: object, _actions: object, signal: dict[str, Any]) -> object:
        return {"status": "failed", "message": "handler failed intentionally"}


class ParentRequiredContext:
    main_thread_id = "thr-main"


class RecordingParentRequiredHandler:
    name = "parent_required"

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def handles(self, _signal: dict[str, Any]) -> bool:
        return False

    def handle_parent_required(
        self,
        _context: object,
        _state: object,
        _actions: object,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        self.requests.append(request)
        return {
            "status": "handled",
            "side_thread_id": request["side_thread_id"],
            "interrupted_turn_id": "turn-main-1",
            "turn_id": "turn-parent-message",
        }


class FailedParentRequiredHandler:
    name = "failed_parent_required"

    def handle_parent_required(self, *_args: object) -> dict[str, Any]:
        return {"status": "failed", "message": "side thread is not registered"}


class DaemonMailboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mailbox = load_module(MAILBOX_PATH)
        self.central = load_module(CENTRAL_CORE_PATH)
        self.client = load_module(DAEMON_CLIENT_PATH)

    def _signal(self, *, target_role: str = "dev", target_instance: str = "act-dev-daemon") -> dict[str, Any]:
        return self.mailbox.daemon_signal_envelope(
            signal_id="sig-daemon-mailbox",
            signal_type="message.available",
            source_actor_address={"role_id": "pm", "actor_id": "act-pm-daemon"},
            target_actor_address={"role_id": target_role, "actor_id": target_instance},
            payload={"message_id": "msg-daemon-mailbox"},
            created_at="2026-05-30T00:00:00Z",
        )

    def test_daemon_signal_envelope_is_generic_and_payload_transparent(self) -> None:
        signal = self._signal()

        self.assertEqual(signal["signal_id"], "sig-daemon-mailbox")
        self.assertEqual(signal["type"], "message.available")
        self.assertEqual(signal["payload"], {"message_id": "msg-daemon-mailbox"})
        self.assertEqual(signal["source_actor_address"], {"role_id": "pm", "actor_id": "act-pm-daemon"})
        self.assertEqual(signal["target_actor_address"], {"role_id": "dev", "actor_id": "act-dev-daemon"})
        for forbidden in ("message_id", "from_actor_address", "to_actor_address", "from_role", "to_role", "content", "message"):
            self.assertNotIn(forbidden, signal)

    def test_validate_daemon_signal_rejects_legacy_message_event_shape(self) -> None:
        legacy_event = {
            "type": "message.available",
            "message_id": "msg-daemon-mailbox",
            "from_actor_address": {"role_id": "pm", "actor_id": "act-pm-daemon"},
            "to_actor_address": {"role_id": "dev", "actor_id": "act-dev-daemon"},
        }

        with self.assertRaisesRegex(ValueError, "DaemonSignalEnvelope"):
            self.mailbox.validate_daemon_signal(legacy_event)

    def test_validate_daemon_signal_allows_unknown_signal_type_with_object_payload(self) -> None:
        signal = self.mailbox.daemon_signal_envelope(
            signal_id="sig-task-updated",
            signal_type="task.updated",
            source_actor_address={"role_id": "pm", "actor_id": "act-pm-daemon"},
            target_actor_address={"role_id": "dev", "actor_id": "act-dev-daemon"},
            payload={"task_id": "task-1", "state": "ready"},
            created_at="2026-05-30T00:00:00Z",
        )

        self.assertEqual(self.mailbox.validate_daemon_signal(signal), signal)

    def test_signal_deliver_writes_to_mailbox_socket(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = Path(temp_root) / "mailbox.sock"
            handler = RecordingSignalHandler()
            server = self.mailbox.DaemonMailboxServer(
                socket_path=socket_path,
                local_actor_address={"role_id": "dev", "actor_id": "act-dev-daemon"},
                handlers=[handler],
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.close)

            paths = self.central.central_daemon_paths(Path(temp_root) / "shared")
            service = self.central.CentralDaemonService(paths=paths, now=lambda: "2026-05-30T00:00:00Z")
            service.handle(
                "daemon.register",
                {
                    "actor_address": {"role_id": "dev", "actor_id": "act-dev-daemon"},
                    "endpoint": {"kind": "daemon_mailbox_socket", "socket_path": str(socket_path)},
                },
            )

            result = service.handle("signal.deliver", {"signal": self._signal()})
            server.close()
            thread.join(timeout=2)

            self.assertEqual(result["delivery_status"], "delivered")
            self.assertEqual(result["handling_status"], "handled")
            self.assertEqual(handler.signals, [self._signal()])
            self.assertFalse(thread.is_alive())

    def test_signal_deliver_reports_delivery_failed_for_unreachable_mailbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            paths = self.central.central_daemon_paths(Path(temp_root) / "shared")
            service = self.central.CentralDaemonService(paths=paths, now=lambda: "2026-05-30T00:00:00Z")
            service.handle(
                "daemon.register",
                {
                    "actor_address": {"role_id": "dev", "actor_id": "act-dev-daemon"},
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
                    "actor_address": {"role_id": "dev", "actor_id": "act-dev-daemon"},
                    "endpoint": {"kind": "daemon_mailbox_socket", "socket_path": str(Path(temp_root) / "missing.sock")},
                },
            )
            service.handle("daemon.unregister", {"actor_address": {"role_id": "dev", "actor_id": "act-dev-daemon"}})

            result = service.handle("signal.deliver", {"signal": self._signal()})

            self.assertEqual(result["delivery_status"], "target_not_online")
            self.assertEqual(result["handling_status"], "ignored")

    def test_event_deliver_rejects_legacy_message_event_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            paths = self.central.central_daemon_paths(Path(temp_root) / "shared")
            service = self.central.CentralDaemonService(paths=paths, now=lambda: "2026-05-30T00:00:00Z")
            legacy_event = {
                "type": "message.available",
                "message_id": "msg-daemon-mailbox",
                "from_actor_address": {"role_id": "pm", "actor_id": "act-pm-daemon"},
                "to_actor_address": {"role_id": "dev", "actor_id": "act-dev-daemon"},
            }

            result = service.handle("event.deliver", {"event": legacy_event})

            self.assertEqual(result["delivery_status"], "invalid_signal")
            self.assertEqual(result["handling_status"], "ignored")

    def test_mailbox_rejects_signal_for_other_actor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = Path(temp_root) / "mailbox.sock"
            server = self.mailbox.DaemonMailboxServer(
                socket_path=socket_path,
                local_actor_address={"role_id": "design", "actor_id": "act-design-daemon"},
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
            server = self.mailbox.DaemonMailboxServer(
                socket_path=socket_path,
                local_actor_address={"role_id": "dev", "actor_id": "act-dev-daemon"},
                handlers=[IgnoringSignalHandler()],
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

    def test_mailbox_reports_failed_when_handler_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = Path(temp_root) / "mailbox.sock"
            server = self.mailbox.DaemonMailboxServer(
                socket_path=socket_path,
                local_actor_address={"role_id": "dev", "actor_id": "act-dev-daemon"},
                handlers=[FailedSignalHandler()],
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

    def test_parent_required_method_dispatches_to_typed_local_handler(self) -> None:
        handler = RecordingParentRequiredHandler()
        server = self.mailbox.DaemonMailboxServer(
            socket_path=Path("/tmp/not-used.sock"),
            local_actor_address={"role_id": "dev", "actor_id": "act-dev-daemon"},
            handlers=[handler],
            context=ParentRequiredContext(),
            actions_factory=lambda: object(),
        )
        request = {
            "protocol": self.client.MAILBOX_PROTOCOL,
            "request_id": "req-parent-required",
            "method": "mailbox.parent_required",
            "params": {
                "actor_address": {"role_id": "dev", "actor_id": "act-dev-daemon"},
                "parent_thread_id": "thr-main",
                "side_thread_id": "thr-side-1",
                "message_id": "msg-daemon-mailbox",
                "reason": "parent is required",
            },
        }

        response = server.dispatch(request)

        self.assertTrue(response["ok"], msg=response)
        result = response["result"]
        self.assertEqual(result["handling_status"], "handled")
        self.assertEqual(result["side_thread_id"], "thr-side-1")
        self.assertEqual(result["interrupted_turn_id"], "turn-main-1")
        self.assertEqual(result["turn_id"], "turn-parent-message")
        self.assertEqual(len(handler.requests), 1)
        self.assertEqual(handler.requests[0]["message_id"], "msg-daemon-mailbox")

    def test_parent_required_method_rejects_wrong_actor_wrong_parent_and_parent_as_side(self) -> None:
        server = self.mailbox.DaemonMailboxServer(
            socket_path=Path("/tmp/not-used.sock"),
            local_actor_address={"role_id": "dev", "actor_id": "act-dev-daemon"},
            handlers=[RecordingParentRequiredHandler()],
            context=ParentRequiredContext(),
            actions_factory=lambda: object(),
        )

        def dispatch(params: dict[str, Any]) -> dict[str, Any]:
            return server.dispatch(
                {
                    "protocol": self.client.MAILBOX_PROTOCOL,
                    "request_id": "req-parent-required",
                    "method": "mailbox.parent_required",
                    "params": params,
                }
            )

        base = {
            "actor_address": {"role_id": "dev", "actor_id": "act-dev-daemon"},
            "parent_thread_id": "thr-main",
            "side_thread_id": "thr-side-1",
            "message_id": "msg-daemon-mailbox",
            "reason": "parent is required",
        }
        wrong_actor = dict(base)
        wrong_actor["actor_address"] = {"role_id": "pm", "actor_id": "act-pm-daemon"}
        wrong_parent = dict(base)
        wrong_parent["parent_thread_id"] = "thr-other"
        parent_as_side = dict(base)
        parent_as_side["side_thread_id"] = "thr-main"

        self.assertEqual(dispatch(wrong_actor)["error"]["code"], "wrong_target_actor")
        self.assertEqual(dispatch(wrong_parent)["error"]["code"], "invalid_parent_required")
        self.assertEqual(dispatch(parent_as_side)["error"]["code"], "invalid_parent_required")

    def test_parent_required_method_reports_handler_failure_for_unknown_side(self) -> None:
        server = self.mailbox.DaemonMailboxServer(
            socket_path=Path("/tmp/not-used.sock"),
            local_actor_address={"role_id": "dev", "actor_id": "act-dev-daemon"},
            handlers=[FailedParentRequiredHandler()],
            context=ParentRequiredContext(),
            actions_factory=lambda: object(),
        )

        response = server.dispatch(
            {
                "protocol": self.client.MAILBOX_PROTOCOL,
                "request_id": "req-parent-required",
                "method": "mailbox.parent_required",
                "params": {
                    "actor_address": {"role_id": "dev", "actor_id": "act-dev-daemon"},
                    "parent_thread_id": "thr-main",
                    "side_thread_id": "thr-side-unknown",
                    "message_id": "msg-daemon-mailbox",
                    "reason": "parent is required",
                },
            }
        )

        self.assertTrue(response["ok"], msg=response)
        self.assertEqual(response["result"]["handling_status"], "failed")
        self.assertIn("not registered", response["result"]["handling_error"])


if __name__ == "__main__":
    unittest.main()
