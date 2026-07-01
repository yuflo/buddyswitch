#!/usr/bin/env python3
"""Record actor-facing Task Sys tool calls for the user simulation.

This helper intentionally invokes env.tools.task_sys._impl instead of
env.domain.task_sys mutators so the evidence stays at the actor tool boundary.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
LAUNCHER = ROOT / "tools" / "launcher"
for candidate in (SCRIPTS, LAUNCHER):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


def _load_instance(instance_json: Path) -> tuple[dict[str, Any], Path]:
    payload = json.loads(instance_json.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("instance json must contain an object")
    shared_root = instance_json.resolve(strict=False).parents[2]
    os.environ["BUDDYSWITCH_STATE_ROOT"] = str(shared_root / "state")
    return payload, shared_root


def _imports() -> tuple[Any, Any, Any]:
    from env.domain import task_sys
    from env.repos import runtime_files
    from env.tools.task_sys import _impl as task_tool
    import task_sys_runtime

    runtime_files.refresh_runtime_roots_from_env()
    return task_sys, task_tool, task_sys_runtime


class _ProbeDaemon:
    def __init__(self, runtime_context: Any, task_sys_runtime: Any) -> None:
        self._runtime_context = runtime_context
        self._task_sys_runtime = task_sys_runtime

    def execute_task_sys_instruction(self, instruction: dict[str, Any]) -> dict[str, Any]:
        return self._task_sys_runtime.execute_instruction(self._runtime_context, instruction)

    def cleanup_task_sys_side_lease(self, task_id: str) -> dict[str, Any]:
        return self._task_sys_runtime.cleanup_task_sys_side_lease(self._runtime_context, task_id)


def _tool_context(instance_json: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    instance, shared_root = _load_instance(instance_json)
    task_sys, _task_tool, task_sys_runtime = _imports()
    runtime_context = task_sys_runtime.context_from_instance_json(instance_json)
    actor_id = instance.get("actor_id")
    role = instance.get("role")
    if not isinstance(actor_id, str) or not actor_id:
        raise ValueError("instance json missing actor_id")
    if not isinstance(role, str) or not role:
        raise ValueError("instance json missing role")
    context = {
        "active_actor": {"actor_id": actor_id, "role_id": role},
        "active_role": role,
        "rules": SimpleNamespace(task_sys=task_sys),
        "daemon": _ProbeDaemon(runtime_context, task_sys_runtime),
    }
    meta = {
        "actor_id": actor_id,
        "role": role,
        "instance_json": str(instance_json),
        "shared_root": str(shared_root),
        "state_root": str(shared_root / "state"),
    }
    return context, meta


def _invoke(task_tool: Any, context: dict[str, Any], action: str, args: dict[str, Any]) -> dict[str, Any]:
    return task_tool.invoke(action=action, args=args, context=context)


def _run_get(task_tool: Any, context: dict[str, Any], task_id: str) -> dict[str, Any]:
    return _invoke(task_tool, context, "get", {"task_id": task_id})


def _run_list(task_tool: Any, context: dict[str, Any], status: str) -> dict[str, Any]:
    return _invoke(task_tool, context, "list", {"status": status, "limit": 20})


def _capture_error(exc: BaseException) -> dict[str, Any]:
    return {
        "ok": False,
        "error_type": type(exc).__name__,
        "message": str(exc),
    }


def _command_close(args: argparse.Namespace) -> int:
    context, meta = _tool_context(Path(args.instance_json))
    _task_sys, task_tool, _runtime = _imports()
    payload: dict[str, Any] = {"command": "close", "instance": meta, "task_id": args.task_id}
    try:
        payload["before_list"] = _run_list(task_tool, context, "all")
        payload["before_get"] = _run_get(task_tool, context, args.task_id)
        payload["mutation"] = _invoke(
            task_tool,
            context,
            "close",
            {"task_id": args.task_id, "summary": args.summary},
        )
        payload["after_get"] = _run_get(task_tool, context, args.task_id)
        payload["after_list"] = _run_list(task_tool, context, "all")
    except Exception as exc:
        payload["error"] = _capture_error(exc)
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return 1
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


def _command_need_parent(args: argparse.Namespace) -> int:
    context, meta = _tool_context(Path(args.instance_json))
    _task_sys, task_tool, _runtime = _imports()
    parent_frame_context = json.loads(args.parent_frame_context)
    if not isinstance(parent_frame_context, dict):
        raise ValueError("--parent-frame-context must be a JSON object")
    params: dict[str, Any] = {
        "parent_frame_context": parent_frame_context,
        "relation": args.relation,
        "interrupt": args.interrupt == "true",
    }
    payload: dict[str, Any] = {"command": "need-parent", "instance": meta, "task_id": args.task_id, "params": params}
    try:
        payload["before_list"] = _run_list(task_tool, context, "all")
        payload["before_get"] = _run_get(task_tool, context, args.task_id)
        payload["mutation"] = _invoke(task_tool, context, "need_parent", {"task_id": args.task_id, "params": params})
        payload["after_get"] = _run_get(task_tool, context, args.task_id)
        payload["after_list"] = _run_list(task_tool, context, "all")
    except Exception as exc:
        payload["error"] = _capture_error(exc)
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return 1
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


def _command_list(args: argparse.Namespace) -> int:
    context, meta = _tool_context(Path(args.instance_json))
    _task_sys, task_tool, _runtime = _imports()
    payload: dict[str, Any] = {"command": "list", "instance": meta, "status": args.status}
    try:
        payload["result"] = _run_list(task_tool, context, args.status)
    except Exception as exc:
        payload["error"] = _capture_error(exc)
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return 1
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


def _command_get(args: argparse.Namespace) -> int:
    context, meta = _tool_context(Path(args.instance_json))
    _task_sys, task_tool, _runtime = _imports()
    payload: dict[str, Any] = {
        "command": "get",
        "instance": meta,
        "task_id": args.task_id,
        "expect_error": bool(args.expect_error),
    }
    try:
        payload["result"] = _run_get(task_tool, context, args.task_id)
    except Exception as exc:
        payload["error"] = _capture_error(exc)
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return 0 if args.expect_error else 1
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 1 if args.expect_error else 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    close_parser = subparsers.add_parser("close")
    close_parser.add_argument("--instance-json", required=True)
    close_parser.add_argument("--task-id", required=True)
    close_parser.add_argument("--summary", required=True)
    close_parser.set_defaults(func=_command_close)

    handoff_parser = subparsers.add_parser("need-parent")
    handoff_parser.add_argument("--instance-json", required=True)
    handoff_parser.add_argument("--task-id", required=True)
    handoff_parser.add_argument("--parent-frame-context", required=True)
    handoff_parser.add_argument("--relation", required=True)
    handoff_parser.add_argument("--interrupt", choices=("true", "false"), required=True)
    handoff_parser.set_defaults(func=_command_need_parent)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--instance-json", required=True)
    list_parser.add_argument("--status", choices=("active", "recoverable", "all"), default="active")
    list_parser.set_defaults(func=_command_list)

    get_parser = subparsers.add_parser("get")
    get_parser.add_argument("--instance-json", required=True)
    get_parser.add_argument("--task-id", required=True)
    get_parser.add_argument("--expect-error", action="store_true")
    get_parser.set_defaults(func=_command_get)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
