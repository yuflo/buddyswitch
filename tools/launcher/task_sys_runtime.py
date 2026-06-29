#!/usr/bin/env python3
"""Execute Task Sys runtime instructions with generic launcher actuators."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping


HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import app_server  # noqa: E402
import side_thread_registry  # noqa: E402
import submit_turn as launcher_submit_turn  # noqa: E402


class InstanceTaskSysContext:
    def __init__(
        self,
        *,
        actor_id: str,
        role: str,
        main_thread_id: str,
        socket_path: Path,
        permissions: str,
        instance_json: Path,
        workspace_dir: Path,
        project_workspace_dir: Path,
    ) -> None:
        self.actor_id = actor_id
        self.role = role
        self.main_thread_id = main_thread_id
        self.socket_path = socket_path
        self.permissions = permissions
        self.instance_json = instance_json
        self.workspace_dir = workspace_dir
        self.project_workspace_dir = project_workspace_dir


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _context_field(context: Any, name: str) -> Any:
    if isinstance(context, Mapping):
        return context.get(name)
    return getattr(context, name, None)


def _context_actor_id(context: Any) -> str:
    return _require_text(_context_field(context, "actor_id"), "context.actor_id")


def _context_role(context: Any) -> str:
    value = _context_field(context, "role")
    if value is None:
        value = _context_field(context, "role_id")
    return _require_text(value, "context.role")


def _context_path(context: Any, name: str) -> Path:
    value = _context_field(context, name)
    if isinstance(value, Path):
        return value
    return Path(_require_text(value, f"context.{name}"))


def _validate_actor_target(context: Any, instruction: Mapping[str, Any]) -> None:
    target = _require_mapping(instruction.get("actor_target"), "instruction.actor_target")
    if target.get("actor_id") != _context_actor_id(context) or target.get("role_id") != _context_role(context):
        raise PermissionError("wrong target actor for Task Sys runtime instruction")


def _json_block(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), ensure_ascii=True, indent=2, sort_keys=True)


def render_side_frame(frame: Mapping[str, Any]) -> str:
    payload = _require_mapping(frame, "frame")
    task_id = _require_text(payload.get("task_id"), "frame.task_id")
    return "\n\n".join(
        (
            "task_sys.side_frame",
            f"Task id: {task_id}",
            "Task Sys source:",
            _json_block(_require_mapping(payload.get("source"), "frame.source")),
            "Task Sys context:",
            _json_block(_require_mapping(payload.get("context"), "frame.context")),
            "Allowed result actions:",
            "- task_sys.close(task_id=..., summary=...) when no parent work is needed.",
            "- task_sys.need_parent(task_id=..., params={parent_frame_context, relation, interrupt, ordering}) when parent work is needed.",
            "Do not use any other side outcome. Treat interrupt only as a task_sys.need_parent params field.",
        )
    )


def render_parent_frame(frame: Mapping[str, Any]) -> str:
    payload = _require_mapping(frame, "frame")
    task_id = _require_text(payload.get("task_id"), "frame.task_id")
    return "\n\n".join(
        (
            "task_sys.parent_frame",
            f"Task id: {task_id}",
            "Task Sys source:",
            _json_block(_require_mapping(payload.get("source"), "frame.source")),
            "Inbound context:",
            _json_block(_require_mapping(payload.get("inbound_context"), "frame.inbound_context")),
            "Side result:",
            _json_block(_require_mapping(payload.get("side_result"), "frame.side_result")),
            "Parent handoff params:",
            _json_block(_require_mapping(payload.get("parent_handoff_params"), "frame.parent_handoff_params")),
            "Required action:",
            "Process this Task Sys parent frame. Use source refs and task context; do not assume raw inbound outside this frame.",
        )
    )


def render_checkpoint_frame(frame: Mapping[str, Any]) -> str:
    payload = _require_mapping(frame, "frame")
    task_id = _require_text(payload.get("task_id"), "frame.task_id")
    legal_operations = payload.get("legal_operations")
    if not isinstance(legal_operations, list):
        raise ValueError("frame.legal_operations must be a list")
    constraints = payload.get("constraints")
    if not isinstance(constraints, list):
        raise ValueError("frame.constraints must be a list")
    return "\n\n".join(
        (
            "task_sys.checkpoint",
            f"Task id: {task_id}",
            "Completed turn:",
            _json_block(_require_mapping(payload.get("completed_turn"), "frame.completed_turn")),
            "Current task context:",
            _json_block(_require_mapping(payload.get("current_task_context"), "frame.current_task_context")),
            "Pending task context:",
            json.dumps(list(payload.get("pending_task_context") or []), ensure_ascii=True, indent=2, sort_keys=True),
            "Legal operations:",
            json.dumps(legal_operations, ensure_ascii=True, indent=2, sort_keys=True),
            "Constraints:",
            json.dumps(constraints, ensure_ascii=True, indent=2, sort_keys=True),
        )
    )


def render_submit_parent_frame(frame: Mapping[str, Any]) -> str:
    payload = _require_mapping(frame, "frame")
    kind = _require_text(payload.get("kind"), "frame.kind")
    if kind == "task_sys.parent_frame":
        return render_parent_frame(payload)
    if kind == "task_sys.checkpoint":
        return render_checkpoint_frame(payload)
    raise ValueError(f"unsupported submit_parent frame kind: {kind}")


def _main_thread_id(context: Any) -> str:
    return _require_text(_context_field(context, "main_thread_id"), "context.main_thread_id")


def _socket_path(context: Any) -> Path:
    return _context_path(context, "socket_path")


def _permissions(context: Any) -> str:
    return _require_text(_context_field(context, "permissions"), "context.permissions")


def _instance_json(context: Any) -> Path:
    return _context_path(context, "instance_json")


def _workspace_dir(context: Any) -> Path:
    return _context_path(context, "workspace_dir")


def _project_workspace_dir(context: Any) -> Path:
    return _context_path(context, "project_workspace_dir")


def _execute_start_side(context: Any, instruction: Mapping[str, Any]) -> dict[str, Any]:
    frame_text = render_side_frame(_require_mapping(instruction.get("frame"), "instruction.frame"))
    parent_thread_id = _main_thread_id(context)
    row = side_thread_registry.find_open_side_thread(
        _instance_json(context),
        actor_id=_context_actor_id(context),
        parent_thread_id=parent_thread_id,
    )
    side_thread_id = row.get("thread_id") if isinstance(row, dict) else None
    if isinstance(side_thread_id, str) and side_thread_id:
        result = app_server.input_turn(
            _socket_path(context),
            side_thread_id,
            frame_text,
            _permissions(context),
        )
        payload = dict(result)
        payload["action"] = "start_side"
        payload["thread_action"] = result.get("action")
        payload["side_thread_id"] = side_thread_id
        payload["task_id"] = instruction.get("task_id")
        return payload

    result = app_server.side_start(
        socket_path=_socket_path(context),
        parent_thread_id=parent_thread_id,
        text=frame_text,
        workspace_dir=_workspace_dir(context),
        shared_project_workspace_dir=_project_workspace_dir(context),
        permissions=_permissions(context),
    )
    new_side_thread_id = _require_text(result.get("side_thread_id"), "side_thread_id")
    side_thread_registry.register_side_thread(
        _instance_json(context),
        actor_id=_context_actor_id(context),
        parent_thread_id=parent_thread_id,
        side_thread_id=new_side_thread_id,
    )
    payload = dict(result)
    payload["action"] = "start_side"
    payload["task_id"] = instruction.get("task_id")
    return payload


def _turn_id_from_submit_result(result: Mapping[str, Any]) -> str:
    value = result.get("turn_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    turn = result.get("turn")
    if isinstance(turn, Mapping):
        turn_id = turn.get("id")
        if isinstance(turn_id, str) and turn_id.strip():
            return turn_id.strip()
    value = result.get("turnId")
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError("submit parent instruction did not return a turn id")


def _execute_submit_parent(context: Any, instruction: Mapping[str, Any], *, interrupt: bool) -> dict[str, Any]:
    task_id = _require_text(instruction.get("task_id"), "instruction.task_id")
    frame_text = render_submit_parent_frame(_require_mapping(instruction.get("frame"), "instruction.frame"))
    interrupted_turn_id: str | None = None
    if interrupt:
        interrupted = app_server.interrupt_turn(_socket_path(context), _main_thread_id(context))
        value = interrupted.get("turn_id") if isinstance(interrupted, Mapping) else None
        if isinstance(value, str) and value.strip():
            interrupted_turn_id = value.strip()
        else:
            raise ValueError("interrupt submit parent instruction did not return an interrupted turn id")
    result = launcher_submit_turn.submit_turn(
        socket_path=_socket_path(context),
        thread_id=_main_thread_id(context),
        text=frame_text,
        permissions=_permissions(context),
    )
    payload: dict[str, Any] = {
        "action": "interrupt_submit_parent" if interrupt else "submit_parent",
        "task_id": task_id,
        "turn_id": _turn_id_from_submit_result(_require_mapping(result, "submit result")),
    }
    if interrupted_turn_id is not None:
        payload["interrupted_turn_id"] = interrupted_turn_id
    return payload


def execute_instruction(context: Any, instruction: Mapping[str, Any]) -> dict[str, Any]:
    payload = _require_mapping(instruction, "instruction")
    _validate_actor_target(context, payload)
    instruction_type = _require_text(payload.get("type"), "instruction.type")
    task_id = _require_text(payload.get("task_id"), "instruction.task_id")
    if instruction_type == "no_actor_action":
        return {"action": "no_actor_action", "task_id": task_id}
    if instruction_type == "start_side":
        return _execute_start_side(context, payload)
    if instruction_type == "submit_parent":
        return _execute_submit_parent(context, payload, interrupt=False)
    if instruction_type == "interrupt_submit_parent":
        return _execute_submit_parent(context, payload, interrupt=True)
    raise ValueError(f"unsupported Task Sys runtime instruction: {instruction_type}")


def context_from_instance_json(instance_json: Path) -> InstanceTaskSysContext:
    payload = json.loads(instance_json.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("instance json must contain an object")
    raw_project_workspace = payload.get("project_workspace_dir")
    if not isinstance(raw_project_workspace, str) or not raw_project_workspace.strip():
        raw_project_workspace = os.environ.get("BUDDYSWITCH_PROJECT_WORKSPACE_DIR")
    if not isinstance(raw_project_workspace, str) or not raw_project_workspace.strip():
        raw_project_workspace = str(instance_json.parent.parent.parent / "project" / "workspace")
    return InstanceTaskSysContext(
        actor_id=_require_text(payload.get("actor_id"), "instance.actor_id"),
        role=_require_text(payload.get("role"), "instance.role"),
        main_thread_id=_require_text(payload.get("thread_id"), "instance.thread_id"),
        socket_path=Path(_require_text(payload.get("app_server_socket"), "instance.app_server_socket")),
        permissions="buddyswitch-runtime",
        instance_json=instance_json,
        workspace_dir=Path(_require_text(payload.get("workspace_dir"), "instance.workspace_dir")),
        project_workspace_dir=Path(_require_text(raw_project_workspace, "instance.project_workspace_dir")),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    execute = subparsers.add_parser("execute")
    execute.add_argument("--instance-json", required=True)
    execute.add_argument("--instruction-json", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "execute":
        context = context_from_instance_json(Path(args.instance_json))
        instruction = json.loads(args.instruction_json)
        if not isinstance(instruction, dict):
            raise ValueError("instruction json must contain an object")
        print(json.dumps(execute_instruction(context, instruction), ensure_ascii=True))
        return 0
    raise ValueError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
