#!/usr/bin/env python3
"""Message repository helpers backed by runtime object files."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from env.tool_runtime.actor_profile import ActorAddress
from . import runtime_files


_FORBIDDEN_MESSAGE_FIELDS = {
    "status",
    "read_at",
    "track_id",
    "task_id",
    "artifact_id",
    "request_id",
    "refs",
    "recipients",
    "broadcast",
}
_VALID_DISPOSITIONS = {"unseen", "absorbed", "replied", "needs_parent"}


def _require_non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _actor_payload(value: ActorAddress | dict[str, Any], field: str) -> dict[str, str]:
    try:
        if isinstance(value, ActorAddress):
            return value.to_payload()
        return ActorAddress.from_payload(value).to_payload()
    except Exception as exc:
        raise ValueError(f"{field} must be a valid ActorAddress: {exc}") from exc


def _message_file(message_id: str) -> Path:
    normalized_id = runtime_files.require_id(message_id, "message id")
    return runtime_files.MESSAGES_DIR / f"{normalized_id}.json"


def _normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    forbidden = sorted(field for field in message if field in _FORBIDDEN_MESSAGE_FIELDS)
    if forbidden:
        raise ValueError(f"unsupported message fields: {', '.join(forbidden)}")

    msg_id = runtime_files.require_id(message.get("id", ""), "message.id")
    from_actor_address = _actor_payload(message.get("from_actor_address"), "message.from_actor_address")
    to_actor_address = _actor_payload(message.get("to_actor_address"), "message.to_actor_address")
    content = _require_non_empty_text(message.get("content"), "message.content")
    reply_to = message.get("reply_to")
    if reply_to is not None:
        runtime_files.require_id(reply_to, "message.reply_to")
    created_at = _require_non_empty_text(message.get("created_at"), "message.created_at")
    disposition = message.get("disposition", "unseen")
    if not isinstance(disposition, str) or disposition not in _VALID_DISPOSITIONS:
        raise ValueError("message.disposition must be one of absorbed, needs_parent, replied, unseen")
    disposition_reason = message.get("disposition_reason")
    if disposition_reason is not None:
        disposition_reason = _require_non_empty_text(disposition_reason, "message.disposition_reason")
    disposition_updated_at = message.get("disposition_updated_at")
    if disposition_updated_at is not None:
        disposition_updated_at = _require_non_empty_text(disposition_updated_at, "message.disposition_updated_at")
    processed_by_actor_address = message.get("processed_by_actor_address")
    if processed_by_actor_address is not None:
        processed_by_actor_address = _actor_payload(
            processed_by_actor_address,
            "message.processed_by_actor_address",
        )

    return {
        "id": msg_id,
        "from_actor_address": from_actor_address,
        "to_actor_address": to_actor_address,
        "content": content,
        "reply_to": reply_to,
        "created_at": created_at,
        "disposition": disposition,
        "disposition_reason": disposition_reason,
        "disposition_updated_at": disposition_updated_at,
        "processed_by_actor_address": processed_by_actor_address,
    }


def list_messages() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if runtime_files.MESSAGES_DIR.is_dir():
        for path in runtime_files.MESSAGES_DIR.glob("*.json"):
            rows.append(_normalize_message(runtime_files.read_json_object(path)))
    rows.sort(key=lambda row: (row.get("created_at", ""), row["id"]))
    return rows


def get_message(message_id: str) -> dict[str, Any] | None:
    path = _message_file(message_id)
    if not path.exists():
        return None
    return _normalize_message(runtime_files.read_json_object(path))


def save_message(message: dict[str, Any]) -> dict[str, Any]:
    normalized_message = _normalize_message(message)
    runtime_files.require_runtime_workspace_write_root()
    runtime_files.MESSAGES_DIR.mkdir(parents=True, exist_ok=True)
    runtime_files.write_json_object(_message_file(normalized_message["id"]), normalized_message)
    return normalized_message


def delete_message(message_id: str) -> bool:
    path = _message_file(message_id)
    runtime_files.require_runtime_workspace_write_root()
    try:
        path.unlink()
        try:
            runtime_files.MESSAGES_DIR.rmdir()
        except OSError:
            pass
        return True
    except FileNotFoundError:
        return False


def create_message(
    *,
    from_actor_address: ActorAddress | dict[str, Any],
    to_actor_address: ActorAddress | dict[str, Any],
    content: str,
    reply_to: str | None = None,
) -> dict[str, Any]:
    normalized_from = _actor_payload(from_actor_address, "from_actor_address")
    normalized_to = _actor_payload(to_actor_address, "to_actor_address")
    normalized_content = _require_non_empty_text(content, "content")
    if reply_to is not None:
        runtime_files.require_id(reply_to, "reply_to")

    message_id = f"msg-{uuid.uuid4().hex[:12]}"
    runtime_files.require_id(message_id, "message id")
    message = {
        "id": message_id,
        "from_actor_address": normalized_from,
        "to_actor_address": normalized_to,
        "content": normalized_content,
        "reply_to": reply_to,
        "created_at": runtime_files.now_iso(),
        "disposition": "unseen",
        "disposition_reason": None,
        "disposition_updated_at": None,
        "processed_by_actor_address": None,
    }
    return save_message(message)
