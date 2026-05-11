#!/usr/bin/env python3
"""Runtime broker client for product-mode turn tools."""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any

PROTOCOL = "buddyswitch-runtime-broker/v1"


class RuntimeBrokerError(RuntimeError):
    """Raised when the runtime broker is unavailable or transport fails."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        response: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.response = response
        self.details = details or {}


def broker_unavailable_feedback(*, socket_path: Path | None = None) -> dict[str, Any]:
    raw_instance_id = os.environ.get("BUDDYSWITCH_INSTANCE_ID")
    instance_id = raw_instance_id.strip() if isinstance(raw_instance_id, str) and raw_instance_id.strip() else "<instance-id>"
    feedback: dict[str, Any] = {
        "permission_boundary": "product-mode-runtime-broker",
        "stop_condition": "stop_and_report_do_not_bypass_broker",
        "allowed_next_actions": [
            "Report that the launcher-managed runtime broker is unavailable.",
            "Do not write raw BuddySwitch state directly.",
            "Do not bypass product-mode runtime safeguards via debug APIs.",
        ],
        "command_hint": f"./buddyswitch-codex instance open {instance_id}",
    }
    if socket_path is not None:
        feedback["socket_path"] = str(socket_path)
    return feedback


def runtime_broker_socket_from_env() -> Path:
    raw = os.environ.get("BUDDYSWITCH_RUNTIME_BROKER_SOCKET")
    if not isinstance(raw, str) or not raw.strip():
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            "BUDDYSWITCH_RUNTIME_BROKER_SOCKET is required in product mode.",
            details=broker_unavailable_feedback(),
        )
    return Path(raw.strip())


def _require_env(name: str) -> str:
    raw = os.environ.get(name)
    if not isinstance(raw, str) or not raw.strip():
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            f"{name} is required in product mode.",
            details=broker_unavailable_feedback(),
        )
    return raw.strip()


def request_runtime_broker(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(method, str) or not method.strip():
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            "runtime broker method is required.",
            details=broker_unavailable_feedback(),
        )
    if not isinstance(payload, dict):
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            "runtime broker payload must be an object.",
            details=broker_unavailable_feedback(),
        )

    socket_path = runtime_broker_socket_from_env()
    instance_id = _require_env("BUDDYSWITCH_INSTANCE_ID")
    active_buddy = _require_env("BUDDYSWITCH_ACTIVE_BUDDY")

    request = {
        "protocol": PROTOCOL,
        "instance_id": instance_id,
        "active_buddy": active_buddy,
        "method": method.strip(),
        "payload": payload,
    }
    encoded = json.dumps(request, ensure_ascii=True).encode("utf-8")

    chunks: list[bytes] = []
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(3.0)
            sock.connect(str(socket_path))
            sock.sendall(encoded)
            sock.shutdown(socket.SHUT_WR)
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
    except OSError as exc:
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            f"runtime broker unavailable at {socket_path}: {exc}",
            details=broker_unavailable_feedback(socket_path=socket_path),
        ) from exc

    raw = b"".join(chunks).decode("utf-8", errors="strict")
    try:
        response = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            f"runtime broker returned invalid JSON: {exc}",
            details=broker_unavailable_feedback(socket_path=socket_path),
        ) from exc
    if not isinstance(response, dict):
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            "runtime broker response must be a JSON object.",
            details=broker_unavailable_feedback(socket_path=socket_path),
        )
    if not isinstance(response.get("ok"), bool):
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            "runtime broker response must contain boolean 'ok'.",
            details=broker_unavailable_feedback(socket_path=socket_path),
        )
    return response
