"""Concrete owner for BuddySwitch side-thread lifecycle operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from buddyswitch.launcher import app_server
from buddyswitch.launcher import side_thread_registry


class SideThreadLifecycleError(RuntimeError):
    """Raised when a side-thread lifecycle operation cannot be completed."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        cleanup: Mapping[str, Any] | None = None,
        input_submitted: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.cleanup = dict(cleanup or {})
        self.input_submitted = input_submitted


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


def _runtime_selection_result(model: str | None, model_reasoning_effort: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if model is not None:
        payload["model"] = model
    if model_reasoning_effort is not None:
        payload["model_reasoning_effort"] = model_reasoning_effort
    return payload


def _thread_id_from_start(result: Mapping[str, Any]) -> str:
    thread = result.get("thread")
    if not isinstance(thread, Mapping):
        raise SideThreadLifecycleError("thread/start did not return a thread object")
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


def _row_turn_kind(row: Mapping[str, Any]) -> str | None:
    value = row.get("turn_kind")
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
    model: str | None = None,
    model_reasoning_effort: str | None = None,
    output_schema: Mapping[str, Any] | None = None,
    config_overrides: Mapping[str, Any] | None = None,
    capability_hash: str | None = None,
    binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_actor = _require_text(actor_id, "actor_id")
    normalized_parent = _require_text(parent_thread_id, "parent_thread_id")
    normalized_purpose = _require_text(purpose, "purpose")
    normalized_model = _optional_text(model, "model")
    normalized_effort = _optional_text(model_reasoning_effort, "model_reasoning_effort")
    started = app_server.thread_start(
        socket_path,
        workspace_dir,
        shared_project_workspace_dir,
        permissions,
        developer_instructions=app_server.SIDE_DEVELOPER_INSTRUCTIONS,
        ephemeral=True,
        model=normalized_model,
        model_reasoning_effort=normalized_effort,
        config_overrides=config_overrides,
    )
    side_thread_id = _thread_id_from_start(started)
    side_thread_registry.register_side_thread(
        instance_json,
        actor_id=normalized_actor,
        parent_thread_id=normalized_parent,
        side_thread_id=side_thread_id,
        purpose=normalized_purpose,
        turn_kind="starting",
        capability_hash=capability_hash,
        binding=binding,
    )
    lease_registered = True
    lease_consumed = False
    turn_id: str | None = None
    try:
        sent = app_server.turn_start(
            socket_path,
            side_thread_id,
            text,
            permissions,
            output_schema=output_schema,
        )
        turn_id = _turn_id_from_result(sent)
        try:
            transitioned = side_thread_registry.transition_side_thread_turn(
                instance_json,
                actor_id=normalized_actor,
                parent_thread_id=normalized_parent,
                side_thread_id=side_thread_id,
                expected_turn_id=None,
                expected_turn_kind="starting",
                turn_id=turn_id,
                turn_kind="work",
            )
        except side_thread_registry.SideThreadRegistryError as exc:
            if not str(exc).startswith("Side thread is not registered for this instance:"):
                raise
            transitioned = None
            lease_registered = False
            lease_consumed = True
            thread_status = "consumed"
        if transitioned is None:
            if not lease_consumed:
                raise SideThreadLifecycleError(f"side thread {side_thread_id} starting lease changed unexpectedly")
        else:
            thread_status = _thread_status_kind(
                app_server.thread_read(socket_path, side_thread_id, include_turns=False)
            )
            if thread_status not in {"active", "idle"}:
                raise SideThreadLifecycleError(f"side thread {side_thread_id} is not active or idle after start")
    except Exception as exc:
        cleanup: dict[str, Any] = {
            "turn_interrupt_attempted": turn_id is not None,
            "turn_interrupt_ok": False,
            "lease_unregistered": False,
        }
        if turn_id is not None:
            try:
                app_server.turn_interrupt(socket_path, side_thread_id, turn_id)
            except Exception as interrupt_exc:
                cleanup["turn_interrupt_error"] = str(interrupt_exc)
            else:
                cleanup["turn_interrupt_ok"] = True
        if lease_registered:
            try:
                cleanup["lease_unregistered"] = side_thread_registry.unregister_side_thread(
                    instance_json,
                    actor_id=normalized_actor,
                    parent_thread_id=normalized_parent,
                    side_thread_id=side_thread_id,
                )
            except Exception as unregister_exc:
                cleanup["lease_unregister_error"] = str(unregister_exc)
        retryable = bool(
            turn_id is not None
            and cleanup["turn_interrupt_ok"]
            and cleanup["lease_unregistered"]
        )
        raise SideThreadLifecycleError(
            str(exc),
            retryable=retryable,
            cleanup=cleanup,
            input_submitted=True if turn_id is not None else None,
        ) from exc
    return {
        "action": "start",
        "purpose": normalized_purpose,
        "parent_thread_id": normalized_parent,
        "side_thread_id": side_thread_id,
        "thread_action": sent.get("action") or "start",
        "turn_id": turn_id,
        "thread_status": thread_status,
        "lease_registered": lease_registered,
        "lease_consumed": lease_consumed,
        **_runtime_selection_result(normalized_model, normalized_effort),
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
    turn_kind: str | None = None,
) -> dict[str, Any]:
    input_submitted: bool | None = False
    try:
        normalized_actor = _require_text(actor_id, "actor_id")
        normalized_parent = _require_text(parent_thread_id, "parent_thread_id")
        normalized_side = _require_text(side_thread_id, "side_thread_id")
        row = side_thread_registry.require_side_thread(
            instance_json,
            actor_id=normalized_actor,
            parent_thread_id=normalized_parent,
            side_thread_id=normalized_side,
        )
        status_kind = _thread_status_kind(
            app_server.thread_read(socket_path, normalized_side, include_turns=False)
        )
        if status_kind == "idle":
            input_submitted = None
            sent = app_server.turn_start(socket_path, normalized_side, text, permissions)
            input_submitted = True
            thread_action = "start"
            expected_turn_id = None
        elif status_kind == "active":
            expected_turn_id = _row_turn_id(row)
            if expected_turn_id is None:
                raise SideThreadLifecycleError(f"side thread {normalized_side} has no stored turn id")
            input_submitted = None
            sent = app_server.turn_steer(socket_path, normalized_side, expected_turn_id, text)
            input_submitted = True
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
            turn_kind=turn_kind,
        )
    except Exception as exc:
        raise SideThreadLifecycleError(
            str(exc),
            input_submitted=input_submitted,
        ) from exc
    payload: dict[str, Any] = {
        "action": "send",
        "purpose": _row_purpose(row),
        "parent_thread_id": normalized_parent,
        "side_thread_id": normalized_side,
        "thread_action": sent.get("action") or thread_action,
        "turn_id": turn_id,
        "turn_kind": turn_kind or _row_turn_kind(row),
        "lease_updated": True,
    }
    if expected_turn_id is not None:
        payload["expected_turn_id"] = expected_turn_id
    return payload


def interrupt_unleased_side_turn(
    *,
    socket_path: Path,
    side_thread_id: str,
    turn_id: str,
) -> dict[str, Any]:
    normalized_side = _require_text(side_thread_id, "side_thread_id")
    normalized_turn = _require_text(turn_id, "turn_id")
    payload: dict[str, Any] = {
        "turn_interrupt_attempted": True,
        "turn_interrupt_ok": False,
        "lease_unregistered": False,
    }
    try:
        app_server.turn_interrupt(socket_path, normalized_side, normalized_turn)
    except Exception as exc:
        payload["turn_interrupt_error"] = str(exc)
    else:
        payload["turn_interrupt_ok"] = True
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


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=True))


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
