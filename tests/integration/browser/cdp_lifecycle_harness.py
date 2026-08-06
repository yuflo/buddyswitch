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
SESSION_PATH = ROOT / "src" / "buddyswitch" / "env" / ("cdp_browser_" + "session.py")
BROWSER_RUNTIME_ROOT = ROOT / "src" / "buddyswitch" / "foundation" / "browser_runtime"
LIFECYCLE_PATH = BROWSER_RUNTIME_ROOT / "lifecycle.py"
TARGET_TRANSPORT_PATH = BROWSER_RUNTIME_ROOT / "target.py"
BROWSER_RUNTIME_MANAGER_PATH = BROWSER_RUNTIME_ROOT / "runtime.py"
MODULE_COUNTER = count()
LEGACY_CURRENT_TARGET_FIELD = "current_" + "target_id"
LEGACY_PAGE_TARGET_MAP_FIELD = "page_id_to_" + "target_id"
LEGACY_TARGETS_FIELD = "tar" + "gets"


def load_lifecycle() -> Any:
    if not LIFECYCLE_PATH.exists():
        raise AssertionError(f"expected module to exist: {LIFECYCLE_PATH}")
    return importlib.reload(importlib.import_module("buddyswitch.foundation.browser_runtime.lifecycle"))


def load_target_transport() -> Any:
    if not TARGET_TRANSPORT_PATH.exists():
        raise AssertionError(f"expected module to exist: {TARGET_TRANSPORT_PATH}")
    return importlib.reload(importlib.import_module("buddyswitch.foundation.browser_runtime.target"))


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
                if message.get("method") == "Target.getTargets":
                    response = {"id": message.get("id"), "result": {"targetInfos": state.get("targets", [])}}
                elif message.get("method") == "Target.getTargetInfo":
                    target_id = message.get("params", {}).get("targetId")
                    targets = state.get("targets")
                    target = None
                    if isinstance(targets, list):
                        target = next(
                            (
                                target
                                for target in targets
                                if isinstance(target, dict) and target.get("targetId") == target_id
                            ),
                            None,
                        )
                    if target is None:
                        response = {"id": message.get("id"), "error": {"message": "No target with given id found"}}
                    else:
                        response = {"id": message.get("id"), "result": {"targetInfo": target}}
                elif message.get("method") == "Target.closeTarget" and state.get("close_error"):
                    response = {"id": message.get("id"), "error": {"message": str(state["close_error"])}}
                elif message.get("method") == "Target.closeTarget":
                    target_id = message.get("params", {}).get("targetId")
                    targets = state.get("targets")
                    if isinstance(targets, list):
                        state["targets"] = [
                            target
                            for target in targets
                            if target.get("targetId") != target_id and target.get("tabTargetId") != target_id
                        ]
                    response = {"id": message.get("id"), "result": {"success": True}}
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
