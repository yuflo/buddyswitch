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
SCRIPTS = ROOT / "scripts"

import runtime_kernel.broker as runtime_broker  # noqa: E402
import runtime_kernel.client as runtime_client  # noqa: E402
from runtime_kernel import process_identity  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
BROKER_V2_PROTOCOL = "buddyswitch-runtime-broker/v2"
PM_REQUEST = "给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track"


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
        self.protocol = _require_module("runtime_kernel.protocol")

    def _framed(self, payload: dict[str, object]) -> bytes:
        body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body

    def test_protocol_round_trips_content_length_framed_json(self) -> None:
        left, right = socket.socketpair()
        try:
            first = {"a": 1}
            second = {"b": 2}
            left.sendall(self._framed(first) + self._framed(second))
            self.assertEqual(self.protocol.read_message(right), first)
            self.assertEqual(self.protocol.read_message(right), second)
        finally:
            left.close()
            right.close()

    def test_protocol_rejects_missing_content_length(self) -> None:
        left, right = socket.socketpair()
        try:
            left.sendall(b"{}\n")
            left.shutdown(socket.SHUT_WR)
            with self.assertRaises(self.protocol.BrokerProtocolError) as raised:
                self.protocol.read_message(right)
        finally:
            left.close()
            right.close()
        self.assertEqual(raised.exception.code, "E_RUNTIME_BROKER_PROTOCOL")

    def test_protocol_rejects_invalid_json_body(self) -> None:
        left, right = socket.socketpair()
        try:
            body = b'{"ok":'
            header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
            left.sendall(header + body)
            with self.assertRaises(self.protocol.BrokerProtocolError) as raised:
                self.protocol.read_message(right)
        finally:
            left.close()
            right.close()
        self.assertEqual(raised.exception.code, "E_RUNTIME_BROKER_PROTOCOL")
        self.assertIn("invalid JSON", raised.exception.message)

    def test_validate_request_requires_v2_protocol_request_id_method_params_deadline(self) -> None:
        valid = {
            "protocol": BROKER_V2_PROTOCOL,
            "request_id": "req-1",
            "method": "prepare",
            "params": {"text": "x"},
            "deadline_ms": 35000,
        }
        for missing in ("protocol", "request_id", "method", "params", "deadline_ms"):
            request = dict(valid)
            request.pop(missing)
            with self.assertRaises(self.protocol.BrokerProtocolError, msg=missing):
                self.protocol.validate_request(request)

    def test_write_methods_require_idempotency_key(self) -> None:
        request = {
            "protocol": BROKER_V2_PROTOCOL,
            "request_id": "req-2",
            "method": "persist",
            "params": {"context": {}, "result": {}},
            "deadline_ms": 35000,
        }
        validated = self.protocol.validate_request(request)
        self.assertEqual(validated["method"], "persist")

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
        self.coordinator = _require_module("runtime_kernel.coordinator")

    def test_lock_mode_for_prepare_and_persist_is_write(self) -> None:
        self.assertEqual(self.coordinator.lock_mode_for_request("prepare", {"text": "x"}), self.coordinator.LockMode.WRITE)
        self.assertEqual(
            self.coordinator.lock_mode_for_request("persist", {"context": {}, "result": {}}),
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
        with patch("turn_runtime._hold_product_runtime_lock", side_effect=fake_lock):
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
            "method": "prepare",
            "params": {"text": "x"},
            "deadline_ms": 35000,
        }
        session = {"instance_json": Path("instance.json"), "manifest_path": MANIFEST}
        with patch("turn_runtime._hold_product_runtime_lock", side_effect=timeout_lock):
            response = self.coordinator.dispatch_with_coordination(request, session, dispatch_fn)
        self.assertFalse(response["ok"], msg=response)
        self.assertEqual(response["error"]["code"], "E_RUNTIME_BROKER_DEADLINE_EXCEEDED")
        self.assertIs(response["error"]["retriable"], True)
