"""Create a Chrome CDP page target without foreground activation."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import socket
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener


WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
WEBSOCKET_VERSION = "13"


class CdpTargetError(RuntimeError):
    pass


def _make_sec_websocket_accept(key: str) -> str:
    digest = hashlib.sha1((key + WEBSOCKET_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def _read_until(sock: socket.socket, marker: bytes, timeout_seconds: float) -> bytes:
    sock.settimeout(timeout_seconds)
    data = b""
    while marker not in data:
        chunk = sock.recv(4096)
        if not chunk:
            raise CdpTargetError("browser websocket closed during handshake")
        data += chunk
    return data


def _read_exact(sock: socket.socket, length: int, timeout_seconds: float, buffer: bytearray) -> bytes:
    sock.settimeout(timeout_seconds)
    while len(buffer) < length:
        chunk = sock.recv(4096)
        if not chunk:
            raise CdpTargetError("browser websocket closed while reading response")
        buffer.extend(chunk)
    payload = bytes(buffer[:length])
    del buffer[:length]
    return payload


def _send_client_frame(sock: socket.socket, payload: bytes) -> None:
    first = 0x80 | 0x1
    length = len(payload)
    if length < 126:
        header = bytes([first, 0x80 | length])
    elif length < (1 << 16):
        header = bytes([first, 0x80 | 126]) + length.to_bytes(2, "big")
    else:
        header = bytes([first, 0x80 | 127]) + length.to_bytes(8, "big")
    mask = os.urandom(4)
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    sock.sendall(header + mask + masked)


def _read_server_frame(sock: socket.socket, timeout_seconds: float, buffer: bytearray) -> tuple[int, bytes]:
    first, second = _read_exact(sock, 2, timeout_seconds, buffer)
    opcode = first & 0x0F
    length = second & 0x7F
    masked = bool(second & 0x80)
    if length == 126:
        length = int.from_bytes(_read_exact(sock, 2, timeout_seconds, buffer), "big")
    elif length == 127:
        length = int.from_bytes(_read_exact(sock, 8, timeout_seconds, buffer), "big")
    mask = _read_exact(sock, 4, timeout_seconds, buffer) if masked else b""
    payload = _read_exact(sock, length, timeout_seconds, buffer)
    if masked:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return opcode, payload


def _browser_version(browser_url: str, timeout_seconds: float) -> dict[str, Any]:
    version_url = f"{browser_url.rstrip('/')}/json/version"
    request = Request(version_url, method="GET")
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise CdpTargetError(f"Chrome DevTools returned HTTP {exc.code} for /json/version") from exc
    except (URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise CdpTargetError(f"failed to read Chrome DevTools /json/version: {exc}") from exc
    if not isinstance(payload, dict):
        raise CdpTargetError("Chrome DevTools /json/version did not return an object")
    return payload


def _browser_websocket_url(browser_url: str, timeout_seconds: float) -> str:
    version = _browser_version(browser_url, timeout_seconds)
    websocket_url = version.get("webSocketDebuggerUrl")
    if not isinstance(websocket_url, str) or not websocket_url.strip():
        raise CdpTargetError("Chrome DevTools /json/version is missing webSocketDebuggerUrl")
    return websocket_url.strip()


def _connect_websocket(websocket_url: str, timeout_seconds: float) -> tuple[socket.socket, bytearray]:
    parsed = urlparse(websocket_url)
    if parsed.scheme != "ws":
        raise CdpTargetError(f"unsupported browser websocket scheme: {parsed.scheme or '<missing>'}")
    if not parsed.hostname:
        raise CdpTargetError("browser websocket URL is missing a host")
    port = parsed.port or 80
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    key = base64.b64encode(os.urandom(16)).decode("ascii")
    sock = socket.create_connection((parsed.hostname, port), timeout=timeout_seconds)
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {parsed.hostname}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: {WEBSOCKET_VERSION}\r\n"
        "\r\n"
    ).encode("ascii")
    try:
        sock.sendall(request)
        raw_response = _read_until(sock, b"\r\n\r\n", timeout_seconds)
    except OSError as exc:
        sock.close()
        raise CdpTargetError(f"failed to open browser websocket: {exc}") from exc

    header_bytes, _, remainder = raw_response.partition(b"\r\n\r\n")
    header_text = header_bytes.decode("ascii", errors="replace")
    lines = header_text.split("\r\n")
    if not lines or " 101 " not in lines[0]:
        sock.close()
        raise CdpTargetError(f"browser websocket upgrade failed: {lines[0] if lines else 'empty response'}")

    accept = None
    for line in lines[1:]:
        if line.lower().startswith("sec-websocket-accept:"):
            accept = line.split(":", 1)[1].strip()
            break
    if accept != _make_sec_websocket_accept(key):
        sock.close()
        raise CdpTargetError("browser websocket returned invalid Sec-WebSocket-Accept")
    return sock, bytearray(remainder)


def _send_browser_command(
    browser_url: str,
    request: dict[str, Any],
    *,
    timeout_seconds: float,
    response_name: str,
) -> dict[str, Any]:
    websocket_url = _browser_websocket_url(browser_url, timeout_seconds)
    sock, buffer = _connect_websocket(websocket_url, timeout_seconds)
    try:
        _send_client_frame(sock, json.dumps(request, ensure_ascii=True, separators=(",", ":")).encode("utf-8"))
        while True:
            opcode, payload = _read_server_frame(sock, timeout_seconds, buffer)
            if opcode == 0x8:
                raise CdpTargetError(f"browser websocket closed before {response_name} response")
            if opcode == 0x9:
                _send_client_frame(sock, payload)
                continue
            if opcode != 0x1:
                continue
            try:
                message = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise CdpTargetError("browser websocket returned invalid JSON") from exc
            if not isinstance(message, dict) or message.get("id") != request.get("id"):
                continue
            if "error" in message:
                error = message.get("error")
                if isinstance(error, dict) and isinstance(error.get("message"), str):
                    raise CdpTargetError(error["message"])
                raise CdpTargetError(json.dumps(error, ensure_ascii=True))
            result = message.get("result")
            if not isinstance(result, dict):
                raise CdpTargetError(f"{response_name} response missing result")
            return result
    except OSError as exc:
        raise CdpTargetError(f"browser websocket communication failed: {exc}") from exc
    finally:
        try:
            sock.close()
        except OSError:
            pass


def create_background_target(browser_url: str, target_url: str, timeout_seconds: float) -> dict[str, Any]:
    result = _send_browser_command(
        browser_url,
        {
            "id": 1,
            "method": "Target.createTarget",
            "params": {
                "url": target_url,
                "background": True,
            },
        },
        timeout_seconds=timeout_seconds,
        response_name="Target.createTarget",
    )
    if not isinstance(result.get("targetId"), str):
        raise CdpTargetError("Target.createTarget response missing result.targetId")
    return result


def close_target(browser_url: str, target_id: str, timeout_seconds: float = 3.0) -> dict[str, Any]:
    if not isinstance(target_id, str) or not target_id.strip():
        raise CdpTargetError("target_id must be a non-empty string")
    result = _send_browser_command(
        browser_url,
        {
            "id": 1,
            "method": "Target.closeTarget",
            "params": {
                "targetId": target_id.strip(),
            },
        },
        timeout_seconds=timeout_seconds,
        response_name="Target.closeTarget",
    )
    if result.get("success") is not True:
        raise CdpTargetError("Target.closeTarget response missing success=true")
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a non-activating Chrome CDP page target.")
    parser.add_argument("--browser-url", required=True, help="Chrome DevTools HTTP endpoint, for example http://127.0.0.1:9222.")
    parser.add_argument("--url", required=True, help="Target URL to open.")
    parser.add_argument("--timeout", type=float, default=3.0, help="HTTP and websocket timeout in seconds.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = create_background_target(args.browser_url, args.url, args.timeout)
    except CdpTargetError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
