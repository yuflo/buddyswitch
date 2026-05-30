#!/usr/bin/env python3
"""Instance daemon mailbox socket and signal validation."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import socket
import sys
import threading
from typing import Any

HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from env.repos import runtime_files  # noqa: E402
from env.tool_runtime.actor_profile import RuntimeActorAddress  # noqa: E402
from env.tool_runtime import daemon_client  # noqa: E402
from runtime_kernel import protocol  # noqa: E402


SIGNAL_ALLOWED_KEYS = {
    "signal_id",
    "type",
    "source_actor_address",
    "target_actor_address",
    "payload",
    "created_at",
}


def _actor_address_payload(value: Any, field: str) -> dict[str, str]:
    if isinstance(value, RuntimeActorAddress):
        return value.to_payload()
    try:
        return RuntimeActorAddress.from_payload(value).to_payload()
    except Exception as exc:
        raise ValueError(f"{field} must be a valid actor_address") from exc


def _non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def daemon_signal_envelope(
    *,
    signal_id: str,
    signal_type: str,
    source_actor_address: RuntimeActorAddress | dict[str, Any],
    target_actor_address: RuntimeActorAddress | dict[str, Any],
    payload: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    return {
        "signal_id": runtime_files.require_id(signal_id, "signal_id"),
        "type": _non_empty_string(signal_type, "type"),
        "source_actor_address": _actor_address_payload(source_actor_address, "source_actor_address"),
        "target_actor_address": _actor_address_payload(target_actor_address, "target_actor_address"),
        "payload": dict(payload),
        "created_at": _non_empty_string(created_at, "created_at"),
    }


def validate_daemon_signal(signal: Any) -> dict[str, Any]:
    if not isinstance(signal, dict):
        raise ValueError("DaemonSignalEnvelope must be an object")
    extra = sorted(key for key in signal if key not in SIGNAL_ALLOWED_KEYS)
    missing = sorted(key for key in SIGNAL_ALLOWED_KEYS if key not in signal)
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing fields: {', '.join(missing)}")
        if extra:
            details.append(f"unsupported fields: {', '.join(extra)}")
        raise ValueError(f"DaemonSignalEnvelope must contain only generic signal fields; {'; '.join(details)}")
    return daemon_signal_envelope(
        signal_id=signal.get("signal_id", ""),
        signal_type=signal.get("type", ""),
        source_actor_address=signal.get("source_actor_address"),
        target_actor_address=signal.get("target_actor_address"),
        payload=signal.get("payload"),
        created_at=signal.get("created_at", ""),
    )


class DaemonMailboxServer:
    def __init__(
        self,
        *,
        socket_path: Path,
        local_actor_address: RuntimeActorAddress | dict[str, Any],
        handlers: list[Any] | tuple[Any, ...],
        context: Any | None = None,
        state: Any | None = None,
        actions_factory: Any | None = None,
    ) -> None:
        self.socket_path = Path(socket_path).expanduser().resolve(strict=False)
        self.local_actor_address = RuntimeActorAddress.from_payload(
            _actor_address_payload(local_actor_address, "local_actor_address")
        )
        self.handlers = list(handlers or [])
        self.context = context
        self.state = state
        self.actions_factory = actions_factory
        self._stop_event = threading.Event()
        self._server: socket.socket | None = None

    def close(self) -> None:
        self._stop_event.set()
        server = self._server
        if server is not None:
            try:
                server.close()
            except OSError:
                pass

    def serve_forever(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.socket_path.unlink()
        except FileNotFoundError:
            pass
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            self._server = server
            server.bind(str(self.socket_path))
            server.listen(64)
            server.settimeout(0.05)
            os.chmod(self.socket_path, 0o600)
            try:
                while not self._stop_event.is_set():
                    try:
                        conn, _ = server.accept()
                    except socket.timeout:
                        continue
                    except OSError:
                        if self._stop_event.is_set():
                            break
                        continue
                    self._handle_connection(conn)
            finally:
                self._server = None
                try:
                    self.socket_path.unlink()
                except OSError:
                    pass

    def _response(
        self,
        request_id: str | None,
        result: dict[str, Any] | None = None,
        *,
        code: str | None = None,
        message: str | None = None,
    ) -> dict[str, Any]:
        if code is None:
            return {
                "protocol": daemon_client.MAILBOX_PROTOCOL,
                "request_id": request_id,
                "ok": True,
                "result": result or {"ok": True},
            }
        return {
            "protocol": daemon_client.MAILBOX_PROTOCOL,
            "request_id": request_id,
            "ok": False,
            "error": {"code": code, "message": message or code, "retriable": False},
        }

    def _handle_connection(self, conn: socket.socket) -> None:
        request_id: str | None = None
        with conn:
            try:
                request = protocol.read_message(conn)
                request_id = request.get("request_id") if isinstance(request.get("request_id"), str) else None
                response = self.dispatch(request)
            except Exception as exc:
                response = self._response(request_id, code="mailbox_protocol_error", message=str(exc))
            try:
                protocol.write_message(conn, response)
            except OSError:
                return

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("request_id") if isinstance(request.get("request_id"), str) else None
        if request.get("protocol") != daemon_client.MAILBOX_PROTOCOL:
            return self._response(request_id, code="mailbox_protocol_error", message="unsupported mailbox protocol")
        if request.get("method") != "mailbox.deliver":
            return self._response(request_id, code="mailbox_unknown_method", message="unsupported mailbox method")
        params = request.get("params")
        if not isinstance(params, dict):
            return self._response(request_id, code="mailbox_protocol_error", message="params must be an object")
        try:
            signal = validate_daemon_signal(params.get("signal"))
        except Exception as exc:
            return self._response(request_id, code="invalid_signal", message=str(exc))
        to_actor = RuntimeActorAddress.from_payload(signal["target_actor_address"])
        if to_actor != self.local_actor_address:
            return self._response(request_id, code="wrong_target_actor", message="signal target does not match local actor")

        handled = 0
        errors: list[str] = []
        matched = 0
        for handler in self.handlers:
            handles = getattr(handler, "handles", None)
            if not callable(handles):
                continue
            try:
                if handles(signal) is not True:
                    continue
            except Exception as exc:
                errors.append(str(exc))
                continue
            matched += 1
            handle = getattr(handler, "handle_signal", None)
            if not callable(handle):
                continue
            try:
                actions = self.actions_factory() if callable(self.actions_factory) else None
                result = handle(self.context, self.state, actions, signal)
                status = getattr(result, "status", None)
                if isinstance(result, dict):
                    status = result.get("status")
                if status == "handled":
                    handled += 1
                if status == "failed":
                    message = result.get("message") if isinstance(result, dict) else getattr(result, "message", "")
                    errors.append(str(message or "handler failed"))
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            return self._response(
                request_id,
                {
                    "accepted": True,
                    "handled_count": handled,
                    "matched_count": matched,
                    "handling_status": "failed",
                    "handling_error": "; ".join(errors),
                    "signal": signal,
                },
            )
        handling_status = "handled" if handled > 0 else "ignored"
        return self._response(
            request_id,
            {
                "accepted": True,
                "handled_count": handled,
                "matched_count": matched,
                "handling_status": handling_status,
                "signal": signal,
            },
        )


def mailbox_socket_path(instance_root: Path) -> Path:
    root = Path(instance_root).expanduser().resolve(strict=False)
    socket_path = root / "runtime" / "daemon" / "mailbox.sock"
    if len(str(socket_path).encode("utf-8")) < 100:
        return socket_path
    digest = hashlib.sha1(str(root).encode("utf-8")).hexdigest()[:12]
    return Path("/tmp") / f"buddyswitch-daemon-mailbox-{digest}.sock"
