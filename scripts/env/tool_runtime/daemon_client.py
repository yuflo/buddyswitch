#!/usr/bin/env python3
"""Client helpers for central daemon and instance mailbox sockets."""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
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
from env.domain.identity import ACTOR_ID_PATTERN, ROLE_ID_PATTERN  # noqa: E402


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


def mailbox_socket_path_for_instance_root(instance_root: Path) -> Path:
    root = Path(instance_root).expanduser().resolve(strict=False)
    socket_path = root / "runtime" / "daemon" / "mailbox.sock"
    if len(str(socket_path).encode("utf-8")) < 100:
        return socket_path
    digest = hashlib.sha1(str(root).encode("utf-8")).hexdigest()[:12]
    return Path("/tmp") / f"buddyswitch-daemon-mailbox-{digest}.sock"


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


def schedule_trigger(
    *,
    instance_root: Path,
    delay_seconds: int | float,
    trigger_type: str,
    payload: dict[str, Any],
    source_context: dict[str, Any] | None = None,
    schedule_key: str | None = None,
) -> dict[str, Any]:
    params = {
        "delay_seconds": delay_seconds,
        "type": trigger_type,
        "payload": dict(payload),
        "source_context": dict(source_context or {}),
    }
    if schedule_key is not None:
        params["schedule_key"] = schedule_key
    envelope = request_mailbox(
        "mailbox.schedule_trigger",
        params,
        socket_path=mailbox_socket_path_for_instance_root(instance_root),
    )
    if envelope.get("ok") is not True:
        error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
        code = error.get("code") if isinstance(error.get("code"), str) else "daemon_schedule_error"
        message = error.get("message") if isinstance(error.get("message"), str) else "daemon schedule request failed"
        raise DaemonClientError(code, message, response=envelope)
    result = envelope.get("result")
    if not isinstance(result, dict):
        raise DaemonClientError("daemon_schedule_protocol_error", "daemon schedule success missing result", response=envelope)
    return result


def _mailbox_success_result(envelope: dict[str, Any], *, error_code: str, protocol_code: str) -> dict[str, Any]:
    if envelope.get("ok") is not True:
        error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
        code = error.get("code") if isinstance(error.get("code"), str) else error_code
        message = error.get("message") if isinstance(error.get("message"), str) else "daemon mailbox request failed"
        raise DaemonClientError(code, message, response=envelope)
    result = envelope.get("result")
    if not isinstance(result, dict):
        raise DaemonClientError(protocol_code, "daemon mailbox success missing result", response=envelope)
    return result


def execute_task_sys_instruction(
    *,
    instance_root: Path,
    instruction: dict[str, Any],
    socket_path: Path | None = None,
) -> dict[str, Any]:
    envelope = request_mailbox(
        "mailbox.task_sys.execute_instruction",
        {"instruction": dict(instruction)},
        socket_path=Path(socket_path) if socket_path is not None else mailbox_socket_path_for_instance_root(instance_root),
    )
    return _mailbox_success_result(
        envelope,
        error_code="daemon_task_sys_execute_error",
        protocol_code="daemon_task_sys_execute_protocol_error",
    )


def cleanup_task_sys_side_lease(
    *,
    instance_root: Path,
    task_id: str,
    socket_path: Path | None = None,
) -> dict[str, Any]:
    envelope = request_mailbox(
        "mailbox.task_sys.cleanup_side_lease",
        {"task_id": task_id},
        socket_path=Path(socket_path) if socket_path is not None else mailbox_socket_path_for_instance_root(instance_root),
    )
    return _mailbox_success_result(
        envelope,
        error_code="daemon_task_sys_cleanup_error",
        protocol_code="daemon_task_sys_cleanup_protocol_error",
    )


def _command_task_sys_execute(args: argparse.Namespace) -> int:
    instruction = json.loads(args.instruction_json)
    if not isinstance(instruction, dict):
        raise ValueError("--instruction-json must decode to an object")
    payload = execute_task_sys_instruction(
        instance_root=Path(args.instance_root),
        instruction=instruction,
        socket_path=Path(args.socket) if args.socket else None,
    )
    print(json.dumps(payload, ensure_ascii=True))
    return 0


