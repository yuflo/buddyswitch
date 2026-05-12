#!/usr/bin/env python3
"""Launcher-managed runtime broker server."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
from pathlib import Path
import socket
import threading
import sys
from typing import Any, Iterator

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from env_manifest import ManifestError, load_manifest
from env.tools import responses as tool_responses
from runtime_kernel.client import PROTOCOL
from runtime_kernel.persist import persist_buddy_run_request
from runtime_kernel.resolve import prepare_turn_context_request
import turn_runtime
from env.tools.router import dispatch_env_tool_request


def _error(code: str, message: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if extra:
        payload.update(extra)
    if "allowed_next_actions" in payload and "allowed_next_action_options" not in payload:
        payload["allowed_next_action_options"] = [
            tool_responses.next_action_option(
                tool="context",
                action="summarize",
                option_id="summarize_current_context_before_retry",
                reason="Summarize current context before retrying runtime operations.",
            ),
            tool_responses.next_action_option(
                tool="context",
                action="get",
                option_id="inspect_context_before_retry",
                reason="Inspect full current context before retrying runtime operations.",
            ),
        ]
    return payload


def _allowed(*actions: str) -> list[str]:
    return list(actions)


def _boundary_error(code: str, message: str, *, boundary: str, actions: list[str]) -> dict[str, Any]:
    return _error(
        code,
        message,
        {
            "permission_boundary": boundary,
            "allowed_next_actions": actions,
        },
    )


def _error_from_payload(payload: dict[str, Any], *, default_code: str, default_message: str) -> dict[str, Any]:
    error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
    message = error.get("message") if isinstance(error.get("message"), str) else default_message
    code = error.get("code") if isinstance(error.get("code"), str) else default_code
    extra = {key: value for key, value in payload.items() if key not in {"ok", "error"}}
    return _error(code, message, extra)


def _load_instance_record(instance_json_path: Path) -> dict[str, Any]:
    payload = json.loads(instance_json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"instance record must be an object: {instance_json_path}")
    instance_id = payload.get("instance_id")
    buddy = payload.get("buddy")
    if not isinstance(instance_id, str) or not instance_id.strip():
        raise ValueError(f"instance record missing instance_id: {instance_json_path}")
    if not isinstance(buddy, str) or not buddy.strip():
        raise ValueError(f"instance record missing buddy: {instance_json_path}")
    return payload


def _instance_shared_root(instance_json_path: Path) -> Path:
    instance_root = instance_json_path.parent
    if instance_root.parent.name == "instances":
        return instance_root.parent.parent
    return instance_root


@contextlib.contextmanager
def _runtime_server_env(*, instance_id: str, buddy_id: str, instance_json_path: Path) -> Iterator[None]:
    shared_root = _instance_shared_root(instance_json_path)
    updates = {
        "BUDDYSWITCH_RUNTIME_BROKER_MODE": "server",
        "BUDDYSWITCH_INSTANCE_ID": instance_id,
        "BUDDYSWITCH_ACTIVE_BUDDY": buddy_id,
        "BUDDYSWITCH_INSTANCE_JSON": str(instance_json_path),
        "BUDDYSWITCH_SHARED_ROOT": str(shared_root),
        "BUDDYSWITCH_STATE_ROOT": str(shared_root / "state"),
    }
    previous = {key: os.environ.get(key) for key in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _product_session(*, instance_json_path: Path, instance_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "instance_json": instance_json_path,
        "payload": dict(instance_record),
        "instance_id": instance_record.get("instance_id"),
        "active_buddy": instance_record.get("buddy"),
    }


def _prepare_dispatch(
    *,
    payload: dict[str, Any],
    manifest_path: Path,
    instance_json_path: Path,
    instance_record: dict[str, Any],
) -> dict[str, Any]:
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("prepare payload.text must be a non-empty string")
    prepared = prepare_turn_context_request(text, manifest_path=manifest_path)
    if prepared.get("ok") is not True:
        return _error_from_payload(prepared, default_code="E_RUNTIME_BROKER", default_message="prepare rejected")
    return {"ok": True, "payload": prepared}


def _persist_dispatch(
    *,
    payload: dict[str, Any],
    manifest_path: Path,
    instance_json_path: Path,
    instance_record: dict[str, Any],
) -> dict[str, Any]:
    context = payload.get("context")
    result = payload.get("result")
    if not isinstance(context, dict):
        return _boundary_error(
            "E_RUNTIME_BROKER",
            "persist payload.context must be an object",
            boundary="request-payload",
            actions=_allowed("Send a persist request with object payload.context and payload.result."),
        )
    if not isinstance(result, dict):
        return _boundary_error(
            "E_RUNTIME_BROKER",
            "persist payload.result must be an object",
            boundary="request-payload",
            actions=_allowed("Send a persist request with object payload.context and payload.result."),
        )
    session = _product_session(instance_json_path=instance_json_path, instance_record=instance_record)
    try:
        turn_runtime._validate_product_persist_context_binding(context, session)
    except turn_runtime.RuntimeFeedbackError as exc:
        return _error(exc.code, exc.message, exc.details)
    persisted = persist_buddy_run_request(context, result=result, manifest_path=manifest_path)
    if persisted.get("ok") is not True:
        return _error_from_payload(persisted, default_code="E_RUNTIME_BROKER", default_message="persist rejected")
    return {"ok": True, "payload": persisted}


def _env_tool_dispatch(
    *,
    payload: dict[str, Any],
    manifest_path: Path,
    instance_json_path: Path,
    instance_record: dict[str, Any],
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    instance_id = str(instance_record["instance_id"]).strip()
    active_buddy = str(instance_record["buddy"]).strip()
    return dispatch_env_tool_request(
        payload=payload,
        active_buddy=active_buddy,
        instance_id=instance_id,
        instance_json=instance_json_path,
        instance_payload=dict(instance_record),
        manifest=manifest,
        manifest_path=manifest_path,
    )


def dispatch_runtime_request(
    *,
    request: dict[str, Any],
    instance_json_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    try:
        if request.get("protocol") != PROTOCOL:
            return _boundary_error(
                "E_RUNTIME_BROKER",
                f"unsupported protocol: {request.get('protocol')!r}",
                boundary="broker-protocol",
                actions=_allowed("Use the launcher-managed BuddySwitch runtime tools instead of direct broker calls."),
            )
        method = request.get("method")
        if not isinstance(method, str) or not method.strip():
            raise ValueError("request.method must be a non-empty string")
        method = method.strip()

        payload = request.get("payload")
        if not isinstance(payload, dict):
            return _boundary_error(
                "E_RUNTIME_BROKER",
                "request.payload must be an object",
                boundary="request-payload",
                actions=_allowed("Send a broker request with an object payload."),
            )

        instance_record = _load_instance_record(instance_json_path)
        request_instance_id = request.get("instance_id")
        request_buddy = request.get("active_buddy")

        instance_id = str(instance_record["instance_id"]).strip()
        active_buddy = str(instance_record["buddy"]).strip()
        if request_instance_id != instance_id:
            return _boundary_error(
                "E_RUNTIME_BROKER",
                f"instance_id mismatch: expected '{instance_id}', got '{request_instance_id}'",
                boundary="active-instance",
                actions=_allowed("Use the active launcher-managed instance id.", "Rerun prepare in the active instance."),
            )
        if request_buddy != active_buddy:
            return _boundary_error(
                "E_RUNTIME_BROKER",
                f"active_buddy mismatch: expected '{active_buddy}', got '{request_buddy}'",
                boundary="active-buddy",
                actions=_allowed("Use the active buddy locked by the launcher.", "Rerun prepare in the active instance."),
            )
        status = instance_record.get("status")
        if status != "active":
            return _boundary_error(
                "E_RUNTIME_BROKER",
                f"instance is not active: {status!r}",
                boundary="active-instance-status",
                actions=_allowed("Open an active launcher-managed instance before calling runtime tools."),
            )

        with _runtime_server_env(
            instance_id=instance_id,
            buddy_id=active_buddy,
            instance_json_path=instance_json_path,
        ):
            if method == "prepare":
                lock_session = _product_session(instance_json_path=instance_json_path, instance_record=instance_record)
                with turn_runtime._hold_product_runtime_lock(lock_session):
                    locked_instance_record = _load_instance_record(instance_json_path)
                    return _prepare_dispatch(
                        payload=payload,
                        manifest_path=manifest_path,
                        instance_json_path=instance_json_path,
                        instance_record=locked_instance_record,
                    )
            if method == "persist":
                lock_session = _product_session(instance_json_path=instance_json_path, instance_record=instance_record)
                with turn_runtime._hold_product_runtime_lock(lock_session):
                    locked_instance_record = _load_instance_record(instance_json_path)
                    return _persist_dispatch(
                        payload=payload,
                        manifest_path=manifest_path,
                        instance_json_path=instance_json_path,
                        instance_record=locked_instance_record,
                    )
            if method == "env.tool":
                lock_session = _product_session(instance_json_path=instance_json_path, instance_record=instance_record)
                with turn_runtime._hold_product_runtime_lock(lock_session):
                    locked_instance_record = _load_instance_record(instance_json_path)
                    return _env_tool_dispatch(
                        payload=payload,
                        manifest_path=manifest_path,
                        instance_json_path=instance_json_path,
                        instance_record=locked_instance_record,
                    )
        return _boundary_error(
            "E_RUNTIME_BROKER",
            f"unsupported method: {method}",
            boundary="broker-protocol",
            actions=_allowed("Use supported runtime methods: prepare, persist, env.tool."),
        )
    except turn_runtime.RuntimeFeedbackError as exc:
        return _error(exc.code, exc.message, exc.details)
    except (ValueError, OSError, json.JSONDecodeError, ManifestError) as exc:
        return _error("E_RUNTIME_BROKER", str(exc))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BuddySwitch runtime broker.")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Serve runtime broker socket")
    serve.add_argument("--socket", required=True, type=Path)
    serve.add_argument("--pid-file", required=True, type=Path)
    serve.add_argument("--instance-json", required=True, type=Path)
    serve.add_argument("--manifest", required=True, type=Path)
    return parser.parse_args()


def _serve(*, socket_path: Path, pid_file: Path, instance_json: Path, manifest: Path) -> int:
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
    if socket_path.exists():
        socket_path.unlink()

    lock = threading.Lock()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(socket_path))
        server.listen(16)
        os.chmod(socket_path, 0o600)
        while True:
            conn, _ = server.accept()
            with conn:
                chunks: list[bytes] = []
                while True:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
                try:
                    request = json.loads(b"".join(chunks).decode("utf-8"))
                except json.JSONDecodeError as exc:
                    response = _error("E_RUNTIME_BROKER", f"invalid request JSON: {exc}")
                else:
                    if not isinstance(request, dict):
                        response = _error("E_RUNTIME_BROKER", "request must be a JSON object")
                    else:
                        with lock:
                            response = dispatch_runtime_request(
                                request=request,
                                instance_json_path=instance_json,
                                manifest_path=manifest,
                            )
                conn.sendall(json.dumps(response, ensure_ascii=True).encode("utf-8"))


def main() -> int:
    args = _parse_args()
    if args.command != "serve":
        return 2
    try:
        return _serve(
            socket_path=args.socket,
            pid_file=args.pid_file,
            instance_json=args.instance_json,
            manifest=args.manifest,
        )
    finally:
        if args.command == "serve":
            try:
                args.socket.unlink(missing_ok=True)
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
