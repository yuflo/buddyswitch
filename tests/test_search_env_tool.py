#!/usr/bin/env python3
"""Tests for broker-routed search env tool behavior."""

from __future__ import annotations

import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
from env.tool_runtime.registry import dispatch_env_tool_request  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


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
            if parsed.path == "/json/version":
                if state.get("version_fail"):
                    self.send_response(500)
                    self.end_headers()
                    return
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
                if state.get("fail"):
                    response = {
                        "id": message.get("id"),
                        "error": {"code": -32000, "message": "simulated cdp create target failure"},
                    }
                else:
                    response = {"id": message.get("id"), "result": {"targetId": "target-search"}}
                _write_server_text_frame(self.wfile, json.dumps(response, ensure_ascii=True))
                return

            self.send_response(404)
            self.end_headers()

        def do_PUT(self) -> None:  # noqa: N802
            state.setdefault("requests", []).append({"method": "PUT", "path": self.path})
            self.send_response(500)
            self.end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return Handler


class SearchEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(
        self,
        *,
        instance_id: str = "inst-search-example",
        buddy: str = "market",
        browser_port: object = 9222,
    ) -> Path:
        instance_json = self._runtime_path(f"{instance_id}.json")
        instance_json.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": "active",
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": browser_port,
                    "created_at": "2026-05-13T00:00:00Z",
                    "updated_at": "2026-05-13T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _dispatch(
        self,
        *,
        action: str,
        args: dict[str, object],
        instance_json: Path,
        instance_id: str = "inst-search-example",
        buddy: str = "market",
    ) -> dict[str, object]:
        manifest = env_manifest.load_manifest(MANIFEST)
        instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
        return dispatch_env_tool_request(
            payload={"tool": "search", "action": action, "args": args},
            active_buddy=buddy,
            instance_id=instance_id,
            instance_json=instance_json,
            instance_payload=instance_payload,
            manifest=manifest,
            manifest_path=MANIFEST,
        )

    def _start_cdp_server(self, state: dict[str, object]) -> tuple[HTTPServer, threading.Thread, int]:
        server = HTTPServer(("127.0.0.1", 0), _make_cdp_handler(state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        return server, thread, int(server.server_port)

    def test_search_cli_help_exposes_status_request_and_open_browser(self) -> None:
        resource_help = subprocess.run(
            ["python3", "scripts/env/client.py", "search", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(resource_help.returncode, 0, msg=resource_help.stderr)
        self.assertIn("status", resource_help.stdout)
        self.assertIn("request", resource_help.stdout)
        self.assertIn("open-browser", resource_help.stdout)
        self.assertNotIn("--query", resource_help.stdout)
        self.assertNotIn("--backend", resource_help.stdout)
        self.assertNotIn("--engine", resource_help.stdout)

        action_help = subprocess.run(
            ["python3", "scripts/env/client.py", "search", "request", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(action_help.returncode, 0, msg=action_help.stderr)
        self.assertIn("--payload", action_help.stdout)

    def test_search_cli_rejects_missing_backend_and_unknown_engine(self) -> None:
        missing_backend = subprocess.run(
            ["python3", "scripts/env/client.py", "search", "request", "--payload", '{"query":"x"}'],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(missing_backend.returncode, 1)
        missing_backend_payload = json.loads(missing_backend.stdout)
        self.assertFalse(missing_backend_payload.get("ok"), msg=missing_backend_payload)
        self.assertEqual((missing_backend_payload.get("error") or {}).get("code"), "E_RUNTIME_BROKER_UNAVAILABLE")

        unknown_engine = subprocess.run(
            [
                "python3",
                "scripts/env/client.py",
                "search",
                "open-browser",
                "--payload",
                '{"query":"x","engine":"unknown"}',
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(unknown_engine.returncode, 1)
        unknown_engine_payload = json.loads(unknown_engine.stdout)
        self.assertFalse(unknown_engine_payload.get("ok"), msg=unknown_engine_payload)
        self.assertEqual((unknown_engine_payload.get("error") or {}).get("code"), "E_RUNTIME_BROKER_UNAVAILABLE")

    def test_search_status_reports_market_profile_backend_and_native_search_boundary(self) -> None:
        instance_json = self._instance_json(buddy="market", browser_port=9222)

        response = self._dispatch(action="status", args={}, instance_json=instance_json, buddy="market")

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("tool"), "search")
        self.assertEqual(response.get("action"), "search.status")
        self.assertEqual(response.get("active_buddy"), "market")
        self.assertEqual(response.get("native_codex_web_search"), "disabled")
        self.assertEqual(response.get("available_backends"), ["browser"])
        backend_status = response.get("backend_status")
        self.assertIsInstance(backend_status, dict, msg=response)
        assert isinstance(backend_status, dict)
        self.assertEqual(backend_status["browser"]["available"], True)
        self.assertEqual(backend_status["browser"]["browser_url"], "http://127.0.0.1:9222")
        self.assertEqual(backend_status["search_api"]["available"], False)
        self.assertEqual(backend_status["search_api"]["permission"], "user-approved-only")
        self.assertEqual(
            response.get("capability_boundary"),
            {
                "native_codex_web_search": "disabled",
                "browser_cockpit": "required",
                "search_api": "user-approved-only",
            },
        )
        self.assertIn("permission_boundary", response)
        self.assertIn("allowed_next_actions", response)
        self.assertIn("command_hint", response)
        self.assertNotIn("preferred_backend", response)
        self.assertNotIn("market_workflow", response)

    def test_search_status_reports_non_market_boundary_without_market_workflow_default(self) -> None:
        instance_json = self._instance_json(buddy="dev", browser_port=9222)

        response = self._dispatch(action="status", args={}, instance_json=instance_json, buddy="dev")

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("capability_boundary", {}).get("browser_cockpit"), "available")
        self.assertEqual(response.get("capability_boundary", {}).get("search_api"), "available")
        for forbidden in ("market_workflow", "browser_native_required_by_market", "preferred_backend"):
            self.assertNotIn(forbidden, response)

    def test_search_request_browser_returns_actionable_instruction_without_opening_page(self) -> None:
        instance_json = self._instance_json(buddy="market", browser_port=9222)

        response = self._dispatch(
            action="request",
            args={"query": "creator analytics pain", "backend": "browser", "engine": "reddit"},
            instance_json=instance_json,
            buddy="market",
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("backend"), "browser")
        self.assertEqual(response.get("engine"), "reddit")
        self.assertEqual(response.get("query"), "creator analytics pain")
        self.assertEqual(response.get("target_url"), "https://www.reddit.com/search/?q=creator+analytics+pain")
        self.assertEqual(response.get("browser_endpoint"), "http://127.0.0.1:9222")
        self.assertEqual(response.get("required_cockpit_tool"), "chrome-devtools-cockpit")
        self.assertEqual(response.get("page_opened"), False)
        self.assertNotIn("tool_evidence", response)
        self.assertIn("search.open_browser", " ".join(response.get("allowed_next_actions", [])))

    def test_search_request_command_hint_does_not_echo_raw_query(self) -> None:
        instance_json = self._instance_json(browser_port=9222)
        query = "creator' && echo pwned"
        response = self._dispatch(
            action="request",
            args={"query": query, "backend": "browser", "engine": "google"},
            instance_json=instance_json,
        )
        self.assertTrue(response.get("ok"), msg=response)
        command_hint = response.get("command_hint")
        self.assertIsInstance(command_hint, str, msg=response)
        assert isinstance(command_hint, str)
        self.assertIn("--payload", command_hint)
        self.assertIn('"query":"<query>"', command_hint)
        self.assertIn('"engine":"google"', command_hint)
        self.assertNotIn(query, command_hint)
        self.assertNotIn("&&", command_hint)

    def test_search_request_browser_builds_expected_url_for_supported_engines(self) -> None:
        instance_json = self._instance_json(browser_port=9222)
        expected = {
            "google": "https://www.google.com/search?q=creator+analytics+pain",
            "web": "https://www.google.com/search?q=creator+analytics+pain",
            "reddit": "https://www.reddit.com/search/?q=creator+analytics+pain",
            "x": "https://x.com/search?q=creator+analytics+pain&src=typed_query",
        }

        for engine, target_url in expected.items():
            with self.subTest(engine=engine):
                response = self._dispatch(
                    action="request",
                    args={"query": "creator analytics pain", "backend": "browser", "engine": engine},
                    instance_json=instance_json,
                )
                self.assertTrue(response.get("ok"), msg=response)
                self.assertEqual(response.get("target_url"), target_url)

    def test_search_request_rejects_missing_or_unknown_backend(self) -> None:
        instance_json = self._instance_json()
        for args in ({"query": "x"}, {"query": "x", "backend": "auto"}):
            with self.subTest(args=args):
                response = self._dispatch(action="request", args=args, instance_json=instance_json)
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual(response.get("error", {}).get("code"), "E_SEARCH_BACKEND")
                self.assertEqual(response.get("allowed_backends"), ["browser", "search_api"])
                self.assertIn("permission_boundary", response)
                self.assertIn("allowed_next_actions", response)
                self.assertIn("command_hint", response)

    def test_search_request_rejects_empty_null_and_non_string_backend(self) -> None:
        instance_json = self._instance_json()
        for backend in ("", None, []):
            with self.subTest(backend=backend):
                response = self._dispatch(
                    action="request",
                    args={"query": "x", "backend": backend},
                    instance_json=instance_json,
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual(response.get("error", {}).get("code"), "E_SEARCH_BACKEND")

    def test_search_request_search_api_returns_market_approval_required(self) -> None:
        instance_json = self._instance_json(buddy="market")

        response = self._dispatch(
            action="request",
            args={"query": "creator analytics pain", "backend": "search_api", "engine": "web"},
            instance_json=instance_json,
            buddy="market",
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("error", {}).get("code"), "E_SEARCH_BACKEND_APPROVAL_REQUIRED")
        self.assertEqual(response.get("permission_boundary"), "search.search_api.user_approved_only")
        self.assertIn("search open-browser", str(response.get("command_hint")))

    def test_search_request_search_api_returns_non_market_provider_unavailable(self) -> None:
        instance_json = self._instance_json(buddy="dev")

        response = self._dispatch(
            action="request",
            args={"query": "release notes", "backend": "search_api", "engine": "web"},
            instance_json=instance_json,
            buddy="dev",
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("error", {}).get("code"), "E_SEARCH_BACKEND_UNAVAILABLE")
        self.assertIn("No BuddySwitch-managed search API provider is configured", response.get("reason", ""))

    def test_search_open_browser_creates_background_cdp_target(self) -> None:
        state: dict[str, object] = {"requests": []}
        _server, _thread, port = self._start_cdp_server(state)
        instance_json = self._instance_json(browser_port=port)

        response = self._dispatch(
            action="open_browser",
            args={"query": "creator analytics pain", "engine": "google"},
            instance_json=instance_json,
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("page_opened"), True)
        target_url = "https://www.google.com/search?q=creator+analytics+pain"
        self.assertEqual(response.get("target_url"), target_url)
        requests = state.get("requests")
        self.assertIsInstance(requests, list, msg=state)
        assert isinstance(requests, list)
        self.assertFalse(any(urlparse(request["path"]).path == "/json/new" for request in requests))
        rpc_requests = state.get("rpc_requests")
        self.assertIsInstance(rpc_requests, list, msg=state)
        assert isinstance(rpc_requests, list)
        self.assertEqual(len(rpc_requests), 1)
        rpc = rpc_requests[0]
        self.assertEqual(rpc.get("method"), "Target.createTarget")
        params = rpc.get("params")
        self.assertIsInstance(params, dict, msg=rpc)
        assert isinstance(params, dict)
        self.assertEqual(params.get("url"), target_url)
        self.assertIs(params.get("background"), True)

    def test_search_open_browser_encodes_queries_for_supported_engines(self) -> None:
        cases = (
            ("google", "a+b & c", "https://www.google.com/search?q=a%2Bb+%26+c"),
            ("web", "creator analytics pain", "https://www.google.com/search?q=creator+analytics+pain"),
            ("reddit", "a+b & c", "https://www.reddit.com/search/?q=a%2Bb+%26+c"),
            ("x", "\u7528\u6237 \u8bbf\u8c08", "https://x.com/search?q=%E7%94%A8%E6%88%B7+%E8%AE%BF%E8%B0%88&src=typed_query"),
        )
        for engine, query, expected_target_url in cases:
            with self.subTest(engine=engine, query=query):
                state: dict[str, object] = {"requests": []}
                _server, _thread, port = self._start_cdp_server(state)
                instance_json = self._instance_json(browser_port=port)
                response = self._dispatch(
                    action="open_browser",
                    args={"query": query, "engine": engine},
                    instance_json=instance_json,
                )
                self.assertTrue(response.get("ok"), msg=response)
                self.assertEqual(response.get("target_url"), expected_target_url)
                requests = state.get("requests")
                self.assertIsInstance(requests, list, msg=state)
                assert isinstance(requests, list)
                self.assertFalse(any(urlparse(request["path"]).path == "/json/new" for request in requests))
                rpc_requests = state.get("rpc_requests")
                self.assertIsInstance(rpc_requests, list, msg=state)
                assert isinstance(rpc_requests, list)
                params = rpc_requests[0]["params"]
                self.assertEqual(params["url"], expected_target_url)
                self.assertIs(params["background"], True)

    def test_search_open_browser_returns_recovery_feedback_when_browser_missing(self) -> None:
        instance_json = self._instance_json(browser_port=None)

        response = self._dispatch(
            action="open_browser",
            args={"query": "creator analytics pain", "engine": "google"},
            instance_json=instance_json,
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("error", {}).get("code"), "E_SEARCH_BROWSER_UNAVAILABLE")
        self.assertEqual(
            response.get("command_hint"),
            "./buddyswitch-codex env browser ensure --instance inst-search-example",
        )

    def test_search_open_browser_reports_cdp_open_failure_with_target_url(self) -> None:
        state: dict[str, object] = {"requests": [], "fail": True}
        _server, _thread, port = self._start_cdp_server(state)
        instance_json = self._instance_json(browser_port=port)

        response = self._dispatch(
            action="open_browser",
            args={"query": "creator analytics pain", "engine": "google"},
            instance_json=instance_json,
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("error", {}).get("code"), "E_SEARCH_BROWSER_OPEN_FAILED")
        self.assertEqual(response.get("target_url"), "https://www.google.com/search?q=creator+analytics+pain")
        self.assertEqual(response.get("browser_endpoint"), f"http://127.0.0.1:{port}")

    def test_search_source_has_no_direct_json_new_page_open(self) -> None:
        text = (ROOT / "scripts" / "env" / "tools" / "search" / "_impl.py").read_text(encoding="utf-8")
        self.assertNotIn("/json/new", text)
        self.assertNotIn('"tools"', text)
        self.assertNotIn('"launcher"', text)
        self.assertNotIn("tools" + "/launcher", text)
        self.assertIn('"scripts"', text)
        self.assertIn('"env"', text)
        self.assertIn("cdp_background_page.py", text)
        self.assertTrue((ROOT / "scripts" / "env" / "cdp_background_page.py").exists())
        self.assertFalse((ROOT / "tools" / "launcher" / "cdp_background_page.py").exists())

    def test_search_open_browser_rejects_invalid_browser_port(self) -> None:
        for port in ("abc", 0, 70000):
            with self.subTest(port=port):
                instance_json = self._instance_json(browser_port=port)
                response = self._dispatch(
                    action="open_browser",
                    args={"query": "creator analytics pain", "engine": "google"},
                    instance_json=instance_json,
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual(response.get("error", {}).get("code"), "E_SEARCH_BROWSER_UNAVAILABLE")
                self.assertIn("invalid", response.get("reason", ""))

    def test_search_rejects_empty_query_and_unknown_engine(self) -> None:
        instance_json = self._instance_json()
        bad_query_cases = ("", "   ", [])
        for query in bad_query_cases:
            with self.subTest(query=query):
                response = self._dispatch(
                    action="request",
                    args={"query": query, "backend": "browser", "engine": "google"},
                    instance_json=instance_json,
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual(response.get("error", {}).get("code"), "E_SEARCH_QUERY")

        for engine in ("", "bing"):
            with self.subTest(engine=engine):
                response = self._dispatch(
                    action="open_browser",
                    args={"query": "x", "engine": engine},
                    instance_json=instance_json,
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual(response.get("error", {}).get("code"), "E_SEARCH_ENGINE")
                self.assertEqual(response.get("allowed_engines"), ["google", "web", "reddit", "x"])

    def test_browser_and_search_dependency_rejections_include_semantic_impact(self) -> None:
        self.test_search_request_search_api_returns_market_approval_required()
        self.test_search_request_search_api_returns_non_market_provider_unavailable()
        self.test_search_open_browser_returns_recovery_feedback_when_browser_missing()
        self.test_search_open_browser_reports_cdp_open_failure_with_target_url()


if __name__ == "__main__":
    unittest.main()
