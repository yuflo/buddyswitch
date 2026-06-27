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
INITIAL_IM_EVENT_CURSOR = "imev-000000000000"


def im_root() -> Path:
    return runtime_files.STATE_ROOT / "im"


def _require_im_write_root() -> None:
    runtime_files.require_central_im_write_root()


def _im_dir(name: str) -> Path:
    return im_root() / name


def im_participant_key(participant: dict[str, Any]) -> str:
    kind = participant.get("kind")
    if kind == "external":
        external_id = runtime_files.require_id(str(participant.get("external_id") or ""), "external_id")
        return f"external:{external_id}"
    if kind == "actor":
        actor = _actor_payload(participant.get("actor_address"), "participant.actor_address")
        return f"actor:{actor['role_id']}:{actor['actor_id']}"
    raise ValueError("participant.kind must be external or actor")


def im_participant_ref(participant: dict[str, Any]) -> dict[str, Any]:
    kind = participant.get("kind")
    if kind == "external":
        return {"kind": "external", "external_id": runtime_files.require_id(str(participant.get("external_id") or ""), "external_id")}
    if kind == "actor":
        return {"kind": "actor", "actor_address": _actor_payload(participant.get("actor_address"), "participant.actor_address")}
    raise ValueError("participant.kind must be external or actor")


def im_participant_filename_key(participant: dict[str, Any]) -> str:
    return im_participant_key(participant).replace(":", "--")


def save_im_participant(participant: dict[str, Any]) -> dict[str, Any]:
    if participant.get("kind") != "external":
        raise ValueError("only external participant profiles are persisted directly")
    external_id = runtime_files.require_id(str(participant.get("external_id") or ""), "external_id")
    normalized = dict(participant, kind="external", external_id=external_id)
    _require_im_write_root()
    runtime_files.write_json_object(_im_dir("participants") / f"{external_id}.json", normalized)
    return normalized


def save_im_connection(connection: dict[str, Any]) -> dict[str, Any]:
    key_hash = _require_non_empty_text(connection.get("connection_key_hash"), "connection.connection_key_hash")
    if not key_hash.startswith("sha256:"):
        raise ValueError("connection.connection_key_hash must start with sha256:")
    participant = connection.get("participant")
    if not isinstance(participant, dict):
        raise ValueError("connection.participant must be an object")
    normalized = dict(
        connection,
        connection_key_hash=key_hash,
        participant=im_participant_ref(participant),
        display_name=_require_non_empty_text(connection.get("display_name"), "connection.display_name"),
        last_event_id=_require_non_empty_text(connection.get("last_event_id"), "connection.last_event_id"),
        created_at=_require_non_empty_text(connection.get("created_at"), "connection.created_at"),
        last_used_at=_require_non_empty_text(connection.get("last_used_at"), "connection.last_used_at"),
    )
    _require_im_write_root()
    runtime_files.write_json_object(_im_dir("connections") / f"{key_hash.replace(':', '-', 1)}.json", normalized)
    return normalized


def get_im_connection_by_key_hash(key_hash: str) -> dict[str, Any] | None:
    normalized = _require_non_empty_text(key_hash, "connection_key_hash")
    if not normalized.startswith("sha256:"):
        raise ValueError("connection_key_hash must start with sha256:")
    path = _im_dir("connections") / f"{normalized.replace(':', '-', 1)}.json"
    if not path.exists():
        return None
    return runtime_files.read_json_object(path)


def next_im_sequence() -> int:
    path = _im_dir("meta") / "sequence.json"
    current = 0
    if path.exists():
        payload = runtime_files.read_json_object(path)
        value = payload.get("value")
        if isinstance(value, int) and value >= 0:
            current = value
    sequence = current + 1
    _require_im_write_root()
    runtime_files.write_json_object(path, {"value": sequence})
    return sequence


def save_im_conversation(conversation: dict[str, Any]) -> dict[str, Any]:
    conversation_id = runtime_files.require_id(str(conversation.get("id") or ""), "conversation.id")
    participants_raw = conversation.get("participants")
    if not isinstance(participants_raw, list) or len(participants_raw) < 2:
        raise ValueError("conversation.participants must contain at least two participants")
    normalized = dict(conversation)
    normalized["id"] = conversation_id
    normalized["participants"] = [im_participant_ref(row) for row in participants_raw]
    normalized["type"] = _require_non_empty_text(conversation.get("type"), "conversation.type")
    _require_im_write_root()
    runtime_files.write_json_object(_im_dir("conversations") / f"{conversation_id}.json", normalized)
    return normalized


def get_im_conversation(conversation_id: str) -> dict[str, Any] | None:
    normalized_id = runtime_files.require_id(conversation_id, "conversation_id")
    path = _im_dir("conversations") / f"{normalized_id}.json"
    if not path.exists():
        return None
    return runtime_files.read_json_object(path)


