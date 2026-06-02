#!/usr/bin/env python3
"""Side-thread registry helper for BuddySwitch instances."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


NowFn = Callable[[], str]


class SideThreadRegistryError(RuntimeError):
    """Raised when side-thread registry validation fails."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _now_value(now: NowFn | None) -> str:
    return now() if callable(now) else _utc_now()


def _require_id(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SideThreadRegistryError(f"{field_name} is required")
    return value.strip()


def _load_payload(instance_json: Path, actor_id: str) -> dict[str, Any]:
    path = Path(instance_json)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SideThreadRegistryError(f"Instance record missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SideThreadRegistryError(f"Instance record is invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise SideThreadRegistryError(f"Instance record must contain an object: {path}")
    if payload.get("actor_id") != actor_id:
        raise SideThreadRegistryError(f"Actor id mismatch in {path}")
    return payload


def _write_payload(instance_json: Path, payload: dict[str, Any]) -> None:
    path = Path(instance_json)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


def _side_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("side_threads")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _validate_side_identity(parent_thread_id: str, side_thread_id: str) -> tuple[str, str]:
    parent = _require_id(parent_thread_id, "Parent thread id")
    side = _require_id(side_thread_id, "Side thread id")
    if side == parent:
        raise SideThreadRegistryError("Side thread id must not be the main thread id.")
    return parent, side


def register_side_thread(
    instance_json: Path,
    *,
    actor_id: str,
    parent_thread_id: str,
    side_thread_id: str,
    now: NowFn | None = None,
) -> dict[str, Any]:
    actor = _require_id(actor_id, "Actor id")
    parent, side = _validate_side_identity(parent_thread_id, side_thread_id)
    payload = _load_payload(Path(instance_json), actor)
    timestamp = _now_value(now)
    row = {
        "thread_id": side,
        "parent_thread_id": parent,
        "status": "open",
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    payload["side_threads"] = [item for item in _side_rows(payload) if item.get("thread_id") != side]
    payload["side_threads"].append(row)
    payload["updated_at"] = timestamp
    _write_payload(Path(instance_json), payload)
    return row


def require_side_thread(
    instance_json: Path,
    *,
    actor_id: str,
    parent_thread_id: str,
    side_thread_id: str,
) -> dict[str, Any]:
    actor = _require_id(actor_id, "Actor id")
    parent, side = _validate_side_identity(parent_thread_id, side_thread_id)
    payload = _load_payload(Path(instance_json), actor)
    for row in _side_rows(payload):
        if row.get("thread_id") == side and row.get("parent_thread_id") == parent and row.get("status") == "open":
            return row
    raise SideThreadRegistryError(f"Side thread is not registered for this instance: {side}")


def find_open_side_thread(
    instance_json: Path,
    *,
    actor_id: str,
    parent_thread_id: str,
) -> dict[str, Any] | None:
    actor = _require_id(actor_id, "Actor id")
    parent = _require_id(parent_thread_id, "Parent thread id")
    payload = _load_payload(Path(instance_json), actor)
    for row in _side_rows(payload):
        thread_id = row.get("thread_id")
        if (
            isinstance(thread_id, str)
            and thread_id
            and thread_id != parent
            and row.get("parent_thread_id") == parent
            and row.get("status") == "open"
        ):
            return row
    return None


def unregister_side_thread(
    instance_json: Path,
    *,
    actor_id: str,
    parent_thread_id: str,
    side_thread_id: str,
    now: NowFn | None = None,
) -> bool:
    actor = _require_id(actor_id, "Actor id")
    parent, side = _validate_side_identity(parent_thread_id, side_thread_id)
    payload = _load_payload(Path(instance_json), actor)
    before = _side_rows(payload)
    after = [
        row
        for row in before
        if not (row.get("thread_id") == side and row.get("parent_thread_id") == parent)
    ]
    removed = len(after) != len(before)
    payload["side_threads"] = after
    payload["updated_at"] = _now_value(now)
    _write_payload(Path(instance_json), payload)
    return removed


def _add_common(parser: argparse.ArgumentParser, *, side: bool) -> None:
    parser.add_argument("--instance-json", required=True)
    parser.add_argument("--actor-id", required=True)
    parser.add_argument("--parent-thread-id", required=True)
    if side:
        parser.add_argument("--side-thread-id", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    register = subparsers.add_parser("register")
    _add_common(register, side=True)
    register.set_defaults(func=_command_register)
    require = subparsers.add_parser("require")
    _add_common(require, side=True)
    require.set_defaults(func=_command_require)
    find = subparsers.add_parser("find-open")
    _add_common(find, side=False)
    find.set_defaults(func=_command_find_open)
    unregister = subparsers.add_parser("unregister")
    _add_common(unregister, side=True)
    unregister.set_defaults(func=_command_unregister)
    return parser


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=True))


def _command_register(args: argparse.Namespace) -> int:
    _print_json(
        register_side_thread(
            Path(args.instance_json),
            actor_id=args.actor_id,
            parent_thread_id=args.parent_thread_id,
            side_thread_id=args.side_thread_id,
        )
    )
    return 0


def _command_require(args: argparse.Namespace) -> int:
    _print_json(
        require_side_thread(
            Path(args.instance_json),
            actor_id=args.actor_id,
            parent_thread_id=args.parent_thread_id,
            side_thread_id=args.side_thread_id,
        )
    )
    return 0


def _command_find_open(args: argparse.Namespace) -> int:
    row = find_open_side_thread(
        Path(args.instance_json),
        actor_id=args.actor_id,
        parent_thread_id=args.parent_thread_id,
    )
    _print_json(row or {})
    return 0


def _command_unregister(args: argparse.Namespace) -> int:
    removed = unregister_side_thread(
        Path(args.instance_json),
        actor_id=args.actor_id,
        parent_thread_id=args.parent_thread_id,
        side_thread_id=args.side_thread_id,
    )
    _print_json({"removed": removed})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except SideThreadRegistryError as exc:
        print(str(exc), file=sys.stderr)
        if "not registered" in str(exc):
            return 3
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
