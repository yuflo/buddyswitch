#!/usr/bin/env python3
"""Tests for instance daemon mailbox delivery."""

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


class RecordingMailboxHandler:
    name = "recording"

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def handle_mailbox_event(self, _context: object, _state: object, _actions: object, event: dict[str, Any]) -> object:
        self.events.append(event)
        return {"status": "handled"}


class DaemonMailboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mailbox = load_module(MAILBOX_PATH)
        self.central = load_module(CENTRAL_CORE_PATH)
        self.client = load_module(DAEMON_CLIENT_PATH)

    def _event(self) -> dict[str, Any]:
        return self.mailbox.message_available_event(
            message_id="msg-daemon-mailbox",
            from_actor_address={"buddy_id": "pm", "instance_id": "inst-pm-daemon"},
            to_actor_address={"buddy_id": "dev", "instance_id": "inst-dev-daemon"},
        )

    def test_message_available_event_is_reference_only(self) -> None:
        event = self._event()

        self.assertEqual(event["type"], "message.available")
        self.assertEqual(event["message_id"], "msg-daemon-mailbox")
        for forbidden in ("content", "message", "from_buddy", "to_buddy"):
            self.assertNotIn(forbidden, event)

    def test_event_deliver_rejects_message_body_fields(self) -> None:
        event = self._event()
        event["content"] = "body must stay in message store"

        with self.assertRaisesRegex(ValueError, "reference-only"):
            self.mailbox.validate_mailbox_event(event)

    def test_event_deliver_writes_to_mailbox_socket(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = Path(temp_root) / "mailbox.sock"
            handler = RecordingMailboxHandler()
            server = self.mailbox.DaemonMailboxServer(
                socket_path=socket_path,
                local_actor_address={"buddy_id": "dev", "instance_id": "inst-dev-daemon"},
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
                    "actor_address": {"buddy_id": "dev", "instance_id": "inst-dev-daemon"},
                    "endpoint": {"kind": "daemon_mailbox_socket", "socket_path": str(socket_path)},
                },
            )

            result = service.handle("event.deliver", {"event": self._event()})
            server.close()
            thread.join(timeout=2)

            self.assertEqual(result["delivery_status"], "delivered")
            self.assertEqual(handler.events, [self._event()])
            self.assertFalse(thread.is_alive())

    def test_event_deliver_reports_delivery_failed_for_unreachable_mailbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            paths = self.central.central_daemon_paths(Path(temp_root) / "shared")
            service = self.central.CentralDaemonService(paths=paths, now=lambda: "2026-05-30T00:00:00Z")
            service.handle(
                "daemon.register",
                {
                    "actor_address": {"buddy_id": "dev", "instance_id": "inst-dev-daemon"},
                    "endpoint": {"kind": "daemon_mailbox_socket", "socket_path": str(Path(temp_root) / "missing.sock")},
                },
            )

            result = service.handle("event.deliver", {"event": self._event()})

            self.assertEqual(result["delivery_status"], "delivery_failed")
            registry = service.handle("daemon.registry", {})
            self.assertEqual(registry["actors"][0]["status"], "online")

    def test_mailbox_rejects_event_for_other_actor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = Path(temp_root) / "mailbox.sock"
            server = self.mailbox.DaemonMailboxServer(
                socket_path=socket_path,
                local_actor_address={"buddy_id": "design", "instance_id": "inst-design-daemon"},
                handlers=[],
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.close)

            result = self.client.request_mailbox("mailbox.deliver", {"event": self._event()}, socket_path=socket_path)
            server.close()
            thread.join(timeout=2)

            self.assertFalse(result["ok"], msg=result)
            self.assertEqual(result["error"]["code"], "wrong_target_actor")


if __name__ == "__main__":
    unittest.main()
