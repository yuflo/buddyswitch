"""Tests for shared Chrome DevTools browser lifecycle helpers."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib.util
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

from tests.python_runtime import PYTHON


ROOT = Path(__file__).resolve().parents[1]
SESSION_PATH = ROOT / "scripts" / "env" / ("cdp_browser_" + "session.py")
LIFECYCLE_PATH = ROOT / "scripts" / "env" / "cdp_browser_lifecycle.py"
BACKGROUND_PAGE_PATH = ROOT / "scripts" / "env" / "cdp_background_page.py"
MODULE_COUNTER = count()
WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
LEGACY_CURRENT_TARGET_FIELD = "current_" + "target_id"
LEGACY_PAGE_TARGET_MAP_FIELD = "page_id_to_" + "target_id"
LEGACY_TARGETS_FIELD = "tar" + "gets"


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


def load_background_page() -> Any:
    if not BACKGROUND_PAGE_PATH.exists():
        raise AssertionError(f"expected module to exist: {BACKGROUND_PAGE_PATH}")
    module_name = f"buddyswitch_cdp_background_page_{next(MODULE_COUNTER)}"
    spec = importlib.util.spec_from_file_location(module_name, BACKGROUND_PAGE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec for {BACKGROUND_PAGE_PATH}")
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
    length = second & 0x7F
    if length == 126:
        length = int.from_bytes(_read_exact(stream, 2), "big")
    elif length == 127:
        length = int.from_bytes(_read_exact(stream, 8), "big")
    mask = _read_exact(stream, 4) if second & 0x80 else b""
    payload = _read_exact(stream, length)
    if mask:
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


class CdpBrowserLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lifecycle = load_lifecycle()
        original_schedule_trigger = self.lifecycle.daemon_client.schedule_trigger
        original_utc_now = self.lifecycle._utc_now
        self.addCleanup(setattr, self.lifecycle.daemon_client, "schedule_trigger", original_schedule_trigger)
        self.addCleanup(setattr, self.lifecycle, "_utc_now", original_utc_now)

    def test_close_target_sends_target_close_target_for_exact_id(self) -> None:
        background = load_background_page()
        self.assertTrue(hasattr(background, "close_target"), "close_target primitive is required")
        cdp_state: dict[str, object] = {"rpc_requests": []}
        browser_url = _start_cdp_browser_server(self, cdp_state)

        result = background.close_target(browser_url, "target-close-exact", timeout_seconds=1.0)

        self.assertEqual(result, {"success": True})
        self.assertEqual(
            cdp_state["rpc_requests"],
            [{"id": 1, "method": "Target.closeTarget", "params": {"targetId": "target-close-exact"}}],
        )

    def test_close_target_raises_clear_error_on_cdp_error(self) -> None:
        background = load_background_page()
        self.assertTrue(hasattr(background, "close_target"), "close_target primitive is required")
        cdp_state: dict[str, object] = {"rpc_requests": [], "close_error": "No target with given id found"}
        browser_url = _start_cdp_browser_server(self, cdp_state)

        with self.assertRaisesRegex(background.CdpTargetError, "No target with given id found"):
            background.close_target(browser_url, "target-missing", timeout_seconds=1.0)

        self.assertEqual(
            cdp_state["rpc_requests"],
            [{"id": 1, "method": "Target.closeTarget", "params": {"targetId": "target-missing"}}],
        )

    def test_schedule_failed_open_page_cleanup_uses_exact_target_key(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_schedule_trigger(**kwargs: object) -> dict[str, object]:
            calls.append(kwargs)
            return {"schedule": {"schedule_id": "schedule-failed-open"}}

        self.lifecycle.daemon_client.schedule_trigger = fake_schedule_trigger
        self.assertTrue(
            hasattr(self.lifecycle, "schedule_failed_open_page_cleanup"),
            "schedule_failed_open_page_cleanup helper is required",
        )

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"

            result = self.lifecycle.schedule_failed_open_page_cleanup(
                instance_root=instance_root,
                target_id="target-cleanup",
                url="https://example.com/failed-open",
                attempts=1,
                first_seen_at="2026-07-07T00:00:00Z",
            )

        self.assertEqual(result, {"schedule": {"schedule_id": "schedule-failed-open"}})
        self.assertEqual(
            calls,
            [
                {
                    "instance_root": instance_root,
                    "delay_seconds": 5,
                    "trigger_type": "browser.failed_open_page.cleanup",
                    "payload": {
                        "target_id": "target-cleanup",
                        "url": "https://example.com/failed-open",
                        "attempts": 1,
                        "first_seen_at": "2026-07-07T00:00:00Z",
                        "reason": "failed_open_page",
                    },
                    "source_context": {"owner": "browser"},
                    "schedule_key": "browser.failed_open_page.cleanup:target-cleanup",
                }
            ],
        )

    def test_refresh_page_idle_uses_page_id_payload_and_state(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_schedule_trigger(**kwargs: object) -> dict[str, object]:
            calls.append(kwargs)
            return {"schedule": {"schedule_id": "schedule-1"}}

        self.lifecycle.daemon_client.schedule_trigger = fake_schedule_trigger
        self.lifecycle._utc_now = lambda: datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"

            result = self.lifecycle.refresh_page_idle(
                instance_root=instance_root,
                page_id="page-idle-1",
                target_url="https://example.com/background",
            )

            self.assertEqual(
                result,
                {
                    "idle_refreshed": True,
                    "idle_seconds": 40,
                    "idle_expires_at": "2026-06-24T00:00:40Z",
                },
            )
            self.assertEqual(
                calls,
                [
                    {
                        "instance_root": instance_root,
                        "delay_seconds": 40,
                        "trigger_type": "browser.page.expired",
                        "payload": {"page_id": "page-idle-1"},
                        "source_context": {"owner": "browser"},
                        "schedule_key": "browser.page.idle:page-idle-1",
                    }
                ],
            )
            state_path = instance_root / "runtime" / "browser" / "page_idle.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertNotIn(LEGACY_CURRENT_TARGET_FIELD, state)
            self.assertNotIn(LEGACY_PAGE_TARGET_MAP_FIELD, state)
            self.assertNotIn(LEGACY_TARGETS_FIELD, state)
            self.assertNotIn("current_page_updated_at", state)
            self.assertEqual(state["pages"]["page-idle-1"]["url"], "https://example.com/background")
            self.assertEqual(state["pages"]["page-idle-1"]["last_used_at"], "2026-06-24T00:00:00Z")

    def test_mark_current_page_does_not_schedule_idle(self) -> None:
        calls: list[dict[str, object]] = []
        self.lifecycle.daemon_client.schedule_trigger = lambda **kwargs: calls.append(kwargs)
        self.lifecycle._utc_now = lambda: datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"

            state = self.lifecycle.mark_current_page(
                instance_root=instance_root,
                page_id="page-current-1",
                target_url="https://example.com/current",
            )

            self.assertEqual(calls, [])
            self.assertEqual(state["current_page_id"], "page-current-1")
            self.assertEqual(state["selected_page_id"], "page-current-1")
            self.assertEqual(state["current_page_updated_at"], "2026-06-24T00:00:00Z")
            self.assertEqual(state["pages"]["page-current-1"]["url"], "https://example.com/current")
            self.assertNotIn(LEGACY_CURRENT_TARGET_FIELD, state)
            self.assertNotIn(LEGACY_PAGE_TARGET_MAP_FIELD, state)

    def test_refresh_current_page_idle_sets_current_and_schedules(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_schedule_trigger(**kwargs: object) -> dict[str, object]:
            calls.append(kwargs)
            return {"schedule": {"schedule_id": "schedule-1"}}

        self.lifecycle.daemon_client.schedule_trigger = fake_schedule_trigger
        self.lifecycle._utc_now = lambda: datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"

            result = self.lifecycle.refresh_current_page_idle(
                instance_root=instance_root,
                page_id="page-current-idle",
                target_url="https://example.com/current",
            )

            self.assertTrue(result["idle_refreshed"])
            self.assertEqual(calls[0]["schedule_key"], "browser.page.idle:page-current-idle")
            self.assertEqual(calls[0]["payload"], {"page_id": "page-current-idle"})
            state = json.loads(self.lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(state["current_page_id"], "page-current-idle")
            self.assertEqual(state["selected_page_id"], "page-current-idle")
            self.assertEqual(state["pages"]["page-current-idle"]["url"], "https://example.com/current")

    def test_schedule_browser_cockpit_release_uses_keyed_browser_release_trigger(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_schedule_trigger(**kwargs: object) -> dict[str, object]:
            calls.append(kwargs)
            return {"schedule": {"schedule_id": "schedule-release"}}

        self.lifecycle.daemon_client.schedule_trigger = fake_schedule_trigger

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"

            result = self.lifecycle.schedule_browser_cockpit_release(instance_root=instance_root)

        self.assertEqual(result, {"schedule": {"schedule_id": "schedule-release"}})
        self.assertEqual(
            calls,
            [
                {
                    "instance_root": instance_root,
                    "delay_seconds": 10,
                    "trigger_type": "browser.cockpit.release",
                    "payload": {"reason": "page_idle_empty"},
                    "source_context": {"owner": "browser"},
                    "schedule_key": "browser.cockpit.release",
                }
            ],
        )

    def test_refresh_page_idle_schedule_failure_leaves_no_idle_state(self) -> None:
        def failing_schedule_trigger(**_kwargs: object) -> dict[str, object]:
            raise RuntimeError("daemon unavailable")

        self.lifecycle.daemon_client.schedule_trigger = failing_schedule_trigger

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"

            with self.assertRaisesRegex(RuntimeError, "daemon unavailable"):
                self.lifecycle.refresh_page_idle(
                    instance_root=instance_root,
                    page_id="page-unmanaged",
                    target_url="https://example.com/unmanaged",
                )

            self.assertFalse(self.lifecycle.page_idle_state_file(instance_root).exists())

    def test_forget_page_idle_page_removes_page_and_current(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"
            self.lifecycle._write_page_idle_state(
                instance_root,
                {
                    "current_page_id": "page-forget",
                    "selected_page_id": "page-forget",
                    "current_page_updated_at": "2026-06-24T00:00:00Z",
                    "pages": {
                        "page-forget": {
                            "page_id": "page-forget",
                            "url": "https://example.com/forget",
                            "last_used_at": "2026-06-24T00:00:00Z",
                        },
                        "page-keep": {"page_id": "page-keep", "last_used_at": "2026-06-24T00:00:00Z"},
                    },
                },
            )

            state = self.lifecycle.forget_page_idle_page(instance_root=instance_root, page_id="page-forget")

            self.assertNotIn("page-forget", state["pages"])
            self.assertIn("page-keep", state["pages"])
            self.assertNotIn("current_page_id", state)
            self.assertNotIn("selected_page_id", state)
            persisted = json.loads(self.lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(persisted, state)

    def test_refresh_page_idle_rejects_blank_page_id_before_scheduling(self) -> None:
        calls: list[dict[str, object]] = []
        self.lifecycle.daemon_client.schedule_trigger = lambda **kwargs: calls.append(kwargs)

        with tempfile.TemporaryDirectory() as temp_root:
            with self.assertRaisesRegex(self.lifecycle.BrowserLifecycleError, "page_id"):
                self.lifecycle.refresh_page_idle(instance_root=Path(temp_root), page_id=" ")

        self.assertEqual(calls, [])

    def test_page_idle_state_ignores_unknown_legacy_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"
            self.lifecycle._write_page_idle_state(
                instance_root,
                {
                    "legacy_current": "legacy-cdp-1",
                    "legacy_map": {"7": "legacy-cdp-1"},
                    "legacy_pages": {"legacy-cdp-1": {"legacy_id": "legacy-cdp-1"}},
                    "current_page_id": "page-7",
                    "selected_page_id": "page-7",
                    "pages": {"page-7": {"page_id": "page-7", "last_used_at": "2026-06-24T00:00:00Z"}},
                },
            )

            state = self.lifecycle._read_page_idle_state(instance_root)

            self.assertEqual(state["current_page_id"], "page-7")
            self.assertEqual(state["selected_page_id"], "page-7")
            self.assertEqual(state["pages"], {"page-7": {"page_id": "page-7", "last_used_at": "2026-06-24T00:00:00Z"}})
            self.assertNotIn("legacy_current", state)
            self.assertNotIn("legacy_map", state)
            self.assertNotIn("legacy_pages", state)

    def test_mark_current_page_waits_for_page_idle_state_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"
            lock_path = instance_root / "runtime" / "browser" / "page_idle.lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_file = lock_path.open("a+", encoding="utf-8")
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            script = """
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
instance_root = Path(sys.argv[2])
sys.path.insert(0, str(repo_root / "scripts" / "env"))

