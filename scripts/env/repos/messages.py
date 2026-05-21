#!/usr/bin/env python3
"""Message repository helpers backed by runtime object files."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

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


def _require_non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _message_file(message_id: str) -> Path:
    normalized_id = runtime_files.require_id(message_id, "message id")
    return runtime_files.MESSAGES_DIR / f"{normalized_id}.json"


def _normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    forbidden = sorted(field for field in message if field in _FORBIDDEN_MESSAGE_FIELDS)
    if forbidden:
        raise ValueError(f"unsupported message fields: {', '.join(forbidden)}")

    msg_id = runtime_files.require_id(message.get("id", ""), "message.id")
    from_buddy = _require_non_empty_text(message.get("from_buddy"), "message.from_buddy")
    to_buddy = _require_non_empty_text(message.get("to_buddy"), "message.to_buddy")
    content = _require_non_empty_text(message.get("content"), "message.content")
    reply_to = message.get("reply_to")
    if reply_to is not None:
        runtime_files.require_id(reply_to, "message.reply_to")
    created_at = _require_non_empty_text(message.get("created_at"), "message.created_at")

    return {
        "id": msg_id,
        "from_buddy": from_buddy,
        "to_buddy": to_buddy,
        "content": content,
        "reply_to": reply_to,
        "created_at": created_at,
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


def create_message(
    *,
    from_buddy: str,
    to_buddy: str,
    content: str,
    reply_to: str | None = None,
) -> dict[str, Any]:
    normalized_from = _require_non_empty_text(from_buddy, "from_buddy")
    normalized_to = _require_non_empty_text(to_buddy, "to_buddy")
    normalized_content = _require_non_empty_text(content, "content")
    if reply_to is not None:
        runtime_files.require_id(reply_to, "reply_to")

    message_id = f"msg-{uuid.uuid4().hex[:12]}"
    runtime_files.require_id(message_id, "message id")
    message = {
        "id": message_id,
        "from_buddy": normalized_from,
        "to_buddy": normalized_to,
        "content": normalized_content,
        "reply_to": reply_to,
        "created_at": runtime_files.now_iso(),
    }
    return save_message(message)
