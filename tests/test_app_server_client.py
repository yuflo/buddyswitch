#!/usr/bin/env python3
"""Tests for the BuddySwitch Codex app-server client."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import queue
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_SERVER_PATH = ROOT / "tools" / "launcher" / "app_server.py"
SPEC = importlib.util.spec_from_file_location("buddyswitch_launcher_app_server", APP_SERVER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load spec for {APP_SERVER_PATH}")
APP_SERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(APP_SERVER)


class FakeUnixWebSocketServer:
    def __init__(self, socket_path: Path) -> None:
        self.socket_path = socket_path
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._client: socket.socket | None = None
        self._incoming: queue.Queue[dict[str, object]] = queue.Queue()
        self._stop = threading.Event()
        self._handshake_headers: str | None = None

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
                self._send_frame(0x8, payload)
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

    def test_text_input_payload_shape_is_codex_compatible(self) -> None:
        self.assertEqual(
            APP_SERVER.text_input_payload("hello"),
            [{"type": "text", "text": "hello", "text_elements": []}],
        )

    def test_turn_steer_requires_expected_turn_id(self) -> None:
        with self.assertRaises(ValueError):
            APP_SERVER.build_turn_steer_params("thread-1", "", "hello")

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
                "inst-pm-20260523-abc123",
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


if __name__ == "__main__":
    unittest.main()
