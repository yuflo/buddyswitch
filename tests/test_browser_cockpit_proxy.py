#!/usr/bin/env python3
"""Tests for the BuddySwitch Chrome DevTools MCP focus-control proxy."""

from __future__ import annotations

import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib.util
import json
import os
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from itertools import count
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from runtime_kernel import protocol  # noqa: E402

PROXY = ROOT / "tools" / "launcher" / "chrome_devtools_cockpit_proxy.py"
DAEMON_CORE_PATH = ROOT / "tools" / "launcher" / "daemon_core.py"
DAEMON_MAILBOX_PATH = ROOT / "tools" / "launcher" / "daemon_mailbox.py"
MODULE_COUNTER = count()
WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
SOFT_PAGE_HINT_5 = "Browser pages: 5/10. Reuse or close pages before opening many more."
HARD_PAGE_BLOCK = (
    "Blocked: browser page limit reached (10/10). Close or reuse existing pages, then retry opening this URL."
)


def _page_targets(count: int, *, start: int = 0) -> list[dict[str, object]]:
    return [
        {
            "id": f"target-{index}",
            "type": "page",
            "url": f"https://example.com/page-{index}",
        }
        for index in range(start, start + count)
    ]


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


def _make_cdp_list_handler(state: dict[str, object]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            state.setdefault("requests", []).append({"method": "GET", "path": self.path})
            parsed = urlparse(self.path)
            if parsed.path == "/json/list":
                if state.get("list_fail"):
                    self.send_response(500)
                    self.end_headers()
                    return
                list_payloads = state.get("list_payloads")
                if isinstance(list_payloads, list) and list_payloads:
                    payload = list_payloads.pop(0)
                else:
                    payload = state.get("list_payload", state.get("targets", []))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(payload, ensure_ascii=True).encode("utf-8"))
                return
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
                if message.get("method") == "Target.createTarget":
                    params = message.get("params") if isinstance(message.get("params"), dict) else {}
                    target_id = state.get("create_target_id", "target-created")
                    if isinstance(target_id, str) and target_id:
                        targets = state.setdefault("targets", [])
                        if isinstance(targets, list):
                            targets.append(
                                {
                                    "id": target_id,
                                    "type": "page",
                                    "url": params.get("url"),
                                    "title": state.get("create_title", "Created"),
                                }
                            )
                    response = {"id": message.get("id"), "result": {"targetId": target_id}}
                else:
                    response = {"id": message.get("id"), "result": {"success": True}}
                _write_server_text_frame(self.wfile, json.dumps(response, ensure_ascii=True))
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return Handler


