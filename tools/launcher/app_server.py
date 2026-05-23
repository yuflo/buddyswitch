#!/usr/bin/env python3
"""BuddySwitch Codex app-server lifecycle and JSON-RPC helper."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
WEBSOCKET_VERSION = "13"
CLIENT_NAME = "buddyswitch_launcher"
CLIENT_TITLE = "BuddySwitch Launcher"
CLIENT_VERSION = "0.1.0"
DEFAULT_TIMEOUT_SECONDS = 2.0
DEFAULT_RPC_TIMEOUT_SECONDS = 15.0
MAX_UNIX_SOCKET_BYTES = 104
APP_SERVER_STARTUP_POLL_SECONDS = 0.05
APP_SERVER_STOP_GRACE_SECONDS = 2.0


class AppServerError(RuntimeError):
    """Base app-server client error."""


class AppServerProtocolError(AppServerError):
    """Wire-protocol or JSON-RPC framing error."""


class AppServerUnavailableError(AppServerError):
    """Socket or peer became unavailable."""


class AppServerTimeoutError(AppServerError):
    """Timed out waiting for app-server response."""


class AppServerRequestError(AppServerError):
    """JSON-RPC request failed."""

    def __init__(self, method: str, code: int | None, message: str) -> None:
        self.method = method
        self.code = code
        self.message = message
        detail = f"{method} failed"
        if code is not None:
            detail += f" ({code})"
        detail += f": {message}"
        super().__init__(detail)


def runtime_dir(instance_root: Path) -> Path:
    return instance_root / "runtime"


def pid_file(instance_root: Path) -> Path:
    return runtime_dir(instance_root) / "app-server.pid"


def marker_file(instance_root: Path) -> Path:
    return runtime_dir(instance_root) / "app-server.socket"


def log_file(instance_root: Path) -> Path:
    return runtime_dir(instance_root) / "app-server.log"


def default_socket_path(instance_root: Path) -> Path:
    return runtime_dir(instance_root) / "app-server.sock"


def fallback_socket_dir() -> Path:
    tmp_root = Path("/tmp")
    if tmp_root.exists():
        resolved_root = Path(os.path.realpath(tmp_root))
    else:
        resolved_root = Path(os.path.realpath(tempfile.gettempdir()))
    return resolved_root / "buddyswitch-app-server"


def effective_socket_path(instance_id: str, instance_root: Path, marker_path: Path) -> Path:
    recorded = _read_text_file(marker_path)
    if recorded:
        return Path(recorded)
    default_path = default_socket_path(instance_root)
    if len(str(default_path).encode("utf-8")) < MAX_UNIX_SOCKET_BYTES:
        return default_path
    digest = hashlib.sha1(instance_id.encode("utf-8")).hexdigest()[:12]
    return fallback_socket_dir() / f"buddyswitch-app-server-{digest}.sock"


def text_input_payload(text: str) -> list[dict[str, object]]:
    return [{"type": "text", "text": text, "text_elements": []}]


def build_turn_steer_params(thread_id: str, expected_turn_id: str, text: str) -> dict[str, object]:
    if not expected_turn_id:
        raise ValueError("expected_turn_id is required for turn/steer")
    return {
        "threadId": thread_id,
        "expectedTurnId": expected_turn_id,
        "input": text_input_payload(text),
    }


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""
    except OSError:
        return ""


def _write_text_file(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value + "\n", encoding="utf-8")


def _remove_path(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except IsADirectoryError:
        return


def _pid_is_live(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _read_pid(pid_path: Path) -> int | None:
    raw = _read_text_file(pid_path)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _cleanup_runtime_files(socket_path: Path, pid_path: Path, marker_path: Path) -> None:
    _remove_path(pid_path)
    _remove_path(marker_path)
    _remove_path(socket_path)


def _socket_connect(socket_path: Path, timeout_seconds: float) -> socket.socket:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout_seconds)
    try:
        sock.connect(str(socket_path))
    except OSError as exc:  # pragma: no cover - exercised in shell integration
        sock.close()
        raise AppServerUnavailableError(f"failed to connect to {socket_path}: {exc}") from exc
    return sock


def _receive_until(sock: socket.socket, marker: bytes, timeout_seconds: float, *, method: str) -> bytes:
    deadline = time.monotonic() + timeout_seconds
    data = b""
    while marker not in data:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AppServerTimeoutError(f"timed out waiting for {method} on {sock.getsockname()!r}")
        sock.settimeout(remaining)
        chunk = sock.recv(4096)
        if not chunk:
            raise AppServerUnavailableError(f"app-server closed the control socket during {method}")
        data += chunk
    return data


def _make_sec_websocket_accept(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key + WEBSOCKET_GUID).encode("ascii")).digest()).decode("ascii")


def _thread_status_kind(value: object) -> str | None:
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, dict):
        status_type = value.get("type")
        if isinstance(status_type, str):
            return status_type.lower()
    return None


def _turn_status_kind(value: object) -> str | None:
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, dict):
        status_type = value.get("type")
        if isinstance(status_type, str):
            return status_type.lower()
    return None


class AppServerClient:
    def __init__(self, socket_path: Path, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.socket_path = socket_path
        self.timeout_seconds = timeout_seconds
        self._sock: socket.socket | None = None
        self._recv_buffer = b""
        self._next_request_id = 1
        self._closed = False

    def __enter__(self) -> AppServerClient:
        self.connect()
        self.initialize()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def connect(self) -> None:
        if self._sock is not None:
            return
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        sock = _socket_connect(self.socket_path, self.timeout_seconds)
        request = (
            "GET / HTTP/1.1\r\n"
            "Host: localhost\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: {WEBSOCKET_VERSION}\r\n"
            "\r\n"
        ).encode("ascii")
        sock.sendall(request)
        raw_response = self._recv_until_http_headers(sock, method="websocket upgrade")
        header_bytes, _, remainder = raw_response.partition(b"\r\n\r\n")
        header_text = header_bytes.decode("ascii", errors="strict")
        lines = header_text.split("\r\n")
        if not lines or not lines[0].startswith("HTTP/1.1 101"):
            sock.close()
            raise AppServerProtocolError(f"websocket upgrade failed for {self.socket_path}: {lines[0] if lines else 'empty response'}")
        accept_header = None
        for line in lines[1:]:
            if line.lower().startswith("sec-websocket-accept:"):
                accept_header = line.split(":", 1)[1].strip()
                break
        expected_accept = _make_sec_websocket_accept(key)
        if accept_header != expected_accept:
            sock.close()
            raise AppServerProtocolError(f"invalid websocket accept header for {self.socket_path}")
        self._sock = sock
        self._recv_buffer = remainder
        self._closed = False

    def close(self) -> None:
        if self._sock is None or self._closed:
            return
        try:
            self._send_frame(0x8, b"")
        except OSError:
            pass
        try:
            self._sock.close()
        finally:
            self._sock = None
            self._closed = True

    def initialize(self) -> dict[str, object]:
        response = self.request(
            "initialize",
            {
                "clientInfo": {
                    "name": CLIENT_NAME,
                    "title": CLIENT_TITLE,
                    "version": CLIENT_VERSION,
                },
                "capabilities": {
                    "experimentalApi": True,
                },
            },
            mark_initialized=False,
        )
        self.notify("initialized", None)
        return response

    def notify(self, method: str, params: dict[str, object] | None) -> None:
        payload: dict[str, object] = {"method": method}
        if params is not None:
            payload["params"] = params
        self._send_json(payload)

    def request(
        self,
        method: str,
        params: dict[str, object] | None,
        *,
        mark_initialized: bool = True,
    ) -> dict[str, object]:
        request_id = self._next_request_id
        self._next_request_id += 1
        payload: dict[str, object] = {"id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._send_json(payload)
        while True:
            message = self._read_json_message(method=method)
            if "method" in message and "id" not in message:
                continue
            if message.get("id") != request_id:
                continue
            if "error" in message:
                error = message["error"]
                if not isinstance(error, dict):
                    raise AppServerProtocolError(f"invalid JSON-RPC error shape for {method}")
                code = error.get("code")
                message_text = error.get("message")
                if not isinstance(message_text, str):
                    message_text = json.dumps(error, ensure_ascii=True)
                raise AppServerRequestError(method, code if isinstance(code, int) else None, message_text)
            result = message.get("result")
            if not isinstance(result, dict):
                raise AppServerProtocolError(f"invalid JSON-RPC result shape for {method}")
            return result

    def _recv_until_http_headers(self, sock: socket.socket, *, method: str) -> bytes:
        deadline = time.monotonic() + self.timeout_seconds
        data = b""
        while b"\r\n\r\n" not in data:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AppServerTimeoutError(f"timed out waiting for {method} on {self.socket_path}")
            sock.settimeout(remaining)
            try:
                chunk = sock.recv(4096)
            except socket.timeout as exc:
                raise AppServerTimeoutError(f"timed out waiting for {method} on {self.socket_path}") from exc
            if not chunk:
                raise AppServerUnavailableError(f"app-server closed the control socket during {method}")
            data += chunk
        return data

    def _send_json(self, payload: dict[str, object]) -> None:
        self._send_frame(0x1, json.dumps(payload, ensure_ascii=True).encode("utf-8"))

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        if self._sock is None:
            raise AppServerUnavailableError(f"app-server socket is not connected: {self.socket_path}")
        first = 0x80 | opcode
        length = len(payload)
        if length < 126:
            header = bytes([first, 0x80 | length])
        elif length < (1 << 16):
            header = bytes([first, 0x80 | 126]) + length.to_bytes(2, "big")
        else:
            header = bytes([first, 0x80 | 127]) + length.to_bytes(8, "big")
        mask = os.urandom(4)
        masked_payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self._sock.sendall(header + mask + masked_payload)

    def _read_json_message(self, *, method: str) -> dict[str, object]:
        while True:
            opcode, payload = self._read_frame(method=method)
            if opcode == 0x1:
                try:
                    message = json.loads(payload.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise AppServerProtocolError(f"failed to parse app-server JSON-RPC message for {method}") from exc
                if not isinstance(message, dict):
                    raise AppServerProtocolError(f"invalid JSON-RPC message shape for {method}")
                return message
            if opcode == 0x2:
                raise AppServerProtocolError(f"unexpected binary websocket frame while waiting for {method}")
            if opcode == 0x8:
                self._closed = True
                try:
                    self._send_frame(0x8, payload)
                except OSError:
                    pass
                raise AppServerUnavailableError(f"app-server closed the control socket during {method}")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            raise AppServerProtocolError(f"unexpected websocket opcode {opcode} while waiting for {method}")

    def _read_frame(self, *, method: str) -> tuple[int, bytes]:
        first_two = self._read_exact(2, method=method)
        first, second = first_two[0], first_two[1]
        opcode = first & 0x0F
        length = second & 0x7F
        masked = bool(second & 0x80)
        if masked:
            raise AppServerProtocolError(f"server sent masked websocket frame while waiting for {method}")
        if length == 126:
            length = int.from_bytes(self._read_exact(2, method=method), "big")
        elif length == 127:
            length = int.from_bytes(self._read_exact(8, method=method), "big")
        payload = self._read_exact(length, method=method)
        return opcode, payload

    def _read_exact(self, length: int, *, method: str) -> bytes:
        if self._sock is None:
            raise AppServerUnavailableError(f"app-server socket is not connected: {self.socket_path}")
        deadline = time.monotonic() + self.timeout_seconds
        while len(self._recv_buffer) < length:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AppServerTimeoutError(f"timed out waiting for {method} on {self.socket_path}")
            self._sock.settimeout(remaining)
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout as exc:
                raise AppServerTimeoutError(f"timed out waiting for {method} on {self.socket_path}") from exc
            if not chunk:
                raise AppServerUnavailableError(f"app-server closed the control socket during {method}")
            self._recv_buffer += chunk
        payload = self._recv_buffer[:length]
        self._recv_buffer = self._recv_buffer[length:]
        return payload


def app_server_status(socket_path: Path, pid_path: Path, marker_path: Path, log_path: Path) -> dict[str, Any]:
    pid = _read_pid(pid_path)
    socket_exists = socket_path.exists()
    marker_socket = _read_text_file(marker_path)
    pid_live = pid is not None and _pid_is_live(pid)
    healthy = False
    probe: dict[str, Any] | None = None

    if pid_live and socket_exists:
        try:
            with AppServerClient(socket_path, timeout_seconds=DEFAULT_TIMEOUT_SECONDS) as client:
                probe = client.request("thread/loaded/list", {"cursor": None, "limit": 1})
            healthy = True
        except AppServerError as exc:
            probe = {"error": str(exc)}
    elif pid is not None and not pid_live:
        _cleanup_runtime_files(socket_path, pid_path, marker_path)
        socket_exists = socket_path.exists()
        marker_socket = _read_text_file(marker_path)

    return {
        "healthy": healthy,
        "pid": pid,
        "pid_live": pid_live,
        "socket_path": str(socket_path),
        "socket_exists": socket_exists,
        "marker_file": str(marker_path),
        "marker_socket": marker_socket or None,
        "pid_file": str(pid_path),
        "log_file": str(log_path),
        "probe": probe,
    }


def ensure_app_server(
    instance_id: str,
    instance_root: Path,
    codex_bin: str = "codex",
    startup_timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    socket_path = effective_socket_path(instance_id, instance_root, marker_file(instance_root))
    pid_path = pid_file(instance_root)
    marker_path = marker_file(instance_root)
    log_path = log_file(instance_root)
    status = app_server_status(socket_path, pid_path, marker_path, log_path)
    if status["healthy"]:
        return status

    runtime_dir(instance_root).mkdir(parents=True, exist_ok=True)
    _cleanup_runtime_files(socket_path, pid_path, marker_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as handle:
        launch_cwd = instance_root / "workspace"
        process = subprocess.Popen(
            [codex_bin, "app-server", "--listen", f"unix://{socket_path}"],
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=str(launch_cwd if launch_cwd.exists() else instance_root),
        )
    _write_text_file(pid_path, str(process.pid))
    _write_text_file(marker_path, str(socket_path))

    deadline = time.monotonic() + startup_timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            _cleanup_runtime_files(socket_path, pid_path, marker_path)
            raise AppServerUnavailableError(
                f"codex app-server exited early for {instance_id}; see {log_path}"
            )
        status = app_server_status(socket_path, pid_path, marker_path, log_path)
        if status["healthy"]:
            return status
        time.sleep(APP_SERVER_STARTUP_POLL_SECONDS)

    stop_app_server(socket_path, pid_path, marker_path, log_path)
    raise AppServerTimeoutError(f"timed out waiting for app-server on {socket_path}")


def stop_app_server(socket_path: Path, pid_path: Path, marker_path: Path, log_path: Path) -> dict[str, Any]:
    del log_path
    pid = _read_pid(pid_path)
    terminated = False
    if pid is not None and _pid_is_live(pid):
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + APP_SERVER_STOP_GRACE_SECONDS
        while time.monotonic() < deadline:
            if not _pid_is_live(pid):
                terminated = True
                break
            time.sleep(APP_SERVER_STARTUP_POLL_SECONDS)
        if not terminated and _pid_is_live(pid):
            os.kill(pid, signal.SIGKILL)
            terminated = True
    _cleanup_runtime_files(socket_path, pid_path, marker_path)
    return {
        "ok": True,
        "pid": pid,
        "terminated": terminated or pid is None,
        "socket_path": str(socket_path),
    }


def thread_start(
    socket_path: Path,
    workspace_dir: Path,
    shared_project_workspace_dir: Path,
    permissions: str,
) -> dict[str, Any]:
    with AppServerClient(socket_path, timeout_seconds=DEFAULT_RPC_TIMEOUT_SECONDS) as client:
        result = client.request(
            "thread/start",
            {
                "cwd": str(workspace_dir),
                "permissions": permissions,
                "runtimeWorkspaceRoots": [
                    str(workspace_dir),
                    str(shared_project_workspace_dir),
                ],
            },
        )
    return result


def thread_read(socket_path: Path, thread_id: str, *, include_turns: bool = False) -> dict[str, Any]:
    with AppServerClient(socket_path, timeout_seconds=DEFAULT_RPC_TIMEOUT_SECONDS) as client:
        return client.request(
            "thread/read",
            {
                "threadId": thread_id,
                "includeTurns": include_turns,
            },
        )


def thread_turns_list(socket_path: Path, thread_id: str, *, limit: int = 5) -> dict[str, Any]:
    with AppServerClient(socket_path, timeout_seconds=DEFAULT_RPC_TIMEOUT_SECONDS) as client:
        return client.request(
            "thread/turns/list",
            {
                "threadId": thread_id,
                "limit": limit,
                "sortDirection": "desc",
                "itemsView": "summary",
            },
        )


def input_turn(socket_path: Path, thread_id: str, text: str) -> dict[str, Any]:
    thread_payload = thread_read(socket_path, thread_id, include_turns=False)
    thread = thread_payload.get("thread")
    if not isinstance(thread, dict):
        raise AppServerProtocolError("thread/read did not return a thread object")
    status_kind = _thread_status_kind(thread.get("status"))
    if status_kind == "idle":
        with AppServerClient(socket_path, timeout_seconds=DEFAULT_RPC_TIMEOUT_SECONDS) as client:
            result = client.request(
                "turn/start",
                {
                    "threadId": thread_id,
                    "input": text_input_payload(text),
                },
            )
        turn = result.get("turn")
        turn_id = turn.get("id") if isinstance(turn, dict) else None
        return {"action": "start", "turn": turn, "turn_id": turn_id}
    if status_kind != "active":
        raise AppServerUnavailableError(f"thread {thread_id} is not active or idle")

    turns_payload = thread_turns_list(socket_path, thread_id, limit=5)
    turns = turns_payload.get("data")
    if not isinstance(turns, list):
        raise AppServerProtocolError("thread/turns/list did not return a data list")
    active_turn_id = None
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        if _turn_status_kind(turn.get("status")) == "inprogress":
            turn_id = turn.get("id")
            if isinstance(turn_id, str) and turn_id:
                active_turn_id = turn_id
                break
    if not active_turn_id:
        raise AppServerUnavailableError(f"thread {thread_id} is active but no in-progress turn was found")

    with AppServerClient(socket_path, timeout_seconds=DEFAULT_RPC_TIMEOUT_SECONDS) as client:
        result = client.request("turn/steer", build_turn_steer_params(thread_id, active_turn_id, text))
    return {"action": "steer", "turn_id": result.get("turnId"), "expected_turn_id": active_turn_id}


def interrupt_turn(socket_path: Path, thread_id: str) -> dict[str, Any]:
    turns_payload = thread_turns_list(socket_path, thread_id, limit=5)
    turns = turns_payload.get("data")
    if not isinstance(turns, list):
        raise AppServerProtocolError("thread/turns/list did not return a data list")
    active_turn_id = None
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        if _turn_status_kind(turn.get("status")) == "inprogress":
            turn_id = turn.get("id")
            if isinstance(turn_id, str) and turn_id:
                active_turn_id = turn_id
                break
    if not active_turn_id:
        raise AppServerUnavailableError(f"thread {thread_id} has no active in-progress turn")
    with AppServerClient(socket_path, timeout_seconds=DEFAULT_RPC_TIMEOUT_SECONDS) as client:
        client.request(
            "turn/interrupt",
            {
                "threadId": thread_id,
                "turnId": active_turn_id,
            },
        )
    return {"ok": True, "turn_id": active_turn_id}


def _command_status(args: argparse.Namespace) -> int:
    payload = app_server_status(Path(args.socket), Path(args.pid_file), Path(args.marker_file), Path(args.log_file))
    print(json.dumps(payload, ensure_ascii=True))
    return 0 if payload["healthy"] else 1


def _command_ensure(args: argparse.Namespace) -> int:
    payload = ensure_app_server(
        instance_id=args.instance_id,
        instance_root=Path(args.instance_root),
        codex_bin=args.codex_bin,
        startup_timeout_seconds=args.startup_timeout_seconds,
    )
    print(json.dumps(payload, ensure_ascii=True))
    return 0


def _command_stop(args: argparse.Namespace) -> int:
    payload = stop_app_server(Path(args.socket), Path(args.pid_file), Path(args.marker_file), Path(args.log_file))
    print(json.dumps(payload, ensure_ascii=True))
    return 0


def _command_thread_start(args: argparse.Namespace) -> int:
    payload = thread_start(
        Path(args.socket),
        Path(args.workspace_dir),
        Path(args.shared_project_workspace_dir),
        args.permissions,
    )
    print(json.dumps(payload, ensure_ascii=True))
    return 0


def _command_thread_read(args: argparse.Namespace) -> int:
    payload = thread_read(Path(args.socket), args.thread_id, include_turns=args.include_turns)
    print(json.dumps(payload, ensure_ascii=True))
    return 0


def _command_input(args: argparse.Namespace) -> int:
    payload = input_turn(Path(args.socket), args.thread_id, args.text)
    print(json.dumps(payload, ensure_ascii=True))
    return 0


def _command_interrupt(args: argparse.Namespace) -> int:
    payload = interrupt_turn(Path(args.socket), args.thread_id)
    print(json.dumps(payload, ensure_ascii=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status")
    status.add_argument("--socket", required=True)
    status.add_argument("--pid-file", required=True)
    status.add_argument("--marker-file", required=True)
    status.add_argument("--log-file", required=True)
    status.set_defaults(func=_command_status)

    ensure = subparsers.add_parser("ensure")
    ensure.add_argument("--instance-id", required=True)
    ensure.add_argument("--instance-root", required=True)
    ensure.add_argument("--codex-bin", default="codex")
    ensure.add_argument("--startup-timeout-seconds", type=float, default=10.0)
    ensure.set_defaults(func=_command_ensure)

    stop = subparsers.add_parser("stop")
    stop.add_argument("--socket", required=True)
    stop.add_argument("--pid-file", required=True)
    stop.add_argument("--marker-file", required=True)
    stop.add_argument("--log-file", required=True)
    stop.set_defaults(func=_command_stop)

    thread_start_parser = subparsers.add_parser("thread-start")
    thread_start_parser.add_argument("--socket", required=True)
    thread_start_parser.add_argument("--workspace-dir", required=True)
    thread_start_parser.add_argument("--shared-project-workspace-dir", required=True)
    thread_start_parser.add_argument("--permissions", required=True)
    thread_start_parser.set_defaults(func=_command_thread_start)

    thread_read_parser = subparsers.add_parser("thread-read")
    thread_read_parser.add_argument("--socket", required=True)
    thread_read_parser.add_argument("--thread-id", required=True)
    thread_read_parser.add_argument("--include-turns", action="store_true")
    thread_read_parser.set_defaults(func=_command_thread_read)

    input_parser = subparsers.add_parser("input")
    input_parser.add_argument("--socket", required=True)
    input_parser.add_argument("--thread-id", required=True)
    input_parser.add_argument("--text", required=True)
    input_parser.set_defaults(func=_command_input)

    interrupt = subparsers.add_parser("interrupt")
    interrupt.add_argument("--socket", required=True)
    interrupt.add_argument("--thread-id", required=True)
    interrupt.set_defaults(func=_command_interrupt)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except AppServerError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
