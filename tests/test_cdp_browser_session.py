#!/usr/bin/env python3
"""Tests for shared Chrome DevTools browser lifecycle helpers."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib.util
import json
import tempfile
import threading
import unittest
from itertools import count
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE_PATH = ROOT / "scripts" / "env" / "cdp_browser_lifecycle.py"
MODULE_COUNTER = count()
WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def load_lifecycle() -> Any:
    if not LIFECYCLE_PATH.exists():
        raise AssertionError(f"expected module to exist: {LIFECYCLE_PATH}")
    module_name = f"buddyswitch_cdp_browser_lifecycle_{next(MODULE_COUNTER)}"
    spec = importlib.util.spec_from_file_location(module_name, LIFECYCLE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec for {LIFECYCLE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _websocket_accept_value(key: str) -> str:
    digest = hashlib.sha1((key + WEBSOCKET_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def _read_exact(stream: object, length: int) -> bytes:
    chunks = b""
    while len(chunks) < length:
        chunk = stream.read(length - len(chunks))  # type: ignore[attr-defined]
        if not chunk:
            raise EOFError("websocket stream closed")
        chunks += chunk
    return chunks


def _read_client_text_frame(stream: object) -> str:
    first, second = _read_exact(stream, 2)
    opcode = first & 0x0F
    if opcode != 0x1:
        raise ValueError(f"expected text frame, got opcode {opcode}")
    masked = bool(second & 0x80)
    length = second & 0x7F
    if length == 126:
        length = int.from_bytes(_read_exact(stream, 2), "big")
    elif length == 127:
        length = int.from_bytes(_read_exact(stream, 8), "big")
    mask = _read_exact(stream, 4) if masked else b""
    payload = _read_exact(stream, length)
    if masked:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return payload.decode("utf-8")


def _write_server_text_frame(stream: object, text: str) -> None:
    payload = text.encode("utf-8")
    first = 0x80 | 0x1
    length = len(payload)
    if length < 126:
        header = bytes([first, length])
    elif length < (1 << 16):
        header = bytes([first, 126]) + length.to_bytes(2, "big")
    else:
        header = bytes([first, 127]) + length.to_bytes(8, "big")
    stream.write(header + payload)  # type: ignore[attr-defined]
    stream.flush()  # type: ignore[attr-defined]


def _make_cdp_handler(state: dict[str, object]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            state.setdefault("requests", []).append({"method": "GET", "path": self.path})
            parsed = urlparse(self.path)
            if parsed.path == "/json/list":
                if state.get("list_fail"):
                    self.send_response(500)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(state.get("targets", []), ensure_ascii=True).encode("utf-8"))
                return
            if parsed.path == "/json/version":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                payload = {
                    "Browser": "test",
                    "webSocketDebuggerUrl": (
                        f"ws://127.0.0.1:{self.server.server_port}/devtools/browser/test"  # type: ignore[attr-defined]
                    ),
                }
                self.wfile.write(json.dumps(payload, ensure_ascii=True).encode("utf-8"))
                return
            if parsed.path == "/devtools/browser/test":
                key = self.headers.get("Sec-WebSocket-Key")
                if not key:
                    self.send_response(400)
                    self.end_headers()
                    return
                self.send_response(101)
                self.send_header("Upgrade", "websocket")
                self.send_header("Connection", "Upgrade")
                self.send_header("Sec-WebSocket-Accept", _websocket_accept_value(key))
                self.end_headers()

                raw_message = _read_client_text_frame(self.rfile)
                message = json.loads(raw_message)
                state.setdefault("rpc_requests", []).append(message)
                if state.get("close_fail"):
                    response = {
                        "id": message.get("id"),
                        "error": {"code": -32000, "message": "simulated close failure"},
                    }
                else:
                    response = {"id": message.get("id"), "result": {"success": True}}
                _write_server_text_frame(self.wfile, json.dumps(response, ensure_ascii=True))
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return Handler


class CdpBrowserLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lifecycle = load_lifecycle()

    def _start_cdp_server(self, state: dict[str, object]) -> tuple[HTTPServer, threading.Thread, str]:
        server = HTTPServer(("127.0.0.1", 0), _make_cdp_handler(state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        return server, thread, f"http://127.0.0.1:{server.server_port}"

    def test_new_page_target_id_requires_exactly_one_new_page_target(self) -> None:
        before = [{"id": "target-1", "type": "page", "url": "https://example.com/1"}]
        after = before + [{"id": "target-2", "type": "page", "url": "https://example.com/2"}]

        self.assertEqual(self.lifecycle.new_page_target_id(before, after), "target-2")
        self.assertIsNone(self.lifecycle.new_page_target_id(before, before))
        self.assertIsNone(
            self.lifecycle.new_page_target_id(
                before,
                after + [{"id": "target-3", "type": "page", "url": "https://example.com/3"}],
            )
        )
        self.assertIsNone(
            self.lifecycle.new_page_target_id(
                before,
                before + [{"id": "worker-1", "type": "service_worker", "url": "https://example.com/sw.js"}],
            )
        )

    def test_close_page_target_sends_target_close_target(self) -> None:
        state: dict[str, object] = {
            "requests": [],
            "targets": [{"id": "target-close-1", "type": "page", "url": "https://example.com"}],
        }
        _server, _thread, browser_url = self._start_cdp_server(state)

        result = self.lifecycle.close_page_target(browser_url, "target-close-1")

        self.assertEqual(result, {"status": "closed", "target_id": "target-close-1"})
        rpc_requests = state.get("rpc_requests")
        self.assertIsInstance(rpc_requests, list, msg=state)
        assert isinstance(rpc_requests, list)
        self.assertEqual(len(rpc_requests), 1)
        self.assertEqual(rpc_requests[0]["method"], "Target.closeTarget")
        self.assertEqual(rpc_requests[0]["params"], {"targetId": "target-close-1"})

    def test_close_page_target_missing_target_is_handled_without_rpc(self) -> None:
        state: dict[str, object] = {"requests": [], "targets": []}
        _server, _thread, browser_url = self._start_cdp_server(state)

        result = self.lifecycle.close_page_target(browser_url, "target-missing")

        self.assertEqual(result, {"status": "already_gone", "target_id": "target-missing"})
        self.assertEqual(state.get("rpc_requests", []), [])

    def test_close_page_target_reports_close_failure(self) -> None:
        state: dict[str, object] = {
            "requests": [],
            "targets": [{"id": "target-close-1", "type": "page", "url": "https://example.com"}],
            "close_fail": True,
        }
        _server, _thread, browser_url = self._start_cdp_server(state)

        with self.assertRaisesRegex(self.lifecycle.BrowserLifecycleError, "simulated close failure"):
            self.lifecycle.close_page_target(browser_url, "target-close-1")

    def test_touch_page_idle_writes_browser_state_and_keyed_schedule(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_schedule_trigger(**kwargs: object) -> dict[str, object]:
            calls.append(kwargs)
            return {"schedule": {"schedule_id": "schedule-1"}}

        self.lifecycle.daemon_client.schedule_trigger = fake_schedule_trigger
        self.lifecycle._utc_now = lambda: datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"

            result = self.lifecycle.touch_page_idle(
                instance_root=instance_root,
                target_id="target-idle-1",
                target_url="https://example.com/current",
                page_id=7,
            )

            self.assertEqual(
                result,
                {
                    "idle_refreshed": True,
                    "idle_seconds": 300,
                    "idle_expires_at": "2026-06-24T00:05:00Z",
                },
            )
            self.assertEqual(
                calls,
                [
                    {
                        "instance_root": instance_root,
                        "delay_seconds": 300,
                        "trigger_type": "browser.page.expired",
                        "payload": {"target_id": "target-idle-1"},
                        "source_context": {"owner": "browser"},
                        "schedule_key": "browser.page.idle:target-idle-1",
                    }
                ],
            )
            state_path = instance_root / "runtime" / "browser" / "page_idle.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["current_target_id"], "target-idle-1")
            self.assertEqual(state["current_page_updated_at"], "2026-06-24T00:00:00Z")
            self.assertEqual(state["page_id_to_target_id"], {"7": "target-idle-1"})
            self.assertEqual(state["targets"]["target-idle-1"]["target_url"], "https://example.com/current")
            self.assertEqual(state["targets"]["target-idle-1"]["last_used_at"], "2026-06-24T00:00:00Z")

    def test_touch_page_idle_rejects_blank_target_before_scheduling(self) -> None:
        calls: list[dict[str, object]] = []
        self.lifecycle.daemon_client.schedule_trigger = lambda **kwargs: calls.append(kwargs)

        with tempfile.TemporaryDirectory() as temp_root:
            with self.assertRaisesRegex(self.lifecycle.BrowserLifecycleError, "target_id"):
                self.lifecycle.touch_page_idle(instance_root=Path(temp_root), target_id=" ")

        self.assertEqual(calls, [])

    def test_page_id_mapping_resolves_to_cdp_target_without_treating_page_id_as_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"

            self.lifecycle.set_current_page(
                instance_root=instance_root,
                target_id="target-cdp-1",
                target_url="https://example.com/current",
                page_id=7,
            )

            self.assertEqual(self.lifecycle.current_target_id(instance_root), "target-cdp-1")
            self.assertEqual(self.lifecycle.target_id_for_page_id(instance_root, 7), "target-cdp-1")
            self.assertIsNone(self.lifecycle.target_id_for_page_id(instance_root, "target-cdp-1"))


if __name__ == "__main__":
    unittest.main()
