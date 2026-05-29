#!/usr/bin/env python3
"""Daemon presence and best-effort notification delivery."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from env.repos import runtime_files
from env.tool_runtime.actor_profile import BUDDY_ID_PATTERN
from env.tool_runtime.actor_profile import RuntimeActorAddress


DeliveryFunc = Callable[[dict[str, Any], dict[str, Any]], None]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_buddy_id(value: Any) -> str:
    if not isinstance(value, str) or BUDDY_ID_PATTERN.fullmatch(value.strip()) is None:
        raise ValueError("buddy_id must match /^[a-z][a-z0-9-]*$/")
    return value.strip()


def registry_path_for_state_root(state_root: Path) -> Path:
    return Path(state_root).expanduser().resolve(strict=False) / "runtime" / "daemon-registry.json"


def registry_path() -> Path:
    return registry_path_for_state_root(runtime_files.STATE_ROOT)


def _normalize_registry(payload: Any) -> dict[str, Any]:
    rows = payload.get("actors") if isinstance(payload, dict) else []
    actors: list[dict[str, Any]] = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            address = RuntimeActorAddress.from_payload(row.get("actor_address", {}))
            endpoint = row.get("endpoint")
            heartbeat = row.get("heartbeat")
            status = row.get("status")
            last_seen_at = row.get("last_seen_at")
            actors.append(
                {
                    "actor_address": address.to_payload(),
                    "endpoint": dict(endpoint) if isinstance(endpoint, Mapping) else {},
                    "heartbeat": dict(heartbeat) if isinstance(heartbeat, Mapping) else {},
                    "status": status if isinstance(status, str) and status else "offline",
                    "last_seen_at": last_seen_at if isinstance(last_seen_at, str) else "",
                }
            )
    return {"actors": actors}


def load_registry(*, registry_path: Path | None = None) -> dict[str, Any]:
    path = registry_path or globals()["registry_path"]()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"actors": []}
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid daemon registry JSON: {path}") from exc
    return _normalize_registry(payload)


def save_registry(payload: dict[str, Any], *, registry_path: Path | None = None) -> dict[str, Any]:
    normalized = _normalize_registry(payload)
    path = registry_path or globals()["registry_path"]()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(json.dumps(normalized, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)
    return normalized


def clear_registry(*, registry_path: Path | None = None) -> None:
    save_registry({"actors": []}, registry_path=registry_path)


def register_online_actor(
    *,
    actor_address: RuntimeActorAddress,
    endpoint: Mapping[str, Any],
    registry_path: Path | None = None,
    heartbeat: Mapping[str, Any] | None = None,
    status: str = "online",
    last_seen_at: str | None = None,
) -> dict[str, Any]:
    row = {
        "actor_address": actor_address.to_payload(),
        "endpoint": dict(endpoint),
        "heartbeat": dict(heartbeat or {"kind": "daemon_ready_state"}),
        "status": status,
        "last_seen_at": last_seen_at or _utc_now(),
    }
    payload = load_registry(registry_path=registry_path)
    actors = [
        existing
        for existing in payload["actors"]
        if existing.get("actor_address", {}).get("instance_id") != actor_address.instance_id
    ]
    actors.append(row)
    save_registry({"actors": actors}, registry_path=registry_path)
    return row


def unregister_actor(*, actor_address: RuntimeActorAddress, registry_path: Path | None = None) -> None:
    payload = load_registry(registry_path=registry_path)
    actors = [
        row
        for row in payload["actors"]
        if row.get("actor_address", {}).get("instance_id") != actor_address.instance_id
    ]
    save_registry({"actors": actors}, registry_path=registry_path)


def online_actor_records_for_buddy(buddy_id: str, *, registry_path: Path | None = None) -> list[dict[str, Any]]:
    normalized_buddy = _require_buddy_id(buddy_id)
    rows: list[dict[str, Any]] = []
    for row in load_registry(registry_path=registry_path)["actors"]:
        address = RuntimeActorAddress.from_payload(row.get("actor_address", {}))
        if address.buddy_id == normalized_buddy and row.get("status") == "online":
            rows.append(dict(row, actor_address=address.to_payload()))
    return rows


def resolve_notification_target(buddy_id: str, *, registry_path: Path | None = None) -> dict[str, Any]:
    rows = online_actor_records_for_buddy(buddy_id, registry_path=registry_path)
    if not rows:
        return {
            "notification_status": "skipped_offline",
            "actor_address": None,
            "online_actor_count": 0,
        }
    if len(rows) > 1:
        return {
            "notification_status": "ambiguous_online_actor",
            "actor_address": None,
            "online_actor_count": len(rows),
        }
    return {
        "notification_status": "target_online",
        "actor_address": rows[0]["actor_address"],
        "online_actor_count": 1,
        "target": rows[0],
    }


def message_available_event(
    *,
    message_id: str,
    from_actor_address: RuntimeActorAddress,
    to_actor_address: RuntimeActorAddress,
) -> dict[str, Any]:
    return {
        "type": "message.available",
        "message_id": runtime_files.require_id(message_id, "message_id"),
        "from_actor_address": from_actor_address.to_payload(),
        "to_actor_address": to_actor_address.to_payload(),
    }


def _append_event_to_endpoint(target: dict[str, Any], event: dict[str, Any]) -> None:
    endpoint = target.get("endpoint")
    if not isinstance(endpoint, dict):
        raise ValueError("daemon endpoint must be an object")
    if endpoint.get("kind") == "failing":
        message = endpoint.get("message")
        raise RuntimeError(message if isinstance(message, str) and message else "daemon delivery failed")
    if endpoint.get("kind") != "daemon_state_file":
        raise ValueError(f"unsupported daemon endpoint kind: {endpoint.get('kind')}")
    path_raw = endpoint.get("path")
    if not isinstance(path_raw, str) or not path_raw.strip():
        raise ValueError("daemon endpoint path is required")
    path = Path(path_raw).expanduser().resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=True) + "\n")


def deliver_message_available(
    *,
    message_id: str,
    from_actor_address: RuntimeActorAddress,
    to_buddy: str,
    registry_path: Path | None = None,
    deliver: DeliveryFunc | None = None,
) -> dict[str, Any]:
    target = resolve_notification_target(to_buddy, registry_path=registry_path)
    status = target["notification_status"]
    if status != "target_online":
        return {
            "notification_status": status,
            "to_actor_address": None,
            "online_actor_count": target["online_actor_count"],
        }

    target_row = target["target"]
    to_actor_address = RuntimeActorAddress.from_payload(target_row["actor_address"])
    event = message_available_event(
        message_id=message_id,
        from_actor_address=from_actor_address,
        to_actor_address=to_actor_address,
    )
    try:
        if deliver is None:
            _append_event_to_endpoint(target_row, event)
        else:
            deliver(target_row, event)
    except Exception as exc:
        return {
            "notification_status": "delivery_failed",
            "to_actor_address": to_actor_address.to_payload(),
            "online_actor_count": 1,
            "notification_event": event,
            "notification_error": str(exc),
        }
    return {
        "notification_status": "delivered",
        "to_actor_address": to_actor_address.to_payload(),
        "online_actor_count": 1,
        "notification_event": event,
    }