import cdp_browser_lifecycle as lifecycle

lifecycle.mark_current_page(
    instance_root=instance_root,
    page_id="page-lock-wait",
    target_url="https://example.com/locked",
)
print("done", flush=True)
"""
            process = subprocess.Popen(
                [PYTHON, "-c", script, str(ROOT), str(instance_root)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    process.communicate(timeout=0.25)
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                stdout, stderr = process.communicate(timeout=2)
                self.assertEqual(process.returncode, 0, msg=stderr)
                self.assertIn("done", stdout)
            finally:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
                lock_file.close()
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=2)

            state = json.loads(self.lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(state["current_page_id"], "page-lock-wait")


class BrowserLifecycleTests(unittest.TestCase):
    def test_actor_page_cdp_open_close_helpers_are_removed_or_readiness_scoped(self) -> None:
        self.assertFalse(SESSION_PATH.exists(), "actor page CDP session helper should not remain as a live module")
        lifecycle_source = LIFECYCLE_PATH.read_text(encoding="utf-8")
        forbidden = (
            "def create_background_page_" + "target",
            "def close_page_" + "target",
            "Target." + "closeTarget",
            "target_idle_expiry_after_" + "due_at",
            "forget_page_idle_" + "target",
            LEGACY_CURRENT_TARGET_FIELD,
            LEGACY_PAGE_TARGET_MAP_FIELD,
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, lifecycle_source)

        manager_source = (ROOT / "tools" / "launcher" / "browser_runtime_manager.py").read_text(encoding="utf-8")
        self.assertIn("cdp_background_page", manager_source)
        self.assertNotIn("create_background_page_" + "target", manager_source)


if __name__ == "__main__":
    unittest.main()
