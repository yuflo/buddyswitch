#!/usr/bin/env python3
"""Skill-facing CLI for broker-routed env task-manager operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from runtime_kernel.client import RuntimeBrokerError, broker_unavailable_feedback, request_runtime_broker


def _error_payload(code: str, message: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if extra:
        error.update(extra)
    return {"ok": False, "error": error}


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"payload file must contain a JSON object: {path}")
    return payload


def _operation_to_action(operation: str) -> str:
    return operation.replace("-", "_")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Call broker-routed BuddySwitch env task operations.")
    sub = parser.add_subparsers(dest="resource", required=True)

    task = sub.add_parser("task", help="Task manager env operations")
    task_sub = task.add_subparsers(dest="operation", required=True)

    create = task_sub.add_parser("create", help="Create active-buddy task")
    create.add_argument("--payload", required=True, type=Path)

    task_sub.add_parser("list", help="List active-buddy tasks")

    get = task_sub.add_parser("get", help="Get active-buddy task by id")
    get.add_argument("--task-id", required=True)

    task_sub.add_parser("get-current", help="Get active instance current task binding")

    set_current = task_sub.add_parser("set-current", help="Set active instance current task binding")
    set_current.add_argument("--task-id", required=True)

    update = task_sub.add_parser("update", help="Update active-buddy task fields")
    update.add_argument("--payload", required=True, type=Path)

    archive = task_sub.add_parser("archive", help="Archive active-buddy task")
    archive.add_argument("--task-id", required=True)
    return parser.parse_args()


def _task_args_from_cli(args: argparse.Namespace) -> dict[str, Any]:
    operation = args.operation
    if operation in {"create", "update"}:
        payload_path = getattr(args, "payload", None)
        if not isinstance(payload_path, Path):
            raise ValueError("payload file is required")
        return _load_json_object(payload_path)
    if operation in {"get", "set-current", "archive"}:
        task_id = getattr(args, "task_id", None)
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task id is required")
        return {"task_id": task_id.strip()}
    if operation in {"list", "get-current"}:
        return {}
    raise ValueError(f"unsupported task operation: {operation}")


def _dispatch_task(args: argparse.Namespace) -> dict[str, Any]:
    operation = str(args.operation)
    action = _operation_to_action(operation)
    payload = {"action": action, "args": _task_args_from_cli(args)}
    response = request_runtime_broker("env.task", payload)
    if not isinstance(response, dict) or not isinstance(response.get("ok"), bool):
        return _error_payload(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            "runtime broker response for env.task is invalid",
            broker_unavailable_feedback(),
        )
    return response


def main() -> int:
    try:
        args = _parse_args()
        if args.resource != "task":
            raise ValueError(f"unsupported resource: {args.resource}")
        payload = _dispatch_task(args)
    except RuntimeBrokerError as exc:
        payload = _error_payload(exc.code, exc.message, exc.details)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: payload file is not readable or invalid JSON object: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
