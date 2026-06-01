#!/usr/bin/env python3
"""Client helpers for central daemon and instance mailbox sockets."""

from __future__ import annotations

import errno
import hashlib
import os
from pathlib import Path
import socket
import sys
import time
from typing import Any
import uuid

SCRIPTS = Path(__file__).resolve().parents[2]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from runtime_kernel import protocol  # noqa: E402


CENTRAL_DAEMON_PROTOCOL = "buddyswitch-central-daemon/v1"
MAILBOX_PROTOCOL = "buddyswitch-daemon-mailbox/v1"
DEFAULT_CONNECT_TIMEOUT_SECONDS = 0.75
DEFAULT_RESPONSE_TIMEOUT_SECONDS = 5.0


class DaemonClientError(RuntimeError):
    def __init__(self, code: str, message: str, *, response: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.response = response


def central_daemon_socket_path_for_shared_root(shared_root: Path) -> Path:
    root = Path(shared_root).expanduser().resolve(strict=False)
    socket_path = root / "run" / "central-daemon" / "central-daemon.sock"
    if len(str(socket_path).encode("utf-8")) < 100:
        return socket_path
    digest = hashlib.sha1(str(root).encode("utf-8")).hexdigest()[:12]
    return Path("/tmp") / f"buddyswitch-central-daemon-{digest}.sock"


def central_daemon_socket_from_env() -> Path:
    raw_socket = os.environ.get("BUDDYSWITCH_CENTRAL_DAEMON_SOCKET")
    if isinstance(raw_socket, str) and raw_socket.strip():
        return Path(raw_socket.strip()).expanduser().resolve(strict=False)
    raw_shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
    if isinstance(raw_shared_root, str) and raw_shared_root.strip():
        return central_daemon_socket_path_for_shared_root(Path(raw_shared_root.strip()))
    return central_daemon_socket_path_for_shared_root(Path.home() / ".codex-buddyswitch")


def _error_envelope(
    protocol_name: str,
    request_id: str,
    *,
    code: str,
    message: str,
    retriable: bool = False,
) -> dict[str, Any]:
    return {
        "protocol": protocol_name,
        "request_id": request_id,
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "retriable": retriable,
        },
    }


def _request_envelope(
    *,
    protocol_name: str,
    method: str,
    params: dict[str, Any],
    socket_path: Path,
    connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
    response_timeout_seconds: float = DEFAULT_RESPONSE_TIMEOUT_SECONDS,
    retry_until_connected: bool = True,
) -> dict[str, Any]:
    if not isinstance(method, str) or not method.strip():
        raise ValueError("method must be a non-empty string")
    if not isinstance(params, dict):
        raise ValueError("params must be an object")
    request_id = f"req-{uuid.uuid4().hex}"
    request = {
        "protocol": protocol_name,
        "request_id": request_id,
        "method": method.strip(),
        "params": dict(params),
    }
    deadline = time.monotonic() + max(0.05, connect_timeout_seconds)
    last_error: OSError | None = None
    while True:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(max(0.05, connect_timeout_seconds))
                sock.connect(str(socket_path))
                sock.settimeout(max(0.05, response_timeout_seconds))
                protocol.write_message(sock, request)
                response = protocol.read_message(sock)
        except OSError as exc:
            last_error = exc
            if (
                retry_until_connected
                and exc.errno in {errno.ENOENT, errno.ECONNREFUSED}
                and time.monotonic() < deadline
            ):
                time.sleep(0.02)
                continue
            return _error_envelope(
                protocol_name,
                request_id,
                code="daemon_socket_unavailable",
                message=f"daemon socket unavailable at {socket_path}: {exc}",
                retriable=True,
            )
        except protocol.BrokerProtocolError as exc:
            return _error_envelope(
                protocol_name,
                request_id,
                code="daemon_protocol_error",
                message=exc.message,
                retriable=False,
            )
        if response.get("protocol") != protocol_name:
            return _error_envelope(
                protocol_name,
                request_id,
                code="daemon_protocol_mismatch",
                message=f"daemon protocol mismatch: {response.get('protocol')!r}",
                retriable=False,
            )
        if response.get("request_id") != request_id:
            return _error_envelope(
                protocol_name,
                request_id,
                code="daemon_request_id_mismatch",
                message="daemon response request_id mismatch",
                retriable=False,
            )
        return response
    if last_error is not None:
        return _error_envelope(
            protocol_name,
            request_id,
            code="daemon_socket_unavailable",
            message=str(last_error),
            retriable=True,
        )
    raise RuntimeError("unreachable daemon request state")


def request_central_daemon(
    method: str,
    params: dict[str, Any],
    *,
    socket_path: Path | None = None,
) -> dict[str, Any]:
    chosen_socket = central_daemon_socket_from_env() if socket_path is None else Path(socket_path)
    envelope = _request_envelope(
        protocol_name=CENTRAL_DAEMON_PROTOCOL,
        method=method,
        params=params,
        socket_path=chosen_socket,
    )
    if envelope.get("ok") is not True:
        error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
        code = error.get("code") if isinstance(error.get("code"), str) else "central_daemon_error"
        message = error.get("message") if isinstance(error.get("message"), str) else "central daemon request failed"
        raise DaemonClientError(code, message, response=envelope)
    result = envelope.get("result")
    if not isinstance(result, dict):
        raise DaemonClientError("central_daemon_protocol_error", "central daemon success missing result", response=envelope)
    return result


def request_mailbox(method: str, params: dict[str, Any], *, socket_path: Path) -> dict[str, Any]:
    return _request_envelope(
        protocol_name=MAILBOX_PROTOCOL,
        method=method,
        params=params,
        socket_path=Path(socket_path),
        retry_until_connected=True,
    )


def register_actor(
    *,
    actor_address: dict[str, Any],
    endpoint: dict[str, Any],
    heartbeat: dict[str, Any] | None = None,
    status: str = "online",
    socket_path: Path | None = None,
) -> dict[str, Any]:
    return request_central_daemon(
        "daemon.register",
        {
            "actor_address": actor_address,
            "endpoint": endpoint,
            "heartbeat": heartbeat or {"kind": "central_daemon_rpc"},
            "status": status,
        },
        socket_path=socket_path,
    )


def unregister_actor(*, actor_address: dict[str, Any], socket_path: Path | None = None) -> dict[str, Any]:
    return request_central_daemon("daemon.unregister", {"actor_address": actor_address}, socket_path=socket_path)


def heartbeat_actor(*, actor_address: dict[str, Any], socket_path: Path | None = None) -> dict[str, Any]:
    return request_central_daemon("daemon.heartbeat", {"actor_address": actor_address}, socket_path=socket_path)


def list_contacts(*, role_id: str | None = None, socket_path: Path | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if isinstance(role_id, str) and role_id.strip():
        params["role_id"] = role_id.strip()
    return request_central_daemon("contacts.list", params, socket_path=socket_path)


def check_reachability(*, target_actor_address: dict[str, Any], socket_path: Path | None = None) -> dict[str, Any]:
    return request_central_daemon(
        "actor.check_reachability",
        {"target_actor_address": target_actor_address},
        socket_path=socket_path,
    )


def deliver_signal(*, signal: dict[str, Any], socket_path: Path | None = None) -> dict[str, Any]:
    return request_central_daemon("signal.deliver", {"signal": signal}, socket_path=socket_path)
