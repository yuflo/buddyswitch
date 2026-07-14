"""Tests for shared Chrome DevTools browser lifecycle helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import fcntl
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from itertools import count
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from tests.support.python import PYTHON


from tests.support.paths import REPO_ROOT
from tests.support.fake_cdp import (
    read_client_text_frame as _read_client_text_frame,
    websocket_accept_value as _websocket_accept_value,
    write_server_text_frame as _write_server_text_frame,
)

ROOT = REPO_ROOT
SESSION_PATH = ROOT / "scripts" / "env" / ("cdp_browser_" + "session.py")
LIFECYCLE_PATH = ROOT / "scripts" / "env" / "cdp_browser_lifecycle.py"
BACKGROUND_PAGE_PATH = ROOT / "scripts" / "env" / "cdp_background_page.py"
BROWSER_RUNTIME_MANAGER_PATH = ROOT / "tools" / "launcher" / "browser_runtime_manager.py"
MODULE_COUNTER = count()
LEGACY_CURRENT_TARGET_FIELD = "current_" + "target_id"
LEGACY_PAGE_TARGET_MAP_FIELD = "page_id_to_" + "target_id"
LEGACY_TARGETS_FIELD = "tar" + "gets"


def load_lifecycle() -> Any:
    if not LIFECYCLE_PATH.exists():
        raise AssertionError(f"expected module to exist: {LIFECYCLE_PATH}")
    return importlib.reload(importlib.import_module("env.cdp_browser_lifecycle"))


def load_background_page() -> Any:
    if not BACKGROUND_PAGE_PATH.exists():
        raise AssertionError(f"expected module to exist: {BACKGROUND_PAGE_PATH}")
    return importlib.reload(importlib.import_module("env.cdp_background_page"))


def _make_cdp_browser_handler(state: dict[str, object]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/json/version":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                payload = {
                    "Browser": "test",
                    "webSocketDebuggerUrl": f"ws://127.0.0.1:{self.server.server_port}/devtools/browser/test",  # type: ignore[attr-defined]
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
                if state.get("close_error"):
                    response = {"id": message.get("id"), "error": {"message": str(state["close_error"])}}
                else:
                    response = {"id": message.get("id"), "result": {"success": True}}
                _write_server_text_frame(self.wfile, json.dumps(response, ensure_ascii=True))
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return Handler


def _start_cdp_browser_server(testcase: unittest.TestCase, state: dict[str, object]) -> str:
    server = HTTPServer(("127.0.0.1", 0), _make_cdp_browser_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    testcase.addCleanup(server.server_close)
    testcase.addCleanup(thread.join, 5)
    testcase.addCleanup(server.shutdown)
    return f"http://127.0.0.1:{server.server_port}"


from tests.support.processes import ResourceLedger, run_process

class CdpBrowserLifecycleHarness(unittest.TestCase):
    def setUp(self) -> None:
        self.lifecycle = load_lifecycle()
        original_schedule_trigger = self.lifecycle.daemon_client.schedule_trigger
        original_utc_now = self.lifecycle._utc_now
        self.addCleanup(setattr, self.lifecycle.daemon_client, "schedule_trigger", original_schedule_trigger)
        self.addCleanup(setattr, self.lifecycle, "_utc_now", original_utc_now)

__all__ = [name for name in globals() if not name.startswith('__')]
