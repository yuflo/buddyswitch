#!/usr/bin/env python3
"""Concrete owner for BuddySwitch side-thread lifecycle operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import app_server
import side_thread_registry


class SideThreadLifecycleError(RuntimeError):
    """Raised when a side-thread lifecycle operation cannot be completed."""


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SideThreadLifecycleError(f"{field_name} is required")
    return value.strip()


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SideThreadLifecycleError(f"{field_name} must not be empty")
    return value.strip()


def _model_config_result(model: str | None, model_reasoning_effort: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model_source": "override" if model is not None else "parent_thread",
        "model_reasoning_effort_source": "override" if model_reasoning_effort is not None else "parent_thread",
        "model_config_durability": "thread_fork_only",
    }
    if model is not None:
        payload["model"] = model
    if model_reasoning_effort is not None:
        payload["model_reasoning_effort"] = model_reasoning_effort
    return payload


def _thread_id_from_fork(result: Mapping[str, Any]) -> str:
    thread = result.get("thread")
    if not isinstance(thread, Mapping):
        raise SideThreadLifecycleError("thread/fork did not return a thread object")
    return _require_text(thread.get("id"), "thread.id")


def _turn_id_from_result(result: Mapping[str, Any]) -> str:
    value = result.get("turn_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    value = result.get("turnId")
    if isinstance(value, str) and value.strip():
        return value.strip()
    turn = result.get("turn")
    if isinstance(turn, Mapping):
        value = turn.get("id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise SideThreadLifecycleError("turn operation did not return a turn id")


def _thread_status_kind(thread_payload: Mapping[str, Any]) -> str:
    thread = thread_payload.get("thread")
    if not isinstance(thread, Mapping):
        raise SideThreadLifecycleError("thread/read did not return a thread object")
    status = thread.get("status")
    if isinstance(status, Mapping):
        value = status.get("type")
        if isinstance(value, str) and value.strip():
            return value.strip()
    if isinstance(status, str) and status.strip():
        return status.strip()
    return ""


def _row_turn_id(row: Mapping[str, Any]) -> str | None:
    value = row.get("turn_id")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _row_purpose(row: Mapping[str, Any]) -> str | None:
    value = row.get("purpose")
    return value.strip() if isinstance(value, str) and value.strip() else None


def start_side_thread(
    *,
    socket_path: Path,
    instance_json: Path,
    actor_id: str,
    parent_thread_id: str,
    text: str,
    purpose: str,
    workspace_dir: Path,
    shared_project_workspace_dir: Path,
    permissions: str,
    task_id: str | None = None,
    model: str | None = None,
    model_reasoning_effort: str | None = None,
) -> dict[str, Any]:
    normalized_actor = _require_text(actor_id, "actor_id")
    normalized_parent = _require_text(parent_thread_id, "parent_thread_id")
    normalized_purpose = _require_text(purpose, "purpose")
    normalized_model = _optional_text(model, "model")
    normalized_effort = _optional_text(model_reasoning_effort, "model_reasoning_effort")
    forked = app_server.thread_fork(
        socket_path,
        normalized_parent,
        workspace_dir=workspace_dir,
        shared_project_workspace_dir=shared_project_workspace_dir,
        permissions=permissions,
        model=normalized_model,
        model_reasoning_effort=normalized_effort,
    )
    side_thread_id = _thread_id_from_fork(forked)
    app_server.thread_inject_items(socket_path, side_thread_id, [app_server.side_boundary_prompt_item()])
    sent = app_server.turn_start(socket_path, side_thread_id, text, permissions)
    turn_id = _turn_id_from_result(sent)
    side_thread_registry.register_side_thread(
        instance_json,
        actor_id=normalized_actor,
        parent_thread_id=normalized_parent,
        side_thread_id=side_thread_id,
        task_id=task_id,
        purpose=normalized_purpose,
        turn_id=turn_id,
    )
    return {
        "action": "start",
        "purpose": normalized_purpose,
        "parent_thread_id": normalized_parent,
        "side_thread_id": side_thread_id,
        "thread_action": sent.get("action") or "start",
        "turn_id": turn_id,
        "lease_registered": True,
        **_model_config_result(normalized_model, normalized_effort),
    }


def send_to_side_thread(
    *,
    socket_path: Path,
    instance_json: Path,
    actor_id: str,
    parent_thread_id: str,
    side_thread_id: str,
    text: str,
    permissions: str,
) -> dict[str, Any]:
    normalized_actor = _require_text(actor_id, "actor_id")
    normalized_parent = _require_text(parent_thread_id, "parent_thread_id")
    normalized_side = _require_text(side_thread_id, "side_thread_id")
    row = side_thread_registry.require_side_thread(
        instance_json,
        actor_id=normalized_actor,
        parent_thread_id=normalized_parent,
        side_thread_id=normalized_side,
    )
    status_kind = _thread_status_kind(app_server.thread_read(socket_path, normalized_side, include_turns=False))
    if status_kind == "idle":
        sent = app_server.turn_start(socket_path, normalized_side, text, permissions)
        thread_action = "start"
        expected_turn_id = None
    elif status_kind == "active":
        expected_turn_id = _row_turn_id(row)
        if expected_turn_id is None:
            raise SideThreadLifecycleError(f"side thread {normalized_side} has no stored turn id")
        sent = app_server.turn_steer(socket_path, normalized_side, expected_turn_id, text)
        thread_action = "steer"
    else:
        raise SideThreadLifecycleError(f"side thread {normalized_side} is not active or idle")
    turn_id = _turn_id_from_result(sent)
    side_thread_registry.update_side_thread(
        instance_json,
        actor_id=normalized_actor,
        parent_thread_id=normalized_parent,
        side_thread_id=normalized_side,
        turn_id=turn_id,
    )
    payload: dict[str, Any] = {
        "action": "send",
        "purpose": _row_purpose(row),
        "parent_thread_id": normalized_parent,
        "side_thread_id": normalized_side,
        "thread_action": sent.get("action") or thread_action,
        "turn_id": turn_id,
        "lease_updated": True,
    }
    if expected_turn_id is not None:
        payload["expected_turn_id"] = expected_turn_id
    return payload


def cleanup_side_thread(
    *,
    socket_path: Path,
    instance_json: Path,
    actor_id: str,
    parent_thread_id: str,
    side_thread_id: str,
) -> dict[str, Any]:
    normalized_actor = _require_text(actor_id, "actor_id")
    normalized_parent = _require_text(parent_thread_id, "parent_thread_id")
    normalized_side = _require_text(side_thread_id, "side_thread_id")
    row = side_thread_registry.require_side_thread(
        instance_json,
        actor_id=normalized_actor,
        parent_thread_id=normalized_parent,
        side_thread_id=normalized_side,
    )
    turn_id = _row_turn_id(row)
    payload: dict[str, Any] = {
        "action": "cleanup",
        "parent_thread_id": normalized_parent,
        "side_thread_id": normalized_side,
        "turn_interrupt_attempted": False,
        "turn_interrupt_ok": False,
        "lease_unregistered": False,
    }
    if turn_id is not None:
        payload["turn_id"] = turn_id
        payload["turn_interrupt_attempted"] = True
        try:
            app_server.turn_interrupt(socket_path, normalized_side, turn_id)
        except Exception as exc:
            payload["turn_interrupt_error"] = str(exc)
        else:
            payload["turn_interrupt_ok"] = True
    try:
        payload["lease_unregistered"] = side_thread_registry.unregister_side_thread(
            instance_json,
            actor_id=normalized_actor,
            parent_thread_id=normalized_parent,
            side_thread_id=normalized_side,
        )
    except Exception as exc:
        payload["lease_unregister_error"] = str(exc)
    return payload


def cleanup_task_side_lease(
    *,
    socket_path: Path,
    instance_json: Path,
    actor_id: str,
    parent_thread_id: str,
    task_id: str,
) -> dict[str, Any]:
    row = side_thread_registry.find_task_side_thread(
        instance_json,
        actor_id=actor_id,
        parent_thread_id=parent_thread_id,
        task_id=task_id,
    )
    if not isinstance(row, Mapping):
        return {
            "action": "cleanup",
            "side_thread_id": None,
            "turn_interrupt_attempted": False,
            "turn_interrupt_ok": False,
            "lease_unregistered": False,
            "lease_unregister_error": "task side lease not found",
        }
    side_thread_id = _require_text(row.get("thread_id"), "side_thread.thread_id")
    return cleanup_side_thread(
        socket_path=socket_path,
        instance_json=instance_json,
        actor_id=actor_id,
        parent_thread_id=parent_thread_id,
        side_thread_id=side_thread_id,
    )


def find_or_start_side_thread(
    *,
    socket_path: Path,
    instance_json: Path,
    actor_id: str,
    parent_thread_id: str,
    text: str,
    purpose: str,
    workspace_dir: Path,
    shared_project_workspace_dir: Path,
    permissions: str,
    model: str | None = None,
    model_reasoning_effort: str | None = None,
) -> dict[str, Any]:
    normalized_model = _optional_text(model, "model")
    normalized_effort = _optional_text(model_reasoning_effort, "model_reasoning_effort")
    row = side_thread_registry.find_open_side_thread(
        instance_json,
        actor_id=actor_id,
        parent_thread_id=parent_thread_id,
    )
    side_thread_id = row.get("thread_id") if isinstance(row, Mapping) else None
    if isinstance(side_thread_id, str) and side_thread_id.strip():
        if normalized_model is not None or normalized_effort is not None:
            raise SideThreadLifecycleError("model and effort only applies when starting a new side thread")
        return send_to_side_thread(
            socket_path=socket_path,
            instance_json=instance_json,
            actor_id=actor_id,
            parent_thread_id=parent_thread_id,
            side_thread_id=side_thread_id,
            text=text,
            permissions=permissions,
        )
    return start_side_thread(
        socket_path=socket_path,
        instance_json=instance_json,
        actor_id=actor_id,
        parent_thread_id=parent_thread_id,
        text=text,
        purpose=purpose,
        workspace_dir=workspace_dir,
        shared_project_workspace_dir=shared_project_workspace_dir,
        permissions=permissions,
        model=normalized_model,
        model_reasoning_effort=normalized_effort,
    )


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=True))


def _command_start(args: argparse.Namespace) -> int:
    _print_json(
        start_side_thread(
            socket_path=Path(args.socket),
            instance_json=Path(args.instance_json),
            actor_id=args.actor_id,
            parent_thread_id=args.parent_thread_id,
            text=args.text,
            purpose=args.purpose,
            workspace_dir=Path(args.workspace_dir),
            shared_project_workspace_dir=Path(args.shared_project_workspace_dir),
            permissions=args.permissions,
            model=args.model,
            model_reasoning_effort=args.effort,
        )
    )
    return 0


def _command_send(args: argparse.Namespace) -> int:
    _print_json(
        send_to_side_thread(
            socket_path=Path(args.socket),
            instance_json=Path(args.instance_json),
            actor_id=args.actor_id,
            parent_thread_id=args.parent_thread_id,
            side_thread_id=args.side_thread_id,
            text=args.text,
            permissions=args.permissions,
        )
    )
    return 0


def _command_cleanup(args: argparse.Namespace) -> int:
    _print_json(
        cleanup_side_thread(
            socket_path=Path(args.socket),
            instance_json=Path(args.instance_json),
            actor_id=args.actor_id,
            parent_thread_id=args.parent_thread_id,
            side_thread_id=args.side_thread_id,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start")
    start.add_argument("--socket", required=True)
    start.add_argument("--instance-json", required=True)
    start.add_argument("--actor-id", required=True)
    start.add_argument("--parent-thread-id", required=True)
    start.add_argument("--text", required=True)
    start.add_argument("--purpose", required=True)
    start.add_argument("--workspace-dir", required=True)
    start.add_argument("--shared-project-workspace-dir", required=True)
    start.add_argument("--permissions", required=True)
    start.add_argument("--model")
    start.add_argument("--effort")
    start.set_defaults(func=_command_start)

    send = subparsers.add_parser("send")
    send.add_argument("--socket", required=True)
    send.add_argument("--instance-json", required=True)
    send.add_argument("--actor-id", required=True)
    send.add_argument("--parent-thread-id", required=True)
    send.add_argument("--side-thread-id", required=True)
    send.add_argument("--text", required=True)
    send.add_argument("--permissions", required=True)
    send.set_defaults(func=_command_send)

    cleanup = subparsers.add_parser("cleanup")
    cleanup.add_argument("--socket", required=True)
    cleanup.add_argument("--instance-json", required=True)
    cleanup.add_argument("--actor-id", required=True)
    cleanup.add_argument("--parent-thread-id", required=True)
    cleanup.add_argument("--side-thread-id", required=True)
    cleanup.set_defaults(func=_command_cleanup)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