def _command_task_sys_cleanup(args: argparse.Namespace) -> int:
    payload = cleanup_task_sys_side_lease(
        instance_root=Path(args.instance_root),
        task_id=args.task_id,
        socket_path=Path(args.socket) if args.socket else None,
    )
    print(json.dumps(payload, ensure_ascii=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    execute = subparsers.add_parser("task-sys-execute")
    execute.add_argument("--instance-root", required=True)
    execute.add_argument("--instruction-json", required=True)
    execute.add_argument("--socket")
    execute.set_defaults(func=_command_task_sys_execute)

    cleanup = subparsers.add_parser("task-sys-cleanup")
    cleanup.add_argument("--instance-root", required=True)
    cleanup.add_argument("--task-id", required=True)
    cleanup.add_argument("--socket")
    cleanup.set_defaults(func=_command_task_sys_cleanup)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except DaemonClientError as exc:
        print(exc.message, file=sys.stderr)
        return 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def register_actor(
    *,
    identity_id: str,
    role_id: str,
    endpoint: dict[str, Any],
    heartbeat: dict[str, Any] | None = None,
    status: str = "online",
    socket_path: Path | None = None,
) -> dict[str, Any]:
    return request_central_daemon(
        "daemon.register",
        {
            "identity_id": identity_id,
            "role_id": role_id,
            "endpoint": endpoint,
            "heartbeat": heartbeat or {"kind": "central_daemon_rpc"},
            "status": status,
        },
        socket_path=socket_path,
    )


def unregister_actor(*, identity_id: str, role_id: str, socket_path: Path | None = None) -> dict[str, Any]:
    return request_central_daemon("daemon.unregister", {"identity_id": identity_id, "role_id": role_id}, socket_path=socket_path)


def heartbeat_actor(*, identity_id: str, socket_path: Path | None = None) -> dict[str, Any]:
    return request_central_daemon("daemon.heartbeat", {"identity_id": identity_id}, socket_path=socket_path)


def list_online_actors(*, role_id: str | None = None, socket_path: Path | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if isinstance(role_id, str) and role_id.strip():
        params["role_id"] = role_id.strip()
    return request_central_daemon("actor_directory.list_online", params, socket_path=socket_path)


def check_reachability(*, target_identity_id: str, socket_path: Path | None = None) -> dict[str, Any]:
    return request_central_daemon(
        "actor.check_reachability",
        {"target_identity_id": target_identity_id},
        socket_path=socket_path,
    )


def _non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _actor_identity_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or ACTOR_ID_PATTERN.fullmatch(value.strip()) is None:
        raise ValueError(f"{field} must be a valid actor identity id")
    return value.strip()


def _role_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or ROLE_ID_PATTERN.fullmatch(value.strip()) is None:
        raise ValueError(f"{field} must be a valid role id")
    return value.strip()


def wake_im_actor(
    payload: dict[str, Any],
    *,
    check_reachability_fn: Any | None = None,
    request_mailbox_fn: Any | None = None,
    socket_path: Path | None = None,
) -> dict[str, Any]:
    """Bridge durable Central IM acceptance into the target actor daemon mailbox."""

    try:
        if not isinstance(payload, dict):
            raise ValueError("wake payload must be an object")
        if payload.get("type") != "im.message.created":
            return {"wake_status": "not_applicable", "runtime_target": "none", "error": "unsupported IM wake type"}
        target_identity_id = _actor_identity_id(payload.get("target_identity_id"), "target_identity_id")
        target_role_id = _role_id(payload.get("target_role_id"), "target_role_id")
        message_id = _non_empty_text(payload.get("message_id"), "message_id")
        conversation_id = _non_empty_text(payload.get("conversation_id"), "conversation_id")
        event_id = _non_empty_text(payload.get("event_id"), "event_id")
        wake_id = _non_empty_text(payload.get("wake_id") or f"imwake-{uuid.uuid4().hex[:12]}", "wake_id")
    except Exception as exc:
        return {"wake_status": "wake_failed", "runtime_target": "none", "error": str(exc)}

    reachability_call = check_reachability_fn or check_reachability
    mailbox_call = request_mailbox_fn or request_mailbox
    try:
        reachability = reachability_call(
            target_identity_id=target_identity_id,
            socket_path=socket_path,
        )
    except Exception as exc:
        return {"wake_status": "wake_failed", "runtime_target": "none", "error": str(exc)}
    if not isinstance(reachability, dict):
        return {"wake_status": "wake_failed", "runtime_target": "none", "error": "reachability response must be an object"}
    if reachability.get("reachability_status") != "online":
        status = reachability.get("reachability_status")
        return {
            "wake_status": "target_not_online",
            "runtime_target": "none",
            "error": f"target identity is not online: {status}",
            "reachability_status": status,
        }

    record = reachability.get("record")
    endpoint = record.get("endpoint") if isinstance(record, dict) else None
    if not isinstance(endpoint, dict) or endpoint.get("kind") != "daemon_mailbox_socket":
        return {"wake_status": "wake_failed", "runtime_target": "none", "error": "target endpoint is not daemon_mailbox_socket"}
    mailbox_socket = endpoint.get("socket_path")
    if not isinstance(mailbox_socket, str) or not mailbox_socket.strip():
        return {"wake_status": "wake_failed", "runtime_target": "none", "error": "target mailbox socket_path is required"}

    try:
        envelope = mailbox_call(
            "mailbox.local_trigger",
            {
                "identity_id": target_identity_id,
                "role_id": target_role_id,
                "type": "im.message.created",
                "payload": {
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "event_id": event_id,
                },
                "origin_id": message_id,
                "correlation_id": wake_id,
                "source_context": {"source": "central_im"},
            },
            socket_path=Path(mailbox_socket),
        )
    except Exception as exc:
        return {"wake_status": "wake_failed", "runtime_target": "none", "error": str(exc)}
    if not isinstance(envelope, dict):
        return {"wake_status": "wake_failed", "runtime_target": "none", "error": "mailbox response must be an object"}
    if envelope.get("ok") is not True:
        error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
        message = error.get("message") if isinstance(error.get("message"), str) else "mailbox local trigger failed"
        return {"wake_status": "wake_failed", "runtime_target": "none", "error": message}
    result = envelope.get("result") if isinstance(envelope.get("result"), dict) else {}
    return {
        "wake_status": "submitted",
        "runtime_target": "daemon_mailbox",
        "error": None,
        "handling_status": result.get("handling_status") if isinstance(result.get("handling_status"), str) else None,
    }


def deliver_signal(*, signal: dict[str, Any], socket_path: Path | None = None) -> dict[str, Any]:
    return request_central_daemon("signal.deliver", {"signal": signal}, socket_path=socket_path)


if __name__ == "__main__":
    raise SystemExit(main())
