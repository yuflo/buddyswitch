"""Message repository helpers backed by runtime object files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from buddyswitch.env.domain.identity import IdentityRef
from buddyswitch.env.domain.identity import actor_identity
from buddyswitch.env.domain.identity import external_identity
from . import runtime_files


INITIAL_IM_EVENT_CURSOR = "imev-000000000000"
_CONVERSATION_FIELDS = frozenset(
    {
        "id",
        "type",
        "identity_ids",
        "created_at",
        "updated_at",
        "last_message_id",
        "last_sequence",
    }
)
_MESSAGE_FIELDS = frozenset(
    {
        "id",
        "conversation_id",
        "sender_identity",
        "target_identity",
        "content",
        "reply_to",
        "created_at",
        "sequence",
    }
)
_EVENT_FIELDS = frozenset(
    {
        "event_id",
        "type",
        "message_id",
        "conversation_id",
        "sender_identity",
        "target_identity",
        "visible_to_identity_id",
        "reply_to",
        "created_at",
        "sequence",
    }
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


def _reject_unknown_fields(row: dict[str, Any], fields: frozenset[str], context: str) -> None:
    unknown = sorted(set(row) - fields)
    if unknown:
        raise ValueError(f"{context} contains unknown IM field(s): {', '.join(unknown)}")


def _require_non_negative_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def save_external_session(external_session: dict[str, Any]) -> dict[str, Any]:
    key_hash = _require_non_empty_text(
        external_session.get("external_session_key_hash"),
        "external_session.external_session_key_hash",
    )
    if not key_hash.startswith("sha256:"):
        raise ValueError("external_session.external_session_key_hash must start with sha256:")
    normalized = dict(
        external_session_key_hash=key_hash,
        identity_id=runtime_files.require_id(
            str(external_session.get("identity_id") or ""),
            "external_session.identity_id",
        ),
        display_name=_require_non_empty_text(external_session.get("display_name"), "external_session.display_name"),
        last_event_id=_require_non_empty_text(external_session.get("last_event_id"), "external_session.last_event_id"),
        created_at=_require_non_empty_text(external_session.get("created_at"), "external_session.created_at"),
        last_used_at=_require_non_empty_text(external_session.get("last_used_at"), "external_session.last_used_at"),
    )
    _require_im_write_root()
    runtime_files.write_json_object(_im_dir("external_sessions") / f"{key_hash.replace(':', '-', 1)}.json", normalized)
    return normalized


def get_external_session_by_key_hash(key_hash: str) -> dict[str, Any] | None:
    normalized = _require_non_empty_text(key_hash, "external_session_key_hash")
    if not normalized.startswith("sha256:"):
        raise ValueError("external_session_key_hash must start with sha256:")
    path = _im_dir("external_sessions") / f"{normalized.replace(':', '-', 1)}.json"
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
    _reject_unknown_fields(conversation, _CONVERSATION_FIELDS, "conversation")
    conversation_id = runtime_files.require_id(str(conversation.get("id") or ""), "conversation.id")
    identity_ids_raw = conversation.get("identity_ids")
    if isinstance(identity_ids_raw, list):
        identity_ids = [im_identity_id_for_row(row, "conversation.identity_ids[]") for row in identity_ids_raw]
    else:
        raise ValueError("conversation.identity_ids must be a list")
    if len(identity_ids) < 2:
        raise ValueError("conversation.identity_ids must contain at least two identities")
    normalized = {
        "id": conversation_id,
        "type": _require_non_empty_text(conversation.get("type"), "conversation.type"),
        "identity_ids": identity_ids,
        "created_at": _require_non_empty_text(conversation.get("created_at"), "conversation.created_at"),
        "updated_at": _require_non_empty_text(conversation.get("updated_at"), "conversation.updated_at"),
        "last_message_id": runtime_files.require_id(
            str(conversation.get("last_message_id") or ""),
            "conversation.last_message_id",
        ),
        "last_sequence": _require_non_negative_int(conversation.get("last_sequence"), "conversation.last_sequence"),
    }
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
    _reject_unknown_fields(message, _MESSAGE_FIELDS, "message")
    message_id = runtime_files.require_id(str(message.get("id") or ""), "message.id")
    conversation_id = runtime_files.require_id(str(message.get("conversation_id") or ""), "message.conversation_id")
    sender_identity = _identity_ref(message.get("sender_identity"), "message.sender_identity")
    target_identity = _identity_ref(message.get("target_identity"), "message.target_identity")
    reply_to = message.get("reply_to")
    if reply_to is not None:
        reply_to = runtime_files.require_id(str(reply_to), "message.reply_to")
    normalized = {
        "id": message_id,
        "conversation_id": conversation_id,
        "sender_identity": sender_identity,
        "target_identity": target_identity,
        "content": _require_non_empty_text(message.get("content"), "message.content"),
        "reply_to": reply_to,
        "created_at": _require_non_empty_text(message.get("created_at"), "message.created_at"),
        "sequence": _require_non_negative_int(message.get("sequence"), "message.sequence"),
    }
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


def save_im_event(event: dict[str, Any]) -> dict[str, Any]:
    _reject_unknown_fields(event, _EVENT_FIELDS, "event")
    event_id = runtime_files.require_id(str(event.get("event_id") or ""), "event.event_id")
    message_id = runtime_files.require_id(str(event.get("message_id") or ""), "event.message_id")
    conversation_id = runtime_files.require_id(str(event.get("conversation_id") or ""), "event.conversation_id")
    sender_identity = _identity_ref(event.get("sender_identity"), "event.sender_identity")
    target_identity = _identity_ref(event.get("target_identity"), "event.target_identity")
    visible_to_identity_id = event.get("visible_to_identity_id")
    reply_to = event.get("reply_to")
    if reply_to is not None:
        reply_to = runtime_files.require_id(str(reply_to), "event.reply_to")
    normalized = {
        "event_id": event_id,
        "type": _require_non_empty_text(event.get("type"), "event.type"),
        "message_id": message_id,
        "conversation_id": conversation_id,
        "sender_identity": sender_identity,
        "target_identity": target_identity,
        "visible_to_identity_id": runtime_files.require_id(
            str(visible_to_identity_id or ""),
            "event.visible_to_identity_id",
        ),
        "reply_to": reply_to,
        "created_at": _require_non_empty_text(event.get("created_at"), "event.created_at"),
        "sequence": _require_non_negative_int(event.get("sequence"), "event.sequence"),
    }
    _require_im_write_root()
    runtime_files.write_json_object(
        _im_dir("events") / f"{event_id}--{_identity_filename_key(normalized['visible_to_identity_id'])}.json",
        normalized,
    )
    return normalized


def get_im_event(
    event_id: str,
    identity: dict[str, Any] | str,
) -> dict[str, Any] | None:
    normalized_event_id = runtime_files.require_id(event_id, "event_id")
    identity_id = im_identity_id_for_row(identity, "identity_id")
    path = _im_dir("events") / f"{normalized_event_id}--{_identity_filename_key(identity_id)}.json"
    if not path.exists():
        return None
    return runtime_files.read_json_object(path)


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
