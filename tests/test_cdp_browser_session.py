#!/usr/bin/env python3
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


ROOT = Path(__file__).resolve().parents[1]
SESSION_PATH = ROOT / "scripts" / "env" / "cdp_browser_session.py"
LIFECYCLE_PATH = ROOT / "scripts" / "env" / "cdp_browser_lifecycle.py"
MODULE_COUNTER = count()
WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def load_session() -> Any:
    if not SESSION_PATH.exists():
        raise AssertionError(f"expected module to exist: {SESSION_PATH}")
    module_name = f"buddyswitch_cdp_browser_session_{next(MODULE_COUNTER)}"
    spec = importlib.util.spec_from_file_location(module_name, SESSION_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec for {SESSION_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


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


def _session_page_targets(count: int, *, start: int = 0) -> list[dict[str, object]]:
    return [
        {
            "id": f"target-{index}",
            "type": "page",
            "url": f"https://example.com/page-{index}",
        }
        for index in range(start, start + count)
    ]


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
                if message.get("method") == "Target.createTarget":
                    if state.get("create_fail"):
                        response = {
                            "id": message.get("id"),
                            "error": {"code": -32000, "message": "simulated create failure"},
                        }
                    else:
                        response = {
                            "id": message.get("id"),
                            "result": {"targetId": state.get("create_target_id", "target-created")},
                        }
                elif state.get("close_fail"):
                    response = {
                        "id": message.get("id"),
                        "error": {"code": -32000, "message": "simulated close failure"},
                    }
                elif state.get("close_success_false"):
                    response = {"id": message.get("id"), "result": {"success": False}}
                else:
                    response = {"id": message.get("id"), "result": {"success": True}}
                _write_server_text_frame(self.wfile, json.dumps(response, ensure_ascii=True))
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return Handler


class CdpBrowserSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = load_session()
        lifecycle = self.session.browser_lifecycle
        originals = {
            "create_background_page_target": lifecycle.create_background_page_target,
            "refresh_current_page_idle": lifecycle.refresh_current_page_idle,
            "close_page_target": lifecycle.close_page_target,
        }
        self.addCleanup(lambda: [setattr(lifecycle, name, value) for name, value in originals.items()])

    def _install_target_list(self, targets: list[dict[str, object]]) -> None:
        self.session._read_target_list = lambda *_args, **_kwargs: targets

    def _install_idle_success(self, calls: list[dict[str, object]]) -> None:
        def fake_refresh_current_page_idle(**kwargs: object) -> dict[str, object]:
            calls.append(kwargs)
            return {
                "idle_refreshed": True,
                "idle_seconds": 40,
                "idle_expires_at": "2026-07-01T00:00:40Z",
            }

        self.session.browser_lifecycle.refresh_current_page_idle = fake_refresh_current_page_idle

    def test_open_or_reuse_page_reuses_exact_url_and_refreshes_current_idle(self) -> None:
        target_url = "https://example.com/open"
        self._install_target_list(
            _session_page_targets(1)
            + [
                {
                    "id": "target-existing",
                    "type": "page",
                    "url": target_url,
                }
            ]
        )
        create_calls: list[dict[str, object]] = []
        idle_calls: list[dict[str, object]] = []
        self.session.browser_lifecycle.create_background_page_target = lambda **kwargs: create_calls.append(kwargs)
        self._install_idle_success(idle_calls)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"
            result = self.session.open_or_reuse_page(
                instance_root=instance_root,
                browser_url="http://127.0.0.1:9222",
                target_url=target_url,
            )

        self.assertEqual(result.kind, "reused")
        self.assertEqual(result.target_url, target_url)
        self.assertEqual(result.target_id, "target-existing")
        self.assertEqual(result.page_count, 2)
        self.assertEqual(result.projected_page_count, 2)
        self.assertFalse(result.page_opened)
        self.assertTrue(result.page_reused)
        self.assertTrue(result.idle_refreshed)
        self.assertEqual(result.idle_seconds, 40)
        self.assertEqual(create_calls, [])
        self.assertEqual(idle_calls[0]["target_id"], "target-existing")
        self.assertEqual(idle_calls[0]["target_url"], target_url)

    def test_open_or_reuse_page_creates_background_target_and_refreshes_current_idle(self) -> None:
        target_url = "https://example.com/new"
        browser_url = "http://127.0.0.1:9222"
        self._install_target_list(_session_page_targets(2))
        create_calls: list[dict[str, object]] = []
        idle_calls: list[dict[str, object]] = []

        def fake_create_background_page_target(*, browser_url: str, target_url: str) -> str:
            create_calls.append({"browser_url": browser_url, "target_url": target_url})
            return "target-new"

        self.session.browser_lifecycle.create_background_page_target = fake_create_background_page_target
        self._install_idle_success(idle_calls)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"
            result = self.session.open_or_reuse_page(
                instance_root=instance_root,
                browser_url=browser_url,
                target_url=target_url,
            )

        self.assertEqual(result.kind, "opened")
        self.assertEqual(result.target_url, target_url)
        self.assertEqual(result.target_id, "target-new")
        self.assertEqual(result.page_count, 2)
        self.assertEqual(result.projected_page_count, 3)
        self.assertTrue(result.page_opened)
        self.assertFalse(result.page_reused)
        self.assertTrue(result.idle_refreshed)
        self.assertEqual(result.idle_expires_at, "2026-07-01T00:00:40Z")
        self.assertEqual(create_calls, [{"browser_url": browser_url, "target_url": target_url}])
        self.assertEqual(idle_calls[0]["target_id"], "target-new")
        self.assertNotIn(browser_url, repr(result))

    def test_open_or_reuse_page_blocks_at_hard_limit_without_creating_target(self) -> None:
        target_url = "https://example.com/new"
        self._install_target_list(_session_page_targets(10))
        self.session.browser_lifecycle.create_background_page_target = lambda **_kwargs: self.fail("create must not run")
        self.session.browser_lifecycle.refresh_current_page_idle = lambda **_kwargs: self.fail("idle refresh must not run")

        with tempfile.TemporaryDirectory() as temp_root:
            result = self.session.open_or_reuse_page(
                instance_root=Path(temp_root) / "instances" / "act-browser",
                browser_url="http://127.0.0.1:9222",
                target_url=target_url,
            )

        self.assertEqual(result.kind, "blocked")
        self.assertEqual(result.target_url, target_url)
        self.assertEqual(result.page_count, 10)
        self.assertEqual(result.projected_page_count, 10)
        self.assertFalse(result.page_opened)
        self.assertFalse(result.page_reused)

    def test_open_or_reuse_page_reports_verification_failure_without_creating_target(self) -> None:
        target_url = "https://example.com/new"

        def fail_read(*_args: object, **_kwargs: object) -> list[object]:
            raise self.session.BrowserPageSnapshotError("simulated list failure")

        self.session._read_target_list = fail_read
        self.session.browser_lifecycle.create_background_page_target = lambda **_kwargs: self.fail("create must not run")

        with tempfile.TemporaryDirectory() as temp_root:
            result = self.session.open_or_reuse_page(
                instance_root=Path(temp_root) / "instances" / "act-browser",
                browser_url="http://127.0.0.1:9222",
                target_url=target_url,
            )

        self.assertEqual(result.kind, "verification_failed")
        self.assertEqual(result.target_url, target_url)
        self.assertIsNone(result.page_count)
        self.assertIn("simulated list failure", result.message or "")

    def test_open_or_reuse_page_closes_new_target_when_idle_registration_fails(self) -> None:
        target_url = "https://example.com/new"
        browser_url = "http://127.0.0.1:9222"
        self._install_target_list(_session_page_targets(1))
        close_calls: list[dict[str, object]] = []
        self.session.browser_lifecycle.create_background_page_target = lambda *, browser_url, target_url: "target-new"

        def fail_refresh_current_page_idle(**_kwargs: object) -> dict[str, object]:
            raise self.session.browser_lifecycle.BrowserLifecycleError("daemon unavailable")

        def fake_close_page_target(browser_url: str, target_id: str) -> dict[str, object]:
            close_calls.append({"browser_url": browser_url, "target_id": target_id})
            return {"status": "closed", "target_id": target_id}

        self.session.browser_lifecycle.refresh_current_page_idle = fail_refresh_current_page_idle
        self.session.browser_lifecycle.close_page_target = fake_close_page_target

        with tempfile.TemporaryDirectory() as temp_root:
            result = self.session.open_or_reuse_page(
                instance_root=Path(temp_root) / "instances" / "act-browser",
                browser_url=browser_url,
                target_url=target_url,
            )

        self.assertEqual(result.kind, "registration_failed")
        self.assertEqual(result.target_url, target_url)
        self.assertEqual(result.target_id, "target-new")
        self.assertFalse(result.page_opened)
        self.assertFalse(result.page_reused)
        self.assertFalse(result.idle_refreshed)
        self.assertIn("daemon unavailable", result.message or "")
        self.assertEqual(close_calls, [{"browser_url": browser_url, "target_id": "target-new"}])
        self.assertNotIn(browser_url, result.message or "")

    def test_open_or_reuse_page_rejects_blank_url_before_target_list_read(self) -> None:
        self.session._read_target_list = lambda *_args, **_kwargs: self.fail("target list must not be read")
        self.session.browser_lifecycle.create_background_page_target = lambda **_kwargs: self.fail("create must not run")

        with tempfile.TemporaryDirectory() as temp_root:
            result = self.session.open_or_reuse_page(
                instance_root=Path(temp_root) / "instances" / "act-browser",
                browser_url="http://127.0.0.1:9222",
                target_url="   ",
            )

        self.assertEqual(result.kind, "invalid_request")
        self.assertEqual(result.target_url, "")
        self.assertIsNone(result.page_count)
        self.assertIn("target_url", result.message or "")

    def test_browser_session_has_no_acquisition_helpers_or_launcher_subprocess(self) -> None:
        source = SESSION_PATH.read_text(encoding="utf-8")
        forbidden = [
            "ensure_" + "browser_url_for_instance",
            "launcher_" + "env_for_instance_root",
            "browser_" + "url_from_instance",
            "shared_" + "root_for_instance_root",
            "BUDDYSWITCH_BROWSER_" + "COCKPIT_ENSURE_COMMAND",
            'ROOT / "' + "buddyswitch-codex" + '"',
            "import " + "subprocess",
            "import " + "shlex",
        ]
        for phrase in forbidden:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, source)


class CdpBrowserLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lifecycle = load_lifecycle()
        original_schedule_trigger = self.lifecycle.daemon_client.schedule_trigger
        original_utc_now = self.lifecycle._utc_now
        self.addCleanup(setattr, self.lifecycle.daemon_client, "schedule_trigger", original_schedule_trigger)
        self.addCleanup(setattr, self.lifecycle, "_utc_now", original_utc_now)

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

    def test_create_background_page_target_sends_target_create_target(self) -> None:
        state: dict[str, object] = {
            "requests": [],
            "targets": [],
            "create_target_id": "target-created-1",
        }
        _server, _thread, browser_url = self._start_cdp_server(state)

        result = self.lifecycle.create_background_page_target(browser_url, "https://example.com/new")

        self.assertEqual(result, "target-created-1")
        rpc_requests = state.get("rpc_requests")
        self.assertIsInstance(rpc_requests, list, msg=state)
        assert isinstance(rpc_requests, list)
        self.assertEqual(len(rpc_requests), 1)
        self.assertEqual(rpc_requests[0]["method"], "Target.createTarget")
        self.assertEqual(rpc_requests[0]["params"], {"url": "https://example.com/new", "background": True})

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

    def test_close_page_target_false_success_is_failure(self) -> None:
        state: dict[str, object] = {
            "requests": [],
            "targets": [{"id": "target-close-1", "type": "page", "url": "https://example.com"}],
            "close_success_false": True,
        }
        _server, _thread, browser_url = self._start_cdp_server(state)

        with self.assertRaisesRegex(self.lifecycle.BrowserLifecycleError, "did not close target"):
            self.lifecycle.close_page_target(browser_url, "target-close-1")

    def test_refresh_page_idle_does_not_set_current_target(self) -> None:
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
                target_id="target-idle-1",
                target_url="https://example.com/background",
                page_id=7,
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
                        "payload": {"target_id": "target-idle-1"},
                        "source_context": {"owner": "browser"},
                        "schedule_key": "browser.page.idle:target-idle-1",
                    }
                ],
            )
            state_path = instance_root / "runtime" / "browser" / "page_idle.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertNotIn("current_target_id", state)
            self.assertNotIn("current_page_updated_at", state)
            self.assertEqual(state["page_id_to_target_id"], {"7": "target-idle-1"})
            self.assertEqual(state["targets"]["target-idle-1"]["target_url"], "https://example.com/background")
            self.assertEqual(state["targets"]["target-idle-1"]["last_used_at"], "2026-06-24T00:00:00Z")

    def test_mark_current_page_does_not_schedule_idle(self) -> None:
        calls: list[dict[str, object]] = []
        self.lifecycle.daemon_client.schedule_trigger = lambda **kwargs: calls.append(kwargs)
        self.lifecycle._utc_now = lambda: datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"

            state = self.lifecycle.mark_current_page(
                instance_root=instance_root,
                target_id="target-current-1",
                target_url="https://example.com/current",
                page_id="9",
            )

            self.assertEqual(calls, [])
            self.assertEqual(state["current_target_id"], "target-current-1")
            self.assertEqual(state["current_page_updated_at"], "2026-06-24T00:00:00Z")
            self.assertEqual(state["page_id_to_target_id"], {"9": "target-current-1"})
            self.assertEqual(state["targets"]["target-current-1"]["target_url"], "https://example.com/current")

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
                target_id="target-current-idle",
                target_url="https://example.com/current",
                page_id=3,
            )

            self.assertTrue(result["idle_refreshed"])
            self.assertEqual(calls[0]["schedule_key"], "browser.page.idle:target-current-idle")
            state = json.loads(self.lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(state["current_target_id"], "target-current-idle")
            self.assertEqual(state["page_id_to_target_id"], {"3": "target-current-idle"})
            self.assertEqual(state["targets"]["target-current-idle"]["target_url"], "https://example.com/current")

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
                    target_id="target-unmanaged",
                    target_url="https://example.com/unmanaged",
                )

            self.assertFalse(self.lifecycle.page_idle_state_file(instance_root).exists())

    def test_forget_page_idle_target_removes_target_mapping_and_current(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"
            self.lifecycle._write_page_idle_state(
                instance_root,
                {
                    "current_target_id": "target-forget",
                    "current_page_updated_at": "2026-06-24T00:00:00Z",
                    "targets": {
                        "target-forget": {
                            "target_id": "target-forget",
                            "target_url": "https://example.com/forget",
                            "last_used_at": "2026-06-24T00:00:00Z",
                            "page_id": "4",
                        },
                        "target-keep": {"target_id": "target-keep", "last_used_at": "2026-06-24T00:00:00Z"},
                    },
                    "page_id_to_target_id": {"4": "target-forget", "5": "target-keep"},
                },
            )

            state = self.lifecycle.forget_page_idle_target(instance_root=instance_root, target_id="target-forget")

            self.assertNotIn("target-forget", state["targets"])
            self.assertIn("target-keep", state["targets"])
            self.assertEqual(state["page_id_to_target_id"], {"5": "target-keep"})
            self.assertNotIn("current_target_id", state)
            persisted = json.loads(self.lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(persisted, state)

    def test_refresh_page_idle_rejects_blank_target_before_scheduling(self) -> None:
        calls: list[dict[str, object]] = []
        self.lifecycle.daemon_client.schedule_trigger = lambda **kwargs: calls.append(kwargs)

        with tempfile.TemporaryDirectory() as temp_root:
            with self.assertRaisesRegex(self.lifecycle.BrowserLifecycleError, "target_id"):
                self.lifecycle.refresh_page_idle(instance_root=Path(temp_root), target_id=" ")

        self.assertEqual(calls, [])

    def test_page_id_mapping_resolves_to_cdp_target_without_treating_page_id_as_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"

            self.lifecycle.mark_current_page(
                instance_root=instance_root,
                target_id="target-cdp-1",
                target_url="https://example.com/current",
                page_id=7,
            )

            self.assertEqual(self.lifecycle.current_target_id(instance_root), "target-cdp-1")
            self.assertEqual(self.lifecycle.target_id_for_page_id(instance_root, 7), "target-cdp-1")
            self.assertIsNone(self.lifecycle.target_id_for_page_id(instance_root, "target-cdp-1"))

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
    target_id="target-lock-wait",
    target_url="https://example.com/locked",
)
print("done", flush=True)
"""
            process = subprocess.Popen(
                [sys.executable, "-c", script, str(ROOT), str(instance_root)],
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
            self.assertEqual(state["current_target_id"], "target-lock-wait")


if __name__ == "__main__":
    unittest.main()
