"""Canonical private instance-record mutations for Host Control."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load(path: Path, actor_id: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Instance record missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("actor_id") != actor_id:
        raise ValueError(f"Actor id mismatch in {path}")
    return payload


def _write(path: Path, payload: dict[str, Any]) -> None:
    payload["updated_at"] = _now()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def activate(
    *,
    path: Path,
    actor_id: str,
    role: str,
    status: str,
    instance_root: Path,
    workspace_dir: Path,
    project_workspace_dir: Path,
    codex_executable: Path,
    codex_version: str,
    runtime_identity: dict[str, object],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _write(
        path,
        {
            "actor_id": actor_id,
            "role": role,
            "status": status,
            "instance_root": str(instance_root),
            "workspace_dir": str(workspace_dir),
            "project_workspace_dir": str(project_workspace_dir),
            "browser_port": None,
            "codex_runtime": {
                "executable": str(codex_executable),
                "version": codex_version,
            },
            "runtime_identity": runtime_identity,
        },
    )


def set_app_server(
    *,
    path: Path,
    actor_id: str,
    thread_id: str,
    pid: int,
    socket_path: str,
    log_file: str,
    status: str,
) -> None:
    payload = _load(path, actor_id)
    payload.update(
        {
            "thread_id": thread_id or payload.get("thread_id"),
            "app_server_pid": pid,
            "app_server_socket": socket_path,
            "app_server_log": log_file,
            "status": status,
        }
    )
    _write(path, payload)


def set_thread(*, path: Path, actor_id: str, thread_id: str) -> None:
    if not thread_id:
        raise ValueError("Thread id is required")
    payload = _load(path, actor_id)
    payload["thread_id"] = thread_id
    _write(path, payload)


def clear_app_server(*, path: Path, actor_id: str, status: str) -> None:
    payload = _load(path, actor_id)
    payload.update(
        {
            "app_server_pid": None,
            "app_server_socket": None,
            "app_server_log": None,
            "status": status,
        }
    )
    _write(path, payload)


def record_failure(
    *,
    path: Path,
    actor_id: str,
    phase: str,
    message: str,
    thread_id: str | None,
    browser_port: int | None,
) -> None:
    payload = _load(path, actor_id)
    failed_at = _now()
    failure: dict[str, object] = {
        "phase": phase,
        "message": message,
        "failed_at": failed_at,
    }
    if thread_id:
        failure["thread_id"] = thread_id
    if browser_port is not None:
        failure["browser_port"] = browser_port
    payload.update(
        {
            "last_failure": failure,
            "status": "inactive",
            "app_server_pid": None,
            "app_server_socket": None,
            "app_server_log": None,
            "browser_port": None,
            "thread_id": None,
        }
    )
    _write(path, payload)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("activate", "set-app-server", "set-thread", "clear-app-server", "record-failure"):
        command = commands.add_parser(name)
        command.add_argument("--path", type=Path, required=True)
        command.add_argument("--actor-id", required=True)
        if name == "activate":
            command.add_argument("--role", required=True)
            command.add_argument("--status", required=True)
            command.add_argument("--instance-root", type=Path, required=True)
            command.add_argument("--workspace-dir", type=Path, required=True)
            command.add_argument("--project-workspace-dir", type=Path, required=True)
            command.add_argument("--codex-executable", type=Path, required=True)
            command.add_argument("--codex-version", required=True)
            command.add_argument("--runtime-identity", required=True)
        elif name == "set-app-server":
            command.add_argument("--thread-id", required=True)
            command.add_argument("--pid", type=int, required=True)
            command.add_argument("--socket-path", required=True)
            command.add_argument("--log-file", required=True)
            command.add_argument("--status", required=True)
        elif name == "set-thread":
            command.add_argument("--thread-id", required=True)
        elif name == "clear-app-server":
            command.add_argument("--status", required=True)
        else:
            command.add_argument("--phase", required=True)
            command.add_argument("--message", required=True)
            command.add_argument("--thread-id")
            command.add_argument("--browser-port", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common = {"path": args.path, "actor_id": args.actor_id}
    if args.command == "activate":
        activate(
            **common,
            role=args.role,
            status=args.status,
            instance_root=args.instance_root,
            workspace_dir=args.workspace_dir,
            project_workspace_dir=args.project_workspace_dir,
            codex_executable=args.codex_executable,
            codex_version=args.codex_version,
            runtime_identity=json.loads(args.runtime_identity),
        )
    elif args.command == "set-app-server":
        set_app_server(
            **common,
            thread_id=args.thread_id,
            pid=args.pid,
            socket_path=args.socket_path,
            log_file=args.log_file,
            status=args.status,
        )
    elif args.command == "set-thread":
        set_thread(**common, thread_id=args.thread_id)
    elif args.command == "clear-app-server":
        clear_app_server(**common, status=args.status)
    else:
        record_failure(
            **common,
            phase=args.phase,
            message=args.message,
            thread_id=args.thread_id,
            browser_port=args.browser_port,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
