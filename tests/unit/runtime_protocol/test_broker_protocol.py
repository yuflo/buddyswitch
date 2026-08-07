"""Tests for runtime broker request routing and identity checks."""

from __future__ import annotations

import json
import os
import signal
import sys
import tempfile
import unittest
import contextlib
import importlib
import shutil
import socket
import subprocess
import threading
import time
import uuid
from pathlib import Path
from unittest.mock import patch

from tests.support.paths import REPO_ROOT
from tests.support.cli import pid_alive, wait_until
from tests.support.fake_cdp import FakeCdpServer, write_fake_chrome

ROOT = REPO_ROOT

import buddyswitch.foundation.runtime_broker.broker as runtime_broker  # noqa: E402
import buddyswitch.foundation.runtime_broker.client as runtime_client  # noqa: E402
import buddyswitch.foundation.process_runtime.process_identity as process_identity  # noqa: E402

MANIFEST = ROOT / "src" / "buddyswitch" / "catalog" / "manifest.toml"
BROKER_V2_PROTOCOL = "buddyswitch-runtime-broker/v2"


def port_accepts(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.2)
        sock.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _require_module(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        raise AssertionError(f"missing required Runtime Broker V2 module: {name}") from exc


class RuntimeBrokerProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.protocol = _require_module("buddyswitch.foundation.runtime_broker.protocol")
        self.framing = _require_module("buddyswitch.foundation.process_runtime.json_framing")

    def _framed(self, payload: dict[str, object]) -> bytes:
        body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body

    def test_protocol_round_trips_content_length_framed_json(self) -> None:
        left, right = socket.socketpair()
        try:
            first = {"a": 1}
            second = {"b": 2}
            left.sendall(self._framed(first) + self._framed(second))
            self.assertEqual(self.framing.read_message(right), first)
            self.assertEqual(self.framing.read_message(right), second)
        finally:
            left.close()
            right.close()

    def test_protocol_rejects_missing_content_length(self) -> None:
        left, right = socket.socketpair()
        try:
            left.sendall(b"{}\n")
            left.shutdown(socket.SHUT_WR)
            with self.assertRaises(self.framing.JsonFramingError) as raised:
                self.framing.read_message(right)
        finally:
            left.close()
            right.close()
        self.assertIn("unexpected EOF", raised.exception.message)

    def test_protocol_rejects_invalid_json_body(self) -> None:
        left, right = socket.socketpair()
        try:
            body = b'{"ok":'
            header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
            left.sendall(header + body)
            with self.assertRaises(self.framing.JsonFramingError) as raised:
                self.framing.read_message(right)
        finally:
            left.close()
            right.close()
        self.assertIn("invalid JSON", raised.exception.message)

    def test_framing_preserves_header_and_body_limits(self) -> None:
        for wire, limits, message in (
            (b"X: 1\r\n\r\n", {"header_limit_bytes": 3}, "header exceeds limit"),
            (b"Content-Length: 2\r\n\r\n{}", {"body_limit_bytes": 1}, "body exceeds limit"),
        ):
            with self.subTest(message=message):
                left, right = socket.socketpair()
                try:
                    left.sendall(wire)
                    with self.assertRaises(self.framing.JsonFramingError) as raised:
                        self.framing.read_message(right, **limits)
                finally:
                    left.close()
                    right.close()
                self.assertIn(message, raised.exception.message)

    def test_framing_rejects_body_eof_and_non_object_json(self) -> None:
        for wire, message in (
            (b"Content-Length: 3\r\n\r\n{}", "unexpected EOF while reading framed JSON body"),
            (b"Content-Length: 2\r\n\r\n[]", "must decode to JSON object"),
        ):
            with self.subTest(message=message):
                left, right = socket.socketpair()
                try:
                    left.sendall(wire)
                    left.shutdown(socket.SHUT_WR)
                    with self.assertRaises(self.framing.JsonFramingError) as raised:
                        self.framing.read_message(right)
                finally:
                    left.close()
                    right.close()
                self.assertIn(message, raised.exception.message)

    def test_framing_write_is_compact_ascii_object_sendall(self) -> None:
        left, right = socket.socketpair()
        try:
            self.framing.write_message(left, {"snow": "雪"})
            expected_body = b'{"snow":"\\u96ea"}'
            expected = f"Content-Length: {len(expected_body)}\r\n\r\n".encode("ascii") + expected_body
            self.assertEqual(right.recv(len(expected)), expected)
            with self.assertRaises(self.framing.JsonFramingError):
                self.framing.write_message(left, ["not", "an", "object"])
        finally:
            left.close()
            right.close()

    def test_validate_request_requires_v2_protocol_request_id_method_params_deadline(self) -> None:
        valid = {
            "protocol": BROKER_V2_PROTOCOL,
            "request_id": "req-1",
            "method": "env.tool",
            "params": {"tool": "context", "action": "summarize", "args": {}},
            "deadline_ms": 35000,
        }
        for missing in ("protocol", "request_id", "method", "params", "deadline_ms"):
            request = dict(valid)
            request.pop(missing)
            with self.assertRaises(self.protocol.BrokerProtocolError, msg=missing):
                self.protocol.validate_request(request)

    def test_validate_request_accepts_current_env_tool_method(self) -> None:
        request = {
            "protocol": BROKER_V2_PROTOCOL,
            "request_id": "req-2",
            "method": "env.tool",
            "params": {"tool": "context", "action": "summarize", "args": {}},
            "deadline_ms": 35000,
        }
        validated = self.protocol.validate_request(request)
        self.assertEqual(validated["method"], "env.tool")

    def test_response_envelopes_use_result_or_error(self) -> None:
        success = self.protocol.success_response("req-ok", {"ok": True, "value": 1})
        self.assertEqual(success["protocol"], BROKER_V2_PROTOCOL)
        self.assertEqual(success["request_id"], "req-ok")
        self.assertTrue(success["ok"])
        self.assertEqual(success["result"], {"ok": True, "value": 1})
        self.assertNotIn("payload", success)

        failure = self.protocol.error_response(
            "req-bad",
            code="E_RUNTIME_BROKER_PERMISSION",
            message="denied",
            retriable=False,
        )
        self.assertEqual(failure["protocol"], BROKER_V2_PROTOCOL)
        self.assertEqual(failure["request_id"], "req-bad")
        self.assertFalse(failure["ok"])
        self.assertEqual(failure["error"]["code"], "E_RUNTIME_BROKER_PERMISSION")
        self.assertIs(failure["error"]["retriable"], False)
        self.assertNotIn("payload", failure)


class RuntimeBrokerCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.coordinator = _require_module("buddyswitch.foundation.runtime_broker.coordinator")

    def test_lock_mode_for_browser_methods_is_write(self) -> None:
        for method in ("browser.acquire", "browser.status", "browser.release"):
            with self.subTest(method=method):
                self.assertEqual(
                    self.coordinator.lock_mode_for_request(method, {}),
                    self.coordinator.LockMode.WRITE,
                )

    def test_lock_mode_for_read_only_env_tool_is_read(self) -> None:
        for params in (
            {"tool": "context", "action": "summarize", "args": {}},
            {"tool": "track", "action": "open", "args": {}},
            {"tool": "artifact", "action": "get", "args": {}},
        ):
            with self.subTest(params=params):
                self.assertEqual(self.coordinator.lock_mode_for_request("env.tool", params), self.coordinator.LockMode.READ)

    def test_lock_mode_for_mutating_env_tool_is_write(self) -> None:
        for params in (
            {"tool": "task_sys", "action": "close", "args": {}},
            {"tool": "track", "action": "update_status", "args": {}},
            {"tool": "track", "action": "add_material", "args": {}},
            {"tool": "track", "action": "add_update", "args": {}},
            {"tool": "track", "action": "add_proof", "args": {}},
            {"tool": "track", "action": "archive", "args": {}},
            {"tool": "evidence", "action": "issue_browser", "args": {}},
        ):
            with self.subTest(params=params):
                self.assertEqual(self.coordinator.lock_mode_for_request("env.tool", params), self.coordinator.LockMode.WRITE)

    def test_unknown_env_tool_action_defaults_to_write(self) -> None:
        params = {"tool": "task_sys", "action": "merge", "args": {}}
        self.assertEqual(self.coordinator.lock_mode_for_request("env.tool", params), self.coordinator.LockMode.WRITE)

    def test_ping_and_status_do_not_acquire_runtime_lock(self) -> None:
        calls: list[str] = []

        @contextlib.contextmanager
        def fake_lock(*args, **kwargs):
            calls.append("lock")
            yield

        def dispatch_fn(request, session):
            return {"ok": True, "method": request["method"]}

        session = {"instance_json": Path("instance.json"), "manifest_path": MANIFEST}
        with patch(
            "buddyswitch.foundation.runtime_broker.coordinator._hold_product_runtime_lock",
            side_effect=fake_lock,
        ):
            for method in ("ping", "status"):
                response = self.coordinator.dispatch_with_coordination(
                    {
                        "protocol": BROKER_V2_PROTOCOL,
                        "request_id": f"req-{method}",
                        "method": method,
                        "params": {},
                        "deadline_ms": 35000,
                    },
                    session,
                    dispatch_fn,
                )
                self.assertEqual(response["method"], method)
        self.assertEqual(calls, [])

    def test_lock_contention_returns_deadline_exceeded(self) -> None:
        def dispatch_fn(request, session):
            return {"ok": True, "method": request["method"], "session": session}

        @contextlib.contextmanager
        def timeout_lock(*args, **kwargs):
            raise TimeoutError("runtime lock busy for test")
            yield

        request = {
            "protocol": BROKER_V2_PROTOCOL,
            "request_id": "req-lock-timeout",
            "method": "env.tool",
            "params": {"tool": "task_sys", "action": "close", "args": {"task_id": "task-missing"}},
            "deadline_ms": 35000,
        }
        session = {"instance_json": Path("instance.json"), "manifest_path": MANIFEST}
        with patch(
            "buddyswitch.foundation.runtime_broker.coordinator._hold_product_runtime_lock",
            side_effect=timeout_lock,
        ):
            response = self.coordinator.dispatch_with_coordination(request, session, dispatch_fn)
        self.assertFalse(response["ok"], msg=response)
        self.assertEqual(response["error"]["code"], "E_RUNTIME_BROKER_DEADLINE_EXCEEDED")
        self.assertIs(response["error"]["retriable"], True)
