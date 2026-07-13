"""Tests for the BuddySwitch Codex app-server client."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import queue
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_SERVER_PATH = ROOT / "tools" / "launcher" / "app_server.py"
APP_SERVER_SHELL_PATH = ROOT / "tools" / "launcher" / "app_server.sh"
SPEC = importlib.util.spec_from_file_location("buddyswitch_launcher_app_server", APP_SERVER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load spec for {APP_SERVER_PATH}")
APP_SERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(APP_SERVER)
from tests.python_runtime import PYTHON  # noqa: E402


class FakeUnixWebSocketServer:
    def __init__(self, socket_path: Path) -> None:
        self.socket_path = socket_path
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._client: socket.socket | None = None
        self._incoming: queue.Queue[dict[str, object]] = queue.Queue()
        self._stop = threading.Event()
        self._handshake_headers: str | None = None
        self.close_received = threading.Event()
        self.close_response_sent = threading.Event()
        self.close_response_delay_seconds = 0.0

    def start(self) -> None:
        if self.socket_path.exists():
            self.socket_path.unlink()
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(str(self.socket_path))
        self._server.listen(1)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._client is not None:
            try:
                self._client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._client.close()
            self._client = None
        if self._server is not None:
            self._server.close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        self.socket_path.unlink(missing_ok=True)

    @property
    def handshake_headers(self) -> str:
        assert self._handshake_headers is not None
        return self._handshake_headers

    def next_message(self, timeout: float = 2.0) -> dict[str, object]:
        return self._incoming.get(timeout=timeout)

    def send_json(self, payload: dict[str, object]) -> None:
        self._send_text(json.dumps(payload, ensure_ascii=True))

    def send_notification(self, method: str, params: dict[str, object] | None = None) -> None:
        payload: dict[str, object] = {"method": method}
        if params is not None:
            payload["params"] = params
        self.send_json(payload)

    def send_response(self, request_id: object, result: dict[str, object]) -> None:
        self.send_json({"id": request_id, "result": result})

    def send_error(self, request_id: object, *, code: int, message: str) -> None:
        self.send_json({"id": request_id, "error": {"code": code, "message": message}})

    def send_ping(self, payload: bytes = b"ping") -> None:
        self._send_frame(0x9, payload)

    def send_close(self, payload: bytes = b"") -> None:
        self._send_frame(0x8, payload)

    def send_binary(self, payload: bytes) -> None:
        self._send_frame(0x2, payload)

    def _serve(self) -> None:
        assert self._server is not None
        client, _addr = self._server.accept()
        self._client = client
        client.settimeout(2.0)
        self._handshake_headers = self._read_http_request(client)
        key = self._extract_sec_websocket_key(self._handshake_headers)
        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        client.sendall(
            (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n"
                "\r\n"
            ).encode("ascii")
        )
        while not self._stop.is_set():
            try:
                opcode, payload = self._read_frame(client)
            except (EOFError, OSError, TimeoutError):
                return
            if opcode == 0x1:
                self._incoming.put(json.loads(payload.decode("utf-8")))
            elif opcode == 0x9:
                self._send_frame(0xA, payload)
            elif opcode == 0x8:
                self.close_received.set()
                if self.close_response_delay_seconds > 0:
                    time.sleep(self.close_response_delay_seconds)
                self._send_frame(0x8, payload)
                self.close_response_sent.set()
                return

    @staticmethod
    def _read_http_request(sock: socket.socket) -> str:
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                raise EOFError("client closed before handshake")
            data += chunk
        return data.decode("ascii")

    @staticmethod
    def _extract_sec_websocket_key(headers: str) -> str:
        for line in headers.split("\r\n"):
            if line.lower().startswith("sec-websocket-key:"):
                return line.split(":", 1)[1].strip()
        raise AssertionError("Missing Sec-WebSocket-Key header")

    @staticmethod
    def _read_exact(sock: socket.socket, size: int) -> bytes:
        data = b""
        while len(data) < size:
            chunk = sock.recv(size - len(data))
            if not chunk:
                raise EOFError("socket closed")
            data += chunk
        return data

    def _read_frame(self, sock: socket.socket) -> tuple[int, bytes]:
        first, second = self._read_exact(sock, 2)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = int.from_bytes(self._read_exact(sock, 2), "big")
        elif length == 127:
            length = int.from_bytes(self._read_exact(sock, 8), "big")
        mask = self._read_exact(sock, 4) if masked else b""
        payload = self._read_exact(sock, length)
        if masked:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return opcode, payload

    def _send_text(self, payload: str) -> None:
        self._send_frame(0x1, payload.encode("utf-8"))

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        if self._client is None:
            return
        first = 0x80 | opcode
        length = len(payload)
        if length < 126:
            header = bytes([first, length])
        elif length < (1 << 16):
            header = bytes([first, 126]) + length.to_bytes(2, "big")
        else:
            header = bytes([first, 127]) + length.to_bytes(8, "big")
        try:
            self._client.sendall(header + payload)
        except OSError:
            return


class AppServerClientTests(unittest.TestCase):
    @staticmethod
    def _pid_is_live(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def _socket_path(self, temp_root: Path, name: str = "app-server.sock") -> Path:
        return temp_root / name

    def _initialize_client(
        self,
        client: object,
        server: FakeUnixWebSocketServer,
    ) -> tuple[dict[str, object], list[dict[str, object]], list[BaseException]]:
        results: list[dict[str, object]] = []
        errors: list[BaseException] = []

        def run_initialize() -> None:
            try:
                results.append(client.initialize())
            except BaseException as exc:  # pragma: no cover - exercised on failures
                errors.append(exc)

        init_thread = threading.Thread(target=run_initialize, daemon=True)
        init_thread.start()
        init = server.next_message()
        self.assertEqual(init["method"], "initialize")
        server.send_response(init["id"], {"userAgent": "codex/1.0.0"})
        self.assertEqual(server.next_message()["method"], "initialized")
        init_thread.join(timeout=2)
        return init, results, errors

    def test_initialize_sends_client_info_and_initialized_notification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)

            client = APP_SERVER.AppServerClient(socket_path, timeout_seconds=2.0)
            client.connect()
            self.addCleanup(client.close)

            init, init_results, init_errors = self._initialize_client(client, server)
            params = init["params"]
            assert isinstance(params, dict)
            self.assertEqual(params["clientInfo"]["name"], "buddyswitch_launcher")
            self.assertTrue(params["capabilities"]["experimentalApi"])
            self.assertEqual(init_errors, [])
            self.assertEqual(init_results, [{"userAgent": "codex/1.0.0"}])

            results: list[dict[str, object]] = []
            errors: list[BaseException] = []

            def run_request() -> None:
                try:
                    results.append(client.request("thread/read", {"threadId": "thread-1", "includeTurns": False}))
                except BaseException as exc:  # pragma: no cover - exercised on failures
                    errors.append(exc)

            request_thread = threading.Thread(target=run_request, daemon=True)
            request_thread.start()
            request = server.next_message()
            self.assertEqual(request["method"], "thread/read")
            self.assertIn("upgrade: websocket", server.handshake_headers.lower())
            self.assertIn("sec-websocket-key:", server.handshake_headers.lower())
            server.send_response(request["id"], {"thread": {"id": "thread-1", "status": "idle"}})
            request_thread.join(timeout=2)

            self.assertEqual(errors, [])
            self.assertEqual(results, [{"thread": {"id": "thread-1", "status": "idle"}}])

    def test_close_waits_for_peer_close_frame(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.close_response_delay_seconds = 0.12
            server.start()
            self.addCleanup(server.close)

            client = APP_SERVER.AppServerClient(socket_path, timeout_seconds=2.0)
            client.connect()
            self.addCleanup(client.close)
            _init, _init_results, init_errors = self._initialize_client(client, server)
            self.assertEqual(init_errors, [])

            started = time.monotonic()
            client.close()
            elapsed = time.monotonic() - started

            self.assertTrue(server.close_received.wait(timeout=1.0))
            self.assertTrue(server.close_response_sent.wait(timeout=1.0))
            self.assertGreaterEqual(elapsed, 0.10)

    def test_thread_resume_sends_thread_id_and_runtime_context(self) -> None:
        self.assertTrue(
            hasattr(APP_SERVER, "thread_resume"),
            "APP_SERVER.thread_resume is required for launcher attach preflight",
        )

        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)

            results: list[dict[str, object]] = []
            errors: list[BaseException] = []

            def run_resume() -> None:
                try:
                    results.append(
                        APP_SERVER.thread_resume(
                            socket_path,
                            "thread-1",
                            workspace_dir=Path("/tmp/bs-workspace"),
                            shared_project_workspace_dir=Path("/tmp/bs-project"),
                            permissions="buddyswitch-runtime",
                        )
                    )
                except BaseException as exc:
                    errors.append(exc)

            resume_thread = threading.Thread(target=run_resume, daemon=True)
            resume_thread.start()

            init = server.next_message()
            self.assertEqual(init["method"], "initialize")
            server.send_response(init["id"], {"userAgent": "codex/1.0.0"})
            self.assertEqual(server.next_message()["method"], "initialized")

            request = server.next_message()
            self.assertEqual(request["method"], "thread/resume")
            params = request["params"]
            assert isinstance(params, dict)
            self.assertEqual(params["threadId"], "thread-1")
            self.assertEqual(params["cwd"], "/tmp/bs-workspace")
            self.assertEqual(params["runtimeWorkspaceRoots"], ["/tmp/bs-workspace", "/tmp/bs-project"])
            self.assertEqual(params["permissions"], "buddyswitch-runtime")
            self.assertEqual(params["excludeTurns"], True)
            self.assertNotIn("path", params)

            server.send_response(
                request["id"],
                {
                    "thread": {"id": "thread-1", "status": {"type": "idle"}},
                    "model": "gpt-5",
                    "modelProvider": "openai",
                    "serviceTier": None,
                    "cwd": "/tmp/bs-workspace",
                    "runtimeWorkspaceRoots": ["/tmp/bs-workspace", "/tmp/bs-project"],
                    "instructionSources": [],
                    "approvalPolicy": "never",
                    "approvalsReviewer": "user",
                    "sandbox": {"mode": "workspace-write"},
                    "activePermissionProfile": {"id": "buddyswitch-runtime"},
                    "reasoningEffort": None,
                },
            )
            resume_thread.join(timeout=2)

            self.assertEqual(errors, [])
            self.assertEqual(results[0]["thread"]["id"], "thread-1")

    def test_thread_fork_sends_model_and_reasoning_effort_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)
            results: list[dict[str, object]] = []
            errors: list[BaseException] = []

            def run_fork() -> None:
                try:
                    results.append(
                        APP_SERVER.thread_fork(
                            socket_path,
                            "thread-parent",
                            workspace_dir=Path("/tmp/bs-workspace"),
                            shared_project_workspace_dir=Path("/tmp/bs-project"),
                            permissions="buddyswitch-runtime",
                            model="gpt-5.4",
                            model_reasoning_effort="high",
                        )
                    )
                except BaseException as exc:
                    errors.append(exc)

            fork_thread = threading.Thread(target=run_fork, daemon=True)
            fork_thread.start()
            fork_thread.join(timeout=0.05)
            if errors:
                raise errors[0]

            init = server.next_message()
            self.assertEqual(init["method"], "initialize")
            server.send_response(init["id"], {"userAgent": "codex/1.0.0"})
            self.assertEqual(server.next_message()["method"], "initialized")

            request = server.next_message()
            self.assertEqual(request["method"], "thread/fork")
            params = request["params"]
            assert isinstance(params, dict)
            self.assertEqual(params["threadId"], "thread-parent")
            self.assertEqual(params["model"], "gpt-5.4")
            self.assertEqual(params["config"], {"model_reasoning_effort": "high"})
            self.assertEqual(params["permissions"], "buddyswitch-runtime")
            self.assertTrue(params["ephemeral"])
            self.assertTrue(params["excludeTurns"])

            server.send_response(
                request["id"],
                {
                    "thread": {"id": "thread-side-1", "status": {"type": "idle"}},
                    "model": "gpt-5.4",
                    "modelProvider": "openai",
                    "serviceTier": None,
                    "cwd": "/tmp/bs-workspace",
                    "runtimeWorkspaceRoots": ["/tmp/bs-workspace", "/tmp/bs-project"],
                    "instructionSources": [],
                    "approvalPolicy": "never",
                    "approvalsReviewer": "user",
                    "sandbox": {"mode": "workspace-write"},
                    "activePermissionProfile": {"id": "buddyswitch-runtime"},
                    "reasoningEffort": "high",
                },
            )
            fork_thread.join(timeout=2)

            self.assertEqual(errors, [])
            self.assertEqual(results[0]["thread"]["id"], "thread-side-1")

    def test_thread_fork_omits_model_and_effort_when_inheriting_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)
            errors: list[BaseException] = []

            def run_fork() -> None:
                try:
                    APP_SERVER.thread_fork(
                        socket_path,
                        "thread-parent",
                        workspace_dir=Path("/tmp/bs-workspace"),
                        shared_project_workspace_dir=Path("/tmp/bs-project"),
                        permissions="buddyswitch-runtime",
                    )
                except BaseException as exc:
                    errors.append(exc)

            fork_thread = threading.Thread(target=run_fork, daemon=True)
            fork_thread.start()

            init = server.next_message()
            self.assertEqual(init["method"], "initialize")
            server.send_response(init["id"], {"userAgent": "codex/1.0.0"})
            self.assertEqual(server.next_message()["method"], "initialized")

            request = server.next_message()
            self.assertEqual(request["method"], "thread/fork")
            params = request["params"]
            assert isinstance(params, dict)
            self.assertNotIn("model", params)
            self.assertNotIn("modelProvider", params)
            self.assertNotIn("config", params)

            server.send_response(
                request["id"],
                {
                    "thread": {"id": "thread-side-1", "status": {"type": "idle"}},
                    "model": "gpt-5",
                    "modelProvider": "openai",
                    "serviceTier": None,
                    "cwd": "/tmp/bs-workspace",
                    "runtimeWorkspaceRoots": ["/tmp/bs-workspace", "/tmp/bs-project"],
                    "instructionSources": [],
                    "approvalPolicy": "never",
                    "approvalsReviewer": "user",
                    "sandbox": {"mode": "workspace-write"},
                    "activePermissionProfile": {"id": "buddyswitch-runtime"},
                    "reasoningEffort": None,
                },
            )
            fork_thread.join(timeout=2)

            self.assertEqual(errors, [])

    def test_build_thread_settings_update_params_omits_absent_fields_and_rejects_noop(self) -> None:
        self.assertEqual(
            APP_SERVER.build_thread_settings_update_params("thread-main", model="gpt-5.4", effort="high"),
            {
                "threadId": "thread-main",
                "model": "gpt-5.4",
                "effort": "high",
            },
        )
        self.assertEqual(
            APP_SERVER.build_thread_settings_update_params("thread-main", effort="medium"),
            {
                "threadId": "thread-main",
                "effort": "medium",
            },
        )
        with self.assertRaises(APP_SERVER.AppServerProtocolError):
            APP_SERVER.build_thread_settings_update_params("thread-main")

    def test_thread_settings_update_returns_response_when_notification_arrives_before_response(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)
            results: list[dict[str, object]] = []
            errors: list[BaseException] = []

            def run_update() -> None:
                try:
                    results.append(
                        APP_SERVER.thread_settings_update(
                            socket_path,
                            "thread-main",
                            model="gpt-5.4",
                            effort="high",
                        )
                    )
                except BaseException as exc:
                    errors.append(exc)

            update_thread = threading.Thread(target=run_update, daemon=True)
            update_thread.start()

            init = server.next_message()
            self.assertEqual(init["method"], "initialize")
            server.send_response(init["id"], {"userAgent": "codex/1.0.0"})
            self.assertEqual(server.next_message()["method"], "initialized")

            request = server.next_message()
            self.assertEqual(request["method"], "thread/settings/update")
            params = request["params"]
            assert isinstance(params, dict)
            self.assertEqual(
                params,
                {
                    "threadId": "thread-main",
                    "model": "gpt-5.4",
                    "effort": "high",
                },
            )
            server.send_notification("thread/settings/updated", {"threadId": "thread-other", "model": "ignored"})
            server.send_notification(
                "thread/settings/updated",
                {
                    "threadId": "thread-main",
                    "model": "gpt-5.4",
                    "effort": "high",
                },
            )
            server.send_response(request["id"], {"ok": True})
            update_thread.join(timeout=2)

            self.assertEqual(errors, [])
            self.assertEqual(results, [{"ok": True}])

    def test_thread_settings_update_returns_response_before_later_notification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)
            results: list[dict[str, object]] = []
            errors: list[BaseException] = []

            def run_update() -> None:
                try:
                    results.append(
                        APP_SERVER.thread_settings_update(
                            socket_path,
                            "thread-main",
                            effort="medium",
                        )
                    )
                except BaseException as exc:
                    errors.append(exc)

            update_thread = threading.Thread(target=run_update, daemon=True)
            update_thread.start()

            init = server.next_message()
            self.assertEqual(init["method"], "initialize")
            server.send_response(init["id"], {"userAgent": "codex/1.0.0"})
            self.assertEqual(server.next_message()["method"], "initialized")

            request = server.next_message()
            self.assertEqual(request["method"], "thread/settings/update")
            params = request["params"]
            assert isinstance(params, dict)
            self.assertEqual(params, {"threadId": "thread-main", "effort": "medium"})
            self.assertNotIn("model", params)

            server.send_response(request["id"], {"ok": True})
            server.send_notification("unrelated/event", {"threadId": "thread-main"})
            server.send_notification(
                "thread/settings/updated",
                {
                    "threadId": "thread-main",
                    "effort": "medium",
                },
            )
            update_thread.join(timeout=2)

            self.assertEqual(errors, [])
            self.assertEqual(results, [{"ok": True}])

    def test_thread_settings_update_returns_response_without_notification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)
            original_timeout = APP_SERVER.DEFAULT_RPC_TIMEOUT_SECONDS
            APP_SERVER.DEFAULT_RPC_TIMEOUT_SECONDS = 0.2
            self.addCleanup(setattr, APP_SERVER, "DEFAULT_RPC_TIMEOUT_SECONDS", original_timeout)
            results: list[dict[str, object]] = []
            errors: list[BaseException] = []

            def run_update() -> None:
                try:
                    results.append(
                        APP_SERVER.thread_settings_update(
                            socket_path,
                            "thread-main",
                            model="gpt-5.5",
                            effort="medium",
                        )
                    )
                except BaseException as exc:
                    errors.append(exc)

            update_thread = threading.Thread(target=run_update, daemon=True)
            update_thread.start()

            init = server.next_message()
            self.assertEqual(init["method"], "initialize")
            server.send_response(init["id"], {"userAgent": "codex/1.0.0"})
            self.assertEqual(server.next_message()["method"], "initialized")

            request = server.next_message()
            self.assertEqual(request["method"], "thread/settings/update")
            params = request["params"]
            assert isinstance(params, dict)
            self.assertEqual(
                params,
                {
                    "threadId": "thread-main",
                    "model": "gpt-5.5",
                    "effort": "medium",
                },
            )
            server.send_response(request["id"], {"ok": True, "threadId": "thread-main"})
            update_thread.join(timeout=2)

            self.assertEqual(errors, [])
            self.assertEqual(results, [{"ok": True, "threadId": "thread-main"}])

    def test_thread_bootstrap_rollout_injects_minimal_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)

            results: list[dict[str, object]] = []
            errors: list[BaseException] = []

            def run_bootstrap() -> None:
                try:
                    results.append(APP_SERVER.thread_bootstrap_rollout(socket_path, "thread-1"))
                except BaseException as exc:
                    errors.append(exc)

            bootstrap_thread = threading.Thread(target=run_bootstrap, daemon=True)
            bootstrap_thread.start()

            init = server.next_message()
            self.assertEqual(init["method"], "initialize")
            server.send_response(init["id"], {"userAgent": "codex/1.0.0"})
            self.assertEqual(server.next_message()["method"], "initialized")

            request = server.next_message()
            self.assertEqual(request["method"], "thread/inject_items")
            params = request["params"]
            assert isinstance(params, dict)
            self.assertEqual(params["threadId"], "thread-1")
            self.assertEqual(
                params["items"],
                [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "[BuddySwitch internal bootstrap marker]",
                            }
                        ],
                    }
                ],
            )
            server.send_response(request["id"], {})
            bootstrap_thread.join(timeout=2)

            self.assertEqual(errors, [])
            self.assertEqual(results, [{"ok": True, "thread_id": "thread-1"}])

    def test_thread_bootstrap_rollout_propagates_inject_items_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)

            errors: list[BaseException] = []

            def run_bootstrap() -> None:
                try:
                    APP_SERVER.thread_bootstrap_rollout(socket_path, "thread-1")
                except BaseException as exc:
                    errors.append(exc)

            bootstrap_thread = threading.Thread(target=run_bootstrap, daemon=True)
            bootstrap_thread.start()

            init = server.next_message()
            self.assertEqual(init["method"], "initialize")
            server.send_response(init["id"], {"userAgent": "codex/1.0.0"})
            self.assertEqual(server.next_message()["method"], "initialized")

            request = server.next_message()
            self.assertEqual(request["method"], "thread/inject_items")
            server.send_error(request["id"], code=-32000, message="inject failed")
            bootstrap_thread.join(timeout=2)

            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], APP_SERVER.AppServerRequestError)
            self.assertIn("thread/inject_items failed", str(errors[0]))

    def test_request_ignores_notifications_until_matching_response(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)

            client = APP_SERVER.AppServerClient(socket_path, timeout_seconds=2.0)
            client.connect()
            self.addCleanup(client.close)
            _init, _results, init_errors = self._initialize_client(client, server)
            self.assertEqual(init_errors, [])

            results: list[dict[str, object]] = []
            errors: list[BaseException] = []

            def run_request() -> None:
                try:
                    results.append(client.request("thread/read", {"threadId": "thread-1", "includeTurns": False}))
                except BaseException as exc:  # pragma: no cover - exercised on failures
                    errors.append(exc)

            request_thread = threading.Thread(target=run_request, daemon=True)
            request_thread.start()
            pending = server.next_message()
            server.send_notification("thread/status/changed", {"threadId": "thread-1", "status": "active"})
            time.sleep(0.05)
            self.assertEqual(results, [])
            self.assertEqual(errors, [])
            server.send_response(pending["id"], {"thread": {"id": "thread-1", "status": "idle"}})
            request_thread.join(timeout=2)

            self.assertEqual(errors, [])
            self.assertEqual(results, [{"thread": {"id": "thread-1", "status": "idle"}}])

    def test_read_notification_returns_server_notification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)

            client = APP_SERVER.AppServerClient(socket_path, timeout_seconds=2.0)
            client.connect()
            self.addCleanup(client.close)
            _init, _results, init_errors = self._initialize_client(client, server)
            self.assertEqual(init_errors, [])

            results: list[dict[str, object]] = []
            errors: list[BaseException] = []

            def run_read() -> None:
                try:
                    results.append(client.read_notification())
                except BaseException as exc:  # pragma: no cover - exercised on failures
                    errors.append(exc)

            read_thread = threading.Thread(target=run_read, daemon=True)
            read_thread.start()
            server.send_notification("turn/completed", {"thread_id": "thread-1", "turn_id": "turn-1", "status": "completed"})
            read_thread.join(timeout=2)

            self.assertEqual(errors, [])
            self.assertEqual(
                results,
                [{"method": "turn/completed", "params": {"thread_id": "thread-1", "turn_id": "turn-1", "status": "completed"}}],
            )

    def test_read_notification_skips_response_shaped_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)

            client = APP_SERVER.AppServerClient(socket_path, timeout_seconds=2.0)
            client.connect()
            self.addCleanup(client.close)
            _init, _results, init_errors = self._initialize_client(client, server)
            self.assertEqual(init_errors, [])

            results: list[dict[str, object]] = []
            errors: list[BaseException] = []

            def run_read() -> None:
                try:
                    results.append(client.read_notification())
                except BaseException as exc:  # pragma: no cover - exercised on failures
                    errors.append(exc)

            read_thread = threading.Thread(target=run_read, daemon=True)
            read_thread.start()
            server.send_response(999, {"ignored": True})
            time.sleep(0.05)
            self.assertEqual(results, [])
            self.assertEqual(errors, [])
            server.send_notification("turn/completed", {"thread_id": "thread-1", "turn_id": "turn-2", "status": "completed"})
            read_thread.join(timeout=2)

            self.assertEqual(errors, [])
            self.assertEqual(results[0]["method"], "turn/completed")
            self.assertEqual(results[0]["params"]["turn_id"], "turn-2")

    def test_client_identity_can_be_set_for_daemon(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)

            client = APP_SERVER.AppServerClient(
                socket_path,
                timeout_seconds=2.0,
                client_name="buddyswitch_daemon",
                client_title="BuddySwitch Daemon",
            )
            client.connect()
            self.addCleanup(client.close)
            init, _results, init_errors = self._initialize_client(client, server)

            params = init["params"]
            assert isinstance(params, dict)
            self.assertEqual(params["clientInfo"]["name"], "buddyswitch_daemon")
            self.assertEqual(params["clientInfo"]["title"], "BuddySwitch Daemon")
            self.assertEqual(init_errors, [])

    def test_text_input_payload_shape_is_codex_compatible(self) -> None:
        self.assertEqual(
            APP_SERVER.text_input_payload("hello"),
            [{"type": "text", "text": "hello", "text_elements": []}],
        )

    def test_side_boundary_prompt_item_shape_is_codex_compatible(self) -> None:
        item = APP_SERVER.side_boundary_prompt_item()
        self.assertEqual(item["type"], "message")
        self.assertEqual(item["role"], "user")
        content = item["content"]
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["type"], "input_text")
        self.assertIn("Side conversation boundary.", content[0]["text"])

    def test_turn_steer_requires_expected_turn_id(self) -> None:
        with self.assertRaises(ValueError):
            APP_SERVER.build_turn_steer_params("thread-1", "", "hello")

    def test_turn_start_sends_input_and_permissions(self) -> None:
        self.assertTrue(hasattr(APP_SERVER, "turn_start"), "APP_SERVER.turn_start is required by side_thread_lifecycle")
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)

            results: list[dict[str, object]] = []
            errors: list[BaseException] = []

            def run_turn_start() -> None:
                try:
                    results.append(APP_SERVER.turn_start(socket_path, "thread-1", "hello", "buddyswitch-runtime"))
                except BaseException as exc:
                    errors.append(exc)

            request_thread = threading.Thread(target=run_turn_start, daemon=True)
            request_thread.start()

            init = server.next_message()
            self.assertEqual(init["method"], "initialize")
            server.send_response(init["id"], {"userAgent": "codex/1.0.0"})
            self.assertEqual(server.next_message()["method"], "initialized")

            request = server.next_message()
            self.assertEqual(request["method"], "turn/start")
            params = request["params"]
            assert isinstance(params, dict)
            self.assertEqual(params["threadId"], "thread-1")
            self.assertEqual(params["input"], APP_SERVER.text_input_payload("hello"))
            self.assertEqual(params["permissions"], "buddyswitch-runtime")
            server.send_response(request["id"], {"turn": {"id": "turn-1"}})
            request_thread.join(timeout=2)

            self.assertEqual(errors, [])
            self.assertEqual(results[0]["turn_id"], "turn-1")

    def test_turn_steer_sends_known_turn_id(self) -> None:
        self.assertTrue(hasattr(APP_SERVER, "turn_steer"), "APP_SERVER.turn_steer is required by side_thread_lifecycle")
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)

            results: list[dict[str, object]] = []
            errors: list[BaseException] = []

            def run_turn_steer() -> None:
                try:
                    results.append(APP_SERVER.turn_steer(socket_path, "thread-1", "turn-1", "hello"))
                except BaseException as exc:
                    errors.append(exc)

            request_thread = threading.Thread(target=run_turn_steer, daemon=True)
            request_thread.start()

            init = server.next_message()
            self.assertEqual(init["method"], "initialize")
            server.send_response(init["id"], {"userAgent": "codex/1.0.0"})
            self.assertEqual(server.next_message()["method"], "initialized")

            request = server.next_message()
            self.assertEqual(request["method"], "turn/steer")
            params = request["params"]
            assert isinstance(params, dict)
            self.assertEqual(params, APP_SERVER.build_turn_steer_params("thread-1", "turn-1", "hello"))
            server.send_response(request["id"], {"turnId": "turn-2"})
            request_thread.join(timeout=2)

            self.assertEqual(errors, [])
            self.assertEqual(results[0]["turn_id"], "turn-2")
            self.assertEqual(results[0]["expected_turn_id"], "turn-1")

    def test_turn_interrupt_sends_known_turn_id(self) -> None:
        self.assertTrue(hasattr(APP_SERVER, "turn_interrupt"), "APP_SERVER.turn_interrupt is required by side_thread_lifecycle")
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)

            results: list[dict[str, object]] = []
            errors: list[BaseException] = []

            def run_turn_interrupt() -> None:
                try:
                    results.append(APP_SERVER.turn_interrupt(socket_path, "thread-1", "turn-1"))
                except BaseException as exc:
                    errors.append(exc)

            request_thread = threading.Thread(target=run_turn_interrupt, daemon=True)
            request_thread.start()

            init = server.next_message()
            self.assertEqual(init["method"], "initialize")
            server.send_response(init["id"], {"userAgent": "codex/1.0.0"})
            self.assertEqual(server.next_message()["method"], "initialized")

            request = server.next_message()
            self.assertEqual(request["method"], "turn/interrupt")
            params = request["params"]
            assert isinstance(params, dict)
            self.assertEqual(params["threadId"], "thread-1")
            self.assertEqual(params["turnId"], "turn-1")
            server.send_response(request["id"], {})
            request_thread.join(timeout=2)

            self.assertEqual(errors, [])
            self.assertEqual(results, [{"ok": True, "turn_id": "turn-1"}])

    def test_input_command_requires_explicit_permissions_profile(self) -> None:
        parser = APP_SERVER.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "input",
                    "--socket",
                    "/tmp/app-server.sock",
                    "--thread-id",
                    "thread-1",
                    "--text",
                    "Draft brief",
                ]
            )

        args = parser.parse_args(
            [
                "input",
                "--socket",
                "/tmp/app-server.sock",
                "--thread-id",
                "thread-1",
                "--text",
                "Draft brief",
                "--permissions",
                "buddyswitch-runtime",
            ]
        )
        self.assertEqual(args.permissions, "buddyswitch-runtime")

    def test_input_command_rejects_legacy_instance_json_argument(self) -> None:
        parser = APP_SERVER.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "input",
                    "--socket",
                    "/tmp/app-server.sock",
                    "--thread-id",
                    "thread-1",
                    "--text",
                    "Draft brief",
                    "--permissions",
                    "buddyswitch-runtime",
                    "--instance-json",
                    "/tmp/instance.json",
                ]
            )

    def test_app_server_source_has_no_task_tui_input_coupling(self) -> None:
        source = APP_SERVER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("task_input_context", source)
        self.assertNotIn("compose_task_context_input", source)
        self.assertNotIn("TaskInputContextError", source)

        shell_source = APP_SERVER_SHELL_PATH.read_text(encoding="utf-8")
        self.assertNotIn("--instance-json", shell_source)

    def test_side_composite_commands_are_not_app_server_entrypoints(self) -> None:
        parser = APP_SERVER.build_parser()
        for command in ("side-start", "side-close"):
            with self.subTest(command=command), self.assertRaises(SystemExit):
                parser.parse_args([command])

    def test_server_error_is_reported_without_retrying_mutating_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)

            client = APP_SERVER.AppServerClient(socket_path, timeout_seconds=2.0)
            client.connect()
            self.addCleanup(client.close)
            _init, _results, init_errors = self._initialize_client(client, server)
            self.assertEqual(init_errors, [])

            errors: list[BaseException] = []

            def run_request() -> None:
                try:
                    client.request("turn/steer", APP_SERVER.build_turn_steer_params("thread-1", "turn-1", "hello"))
                except BaseException as exc:
                    errors.append(exc)

            request_thread = threading.Thread(target=run_request, daemon=True)
            request_thread.start()
            steer = server.next_message()
            self.assertEqual(steer["method"], "turn/steer")
            server.send_error(steer["id"], code=-32005, message="turn not steerable")
            request_thread.join(timeout=2)

            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], APP_SERVER.AppServerRequestError)
            self.assertEqual(server._incoming.qsize(), 0)

    def test_client_times_out_when_socket_never_responds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)

            client = APP_SERVER.AppServerClient(socket_path, timeout_seconds=0.2)
            client.connect()
            self.addCleanup(client.close)
            with self.assertRaises(APP_SERVER.AppServerTimeoutError) as context:
                client.initialize()

            self.assertIn(str(socket_path), str(context.exception))
            self.assertIn("initialize", str(context.exception))

    def test_thread_bootstrap_rollout_uses_dedicated_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)

            errors: list[BaseException] = []
            started_at = time.monotonic()

            def run_bootstrap() -> None:
                try:
                    APP_SERVER.thread_bootstrap_rollout(
                        socket_path,
                        "thread-1",
                        timeout_seconds=0.2,
                    )
                except BaseException as exc:
                    errors.append(exc)

            bootstrap_thread = threading.Thread(target=run_bootstrap, daemon=True)
            bootstrap_thread.start()

            init = server.next_message()
            self.assertEqual(init["method"], "initialize")
            server.send_response(init["id"], {"userAgent": "codex/1.0.0"})
            self.assertEqual(server.next_message()["method"], "initialized")

            request = server.next_message()
            self.assertEqual(request["method"], "thread/inject_items")

            bootstrap_thread.join(timeout=2)
            elapsed = time.monotonic() - started_at

            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], APP_SERVER.AppServerTimeoutError)
            self.assertIn("thread/inject_items", str(errors[0]))
            self.assertLess(elapsed, 2.0)

    def test_close_ping_and_unexpected_binary_frames_are_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = self._socket_path(Path(temp_root))
            server = FakeUnixWebSocketServer(socket_path)
            server.start()
            self.addCleanup(server.close)

            client = APP_SERVER.AppServerClient(socket_path, timeout_seconds=2.0)
            client.connect()
            self.addCleanup(client.close)
            _init, _results, init_errors = self._initialize_client(client, server)
            self.assertEqual(init_errors, [])

            server.send_ping(b"hello")
            binary_errors: list[BaseException] = []

            def run_request() -> None:
                try:
                    client.request("thread/read", {"threadId": "thread-1", "includeTurns": False})
                except BaseException as exc:
                    binary_errors.append(exc)

            request_thread = threading.Thread(target=run_request, daemon=True)
            request_thread.start()
            request = server.next_message()
            self.assertEqual(request["method"], "thread/read")
            server.send_binary(b"bad")
            request_thread.join(timeout=2)
            self.assertEqual(len(binary_errors), 1)
            self.assertIsInstance(binary_errors[0], APP_SERVER.AppServerProtocolError)

        with tempfile.TemporaryDirectory() as temp_root_two:
            socket_path_two = self._socket_path(Path(temp_root_two))
            close_server = FakeUnixWebSocketServer(socket_path_two)
            close_server.start()
            self.addCleanup(close_server.close)

            client = APP_SERVER.AppServerClient(socket_path_two, timeout_seconds=2.0)
            client.connect()
            self.addCleanup(client.close)
            _init, _results, init_errors = self._initialize_client(client, close_server)
            self.assertEqual(init_errors, [])

            close_errors: list[BaseException] = []

            def run_close_request() -> None:
                try:
                    client.request("thread/read", {"threadId": "thread-1", "includeTurns": False})
                except BaseException as exc:
                    close_errors.append(exc)

            request_thread = threading.Thread(target=run_close_request, daemon=True)
            request_thread.start()
            request = close_server.next_message()
            self.assertEqual(request["method"], "thread/read")
            close_server.send_close()
            request_thread.join(timeout=2)

            self.assertEqual(len(close_errors), 1)
            self.assertIsInstance(close_errors[0], APP_SERVER.AppServerUnavailableError)

    def test_long_socket_path_uses_tmp_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root) / ("nested-" * 20)
            marker = root / "runtime" / "app-server.socket"
            socket_path = APP_SERVER.effective_socket_path(
                "act-pm-20260523-abc123",
                root,
                marker,
            )
            if Path("/tmp").exists():
                expected_root = Path(os.path.realpath("/tmp")) / "buddyswitch-app-server"
            else:
                expected_root = Path(os.path.realpath(tempfile.gettempdir())) / "buddyswitch-app-server"
            self.assertEqual(socket_path.parent, expected_root)
            self.assertTrue(socket_path.name.startswith("buddyswitch-app-server-"))
            self.assertTrue(str(socket_path).endswith(".sock"))
            self.assertLess(len(str(socket_path).encode("utf-8")), 104)

    def test_stop_app_server_terminates_child_processes_in_launch_group(self) -> None:
        script = (
            "import os, subprocess, sys, time\n"
            "from pathlib import Path\n"
            "child = subprocess.Popen([os.environ['BUDDYSWITCH_PYTHON'], '-c', 'import time; time.sleep(60)'])\n"
            "Path(sys.argv[1]).write_text(str(child.pid), encoding='utf-8')\n"
            "time.sleep(60)\n"
        )
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            child_pid_file = root / "child.pid"
            leader = subprocess.Popen(
                [PYTHON, "-c", script, str(child_pid_file)],
                start_new_session=True,
            )
            pgid = os.getpgid(leader.pid)
            child_pid = 0
            previous_grace = APP_SERVER.APP_SERVER_STOP_GRACE_SECONDS
            APP_SERVER.APP_SERVER_STOP_GRACE_SECONDS = 0.2
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if child_pid_file.exists():
                        child_pid = int(child_pid_file.read_text(encoding="utf-8"))
                        break
                    time.sleep(0.05)
                self.assertNotEqual(child_pid, 0)
                self.assertEqual(os.getpgid(child_pid), pgid)

                socket_path = root / "app-server.sock"
                pid_path = root / "app-server.pid"
                marker_path = root / "app-server.socket"
                log_path = root / "app-server.log"
                pid_path.write_text(f"{leader.pid}\n", encoding="utf-8")
                marker_path.write_text(f"{socket_path}\n", encoding="utf-8")
                socket_path.touch()

                payload = APP_SERVER.stop_app_server(socket_path, pid_path, marker_path, log_path)

                self.assertTrue(payload["terminated"])
                leader.wait(timeout=2)
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline and self._pid_is_live(child_pid):
                    time.sleep(0.05)
                self.assertFalse(self._pid_is_live(child_pid))
                self.assertFalse(pid_path.exists())
                self.assertFalse(marker_path.exists())
                self.assertFalse(socket_path.exists())
            finally:
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except OSError:
                    pass
                if child_pid:
                    try:
                        os.kill(child_pid, signal.SIGKILL)
                    except OSError:
                        pass
                try:
                    leader.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
                APP_SERVER.APP_SERVER_STOP_GRACE_SECONDS = previous_grace


if __name__ == "__main__":
    unittest.main()