def find_im_direct_conversation(participants: list[dict[str, Any]]) -> dict[str, Any] | None:
    expected = {im_participant_key(row) for row in participants}
    conversations_dir = _im_dir("conversations")
    if not conversations_dir.is_dir():
        return None
    for path in sorted(conversations_dir.glob("*.json")):
        row = runtime_files.read_json_object(path)
        if row.get("type") != "direct":
            continue
        rows = row.get("participants")
        if not isinstance(rows, list):
            continue
        try:
            actual = {im_participant_key(item) for item in rows if isinstance(item, dict)}
        except ValueError:
            continue
        if actual == expected:
            return row
    return None


def save_im_message(message: dict[str, Any]) -> dict[str, Any]:
    message_id = runtime_files.require_id(str(message.get("id") or ""), "message.id")
    conversation_id = runtime_files.require_id(str(message.get("conversation_id") or ""), "message.conversation_id")
    recipients_raw = message.get("to")
    if not isinstance(recipients_raw, list) or len(recipients_raw) != 1:
        raise ValueError("message.to must contain exactly one recipient in Phase 1")
    reply_to = message.get("reply_to")
    if reply_to is not None:
        runtime_files.require_id(str(reply_to), "message.reply_to")
    normalized = dict(message)
    normalized["id"] = message_id
    normalized["conversation_id"] = conversation_id
    normalized["from"] = im_participant_ref(message.get("from") if isinstance(message.get("from"), dict) else {})
    normalized["to"] = [im_participant_ref(recipients_raw[0])]
    normalized["content"] = _require_non_empty_text(message.get("content"), "message.content")
    normalized["reply_to"] = reply_to
    _require_im_write_root()
    runtime_files.write_json_object(_im_dir("messages") / f"{message_id}.json", normalized)
    return normalized


def get_im_message(message_id: str) -> dict[str, Any] | None:
    normalized_id = runtime_files.require_id(message_id, "message_id")
    path = _im_dir("messages") / f"{normalized_id}.json"
    if not path.exists():
        return None
    return runtime_files.read_json_object(path)


def list_im_messages() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    messages_dir = _im_dir("messages")
    if messages_dir.is_dir():
        for path in messages_dir.glob("*.json"):
            rows.append(runtime_files.read_json_object(path))
    rows.sort(key=lambda row: (str(row.get("created_at") or ""), _im_sequence_value(row), str(row.get("id") or "")))
    return rows


def save_im_message_state(state: dict[str, Any]) -> dict[str, Any]:
    message_id = runtime_files.require_id(str(state.get("message_id") or ""), "state.message_id")
    participant = state.get("participant")
    if not isinstance(participant, dict):
        raise ValueError("state.participant must be an object")
    disposition = state.get("disposition")
    if disposition not in _VALID_DISPOSITIONS:
        raise ValueError("state.disposition must be one of absorbed, needs_parent, replied, unseen")
    normalized = dict(state)
    normalized["message_id"] = message_id
    normalized["participant"] = im_participant_ref(participant)
    _require_im_write_root()
    runtime_files.write_json_object(
        _im_dir("message_states") / f"{message_id}--{im_participant_filename_key(participant)}.json",
        normalized,
    )
    return normalized


def get_im_message_state(message_id: str, participant: dict[str, Any]) -> dict[str, Any] | None:
    normalized_id = runtime_files.require_id(message_id, "message_id")
    path = _im_dir("message_states") / f"{normalized_id}--{im_participant_filename_key(participant)}.json"
    if not path.exists():
        return None
    return runtime_files.read_json_object(path)


def save_im_event(event: dict[str, Any]) -> dict[str, Any]:
    event_id = runtime_files.require_id(str(event.get("event_id") or ""), "event.event_id")
    message_id = runtime_files.require_id(str(event.get("message_id") or ""), "event.message_id")
    conversation_id = runtime_files.require_id(str(event.get("conversation_id") or ""), "event.conversation_id")
    participant = event.get("participant")
    if not isinstance(participant, dict):
        raise ValueError("event.participant must be an object")
    normalized = dict(event)
    normalized["event_id"] = event_id
    normalized["message_id"] = message_id
    normalized["conversation_id"] = conversation_id
    normalized["participant"] = im_participant_ref(participant)
    _require_im_write_root()
    runtime_files.write_json_object(
        _im_dir("events") / f"{event_id}--{im_participant_filename_key(participant)}.json",
        normalized,
    )
    return normalized


def list_im_events_for_participant(participant: dict[str, Any]) -> list[dict[str, Any]]:
    participant_ref = im_participant_ref(participant)
    rows: list[dict[str, Any]] = []
    events_dir = _im_dir("events")
    if events_dir.is_dir():
        for path in events_dir.glob("*.json"):
            row = runtime_files.read_json_object(path)
            try:
                if im_participant_ref(row.get("participant") if isinstance(row.get("participant"), dict) else {}) != participant_ref:
                    continue
            except ValueError:
                continue
            rows.append(row)
    rows.sort(key=lambda row: (str(row.get("created_at") or ""), _im_sequence_value(row), str(row.get("event_id") or "")))
    return rows


def _im_sequence_value(row: dict[str, Any]) -> int:
    value = row.get("sequence")
    return value if isinstance(value, int) and value >= 0 else 0


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
