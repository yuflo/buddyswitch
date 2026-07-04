#!/usr/bin/env python3
"""Message repository helpers backed by runtime object files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from env.domain.identity import IdentityRef
from env.domain.identity import actor_identity
from env.domain.identity import external_identity
from . import runtime_files


_VALID_DISPOSITIONS = {"unseen", "absorbed", "replied", "needs_parent"}
INITIAL_IM_EVENT_CURSOR = "imev-000000000000"
_RETIRED_CONVERSATION_FIELDS = ("partici" + "pants",)
_RETIRED_MESSAGE_FIELDS = ("fr" + "om", "to", "from_" + "identity_id", "to_" + "identity_id")
_RETIRED_STATE_FIELDS = ("partici" + "pant",)
_RETIRED_EVENT_FIELDS = (
    "fr" + "om",
    "to",
    "from_" + "identity_id",
    "to_" + "identity_id",
    "visible_to_" + "identity",
)


def im_root() -> Path:
    return runtime_files.STATE_ROOT / "im"


def _require_im_write_root() -> None:
    runtime_files.require_central_im_write_root()


def _im_dir(name: str) -> Path:
    return im_root() / name


def im_identity_id_for_row(row: Any, field: str) -> str:
    if isinstance(row, str):
        return runtime_files.require_id(row, field)
    if isinstance(row, dict):
        if isinstance(row.get("id"), str) and isinstance(row.get("type"), str):
            return IdentityRef.from_payload(row).id
        if isinstance(row.get("identity"), dict):
            return IdentityRef.from_payload(row["identity"]).id
        if isinstance(row.get("identity_id"), str):
            return runtime_files.require_id(row["identity_id"], field)
    raise ValueError(f"{field} must be an identity id or identity payload")


def _identity_filename_key(identity_id: str) -> str:
    return runtime_files.require_id(identity_id, "identity_id").replace(":", "--")


def _identity_ref(value: Any, field: str) -> dict[str, str]:
    if isinstance(value, dict):
        if isinstance(value.get("identity"), dict):
            return IdentityRef.from_payload(value["identity"]).to_payload()
        if isinstance(value.get("id"), str) and isinstance(value.get("type"), str):
            return IdentityRef.from_payload(value).to_payload()
    if isinstance(value, str) and value.strip():
        identity_id = value.strip()
        if identity_id.startswith("act-"):
            return actor_identity(identity_id).to_payload()
        if identity_id.startswith("ext-"):
            return external_identity(identity_id).to_payload()
    raise ValueError(f"{field} must be an identity payload or identity id")


def _reject_retired_fields(row: dict[str, Any], fields: tuple[str, ...], context: str) -> None:
    present = [field for field in fields if field in row]
    if present:
        raise ValueError(f"{context} contains retired IM field(s): {', '.join(present)}")


def save_im_connection(connection: dict[str, Any]) -> dict[str, Any]:
    key_hash = _require_non_empty_text(connection.get("connection_key_hash"), "connection.connection_key_hash")
    if not key_hash.startswith("sha256:"):
        raise ValueError("connection.connection_key_hash must start with sha256:")
    normalized = dict(
        connection_key_hash=key_hash,
        identity_id=runtime_files.require_id(str(connection.get("identity_id") or ""), "connection.identity_id"),
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
    _reject_retired_fields(conversation, _RETIRED_CONVERSATION_FIELDS, "conversation")
    conversation_id = runtime_files.require_id(str(conversation.get("id") or ""), "conversation.id")
    identity_ids_raw = conversation.get("identity_ids")
    if isinstance(identity_ids_raw, list):
        identity_ids = [im_identity_id_for_row(row, "conversation.identity_ids[]") for row in identity_ids_raw]
    else:
        raise ValueError("conversation.identity_ids must be a list")
    if len(identity_ids) < 2:
        raise ValueError("conversation.identity_ids must contain at least two identities")
    normalized = dict(conversation)
    normalized["id"] = conversation_id
    normalized["identity_ids"] = identity_ids
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


def find_im_direct_conversation(identities: list[dict[str, Any] | str]) -> dict[str, Any] | None:
    expected = {im_identity_id_for_row(row, "identities[]") for row in identities}
    conversations_dir = _im_dir("conversations")
    if not conversations_dir.is_dir():
        return None
    for path in sorted(conversations_dir.glob("*.json")):
        row = runtime_files.read_json_object(path)
        if row.get("type") != "direct":
            continue
        try:
            if not isinstance(row.get("identity_ids"), list):
                continue
            actual = {im_identity_id_for_row(item, "conversation.identity_ids[]") for item in row["identity_ids"]}
        except ValueError:
            continue
        if actual == expected:
            return row
    return None


def save_im_message(message: dict[str, Any]) -> dict[str, Any]:
    _reject_retired_fields(message, _RETIRED_MESSAGE_FIELDS, "message")
    message_id = runtime_files.require_id(str(message.get("id") or ""), "message.id")
    conversation_id = runtime_files.require_id(str(message.get("conversation_id") or ""), "message.conversation_id")
    sender_identity = _identity_ref(message.get("sender_identity"), "message.sender_identity")
    target_identity = _identity_ref(message.get("target_identity"), "message.target_identity")
    reply_to = message.get("reply_to")
    if reply_to is not None:
        runtime_files.require_id(str(reply_to), "message.reply_to")
    normalized = dict(message)
    normalized["id"] = message_id
    normalized["conversation_id"] = conversation_id
    normalized["sender_identity"] = sender_identity
    normalized["target_identity"] = target_identity
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
    _reject_retired_fields(state, _RETIRED_STATE_FIELDS, "state")
    message_id = runtime_files.require_id(str(state.get("message_id") or ""), "state.message_id")
    disposition = state.get("disposition")
    if disposition not in _VALID_DISPOSITIONS:
        raise ValueError("state.disposition must be one of absorbed, needs_parent, replied, unseen")
    normalized = dict(state)
    normalized["message_id"] = message_id
    normalized["owner_identity_id"] = runtime_files.require_id(str(state.get("owner_identity_id") or ""), "state.owner_identity_id")
    _require_im_write_root()
    runtime_files.write_json_object(
        _im_dir("message_states") / f"{message_id}--{_identity_filename_key(normalized['owner_identity_id'])}.json",
        normalized,
    )
    return normalized


def get_im_message_state(message_id: str, identity: dict[str, Any] | str) -> dict[str, Any] | None:
    normalized_id = runtime_files.require_id(message_id, "message_id")
    identity_id = im_identity_id_for_row(identity, "state.owner_identity_id")
    path = _im_dir("message_states") / f"{normalized_id}--{_identity_filename_key(identity_id)}.json"
    if not path.exists():
        return None
    return runtime_files.read_json_object(path)


def save_im_event(event: dict[str, Any]) -> dict[str, Any]:
    _reject_retired_fields(event, _RETIRED_EVENT_FIELDS, "event")
    event_id = runtime_files.require_id(str(event.get("event_id") or ""), "event.event_id")
    message_id = runtime_files.require_id(str(event.get("message_id") or ""), "event.message_id")
    conversation_id = runtime_files.require_id(str(event.get("conversation_id") or ""), "event.conversation_id")
    sender_identity = _identity_ref(event.get("sender_identity"), "event.sender_identity")
    target_identity = _identity_ref(event.get("target_identity"), "event.target_identity")
    visible_to_identity_id = event.get("visible_to_identity_id")
    normalized = dict(event)
    normalized["event_id"] = event_id
    normalized["message_id"] = message_id
    normalized["conversation_id"] = conversation_id
    normalized["sender_identity"] = sender_identity
    normalized["target_identity"] = target_identity
    normalized["visible_to_identity_id"] = runtime_files.require_id(
        str(visible_to_identity_id or ""),
        "event.visible_to_identity_id",
    )
    _require_im_write_root()
    runtime_files.write_json_object(
        _im_dir("events") / f"{event_id}--{_identity_filename_key(normalized['visible_to_identity_id'])}.json",
        normalized,
    )
    return normalized


def list_im_events_for_identity(identity: dict[str, Any] | str) -> list[dict[str, Any]]:
    if isinstance(identity, str):
        identity_id = runtime_files.require_id(identity, "identity_id")
    elif isinstance(identity, dict) and isinstance(identity.get("id"), str):
        identity_id = runtime_files.require_id(identity["id"], "identity.id")
    elif isinstance(identity, dict) and isinstance(identity.get("identity"), dict):
        identity_payload = identity["identity"]
        identity_id = runtime_files.require_id(str(identity_payload.get("id") or ""), "identity.id")
    else:
        raise ValueError("identity must be an identity id or identity payload")
    rows: list[dict[str, Any]] = []
    events_dir = _im_dir("events")
    if events_dir.is_dir():
        for path in events_dir.glob("*.json"):
            row = runtime_files.read_json_object(path)
            if row.get("visible_to_identity_id") == identity_id:
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
