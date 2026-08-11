"""Tests for the BuddySwitch Chrome DevTools MCP focus-control proxy."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib
import json
import os
import signal
import socket
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

from tests.support.python import PYTHON, executable_python_source


from tests.support.paths import REPO_ROOT
from tests.support.fake_cdp import (
    read_client_text_frame as _read_client_text_frame,
    websocket_accept_value as _websocket_accept_value,
    write_server_text_frame as _write_server_text_frame,
)
from tests.support.cli import write_executable

ROOT = REPO_ROOT
LAUNCHER = ROOT / "src" / "buddyswitch" / "launcher"

from buddyswitch.foundation.daemon import state as daemon_state  # noqa: E402
from buddyswitch.foundation.runtime_broker import protocol  # noqa: E402
import buddyswitch.foundation.process_runtime.json_framing as json_framing  # noqa: E402

PROXY = ROOT / "src" / "buddyswitch" / "foundation" / "browser_runtime" / "cockpit_proxy.py"
DAEMON_CORE_PATH = ROOT / "src" / "buddyswitch" / "foundation" / "daemon" / "instance.py"
DAEMON_MAILBOX_PATH = ROOT / "src" / "buddyswitch" / "foundation" / "daemon" / "mailbox.py"
MODULE_COUNTER = count()
SOFT_PAGE_HINT_5 = "Browser pages: 5/10. Reuse or close pages before opening many more."
HARD_PAGE_BLOCK = (
    "Blocked: browser page limit reached (10/10). Close or reuse existing pages, then retry opening this URL."
)
LEGACY_CURRENT_TARGET_FIELD = "current_" + "target_id"
LEGACY_PAGE_TARGET_MAP_FIELD = "page_id_to_" + "target_id"


def _page_targets(count: int, *, start: int = 0) -> list[dict[str, object]]:
    return [
        {
            "id": f"target-{index}",
            "type": "page",
            "url": f"https://example.com/page-{index}",
        }
        for index in range(start, start + count)
    ]


def _target_id_for_test(target: object) -> object:
    if not isinstance(target, dict):
        return None
    return target.get("targetId", target.get("id"))


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
                method = message.get("method")
                if method == "Target.getTargets":
                    list_payloads = state.get("list_payloads")
                    if isinstance(list_payloads, list) and list_payloads:
                        targets = list_payloads.pop(0)
                    else:
                        targets = state.get("list_payload", state.get("targets", []))
                    response = {"id": message.get("id"), "result": {"targetInfos": targets}}
                elif method == "Target.closeTarget" and state.get("close_error"):
                    response = {"id": message.get("id"), "error": {"message": str(state["close_error"])}}
                elif method == "Target.closeTarget":
                    params = message.get("params") if isinstance(message.get("params"), dict) else {}
                    target_id = params.get("targetId")
                    targets = state.get("targets")
                    if isinstance(targets, list):
                        state["targets"] = [target for target in targets if _target_id_for_test(target) != target_id]
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


def load_module(path: Path) -> Any:
    return importlib.reload(
        importlib.import_module(f"buddyswitch.foundation.daemon.{path.stem}")
    )


from tests.support.processes import ResourceLedger

class BrowserCockpitProxyHarness(unittest.TestCase):
    def _write_fake_upstream(self, path: Path) -> None:
        write_executable(
            path,
            executable_python_source(
                """
from __future__ import annotations

import json
import os
import sys
import time
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
        if params.get("name") == "get_tab_id":
            if os.environ.get("BUDDYSWITCH_TEST_PROXY_GET_TAB_ID_ERROR") == "1":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": "tab identity unavailable"}],
                        "isError": True,
                    },
                }
            else:
                page_id = arguments.get("pageId", "selected")
                tab_id = os.environ.get("BUDDYSWITCH_TEST_PROXY_TAB_ID") or ("stable-tab-" + str(page_id))
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": tab_id}],
                        "structuredContent": {"tabId": tab_id},
                    },
                }
            print(json.dumps(response, ensure_ascii=True), flush=True)
            continue
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
        if params.get("name") == "new_page" and os.environ.get("BUDDYSWITCH_TEST_PROXY_NEW_PAGE_ERROR_TEXT"):
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": os.environ["BUDDYSWITCH_TEST_PROXY_NEW_PAGE_ERROR_TEXT"],
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
        if params.get("name") == "new_page":
            response_text = os.environ.get("BUDDYSWITCH_TEST_PROXY_NEW_PAGE_TEXT", response_text)
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
                ],
                "structuredContent": {"publicTestField": "must-not-leak"},
            },
        }
    else:
        response = {"jsonrpc": "2.0", "id": request_id, "result": {}}
    print(json.dumps(response, ensure_ascii=True), flush=True)
    if method == "tools/call" and os.environ.get("BUDDYSWITCH_TEST_PROXY_EXIT_AFTER_RESPONSE") == "1":
        raise SystemExit(0)
"""
            ),
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
                            request = json_framing.read_message(conn)
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
                        json_framing.write_message(conn, response)

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
                ttl_config = instance_root.parent.parent / "config" / "browser.toml"
                ttl_config.parent.mkdir(parents=True, exist_ok=True)
                ttl_config.write_text(
                    "schema_version = 1\n\n[ttl]\npage_idle_seconds = 40\nrelease_delay_seconds = 10\n",
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
                PYTHON,
                str(PROXY),
                "--upstream-command",
                f"{PYTHON} {upstream}",
            ]
            if pass_broker_socket_arg:
                command.extend(["--broker-socket", str(broker_socket_path)])
            if instance_root is not None:
                command.append(f"--instance-root={instance_root}")
            proc = ResourceLedger.from_environment().start_process(
                command,
                cwd=ROOT,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
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
            all_forwarded = (
                [json.loads(line) for line in calls_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                if calls_path.exists()
                else []
            )
            forwarded = [
                call
                for call in all_forwarded
                if not str(call.get("id", "")).startswith("buddyswitch.internal.")
            ]
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
    def _assert_only_cleanup_snapshot_reads(self, cdp_state: dict[str, object]) -> None:
        rpc_requests = cdp_state.get("rpc_requests", [])
        self.assertIsInstance(rpc_requests, list, msg=rpc_requests)
        assert isinstance(rpc_requests, list)
        self.assertTrue(rpc_requests, msg="new-page cleanup ownership snapshot was not taken")
        self.assertTrue(
            all(request.get("method") == "Target.getTargets" for request in rpc_requests),
            msg=rpc_requests,
        )
    def _start_mailbox(self, instance_root: Path, *, now: str = "2026-06-24T00:00:00Z") -> tuple[Any, Any, threading.Thread]:
        instance = load_module(DAEMON_CORE_PATH)
        mailbox = load_module(DAEMON_MAILBOX_PATH)
        instance_root.mkdir(parents=True, exist_ok=True)
        state = daemon_state.DaemonState.load(
            instance_root=instance_root,
            actor_id="act-dev-browser",
            main_thread_id="thr-main",
        )
        server = mailbox.DaemonMailboxServer(
            socket_path=mailbox.mailbox_socket_path(instance_root),
            local_identity_id="act-dev-browser",
            local_role_id="dev",
            handlers=[],
            state=state,
            now=lambda: now,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.close)
        return instance, server, thread
    def _write_page_idle_state(self, instance_root: Path, payload: dict[str, object]) -> None:
        state_path = instance_root / "runtime" / "browser" / "page_idle.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

__all__ = [name for name in globals() if not name.startswith('__')]
