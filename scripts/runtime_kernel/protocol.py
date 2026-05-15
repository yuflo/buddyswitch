#!/usr/bin/env python3
"""Runtime broker v2 framing and envelope utilities."""

from __future__ import annotations

import json
from typing import Any

PROTOCOL = "buddyswitch-runtime-broker/v2"
HEADER_LIMIT_BYTES = 8192
BODY_LIMIT_BYTES = 1048576


class BrokerProtocolError(ValueError):
    """Raised when a broker wire message violates protocol constraints."""

    def __init__(self, code: str, message: str, *, request_id: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.request_id = request_id


def make_request(
    *,
    request_id: str,
    method: str,
    params: dict[str, Any],
    deadline_ms: int,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "protocol": PROTOCOL,
        "request_id": request_id,
        "method": method,
        "params": params,
        "deadline_ms": deadline_ms,
    }
    if isinstance(idempotency_key, str) and idempotency_key.strip():
        request["idempotency_key"] = idempotency_key.strip()
    return request


def _raise_protocol(message: str, *, request_id: str | None = None) -> None:
    raise BrokerProtocolError("E_RUNTIME_BROKER_PROTOCOL", message, request_id=request_id)


def _read_until(sock: Any, marker: bytes, *, header_limit_bytes: int) -> bytes:
    buffer = bytearray()
    while marker not in buffer:
        chunk = sock.recv(1)
        if not chunk:
            _raise_protocol("unexpected EOF while reading broker headers")
        buffer.extend(chunk)
        if len(buffer) > header_limit_bytes:
            _raise_protocol("broker header exceeds limit")
    return bytes(buffer)


def _read_exact(sock: Any, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            _raise_protocol("unexpected EOF while reading broker body")
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
        _raise_protocol(f"broker header must be ASCII: {exc}")

    content_length: int | None = None
    for line in header_text.split("\r\n"):
        if not line:
            continue
        if ":" not in line:
            _raise_protocol("invalid broker header line")
        name, value = line.split(":", 1)
        if name.strip().lower() == "content-length":
            value = value.strip()
            if not value.isdigit():
                _raise_protocol("Content-Length must be a non-negative integer")
            content_length = int(value)

    if content_length is None:
        _raise_protocol("missing Content-Length header")
    if content_length > body_limit_bytes:
        _raise_protocol("broker body exceeds limit")

    body_bytes = _read_exact(sock, content_length)
    payload_bytes = body_bytes[:content_length]
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _raise_protocol(f"invalid JSON body: {exc}")
    if not isinstance(payload, dict):
        _raise_protocol("broker message must decode to JSON object")
    return payload


def write_message(sock: Any, payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        _raise_protocol("broker payload must be a JSON object")
    body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    sock.sendall(header + body)


def validate_request(request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict):
        _raise_protocol("request must be an object")

    protocol = request.get("protocol")
    if protocol != PROTOCOL:
        _raise_protocol(f"unsupported protocol: {protocol!r}")

    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        _raise_protocol("request_id must be a non-empty string")

    method = request.get("method")
    if not isinstance(method, str) or not method.strip():
        _raise_protocol("method must be a non-empty string", request_id=request_id)

    params = request.get("params")
    if not isinstance(params, dict):
        _raise_protocol("params must be an object", request_id=request_id)

    deadline_ms = request.get("deadline_ms")
    if not isinstance(deadline_ms, int) or deadline_ms <= 0:
        _raise_protocol("deadline_ms must be a positive integer", request_id=request_id)

    return request


def success_response(request_id: str | None, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol": PROTOCOL,
        "request_id": request_id,
        "ok": True,
        "result": result,
    }


def error_response(
    request_id: str | None,
    error: dict[str, Any] | None = None,
    *,
    code: str | None = None,
    message: str | None = None,
    retriable: bool | None = None,
    **extra: Any,
) -> dict[str, Any]:
    if error is not None:
        if code is None:
            code = str(error.get("code", "E_RUNTIME_BROKER_PROTOCOL"))
        if message is None:
            message = str(error.get("message", "runtime broker error"))
        if retriable is None:
            retriable = bool(error.get("retriable", False))
        for key, value in error.items():
            if key not in {"code", "message", "retriable"} and key not in extra:
                extra[key] = value
    if code is None:
        code = "E_RUNTIME_BROKER_PROTOCOL"
    if message is None:
        message = "runtime broker error"
    if retriable is None:
        retriable = False

    error_payload: dict[str, Any] = {
        "code": code,
        "message": message,
        "retriable": retriable,
    }
    for key, value in extra.items():
        if value is not None:
            error_payload[key] = value
    return {
        "protocol": PROTOCOL,
        "request_id": request_id,
        "ok": False,
        "error": error_payload,
    }
