"""Instance daemon mailbox socket and signal validation."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import socket
import sys
import threading
from typing import Any, Mapping


import buddyswitch.foundation.state.runtime as state_runtime  # noqa: E402
from buddyswitch.foundation.identity.model import ACTOR_ID_PATTERN, ROLE_ID_PATTERN  # noqa: E402
from buddyswitch.foundation.daemon import client as daemon_client  # noqa: E402
from buddyswitch.launcher import daemon_triggers  # noqa: E402
from buddyswitch.runtime_kernel import protocol  # noqa: E402


SIGNAL_ALLOWED_KEYS = {
    "signal_id",
    "type",
    "source_identity_id",
    "source_role_id",
    "target_identity_id",
    "target_role_id",
    "payload",
    "created_at",
}
CONTROL_METHODS = frozenset(
    {"mailbox.deliver", "mailbox.local_trigger", "mailbox.schedule_trigger"}
)


def _actor_identity_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or ACTOR_ID_PATTERN.fullmatch(value.strip()) is None:
        raise ValueError(f"{field} must be a valid actor identity id")
    return value.strip()


def _role_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or ROLE_ID_PATTERN.fullmatch(value.strip()) is None:
        raise ValueError(f"{field} must be a valid role id")
    return value.strip()


def _non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_non_empty_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _non_empty_string(value, field)


def daemon_signal_envelope(
    *,
    signal_id: str,
    signal_type: str,
    source_identity_id: str,
    source_role_id: str,
    target_identity_id: str,
    target_role_id: str,
    payload: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    return {
        "signal_id": state_runtime.require_id(signal_id, "signal_id"),
        "type": _non_empty_string(signal_type, "type"),
        "source_identity_id": _actor_identity_id(source_identity_id, "source_identity_id"),
        "source_role_id": _role_id(source_role_id, "source_role_id"),
        "target_identity_id": _actor_identity_id(target_identity_id, "target_identity_id"),
        "target_role_id": _role_id(target_role_id, "target_role_id"),
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
        source_identity_id=signal.get("source_identity_id"),
        source_role_id=signal.get("source_role_id"),
        target_identity_id=signal.get("target_identity_id"),
        target_role_id=signal.get("target_role_id"),
        payload=signal.get("payload"),
        created_at=signal.get("created_at", ""),
    )


class DaemonMailboxServer:
    def __init__(
        self,
        *,
        socket_path: Path,
        local_identity_id: str,
        local_role_id: str,
        handlers: list[Any] | tuple[Any, ...],
        context: Any | None = None,
        state: Any | None = None,
        trigger_dispatcher: Any | None = None,
        application_commands: Mapping[str, Any] | None = None,
        now: Any | None = None,
    ) -> None:
        self.socket_path = Path(socket_path).expanduser().resolve(strict=False)
        self.local_identity_id = _actor_identity_id(local_identity_id, "local_identity_id")
        self.local_role_id = _role_id(local_role_id, "local_role_id")
        self.handlers = list(handlers or [])
        self.context = context
        self.state = state
        self.trigger_dispatcher = trigger_dispatcher
        if application_commands is None:
            application_commands = {}
        if not isinstance(application_commands, Mapping):
            raise ValueError("application_commands must be a mapping")
        commands: dict[str, Any] = {}
        for key, command in application_commands.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("application command keys must be non-empty strings")
            normalized_key = key.strip()
            if normalized_key in CONTROL_METHODS:
                raise ValueError(f"application command conflicts with control method: {normalized_key}")
            if not callable(command):
                raise ValueError(f"application command must be callable: {normalized_key}")
            commands[normalized_key] = command
        self.application_commands = commands
        self.now = now
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
        try:
            self.socket_path.unlink()
        except FileNotFoundError:
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
        method = request.get("method")
        if method == "mailbox.local_trigger":
            params = request.get("params")
            if not isinstance(params, dict):
                return self._response(request_id, code="mailbox_protocol_error", message="params must be an object")
            return self._dispatch_local_trigger(request_id, params)
        if method == "mailbox.schedule_trigger":
            params = request.get("params")
            if not isinstance(params, dict):
                return self._response(request_id, code="mailbox_protocol_error", message="params must be an object")
            return self._dispatch_schedule_trigger(request_id, params)
        if method in self.application_commands:
            params = request.get("params")
            if not isinstance(params, dict):
                return self._response(request_id, code="mailbox_protocol_error", message="params must be an object")
            return self._dispatch_application_command(request_id, method, params)
        if method != "mailbox.deliver":
            return self._response(request_id, code="mailbox_unknown_method", message="unsupported mailbox method")
        params = request.get("params")
        if not isinstance(params, dict):
            return self._response(request_id, code="mailbox_protocol_error", message="params must be an object")
        try:
            signal = validate_daemon_signal(params.get("signal"))
        except Exception as exc:
            return self._response(request_id, code="invalid_signal", message=str(exc))
        if signal["target_identity_id"] != self.local_identity_id:
            return self._response(request_id, code="wrong_target_actor", message="signal target does not match local actor")
        trigger = daemon_triggers.normalize_cross_actor_signal(signal)
        return self._dispatch_trigger(request_id, trigger)

    def _dispatch_application_command(
        self,
        request_id: str | None,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        command = self.application_commands[method]
        try:
            result = command(dict(params))
        except Exception as exc:
            return self._response(request_id, code="application_command_error", message=str(exc))
        if not isinstance(result, Mapping):
            return self._response(
                request_id,
                code="application_command_error",
                message=f"application command returned invalid result: {type(result).__name__}",
            )
        return self._response(request_id, dict(result))

    def _dispatch_trigger(self, request_id: str | None, trigger: daemon_triggers.DaemonTrigger) -> dict[str, Any]:
        if callable(self.trigger_dispatcher):
            result = self.trigger_dispatcher(trigger)
            if not isinstance(result, dict):
                return self._response(
                    request_id,
                    code="mailbox_dispatch_error",
                    message=f"trigger dispatcher returned invalid result: {type(result).__name__}",
                )
            payload = dict(result)
        else:
            payload = {
                "accepted": True,
                "handled_count": 0,
                "matched_count": 0,
                "handling_status": "ignored",
            }
        payload.setdefault("trigger", trigger.to_payload())
        return self._response(request_id, payload)

    def _normalize_local_trigger_request(self, params: dict[str, Any]) -> daemon_triggers.DaemonTrigger:
        identity_id = _actor_identity_id(params.get("identity_id"), "identity_id")
        role_id = _role_id(params.get("role_id"), "role_id")
        if identity_id != self.local_identity_id:
            raise PermissionError("signal target does not match local actor")
        trigger_type = _non_empty_string(params.get("type"), "type")
        payload = params.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        source_context = params.get("source_context", {})
        if not isinstance(source_context, dict):
            raise ValueError("source_context must be an object")
        return daemon_triggers.normalize_local_trigger(
            trigger_type=trigger_type,
            target_identity_id=identity_id,
            target_role_id=role_id,
            origin_id=_optional_non_empty_string(params.get("origin_id"), "origin_id"),
            correlation_id=_optional_non_empty_string(params.get("correlation_id"), "correlation_id"),
            payload=dict(payload),
            source_context=dict(source_context),
        )

    def _dispatch_local_trigger(self, request_id: str | None, params: dict[str, Any]) -> dict[str, Any]:
        try:
            trigger = self._normalize_local_trigger_request(params)
        except PermissionError as exc:
            return self._response(request_id, code="wrong_target_actor", message=str(exc))
        except Exception as exc:
            return self._response(request_id, code="invalid_local_trigger", message=str(exc))
        return self._dispatch_trigger(request_id, trigger)

    def _now_text(self) -> str | None:
        if callable(self.now):
            value = self.now()
            if isinstance(value, str) and value:
                return value
        return None

    def _dispatch_schedule_trigger(self, request_id: str | None, params: dict[str, Any]) -> dict[str, Any]:
        if self.state is None or not callable(getattr(self.state, "create_schedule", None)):
            return self._response(
                request_id,
                code="schedule_unavailable",
                message="daemon state does not support scheduled triggers",
            )
        try:
            source_context = params.get("source_context", {})
            if source_context is None:
                source_context = {}
            if not isinstance(source_context, dict):
                raise ValueError("source_context must be an object")
            schedule_key = params.get("schedule_key")
            if schedule_key is None:
                schedule = self.state.create_schedule(
                    delay_seconds=params.get("delay_seconds"),
                    trigger_type=params.get("type"),
                    payload=params.get("payload"),
                    source_context=source_context,
                    now=self._now_text(),
                )
            else:
                if not isinstance(schedule_key, str) or not schedule_key.strip():
                    raise ValueError("schedule_key must be a non-empty string when provided")
                if not callable(getattr(self.state, "upsert_schedule", None)):
                    raise ValueError("daemon state does not support keyed scheduled triggers")
                schedule = self.state.upsert_schedule(
                    delay_seconds=params.get("delay_seconds"),
                    trigger_type=params.get("type"),
                    payload=params.get("payload"),
                    source_context=source_context,
                    schedule_key=schedule_key.strip(),
                    now=self._now_text(),
                )
        except Exception as exc:
            return self._response(request_id, code="invalid_schedule_trigger", message=str(exc))
        return self._response(request_id, {"schedule": schedule})


def mailbox_socket_path(instance_root: Path) -> Path:
    root = Path(instance_root).expanduser().resolve(strict=False)
    socket_path = root / "runtime" / "daemon" / "mailbox.sock"
    if len(str(socket_path).encode("utf-8")) < 100:
        return socket_path
    digest = hashlib.sha1(str(root).encode("utf-8")).hexdigest()[:12]
    return Path("/tmp") / f"buddyswitch-daemon-mailbox-{digest}.sock"