def load_module(path: Path) -> Any:
    module_name = f"buddyswitch_{path.stem}_{next(MODULE_COUNTER)}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BrowserCockpitProxyTests(unittest.TestCase):
    def _write_exec(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _write_fake_upstream(self, path: Path) -> None:
        self._write_exec(
            path,
            """#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


calls_path = Path(os.environ["BUDDYSWITCH_TEST_PROXY_CALLS"])
all_calls_path = Path(os.environ.get("BUDDYSWITCH_TEST_PROXY_ALL_CALLS", str(calls_path)))
argv_path = Path(os.environ["BUDDYSWITCH_TEST_PROXY_ARGV"])
calls_path.parent.mkdir(parents=True, exist_ok=True)
with argv_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(sys.argv[1:], ensure_ascii=True) + "\\n")

TOOLS = [
    {
        "name": "new_page",
        "description": "Open a new tab and load a URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "background": {
                    "type": "boolean",
                    "description": "Whether to open the page in the background without bringing it to the front.",
                },
                "isolatedContext": {"type": "string"},
            },
        },
    },
    {
        "name": "select_page",
        "description": "Select a page as a context for future tool calls.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pageId": {"type": "number"},
                "bringToFront": {
                    "type": "boolean",
                    "description": "Whether to focus the page and bring it to the top.",
                },
            },
        },
    },
]

initialized = False

for raw_line in sys.stdin:
    line = raw_line.strip()
    if not line:
        continue
    message = json.loads(line)
    with all_calls_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(message, ensure_ascii=True) + "\\n")

    request_id = message.get("id")
    method = message.get("method")
    if method == "tools/call":
        with calls_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(message, ensure_ascii=True) + "\\n")
    if request_id is None:
        if method == "notifications/initialized":
            initialized = True
        continue
    if method == "initialize":
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake-chrome-devtools-mcp", "version": "test"},
            },
        }
    elif method == "tools/list":
        response = {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    elif method == "tools/call":
        marker_snapshot = os.environ.get("BUDDYSWITCH_TEST_PROXY_MARKER_SNAPSHOT")
        instance_root = os.environ.get("BUDDYSWITCH_TEST_PROXY_INSTANCE_ROOT")
        if marker_snapshot and instance_root:
            pid_path = Path(instance_root) / "runtime" / "browser" / "cockpit-upstream.pid"
            pgid_path = Path(instance_root) / "runtime" / "browser" / "cockpit-upstream.pgid"
            for _ in range(50):
                if pid_path.exists() and pgid_path.exists():
                    break
                time.sleep(0.02)
            Path(marker_snapshot).write_text(
                json.dumps(
                    {
                        "pid": pid_path.read_text(encoding="ascii").strip() if pid_path.exists() else None,
                        "pgid": pgid_path.read_text(encoding="ascii").strip() if pgid_path.exists() else None,
                    },
                    ensure_ascii=True,
                )
                + "\\n",
                encoding="utf-8",
            )
        once_path = os.environ.get("BUDDYSWITCH_TEST_PROXY_EXIT_WITHOUT_RESPONSE_ONCE")
        if once_path and not Path(once_path).exists():
            Path(once_path).write_text("1\\n", encoding="utf-8")
            raise SystemExit(0)
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        if arguments.get("forceError"):
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": "failed " + str(params.get("name")),
                        }
                    ],
                    "isError": True,
                },
            }
            print(json.dumps(response, ensure_ascii=True), flush=True)
            if os.environ.get("BUDDYSWITCH_TEST_PROXY_EXIT_AFTER_RESPONSE") == "1":
                raise SystemExit(0)
            continue
        response_text = "called " + str(params.get("name"))
        if params.get("name") == "select_page":
            response_text = "Selected page: https://example.com/selected [selected]"
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": response_text,
                    }
                ]
            },
        }
    else:
        response = {"jsonrpc": "2.0", "id": request_id, "result": {}}
    print(json.dumps(response, ensure_ascii=True), flush=True)
    if method == "tools/call" and os.environ.get("BUDDYSWITCH_TEST_PROXY_EXIT_AFTER_RESPONSE") == "1":
        raise SystemExit(0)
""",
        )

    def _start_cdp_list_server(self, state: dict[str, object]) -> str:
        server = HTTPServer(("127.0.0.1", 0), _make_cdp_list_handler(state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}"

    def _start_fake_runtime_broker(self, *, socket_path: Path, browser_url: str, calls_path: Path) -> Any:
        stop = threading.Event()
        ready = threading.Event()
        browser_port = urlparse(browser_url).port
        if browser_port is None:
            raise AssertionError(f"test browser_url has no port: {browser_url}")
        try:
            socket_path.unlink()
        except FileNotFoundError:
            pass

        def append_call(request: dict[str, Any]) -> None:
            calls_path.parent.mkdir(parents=True, exist_ok=True)
            with calls_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(request, ensure_ascii=True) + "\n")

        def serve() -> None:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(socket_path))
                server.listen()
                server.settimeout(0.1)
                ready.set()
                while not stop.is_set():
                    try:
                        conn, _addr = server.accept()
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    with conn:
                        try:
                            request = protocol.read_message(conn)
                        except Exception:
                            continue
                        if not isinstance(request, dict):
                            continue
                        append_call(request)
                        request_id = request.get("request_id")
                        method = request.get("method")
                        if method == "browser.acquire":
                            response = {
                                "protocol": protocol.PROTOCOL,
                                "request_id": request_id,
                                "ok": True,
                                "result": {
                                    "ok": True,
                                    "browser_url": browser_url,
                                    "browser_port": browser_port,
                                    "ready": True,
                                    "state_changed": True,
                                    "durability": "runtime",
                                },
                            }
                        else:
                            response = {
                                "protocol": protocol.PROTOCOL,
                                "request_id": request_id,
                                "ok": False,
                                "error": {
                                    "code": "E_TEST_UNSUPPORTED_BROKER_METHOD",
                                    "message": f"unsupported fake broker method: {method}",
                                },
                                "permission_boundary": "test.fake_broker",
                                "state_changed": False,
                                "durability": "none",
                            }
                        protocol.write_message(conn, response)

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        if not ready.wait(timeout=5):
            raise AssertionError("fake runtime broker did not start")

        def stop_broker() -> None:
            stop.set()
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                    client.settimeout(0.1)
                    client.connect(str(socket_path))
            except OSError:
                pass
            thread.join(timeout=5)
            try:
                socket_path.unlink()
            except FileNotFoundError:
                pass

        return stop_broker

    def _run_proxy(
        self,
        messages: list[dict[str, Any]],
        *,
        browser_url: str | None = None,
        instance_root: Path | None = None,
        extra_env: dict[str, str] | None = None,
        clear_instance_root_env: bool = False,
        initial_browser_port_missing: bool = False,
        message_delay_seconds: float = 0.0,
        exit_without_response_once: bool = False,
        unset_env: list[str] | None = None,
        set_broker_socket_env: bool = True,
        pass_broker_socket_arg: bool = False,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], str]:
        self._last_proxy_all_calls: list[dict[str, Any]] = []
        self._last_proxy_marker_snapshot: dict[str, Any] = {}
        self._last_proxy_broker_calls: list[dict[str, Any]] = []
        if browser_url is None:
            browser_url = self._start_cdp_list_server({"requests": [], "targets": []})
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            if instance_root is None and not clear_instance_root_env:
                instance_root = temp_root_path / "instances" / "act-dev-browser"
            if instance_root is not None:
                browser_port = urlparse(browser_url).port
                if browser_port is None:
                    raise AssertionError(f"test browser_url has no port: {browser_url}")
                instance_root.mkdir(parents=True, exist_ok=True)
                (instance_root / "instance.json").write_text(
                    json.dumps(
                        {
                            "actor_id": "act-dev-browser",
                            "role": "dev",
                            "browser_port": None if initial_browser_port_missing else browser_port,
                        },
                        ensure_ascii=True,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            upstream = temp_root_path / "fake_upstream.py"
            calls_path = temp_root_path / "calls.jsonl"
            all_calls_path = temp_root_path / "all-calls.jsonl"
            argv_path = temp_root_path / "argv.jsonl"
            broker_calls_path = temp_root_path / "broker-calls.jsonl"
            broker_socket_path = temp_root_path / "runtime-broker.sock"
            marker_snapshot_path = temp_root_path / "marker-snapshot.json"
            exit_without_response_once_path = temp_root_path / "exit-without-response.once"
            self._write_fake_upstream(upstream)

            env = os.environ.copy()
            env["BUDDYSWITCH_TEST_PROXY_CALLS"] = str(calls_path)
            env["BUDDYSWITCH_TEST_PROXY_ALL_CALLS"] = str(all_calls_path)
            env["BUDDYSWITCH_TEST_PROXY_ARGV"] = str(argv_path)
            env["BUDDYSWITCH_TEST_PROXY_MARKER_SNAPSHOT"] = str(marker_snapshot_path)
            if set_broker_socket_env:
                env["BUDDYSWITCH_RUNTIME_BROKER_SOCKET"] = str(broker_socket_path)
            else:
                env.pop("BUDDYSWITCH_RUNTIME_BROKER_SOCKET", None)
            if instance_root is not None:
                env["BUDDYSWITCH_TEST_PROXY_INSTANCE_ROOT"] = str(instance_root)
            if exit_without_response_once:
                env["BUDDYSWITCH_TEST_PROXY_EXIT_WITHOUT_RESPONSE_ONCE"] = str(exit_without_response_once_path)
            if clear_instance_root_env:
                env.pop("BUDDYSWITCH_INSTANCE_ROOT", None)
            if unset_env:
                for key in unset_env:
                    env.pop(key, None)
            if extra_env:
                env.update(extra_env)
            broker_stop = self._start_fake_runtime_broker(
                socket_path=broker_socket_path,
                browser_url=browser_url,
                calls_path=broker_calls_path,
            )
            command = [
                sys.executable,
                str(PROXY),
                "--upstream-command",
                f"{sys.executable} {upstream}",
            ]
            if pass_broker_socket_arg:
                command.extend(["--broker-socket", str(broker_socket_path)])
            if instance_root is not None:
                command.append(f"--instance-root={instance_root}")
            proc = subprocess.Popen(
                command,
                cwd=ROOT,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            input_text = "".join(json.dumps(message, ensure_ascii=True) + "\n" for message in messages)
            try:
                if message_delay_seconds > 0:
                    assert proc.stdin is not None
                    assert proc.stdout is not None
                    assert proc.stderr is not None
                    for message in messages:
                        proc.stdin.write(json.dumps(message, ensure_ascii=True) + "\n")
                        proc.stdin.flush()
                        time.sleep(message_delay_seconds)
                    proc.stdin.close()
                    stdout = proc.stdout.read()
                    stderr = proc.stderr.read()
                    proc.stdout.close()
                    proc.stderr.close()
                    proc.wait(timeout=5)
                else:
                    stdout, stderr = proc.communicate(input=input_text, timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                stdout, stderr = proc.communicate()
                broker_stop()
                self.fail(f"proxy timed out\nstdout:\n{stdout}\nstderr:\n{stderr}")
            broker_stop()

            self.assertEqual(proc.returncode, 0, msg=f"proxy failed\nstdout:\n{stdout}\nstderr:\n{stderr}")
            responses = [json.loads(line) for line in stdout.splitlines() if line.strip()]
            forwarded = (
                [json.loads(line) for line in calls_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                if calls_path.exists()
                else []
            )
            self._last_proxy_all_calls = (
                [json.loads(line) for line in all_calls_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                if all_calls_path.exists()
                else []
            )
            self._last_proxy_marker_snapshot = (
                json.loads(marker_snapshot_path.read_text(encoding="utf-8"))
                if marker_snapshot_path.exists()
                else {}
            )
            self._last_proxy_broker_calls = (
                [json.loads(line) for line in broker_calls_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                if broker_calls_path.exists()
                else []
            )
            upstream_argv = json.loads(argv_path.read_text(encoding="utf-8").splitlines()[0]) if argv_path.exists() else []
            return responses, forwarded, upstream_argv, stderr

    def _single_call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

    def test_initialize_and_tools_list_do_not_start_upstream_without_browser_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            upstream = temp_root_path / "fake_upstream.py"
            calls_path = temp_root_path / "calls.jsonl"
            argv_path = temp_root_path / "argv.jsonl"
            instance_root = temp_root_path / "instance"
            instance_root.mkdir()
            self._write_fake_upstream(upstream)

            env = os.environ.copy()
            env["BUDDYSWITCH_TEST_PROXY_CALLS"] = str(calls_path)
            env["BUDDYSWITCH_TEST_PROXY_ARGV"] = str(argv_path)
            command = [
                sys.executable,
                str(PROXY),
                "--upstream-command",
                f"{sys.executable} {upstream}",
                f"--instance-root={instance_root}",
            ]
            proc = subprocess.Popen(
                command,
                cwd=ROOT,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            messages = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "test"}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            ]
            input_text = "".join(json.dumps(message, ensure_ascii=True) + "\n" for message in messages)
            try:
                stdout, stderr = proc.communicate(input=input_text, timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                stdout, stderr = proc.communicate()
                self.fail(f"proxy timed out\nstdout:\n{stdout}\nstderr:\n{stderr}")

            self.assertEqual(proc.returncode, 0, msg=f"proxy failed\nstdout:\n{stdout}\nstderr:\n{stderr}")
            self.assertFalse(argv_path.exists(), "initialize/tools-list must not spawn upstream")
            self.assertFalse(calls_path.exists(), "initialize/tools-list must not forward to upstream")
            responses = [json.loads(line) for line in stdout.splitlines() if line.strip()]
            self.assertEqual([response.get("id") for response in responses], [1, 2])
            self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "chrome-devtools-cockpit")
            tools = responses[1]["result"]["tools"]
            by_name = {tool["name"]: tool for tool in tools}
            self.assertIn("new_page", by_name)
            self.assertIn("BuddySwitch", json.dumps(by_name["new_page"], ensure_ascii=True))

    def test_tools_list_includes_buddyswitch_search_page(self) -> None:
        responses, _forwarded, _upstream_argv, _stderr = self._run_proxy(
            [{"jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": {}}]
        )

        tools = responses[0]["result"]["tools"]
        by_name = {tool["name"]: tool for tool in tools}
        self.assertIn("search_page", by_name)
        search_page = by_name["search_page"]
        self.assertIn("BuddySwitch", search_page.get("description", ""))
        self.assertIn("browser-session", search_page.get("description", ""))
        schema = search_page.get("inputSchema")
        self.assertIsInstance(schema, dict, msg=search_page)
        assert isinstance(schema, dict)
        self.assertEqual(schema.get("required"), ["query"])
        properties = schema.get("properties")
        self.assertIsInstance(properties, dict, msg=schema)
        assert isinstance(properties, dict)
        self.assertIn("query", properties)
        self.assertEqual(properties.get("engine", {}).get("enum"), ["google", "web", "reddit", "x"])

    def test_first_tools_call_uses_broker_acquire_not_ensure_subprocess(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": _page_targets(1)})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            responses, forwarded, upstream_argv, _stderr = self._run_proxy(
                [self._single_call("list_pages", {})],
                browser_url=browser_url,
                instance_root=instance_root,
                initial_browser_port_missing=True,
                extra_env={
                    "BUDDYSWITCH_TEST_PROXY_BROKER_BROWSER_URL": browser_url,
                },
            )

        self.assertEqual(responses[0]["id"], 1)
        self.assertEqual(len(forwarded), 1)
        self.assertEqual(forwarded[0]["params"]["name"], "list_pages")
        self.assertIn(f"--browser-url={browser_url}", upstream_argv)
        self.assertEqual([call.get("method") for call in self._last_proxy_broker_calls], ["browser.acquire"])
        broker_params = self._last_proxy_broker_calls[0].get("params")
        self.assertIsInstance(broker_params, dict, msg=self._last_proxy_broker_calls[0])
        assert isinstance(broker_params, dict)
        self.assertEqual(broker_params.get("reason"), "chrome-devtools-cockpit")
        broker_params_text = json.dumps(broker_params, ensure_ascii=True)
        self.assertNotIn("source_root", broker_params_text)
        self.assertNotIn("launcher_path", broker_params_text)
        self.assertNotIn("buddyswitch-" + "codex", broker_params_text)

    def test_broker_socket_arg_sets_runtime_broker_socket_for_first_tools_call(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": _page_targets(1)})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            responses, forwarded, upstream_argv, stderr = self._run_proxy(
                [self._single_call("list_pages", {})],
                browser_url=browser_url,
                instance_root=instance_root,
                initial_browser_port_missing=True,
                set_broker_socket_env=False,
                pass_broker_socket_arg=True,
            )

        self.assertEqual(stderr, "")
        self.assertEqual(responses[0]["id"], 1)
        self.assertFalse(responses[0].get("result", {}).get("isError", False), msg=responses[0])
        self.assertEqual(len(forwarded), 1)
        self.assertEqual(forwarded[0]["params"]["name"], "list_pages")
        self.assertIn(f"--browser-url={browser_url}", upstream_argv)
        self.assertEqual([call.get("method") for call in self._last_proxy_broker_calls], ["browser.acquire"])

    def test_invalid_json_before_upstream_does_not_start_upstream(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            upstream = temp_root_path / "fake_upstream.py"
            calls_path = temp_root_path / "calls.jsonl"
            argv_path = temp_root_path / "argv.jsonl"
            instance_root = temp_root_path / "instance"
            instance_root.mkdir()
            self._write_fake_upstream(upstream)

            env = os.environ.copy()
            env["BUDDYSWITCH_TEST_PROXY_CALLS"] = str(calls_path)
            env["BUDDYSWITCH_TEST_PROXY_ARGV"] = str(argv_path)
            command = [
                sys.executable,
                str(PROXY),
                "--upstream-command",
                f"{sys.executable} {upstream}",
                f"--instance-root={instance_root}",
            ]
            proc = subprocess.Popen(
                command,
                cwd=ROOT,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            try:
                stdout, stderr = proc.communicate(input="{not-json}\n", timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                stdout, stderr = proc.communicate()
                self.fail(f"proxy timed out\nstdout:\n{stdout}\nstderr:\n{stderr}")

            self.assertEqual(proc.returncode, 0, msg=f"proxy failed\nstdout:\n{stdout}\nstderr:\n{stderr}")
            self.assertEqual(stdout, "")
            self.assertFalse(argv_path.exists(), "invalid JSON before a tool call must not spawn upstream")

    def _start_mailbox(self, instance_root: Path, *, now: str = "2026-06-24T00:00:00Z") -> tuple[Any, Any, threading.Thread]:
        daemon_core = load_module(DAEMON_CORE_PATH)
        daemon_mailbox = load_module(DAEMON_MAILBOX_PATH)
        instance_root.mkdir(parents=True, exist_ok=True)
        state = daemon_core.DaemonState.load(
            instance_root=instance_root,
            actor_id="act-dev-browser",
            main_thread_id="thr-main",
        )
        server = daemon_mailbox.DaemonMailboxServer(
            socket_path=daemon_mailbox.mailbox_socket_path(instance_root),
            local_actor_address={"role_id": "dev", "actor_id": "act-dev-browser"},
            handlers=[],
            state=state,
            now=lambda: now,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.close)
        return daemon_core, server, thread

    def _write_page_idle_state(self, instance_root: Path, payload: dict[str, object]) -> None:
        state_path = instance_root / "runtime" / "browser" / "page_idle.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def test_first_tools_call_acquires_browser_and_starts_upstream(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": _page_targets(1)})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            responses, forwarded, upstream_argv, _stderr = self._run_proxy(
                [self._single_call("list_pages", {})],
                browser_url=browser_url,
                instance_root=instance_root,
                initial_browser_port_missing=True,
            )

        self.assertEqual(responses[0]["id"], 1)
        self.assertEqual(len(forwarded), 1)
        self.assertEqual(forwarded[0]["params"]["name"], "list_pages")
        self.assertIn(f"--browser-url={browser_url}", upstream_argv)
        self.assertEqual([call.get("method") for call in self._last_proxy_broker_calls], ["browser.acquire"])
        self.assertEqual(self._last_proxy_broker_calls[0].get("params"), {"reason": "chrome-devtools-cockpit"})
        self.assertEqual(
            [message.get("method") for message in self._last_proxy_all_calls],
            ["initialize", "notifications/initialized", "tools/call"],
        )
        self.assertNotEqual(self._last_proxy_all_calls[0].get("id"), responses[0].get("id"))
        self.assertTrue(self._last_proxy_marker_snapshot.get("pid"), msg=self._last_proxy_marker_snapshot)
        self.assertTrue(self._last_proxy_marker_snapshot.get("pgid"), msg=self._last_proxy_marker_snapshot)
        self.assertFalse((instance_root / "runtime" / "browser" / "cockpit-upstream.pid").exists())
        self.assertFalse((instance_root / "runtime" / "browser" / "cockpit-upstream.pgid").exists())

    def test_first_tools_call_broker_acquire_params_do_not_include_source_root_when_actor_home_is_bound(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": _page_targets(1)})

        with tempfile.TemporaryDirectory() as temp_root:
            shared_root = Path(temp_root) / ".codex-buddyswitch"
            instance_root = shared_root / "instances" / "act-dev-browser"
            responses, forwarded, upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/new"})],
                browser_url=browser_url,
                instance_root=instance_root,
                initial_browser_port_missing=True,
                extra_env={
                    "HOME": str(instance_root / "home"),
                    "CODEX_HOME": str(instance_root / "codex-home"),
                },
                unset_env=["BUDDYSWITCH_SHARED_ROOT", "BUDDYSWITCH_SOURCE_HOME"],
        )

        self.assertEqual(responses[0]["id"], 1)
        self.assertEqual(forwarded, [])
        self.assertEqual(upstream_argv, [])
        self.assertEqual([call.get("method") for call in self._last_proxy_broker_calls], ["browser.acquire"])
        broker_params_text = json.dumps(self._last_proxy_broker_calls[0].get("params"), ensure_ascii=True)
        self.assertNotIn(str(ROOT), broker_params_text)
        self.assertNotIn(str(shared_root), broker_params_text)
        self.assertNotIn(str(shared_root.parent), broker_params_text)
        self.assertNotIn("HOME", broker_params_text)
        self.assertNotIn("CODEX_HOME", broker_params_text)

    def test_new_page_opens_locally_through_browser_session_without_forwarding(self) -> None:
        cdp_state: dict[str, object] = {
            "requests": [],
            "targets": _page_targets(1),
            "create_target_id": "target-new-local",
        }
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            daemon_core, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/new"})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(forwarded, [])
            self.assertEqual(upstream_argv, [])
            response = responses[0]
            self.assertFalse(response["result"].get("isError", False), msg=response)
            text = response["result"]["content"][0]["text"]
            self.assertIn("browser-session", text)
            self.assertIn("opened", text)
            self.assertIn("https://example.com/new", text)
            self.assertIn("target-new-local", text)
            self.assertIn("40s", text)
            self.assertIn("2026-", text)
            saved = json.loads(daemon_core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["scheduled_triggers"]["schedule-1"]["schedule_key"], "browser.page.idle:target-new-local")
            page_idle = json.loads((instance_root / "runtime" / "browser" / "page_idle.json").read_text(encoding="utf-8"))
            self.assertEqual(page_idle["current_target_id"], "target-new-local")

        rpc_requests = cdp_state.get("rpc_requests")
        self.assertIsInstance(rpc_requests, list, msg=cdp_state)
        assert isinstance(rpc_requests, list)
        self.assertEqual([request.get("method") for request in rpc_requests], ["Target.createTarget"])

    def test_new_page_reuse_reports_browser_session_state_without_forwarding(self) -> None:
        target_url = "https://example.com/reuse"
        cdp_state: dict[str, object] = {
            "requests": [],
            "targets": _page_targets(1) + [{"id": "target-existing-local", "type": "page", "url": target_url}],
        }
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            daemon_core, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": target_url})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(forwarded, [])
            self.assertEqual(upstream_argv, [])
            response = responses[0]
            self.assertFalse(response["result"].get("isError", False), msg=response)
            text = response["result"]["content"][0]["text"]
            self.assertIn("browser-session", text)
            self.assertIn("reused", text)
            self.assertIn(target_url, text)
            self.assertIn("target-existing-local", text)
            self.assertIn("40s", text)
            saved = json.loads(daemon_core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["scheduled_triggers"]["schedule-1"]["schedule_key"], "browser.page.idle:target-existing-local")

        self.assertEqual(cdp_state.get("rpc_requests", []), [])

    def test_search_page_opens_locally_without_forwarding(self) -> None:
        cdp_state: dict[str, object] = {
            "requests": [],
            "targets": _page_targets(1),
            "create_target_id": "target-search-local",
        }
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            daemon_core, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, upstream_argv, _stderr = self._run_proxy(
                [self._single_call("search_page", {"query": "BuddySwitch browser resource lifecycle", "engine": "google"})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(forwarded, [])
            self.assertEqual(upstream_argv, [])
            response = responses[0]
            self.assertFalse(response["result"].get("isError", False), msg=response)
            text = response["result"]["content"][0]["text"]
            self.assertIn("browser-session", text)
            self.assertIn("search_page", text)
            self.assertIn("google", text)
            self.assertIn("https://www.google.com/search?q=BuddySwitch+browser+resource+lifecycle", text)
            self.assertIn("target-search-local", text)
            self.assertIn("40s", text)
            saved = json.loads(daemon_core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["scheduled_triggers"]["schedule-1"]["schedule_key"], "browser.page.idle:target-search-local")

        rpc_requests = cdp_state.get("rpc_requests")
        self.assertIsInstance(rpc_requests, list, msg=cdp_state)
        assert isinstance(rpc_requests, list)
        self.assertEqual([request.get("method") for request in rpc_requests], ["Target.createTarget"])

    def test_search_page_blank_query_is_rejected_locally(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "targets": _page_targets(1)}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            responses, forwarded, upstream_argv, _stderr = self._run_proxy(
                [self._single_call("search_page", {"query": "   ", "engine": "google"})],
                browser_url=browser_url,
                instance_root=Path(temp_root) / "instances" / "act-dev-browser",
            )

        self.assertEqual(forwarded, [])
        self.assertEqual(upstream_argv, [])
        response = responses[0]
        self.assertTrue(response["result"].get("isError"), msg=response)
        self.assertIn("query", response["result"]["content"][0]["text"])
        self.assertEqual(cdp_state.get("requests"), [])

    def test_search_page_rejects_unsupported_engine(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "targets": _page_targets(1)}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            responses, forwarded, upstream_argv, _stderr = self._run_proxy(
                [self._single_call("search_page", {"query": "BuddySwitch", "engine": "unknown"})],
                browser_url=browser_url,
                instance_root=Path(temp_root) / "instances" / "act-dev-browser",
            )

        self.assertEqual(forwarded, [])
        self.assertEqual(upstream_argv, [])
        response = responses[0]
        self.assertTrue(response["result"].get("isError"), msg=response)
        text = response["result"]["content"][0]["text"]
        self.assertIn("engine", text)
        self.assertIn("google", text)
        self.assertEqual(cdp_state.get("requests"), [])

    def test_search_page_builds_supported_engine_urls(self) -> None:
        expected_urls = {
            "google": "https://www.google.com/search?q=BuddySwitch+browser+resource+lifecycle",
            "web": "https://www.google.com/search?q=BuddySwitch+browser+resource+lifecycle",
            "reddit": "https://www.reddit.com/search/?q=BuddySwitch+browser+resource+lifecycle",
            "x": "https://x.com/search?q=BuddySwitch+browser+resource+lifecycle&src=typed_query",
        }
        for engine, expected_url in expected_urls.items():
            with self.subTest(engine=engine):
                cdp_state: dict[str, object] = {
                    "requests": [],
                    "targets": _page_targets(1),
                    "create_target_id": f"target-search-{engine}",
                }
                browser_url = self._start_cdp_list_server(cdp_state)

                with tempfile.TemporaryDirectory() as temp_root:
                    instance_root = Path(temp_root) / "instances" / f"act-dev-browser-{engine}"
                    daemon_core, server, thread = self._start_mailbox(instance_root)

                    responses, forwarded, upstream_argv, _stderr = self._run_proxy(
                        [
                            self._single_call(
                                "search_page",
                                {"query": "BuddySwitch browser resource lifecycle", "engine": engine},
                            )
                        ],
                        browser_url=browser_url,
                        instance_root=instance_root,
                    )
                    server.close()
                    thread.join(timeout=2)

                    self.assertEqual(forwarded, [])
                    self.assertEqual(upstream_argv, [])
                    response = responses[0]
                    self.assertFalse(response["result"].get("isError", False), msg=response)
                    text = response["result"]["content"][0]["text"]
                    self.assertIn(engine, text)
                    self.assertIn(expected_url, text)
                    self.assertIn(f"target-search-{engine}", text)
                    saved = json.loads(daemon_core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
                    self.assertEqual(
                        saved["scheduled_triggers"]["schedule-1"]["schedule_key"],
                        f"browser.page.idle:target-search-{engine}",
                    )

    def test_new_page_blank_url_is_rejected_locally(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "targets": _page_targets(1)}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            responses, forwarded, upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "   "})],
                browser_url=browser_url,
                instance_root=Path(temp_root) / "instances" / "act-dev-browser",
            )

        self.assertEqual(forwarded, [])
        self.assertEqual(upstream_argv, [])
        response = responses[0]
        self.assertTrue(response["result"].get("isError"), msg=response)
        self.assertIn("target_url", response["result"]["content"][0]["text"])
        self.assertEqual(cdp_state.get("requests"), [])

    def test_list_pages_appends_browser_session_state(self) -> None:
        cdp_state: dict[str, object] = {
            "requests": [],
            "targets": [
                {
                    "id": "target-current",
                    "type": "page",
                    "url": "https://example.com/current",
                    "title": "Current Title",
                }
            ],
        }
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_idle_state(
                instance_root,
                {
                    "current_target_id": "target-current",
                    "current_page_updated_at": "2026-07-01T00:00:00Z",
                    "targets": {
                        "target-current": {
                            "target_id": "target-current",
                            "target_url": "https://example.com/current",
                            "last_used_at": "2026-07-01T00:00:00Z",
                        }
                    },
                    "page_id_to_target_id": {},
                },
            )

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("list_pages", {})],
                browser_url=browser_url,
                instance_root=instance_root,
            )

        self.assertEqual(len(forwarded), 1)
        self.assertEqual(forwarded[0]["params"]["name"], "list_pages")
        text = "\n".join(item["text"] for item in responses[0]["result"]["content"] if item.get("type") == "text")
        self.assertIn("called list_pages", text)
        self.assertIn("BuddySwitch browser-session state:", text)
        self.assertIn("current_target_id: target-current", text)
        self.assertIn("target_id: target-current", text)
        self.assertIn("title: Current Title", text)
        self.assertIn("url: https://example.com/current", text)
        self.assertIn("current: true", text)
        self.assertIn("idle_expires_at: 2026-07-01T00:00:40Z", text)
        self.assertNotIn("Browser lifecycle warning:", text)

    def test_list_pages_with_no_tracked_pages_schedules_release(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": []})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            daemon_core, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("list_pages", {})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(len(forwarded), 1)
            self.assertEqual(forwarded[0]["params"]["name"], "list_pages")
            self.assertFalse(responses[0]["result"].get("isError", False), msg=responses[0])
            saved = json.loads(daemon_core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            release_schedules = [
                item
                for item in saved["scheduled_triggers"].values()
                if item["type"] == "browser.cockpit.release"
            ]
            self.assertEqual(len(release_schedules), 1)
            self.assertEqual(release_schedules[0]["payload"], {"reason": "page_idle_empty"})
            self.assertEqual(release_schedules[0]["schedule_key"], "browser.cockpit.release")

    def test_upstream_exit_does_not_stop_proxy_and_next_call_restarts(self) -> None:
        messages = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "list_pages", "arguments": {}},
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "close_page", "arguments": {"pageId": 1}},
            },
        ]

        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            messages,
            extra_env={"BUDDYSWITCH_TEST_PROXY_EXIT_AFTER_RESPONSE": "1"},
            message_delay_seconds=0.2,
        )

        self.assertEqual([response.get("id") for response in responses], [1, 2])
        self.assertEqual(
            [item["params"]["name"] for item in forwarded if item.get("method") == "tools/call"],
            ["list_pages", "close_page"],
        )

    def test_upstream_exit_during_request_returns_error_and_next_call_restarts(self) -> None:
        messages = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "list_pages", "arguments": {}},
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "close_page", "arguments": {"pageId": 1}},
            },
        ]

        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            messages,
            exit_without_response_once=True,
            message_delay_seconds=0.2,
        )

        self.assertEqual([response.get("id") for response in responses], [1, 2])
        self.assertTrue(responses[0]["result"].get("isError"), msg=responses[0])
        self.assertIn("exited", responses[0]["result"]["content"][0]["text"])
        self.assertFalse(responses[1]["result"].get("isError"), msg=responses[1])
        self.assertEqual(
            [item["params"]["name"] for item in forwarded if item.get("method") == "tools/call"],
            ["list_pages", "close_page"],
        )

    def test_new_page_below_hint_threshold_opens_without_page_hint(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": _page_targets(3), "create_target_id": "target-new-page"})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            _daemon_core, server, thread = self._start_mailbox(instance_root)
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/new"})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

        self.assertEqual(forwarded, [])
        self.assertNotIn("Browser pages:", json.dumps(responses, ensure_ascii=True))

    def test_new_page_refreshes_idle_with_explicit_instance_root_without_env(self) -> None:
        before = _page_targets(1)
        browser_url = self._start_cdp_list_server({"requests": [], "targets": before, "create_target_id": "target-new-page"})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            daemon_core, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/new"})],
                browser_url=browser_url,
                instance_root=instance_root,
                clear_instance_root_env=True,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(forwarded, [])
            self.assertIn("Browser page idle refreshed: 40s", json.dumps(responses, ensure_ascii=True))
            self.assertNotIn("TTL", json.dumps(responses, ensure_ascii=True))
            saved = json.loads(daemon_core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            schedule = saved["scheduled_triggers"]["schedule-1"]
            self.assertEqual(schedule["type"], "browser.page.expired")
            self.assertEqual(schedule["schedule_key"], "browser.page.idle:target-new-page")
            self.assertEqual(schedule["payload"]["target_id"], "target-new-page")
            self.assertEqual(schedule["payload"], {"target_id": "target-new-page"})
            page_idle = json.loads((instance_root / "runtime" / "browser" / "page_idle.json").read_text(encoding="utf-8"))
            self.assertEqual(page_idle["current_target_id"], "target-new-page")
            self.assertFalse(thread.is_alive())

    def test_new_page_without_instance_root_is_blocked_before_forwarding(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": []})

        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [self._single_call("new_page", {"url": "https://example.com/new"})],
            browser_url=browser_url,
            clear_instance_root_env=True,
        )

        self.assertEqual(forwarded, [])
        response = responses[0]
        self.assertIs(response["result"]["isError"], True)
        self.assertIn("--instance-root", response["result"]["content"][0]["text"])

    def test_new_page_registration_failure_closes_new_target_and_returns_error(self) -> None:
        before = _page_targets(1)
        cdp_state: dict[str, object] = {"requests": [], "targets": before, "create_target_id": "target-new-page"}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/new"})],
                browser_url=browser_url,
                instance_root=Path(temp_root) / "instances" / "act-dev-browser",
            )

        self.assertEqual(forwarded, [])
        response = responses[0]
        self.assertTrue(response["result"].get("isError"), msg=response)
        self.assertIn("registration_failed", response["result"]["content"][0]["text"])
        rpc_requests = cdp_state.get("rpc_requests")
        self.assertIsInstance(rpc_requests, list, msg=cdp_state)
        assert isinstance(rpc_requests, list)
        self.assertEqual([request.get("method") for request in rpc_requests], ["Target.createTarget", "Target.closeTarget"])
        self.assertEqual(rpc_requests[1].get("params"), {"targetId": "target-new-page"})

    def test_new_page_reuse_registration_failure_returns_error_without_forwarding(self) -> None:
        target_url = "https://example.com/new"
        cdp_state: dict[str, object] = {
            "requests": [],
            "targets": [{"id": "target-existing-page", "type": "page", "url": target_url}],
        }
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": target_url})],
                browser_url=browser_url,
                instance_root=Path(temp_root) / "instances" / "act-dev-browser",
            )

        self.assertEqual(forwarded, [])
        response = responses[0]
        self.assertTrue(response["result"].get("isError"), msg=response)
        self.assertIn("registration_failed", response["result"]["content"][0]["text"])
        self.assertEqual(cdp_state.get("rpc_requests", []), [])

    def test_new_page_reuse_refreshes_idle_without_forwarding(self) -> None:
        target_url = "https://example.com/new"
        targets = _page_targets(9) + [{"id": "target-existing-page", "type": "page", "url": target_url}]
        browser_url = self._start_cdp_list_server({"requests": [], "targets": targets})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            daemon_core, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": target_url})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(forwarded, [])
            self.assertIn("target-existing-page", json.dumps(responses, ensure_ascii=True))
            saved = json.loads(daemon_core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            schedule = saved["scheduled_triggers"]["schedule-1"]
            self.assertEqual(schedule["schedule_key"], "browser.page.idle:target-existing-page")
            self.assertEqual(schedule["payload"], {"target_id": "target-existing-page"})
            self.assertFalse(thread.is_alive())

    def test_select_page_refreshes_idle_for_resolved_page_id(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": _page_targets(1)})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_idle_state(
                instance_root,
                {
                    "current_target_id": "target-old",
                    "current_page_updated_at": "2026-06-23T00:00:00Z",
                    "targets": {
                        "target-select": {
                            "target_id": "target-select",
                            "target_url": "https://example.com/select",
                            "last_used_at": "2026-06-23T00:00:00Z",
                            "page_id": "3",
                        }
                    },
                    "page_id_to_target_id": {"3": "target-select"},
                },
            )
            daemon_core, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("select_page", {"pageId": 3, "bringToFront": True})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(responses[0]["id"], 1)
            self.assertEqual(forwarded[0]["params"]["arguments"]["bringToFront"], False)
            saved = json.loads(daemon_core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            schedule = saved["scheduled_triggers"]["schedule-1"]
            self.assertEqual(schedule["schedule_key"], "browser.page.idle:target-select")
            page_idle = json.loads((instance_root / "runtime" / "browser" / "page_idle.json").read_text(encoding="utf-8"))
            self.assertEqual(page_idle["current_target_id"], "target-select")
            self.assertFalse(thread.is_alive())

    def test_select_page_resolves_selected_url_when_page_id_mapping_is_empty(self) -> None:
        browser_url = self._start_cdp_list_server(
            {
                "requests": [],
                "targets": [
                    {
                        "id": "target-selected",
                        "type": "page",
                        "url": "https://example.com/selected",
                    }
                ],
            }
        )

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_idle_state(instance_root, {"targets": {}, "page_id_to_target_id": {}})
            daemon_core, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("select_page", {"pageId": 3, "bringToFront": True})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(responses[0]["id"], 1)
            self.assertEqual(forwarded[0]["params"]["arguments"]["bringToFront"], False)
            saved = json.loads(daemon_core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            schedule = saved["scheduled_triggers"]["schedule-1"]
            self.assertEqual(schedule["schedule_key"], "browser.page.idle:target-selected")
            page_idle = json.loads((instance_root / "runtime" / "browser" / "page_idle.json").read_text(encoding="utf-8"))
            self.assertEqual(page_idle["current_target_id"], "target-selected")
            self.assertEqual(page_idle["page_id_to_target_id"], {"3": "target-selected"})

    def test_select_page_ambiguous_selected_url_does_not_refresh_wrong_target(self) -> None:
        browser_url = self._start_cdp_list_server(
            {
                "requests": [],
                "targets": [
                    {"id": "target-selected-a", "type": "page", "url": "https://example.com/selected"},
                    {"id": "target-selected-b", "type": "page", "url": "https://example.com/selected"},
                ],
            }
        )

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_idle_state(instance_root, {"targets": {}, "page_id_to_target_id": {}})
            daemon_core, server, thread = self._start_mailbox(instance_root)

            responses, _forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("select_page", {"pageId": 3, "bringToFront": True})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertFalse(daemon_core.daemon_state_file(instance_root).exists())
            self.assertIn("lifecycle warning", json.dumps(responses, ensure_ascii=True).lower())
            page_idle = json.loads((instance_root / "runtime" / "browser" / "page_idle.json").read_text(encoding="utf-8"))
            self.assertNotIn("current_target_id", page_idle)

    def test_page_scoped_success_refreshes_current_page_idle(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": _page_targets(1)})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_idle_state(
                instance_root,
                {
                    "current_target_id": "target-current",
                    "current_page_updated_at": "2026-06-23T00:00:00Z",
                    "targets": {
                        "target-current": {
                            "target_id": "target-current",
                            "target_url": "https://example.com/current",
                            "last_used_at": "2026-06-23T00:00:00Z",
                        }
                    },
                    "page_id_to_target_id": {},
                },
            )
            daemon_core, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("take_snapshot", {})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(responses[0]["id"], 1)
            self.assertEqual(forwarded[0]["params"]["name"], "take_snapshot")
            saved = json.loads(daemon_core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            schedule = saved["scheduled_triggers"]["schedule-1"]
            self.assertEqual(schedule["schedule_key"], "browser.page.idle:target-current")
            self.assertEqual(schedule["payload"], {"target_id": "target-current"})
            self.assertFalse(thread.is_alive())

    def test_page_scoped_success_without_current_page_reports_lifecycle_warning(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": _page_targets(1)})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_idle_state(instance_root, {"targets": {}, "page_id_to_target_id": {}})
            daemon_core, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("take_snapshot", {})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(forwarded[0]["params"]["name"], "take_snapshot")
            self.assertFalse(daemon_core.daemon_state_file(instance_root).exists())
            self.assertIn("lifecycle warning", json.dumps(responses, ensure_ascii=True).lower())

    def test_non_page_use_and_failed_page_response_do_not_refresh_idle(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": _page_targets(1)})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_idle_state(
                instance_root,
                {
                    "current_target_id": "target-current",
                    "current_page_updated_at": "2026-06-23T00:00:00Z",
                    "targets": {"target-current": {"target_id": "target-current", "last_used_at": "2026-06-23T00:00:00Z"}},
                    "page_id_to_target_id": {},
                },
            )
            daemon_core, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [
                    {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_pages", "arguments": {}}},
                    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "close_page", "arguments": {"pageId": 3}}},
                    {
                        "jsonrpc": "2.0",
                        "id": 4,
                        "method": "tools/call",
                        "params": {"name": "take_snapshot", "arguments": {"forceError": True}},
                    },
                ],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual([response["id"] for response in responses], [1, 2, 3, 4])
            self.assertEqual([item["params"]["name"] for item in forwarded if item.get("method") == "tools/call"], ["list_pages", "close_page", "take_snapshot"])
            self.assertFalse(daemon_core.daemon_state_file(instance_root).exists())
            self.assertFalse(thread.is_alive())

    def test_new_page_reaching_hint_threshold_opens_and_appends_page_hint(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": _page_targets(4), "create_target_id": "target-new-page"})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            _daemon_core, server, thread = self._start_mailbox(instance_root)
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/new"})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

        self.assertEqual(forwarded, [])
        self.assertIn(SOFT_PAGE_HINT_5, json.dumps(responses, ensure_ascii=True))

    def test_new_page_blocks_locally_at_hard_page_limit_without_forwarding(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": _page_targets(10)})

        with tempfile.TemporaryDirectory() as temp_root:
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/new"})],
                browser_url=browser_url,
                instance_root=Path(temp_root) / "instances" / "act-dev-browser",
            )

        self.assertEqual(forwarded, [])
        response = responses[0]
        self.assertIs(response["result"]["isError"], True)
        self.assertIn(HARD_PAGE_BLOCK, response["result"]["content"][0]["text"])

    def test_new_page_reuses_exact_url_at_hard_page_limit_without_forwarding(self) -> None:
        target_url = "https://example.com/new"
        targets = _page_targets(9) + [{"id": "target-existing-page", "type": "page", "url": target_url}]
        browser_url = self._start_cdp_list_server({"requests": [], "targets": targets})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            _daemon_core, server, thread = self._start_mailbox(instance_root)
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": target_url})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

        self.assertEqual(forwarded, [])
        response = responses[0]
        self.assertFalse(response["result"].get("isError", False), msg=response)
        text = response["result"]["content"][0]["text"]
        self.assertIn("target-existing-page", text)
        self.assertIn("state: reused", text)

    def test_new_page_reports_page_count_verification_failure_without_forwarding(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "list_fail": True})

        with tempfile.TemporaryDirectory() as temp_root:
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/new"})],
                browser_url=browser_url,
                instance_root=Path(temp_root) / "instances" / "act-dev-browser",
            )

        self.assertEqual(forwarded, [])
        response = responses[0]
        self.assertIs(response["result"]["isError"], True)
        self.assertIn("page-count", response["result"]["content"][0]["text"].lower())

    def test_select_page_forces_no_bring_to_front(self) -> None:
        _responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [self._single_call("select_page", {"pageId": 3, "bringToFront": True})]
        )

        arguments = forwarded[0]["params"]["arguments"]
        self.assertEqual(arguments["pageId"], 3)
        self.assertIs(arguments["bringToFront"], False)

    def test_focus_rpc_methods_are_rejected_without_forwarding(self) -> None:
        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [
                {"jsonrpc": "2.0", "id": 1, "method": "Page.bringToFront", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "Target.activateTarget", "params": {}},
            ]
        )

        self.assertEqual(forwarded, [])
        by_id = {response["id"]: response for response in responses}
        for request_id, method in ((1, "Page.bringToFront"), (2, "Target.activateTarget")):
            with self.subTest(method=method):
                response = by_id[request_id]
                self.assertEqual(response["error"]["code"], -32000)
                self.assertIn(method, response["error"]["message"])
                self.assertIn("non-activating", response["error"]["message"])

    def test_new_page_isolated_context_is_rejected_without_forwarding(self) -> None:
        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [self._single_call("new_page", {"url": "https://example.com", "isolatedContext": "login"})]
        )

        self.assertEqual(forwarded, [])
        response = responses[0]
        self.assertEqual(response["id"], 1)
        result = response["result"]
        self.assertIs(result["isError"], True)
        self.assertIn("isolatedContext", result["content"][0]["text"])
        self.assertIn("non-activating", result["content"][0]["text"])

    def test_tools_list_patches_focus_sensitive_descriptions(self) -> None:
        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [{"jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": {}}]
        )

        self.assertEqual(forwarded, [])
        tools = responses[0]["result"]["tools"]
        by_name = {tool["name"]: tool for tool in tools}
        self.assertIn("BuddySwitch", json.dumps(by_name["new_page"], ensure_ascii=True))
        self.assertIn("browser-session", json.dumps(by_name["new_page"], ensure_ascii=True))
        self.assertIn("foreground activation", json.dumps(by_name["select_page"], ensure_ascii=True))


if __name__ == "__main__":
    unittest.main()
