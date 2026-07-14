"""WebSocket framing and connection handling for fake Codex."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
from collections.abc import Callable

from .rpc import handle_rpc_message
from .state import append_calls, load_server_state, save_server_state


WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def read_http_request(sock: socket.socket) -> str:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            raise EOFError("client closed before websocket upgrade")
        data += chunk
    return data.decode("ascii")


def websocket_accept_value(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key + WEBSOCKET_GUID).encode("ascii")).digest()).decode("ascii")


def extract_websocket_key(headers: str) -> str:
    for line in headers.split("\r\n"):
        if line.lower().startswith("sec-websocket-key:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError("missing Sec-WebSocket-Key")


def read_exact(sock: socket.socket, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise EOFError("socket closed")
        data += chunk
    return data


def read_frame(sock: socket.socket) -> tuple[int, bytes]:
    first, second = read_exact(sock, 2)
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F
    if length == 126:
        length = int.from_bytes(read_exact(sock, 2), "big")
    elif length == 127:
        length = int.from_bytes(read_exact(sock, 8), "big")
    mask = read_exact(sock, 4) if masked else b""
    payload = read_exact(sock, length)
    if masked:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return opcode, payload


def send_frame(sock: socket.socket, opcode: int, payload: bytes) -> None:
    first = 0x80 | opcode
    length = len(payload)
    if length < 126:
        header = bytes([first, length])
    elif length < (1 << 16):
        header = bytes([first, 126]) + length.to_bytes(2, "big")
    else:
        header = bytes([first, 127]) + length.to_bytes(8, "big")
    sock.sendall(header + payload)


def send_json(sock: socket.socket, payload: dict[str, object]) -> None:
    send_frame(sock, 0x1, json.dumps(payload, ensure_ascii=True).encode("utf-8"))


def _daemon_notifications(entry: dict[str, object]) -> list[dict[str, object]]:
    default_thread_id = str(entry.get("actor_id") or "thread-test")
    state = load_server_state(f"thread-{default_thread_id}")
    notifications = state.get("daemon_notifications")
    if not isinstance(notifications, list):
        return []
    return [notification for notification in notifications if isinstance(notification, dict)]


def send_daemon_notifications(sock: socket.socket, entry: dict[str, object], *, client_name: str) -> None:
    for notification in _daemon_notifications(entry):
        append_calls(
            {
                "argv": ["daemon-notification"],
                "kind": "daemon-notification",
                "notification_method": notification.get("method"),
                "params": notification.get("params"),
                "cwd": os.getcwd(),
                "actor_id": entry.get("actor_id"),
                "client_name": client_name,
            }
        )
        send_json(sock, notification)


def send_daemon_started_turn_completion(
    sock: socket.socket,
    entry: dict[str, object],
    request: dict[str, object],
    response: dict[str, object] | None,
    *,
    client_name: str,
) -> None:
    if request.get("method") != "turn/start" or response is None:
        return
    default_thread_id = str(entry.get("actor_id") or "thread-test")
    state = load_server_state(f"thread-{default_thread_id}")
    if not state.get("daemon_emit_completion_for_started_turn"):
        return
    subscribed_thread_id = state.get("daemon_subscribed_thread_id")
    if not isinstance(subscribed_thread_id, str) or not subscribed_thread_id:
        return
    result = response.get("result")
    turn = result.get("turn") if isinstance(result, dict) else None
    turn_id = turn.get("id") if isinstance(turn, dict) else None
    params = request.get("params")
    thread_id = params.get("threadId") if isinstance(params, dict) else None
    if not isinstance(turn_id, str) or not turn_id:
        return
    if not isinstance(thread_id, str) or not thread_id:
        thread_id = subscribed_thread_id
    notification = {
        "method": "turn/completed",
        "params": {
            "threadId": thread_id,
            "turn": {
                "id": turn_id,
                "items": [],
                "itemsView": "summary",
                "status": "completed",
                "error": None,
                "startedAt": 0,
                "completedAt": 1,
                "durationMs": 1,
            },
        },
    }
    append_calls(
        {
            "argv": ["daemon-notification"],
            "kind": "daemon-notification",
            "notification_method": notification.get("method"),
            "params": notification.get("params"),
            "cwd": os.getcwd(),
            "actor_id": entry.get("actor_id"),
            "client_name": client_name,
        }
    )
    send_json(sock, notification)


def handle_websocket_connection(
    sock: socket.socket,
    entry: dict[str, object],
    *,
    is_running: Callable[[], bool],
) -> None:
    sock.settimeout(0.5)
    headers = read_http_request(sock)
    websocket_key = extract_websocket_key(headers)
    client_name = ""
    sock.sendall(
        (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {websocket_accept_value(websocket_key)}\r\n"
            "\r\n"
        ).encode("ascii")
    )
    while is_running():
        try:
            opcode, payload = read_frame(sock)
        except (TimeoutError, socket.timeout):
            continue
        except (EOFError, OSError):
            return
        if opcode == 0x1:
            message = json.loads(payload.decode("utf-8"))
            if not isinstance(message, dict):
                continue
            method = message.get("method")
            if method == "initialize":
                params = message.get("params")
                client_info = params.get("clientInfo") if isinstance(params, dict) else None
                name = client_info.get("name") if isinstance(client_info, dict) else None
                if isinstance(name, str):
                    client_name = name
            response = handle_rpc_message(message, entry, client_name=client_name)
            if response is not None:
                send_json(sock, response)
            if (
                client_name == "buddyswitch_daemon"
                and method == "thread/resume"
                and isinstance(response, dict)
                and "result" in response
            ):
                params = message.get("params")
                thread_id = params.get("threadId") if isinstance(params, dict) else None
                if isinstance(thread_id, str) and thread_id:
                    default_thread_id = str(entry.get("actor_id") or "thread-test")
                    state = load_server_state(f"thread-{default_thread_id}")
                    state["daemon_subscribed_thread_id"] = thread_id
                    save_server_state(state)
                send_daemon_notifications(sock, entry, client_name=client_name)
            if client_name == "buddyswitch_daemon":
                send_daemon_started_turn_completion(sock, entry, message, response, client_name=client_name)
        elif opcode == 0x8:
            try:
                send_frame(sock, 0x8, payload)
            except OSError:
                pass
            return
        elif opcode == 0x9:
            try:
                send_frame(sock, 0xA, payload)
            except OSError:
                return
