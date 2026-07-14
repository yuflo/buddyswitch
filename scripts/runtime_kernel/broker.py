"""Runtime broker CLI and v2 request dispatcher."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal
import sys
from typing import Any

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from runtime_kernel import coordinator, dispatcher, lifecycle, protocol, server


def _session_context(
    instance_json_path: Path,
    manifest_path: Path,
    *,
    request_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params = request_params if isinstance(request_params, dict) else {}
    actor_id = params.get("actor_id") if isinstance(params.get("actor_id"), str) else None
    active_role = params.get("active_role") if isinstance(params.get("active_role"), str) else None
    payload: dict[str, Any] = {}
    if isinstance(actor_id, str) and isinstance(active_role, str):
        payload = {"actor_id": actor_id, "role": active_role}
    return {
        "instance_json": instance_json_path,
        "manifest_path": manifest_path,
        "actor_id": actor_id,
        "active_role": active_role,
        "payload": payload,
    }


def _runtime_session(
    instance_json_path: Path,
    manifest_path: Path,
    *,
    socket_path: Path | None,
    pid_file: Path | None,
    repo_root_path: Path | None = None,
) -> dispatcher.RuntimeBrokerSession:
    return dispatcher.RuntimeBrokerSession(
        instance_json_path=instance_json_path,
        manifest_path=manifest_path,
        repo_root_path=repo_root_path,
        socket_path=socket_path,
        pid_file=pid_file,
    )


def _dispatch_with_runtime_session(
    request: dict[str, Any],
    runtime_session: dispatcher.RuntimeBrokerSession,
) -> dict[str, Any]:
    return dispatcher.dispatch_runtime_request(request, runtime_session)


def _to_error_envelope(request_id: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
    code = error.get("code") if isinstance(error.get("code"), str) else "E_RUNTIME_BROKER_PERMISSION"
    message = error.get("message") if isinstance(error.get("message"), str) else "runtime broker request failed"
    retriable = bool(error.get("retriable", False))
    retry_after_ms = error.get("retry_after_ms") if isinstance(error.get("retry_after_ms"), int) else None
    error_extra = {
        key: value
        for key, value in error.items()
        if key not in {"code", "message", "retriable"} and value is not None
    }
    extra = {key: value for key, value in payload.items() if key not in {"ok", "error"}}
    envelope = protocol.error_response(
        request_id,
        code=code,
        message=message,
        retriable=retriable,
        retry_after_ms=retry_after_ms,
        **error_extra,
    )
    for key, value in extra.items():
        envelope[key] = value
    return envelope


def _dispatch_v2_request(
    *,
    request: dict[str, Any],
    instance_json_path: Path,
    manifest_path: Path,
    socket_path: Path | None = None,
    pid_file: Path | None = None,
    repo_root_path: Path | None = None,
) -> dict[str, Any]:
    try:
        validated = protocol.validate_request(request)
    except protocol.BrokerProtocolError as exc:
        return protocol.error_response(
            exc.request_id,
            code=exc.code,
            message=exc.message,
            retriable=False,
        )

    request_id = validated.get("request_id") if isinstance(validated.get("request_id"), str) else None
    runtime_session = _runtime_session(
        instance_json_path,
        manifest_path,
        socket_path=socket_path,
        pid_file=pid_file,
        repo_root_path=repo_root_path,
    )

    payload = coordinator.dispatch_with_coordination(
        validated,
        _session_context(
            instance_json_path,
            manifest_path,
            request_params=validated.get("params") if isinstance(validated.get("params"), dict) else None,
        ),
        lambda req, _ctx: _dispatch_with_runtime_session(req, runtime_session),
    )
    if not isinstance(payload, dict):
        return protocol.error_response(
            request_id,
            code="E_RUNTIME_BROKER_PROTOCOL",
            message="dispatcher returned non-object response",
            retriable=False,
        )
    if payload.get("ok") is True:
        return protocol.success_response(request_id, payload)
    return _to_error_envelope(request_id, payload)


def dispatch_runtime_request(
    *,
    request: dict[str, Any],
    instance_json_path: Path,
    manifest_path: Path,
    socket_path: Path | None = None,
    pid_file: Path | None = None,
    repo_root_path: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(request, dict):
        return protocol.error_response(
            None,
            code="E_RUNTIME_BROKER_PROTOCOL",
            message="request must be an object",
            retriable=False,
        )
    return _dispatch_v2_request(
        request=request,
        instance_json_path=instance_json_path,
        manifest_path=manifest_path,
        socket_path=socket_path,
        pid_file=pid_file,
        repo_root_path=repo_root_path,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BuddySwitch runtime broker.")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Serve runtime broker socket")
    serve.add_argument("--socket", required=True, type=Path)
    serve.add_argument("--pid-file", required=True, type=Path)
    serve.add_argument("--marker-file", required=True, type=Path)
    serve.add_argument("--log-file", required=True, type=Path)
    serve.add_argument("--instance-json", required=True, type=Path)
    serve.add_argument("--manifest", required=True, type=Path)
    serve.add_argument("--repo-root", type=Path)

    for name in ("ping", "status", "ensure", "stop"):
        cmd = sub.add_parser(name, help=f"Runtime broker {name}")
        cmd.add_argument("--socket", required=True, type=Path)
        cmd.add_argument("--pid-file", required=True, type=Path)
        cmd.add_argument("--marker-file", required=True, type=Path)
        cmd.add_argument("--log-file", required=True, type=Path)
        cmd.add_argument("--instance-json", required=True, type=Path)
        cmd.add_argument("--manifest", required=True, type=Path)
        cmd.add_argument("--repo-root", type=Path)

    return parser.parse_args()


def _paths_from_args(args: argparse.Namespace) -> lifecycle.BrokerPaths:
    return lifecycle.BrokerPaths(
        socket_path=args.socket,
        pid_file=args.pid_file,
        marker_file=args.marker_file,
        log_file=args.log_file,
    )


def _expected_runtime_context(instance_json_path: Path) -> tuple[str, str, Path | None]:
    payload = json.loads(instance_json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"instance record must be object: {instance_json_path}")
    actor_id = payload.get("actor_id")
    active_role = payload.get("role")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise ValueError(f"instance record missing actor_id: {instance_json_path}")
    if not isinstance(active_role, str) or not active_role.strip():
        raise ValueError(f"instance record missing role: {instance_json_path}")
    workspace_dir = payload.get("workspace_dir")
    workspace_root = None
    if isinstance(workspace_dir, str) and workspace_dir.strip():
        workspace_root = Path(workspace_dir.strip()).resolve(strict=False)
    return actor_id.strip(), active_role.strip(), workspace_root


def _run_cli(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    if args.command == "serve":
        cfg = server.RuntimeBrokerConfig(
            socket_path=args.socket,
            pid_file=args.pid_file,
            instance_json_path=args.instance_json,
            manifest_path=args.manifest,
            repo_root_path=args.repo_root,
            marker_file=args.marker_file,
        )
        broker_server = server.RuntimeBrokerServer(
            config=cfg,
            dispatch_fn=lambda req, sess: dispatcher.dispatch_runtime_request(req, sess),
        )
        previous_sigint = signal.signal(
            signal.SIGINT,
            lambda _signum, _frame: broker_server.close(),
        )
        previous_sigterm = signal.signal(
            signal.SIGTERM,
            lambda _signum, _frame: broker_server.close(),
        )
        try:
            broker_server.serve_forever()
        finally:
            signal.signal(signal.SIGINT, previous_sigint)
            signal.signal(signal.SIGTERM, previous_sigterm)
        return 0, {"ok": True}

    paths = _paths_from_args(args)

    if args.command == "stop":
        payload = lifecycle.stop_broker(paths)
        return (0 if payload.get("ok") else 1), payload

    expected_actor_id, expected_active_role, expected_workspace_root = _expected_runtime_context(args.instance_json)

    if args.command == "ping":
        payload = lifecycle.ping_broker(
            paths,
            expected_actor_id=expected_actor_id,
            expected_active_role=expected_active_role,
        )
        return (0 if payload.get("ok") else 1), payload

    if args.command == "status":
        payload = lifecycle.broker_status(
            paths,
            expected_actor_id=expected_actor_id,
            expected_active_role=expected_active_role,
            expected_workspace_root=expected_workspace_root,
        )
        return (0 if payload.get("healthy") else 1), payload

    if args.command == "ensure":
        payload = lifecycle.ensure_broker(
            paths,
            instance_json_path=args.instance_json,
            manifest_path=args.manifest,
            repo_root_path=args.repo_root,
            expected_actor_id=expected_actor_id,
            expected_active_role=expected_active_role,
            expected_workspace_root=expected_workspace_root,
        )
        return (0 if payload.get("ok") else 1), payload

    return 2, {
        "ok": False,
        "error": {
            "code": "E_RUNTIME_BROKER_PROTOCOL",
            "message": f"unsupported command: {args.command}",
            "retriable": False,
        },
    }


def main() -> int:
    args = _parse_args()
    try:
        code, payload = _run_cli(args)
    except Exception as exc:  # pragma: no cover - CLI safety net
        code = 1
        payload = {
            "ok": False,
            "error": {
                "code": "E_RUNTIME_BROKER_PROTOCOL",
                "message": str(exc),
                "retriable": False,
            },
        }
    if args.command != "serve":
        print(json.dumps(payload, ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
