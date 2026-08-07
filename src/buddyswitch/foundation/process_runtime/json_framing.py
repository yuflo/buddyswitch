"""Content-Length framed JSON objects for local Unix socket transports."""

from __future__ import annotations

import json
from typing import Any


HEADER_LIMIT_BYTES = 8192
BODY_LIMIT_BYTES = 1048576


class JsonFramingError(ValueError):
    """Raised when a framed JSON socket message is malformed."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _raise_framing(message: str) -> None:
    raise JsonFramingError(message)


def _read_until(sock: Any, marker: bytes, *, header_limit_bytes: int) -> bytes:
    buffer = bytearray()
    while marker not in buffer:
        chunk = sock.recv(1)
        if not chunk:
            _raise_framing("unexpected EOF while reading framed JSON headers")
        buffer.extend(chunk)
        if len(buffer) > header_limit_bytes:
            _raise_framing("framed JSON header exceeds limit")
    return bytes(buffer)


def _read_exact(sock: Any, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            _raise_framing("unexpected EOF while reading framed JSON body")
        data.extend(chunk)
    return bytes(data)


def read_message(
    sock: Any,
    *,
    header_limit_bytes: int = HEADER_LIMIT_BYTES,
    body_limit_bytes: int = BODY_LIMIT_BYTES,
) -> dict[str, Any]:
    raw = _read_until(sock, b"\r\n\r\n", header_limit_bytes=header_limit_bytes)
    header_blob, _ = raw.split(b"\r\n\r\n", 1)
    try:
        header_text = header_blob.decode("ascii")
    except UnicodeDecodeError as exc:
        _raise_framing(f"framed JSON header must be ASCII: {exc}")

    content_length: int | None = None
    for line in header_text.split("\r\n"):
        if not line:
            continue
        if ":" not in line:
            _raise_framing("invalid framed JSON header line")
        name, value = line.split(":", 1)
        if name.strip().lower() == "content-length":
            value = value.strip()
            if not value.isdigit():
                _raise_framing("Content-Length must be a non-negative integer")
            content_length = int(value)

    if content_length is None:
        _raise_framing("missing Content-Length header")
    if content_length > body_limit_bytes:
        _raise_framing("framed JSON body exceeds limit")

    body_bytes = _read_exact(sock, content_length)
    payload_bytes = body_bytes[:content_length]
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _raise_framing(f"invalid JSON body: {exc}")
    if not isinstance(payload, dict):
        _raise_framing("framed JSON message must decode to JSON object")
    return payload


def write_message(sock: Any, payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        _raise_framing("framed JSON payload must be a JSON object")
    body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    sock.sendall(header + body)
