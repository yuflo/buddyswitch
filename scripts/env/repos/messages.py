#!/usr/bin/env python3
"""Message repository helpers backed by runtime object files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from env.domain.identity import identity_from_im_participant
from env.tool_runtime.actor_profile import ActorAddress
from . import runtime_files


_VALID_DISPOSITIONS = {"unseen", "absorbed", "replied", "needs_parent"}
INITIAL_IM_EVENT_CURSOR = "imev-000000000000"


def im_root() -> Path:
    return runtime_files.STATE_ROOT / "im"


def _require_im_write_root() -> None:
    runtime_files.require_central_im_write_root()


def _im_dir(name: str) -> Path:
    return im_root() / name


def im_participant_key(participant: dict[str, Any]) -> str:
    return im_identity_id_for_participant(participant)


def im_identity_id_for_participant(participant: dict[str, Any]) -> str:
    return identity_from_im_participant(participant).id


def im_identity_id_for_row(row: Any, field: str) -> str:
    if isinstance(row, str):
        return runtime_files.require_id(row, field)
    if isinstance(row, dict):
        if isinstance(row.get("identity_id"), str):
            return runtime_files.require_id(row["identity_id"], field)
        return im_identity_id_for_participant(row)
    raise ValueError(f"{field} must be an identity id or participant object")


def _participant_type(participant: dict[str, Any]) -> str:
    kind = participant.get("kind")
    if kind == "external":
        runtime_files.require_id(str(participant.get("external_id") or ""), "external_id")
        return "external"
    if kind == "actor":
        _actor_payload(participant.get("actor_address"), "participant.actor_address")
        return "actor"
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


def _identity_filename_key(identity_id: str) -> str:
    return runtime_files.require_id(identity_id, "identity_id").replace(":", "--")


def save_im_participant(participant: dict[str, Any]) -> dict[str, Any]:
    if participant.get("kind") != "external":
        raise ValueError("only external participant profiles are persisted directly")
    external_id = runtime_files.require_id(str(participant.get("external_id") or ""), "external_id")
    normalized = dict(participant, kind="external", external_id=external_id)
    _require_im_write_root()
    runtime_files.write_json_object(_im_dir("participants") / f"{external_id}.json", normalized)
    return normalized


def get_im_external_participant(external_id: str) -> dict[str, Any] | None:
    normalized_id = runtime_files.require_id(external_id, "external_id")
    path = _im_dir("participants") / f"{normalized_id}.json"
    if not path.exists():
        return None
    row = runtime_files.read_json_object(path)
    if row.get("kind") != "external":
        return None
    return im_participant_ref(row)


def save_im_connection(connection: dict[str, Any]) -> dict[str, Any]:
    key_hash = _require_non_empty_text(connection.get("connection_key_hash"), "connection.connection_key_hash")
    if not key_hash.startswith("sha256:"):
        raise ValueError("connection.connection_key_hash must start with sha256:")
    identity_id = connection.get("identity_id")
    if identity_id is None:
        participant = connection.get("participant")
        if not isinstance(participant, dict):
            raise ValueError("connection.identity_id must be a non-empty string")
        participant_ref = im_participant_ref(participant)
        if participant_ref.get("kind") != "external":
            raise ValueError("connection.identity_id is required for non-external connection participants")
        identity_id = participant_ref.get("external_id")
    normalized = dict(
        connection_key_hash=key_hash,
        identity_id=runtime_files.require_id(str(identity_id or ""), "connection.identity_id"),
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
    identity_ids_raw = conversation.get("identity_ids")
    if identity_ids_raw is None:
        participants_raw = conversation.get("participants")
        if not isinstance(participants_raw, list):
            raise ValueError("conversation.identity_ids must contain at least two identities")
        identity_ids = [im_identity_id_for_row(row, "conversation.identity_ids[]") for row in participants_raw]
    elif isinstance(identity_ids_raw, list):
        identity_ids = [im_identity_id_for_row(row, "conversation.identity_ids[]") for row in identity_ids_raw]
    else:
        raise ValueError("conversation.identity_ids must be a list")
    if len(identity_ids) < 2:
        raise ValueError("conversation.identity_ids must contain at least two identities")
    normalized = dict(conversation)
    normalized["id"] = conversation_id
    normalized.pop("participants", None)
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


def find_im_direct_conversation(participants: list[dict[str, Any]]) -> dict[str, Any] | None:
    expected = {im_identity_id_for_row(row, "participants[]") for row in participants}
    conversations_dir = _im_dir("conversations")
    if not conversations_dir.is_dir():
        return None
    for path in sorted(conversations_dir.glob("*.json")):
        row = runtime_files.read_json_object(path)
        if row.get("type") != "direct":
            continue
        try:
            if isinstance(row.get("identity_ids"), list):
                actual = {im_identity_id_for_row(item, "conversation.identity_ids[]") for item in row["identity_ids"]}
            else:
                rows = row.get("participants")
                if not isinstance(rows, list):
                    continue
                actual = {im_identity_id_for_row(item, "conversation.participants[]") for item in rows}
        except ValueError:
            continue
        if actual == expected:
            return row
    return None


def save_im_message(message: dict[str, Any]) -> dict[str, Any]:
    message_id = runtime_files.require_id(str(message.get("id") or ""), "message.id")
    conversation_id = runtime_files.require_id(str(message.get("conversation_id") or ""), "message.conversation_id")
    from_identity_id = message.get("from_identity_id")
    if from_identity_id is None:
        from_identity_id = im_identity_id_for_row(message.get("from"), "message.from_identity_id")
    to_identity_id = message.get("to_identity_id")
    if to_identity_id is None:
        recipients_raw = message.get("to")
        if not isinstance(recipients_raw, list) or len(recipients_raw) != 1:
            raise ValueError("message.to_identity_id must be provided")
        to_identity_id = im_identity_id_for_row(recipients_raw[0], "message.to_identity_id")
    reply_to = message.get("reply_to")
    if reply_to is not None:
        runtime_files.require_id(str(reply_to), "message.reply_to")
    normalized = dict(message)
    normalized["id"] = message_id
    normalized["conversation_id"] = conversation_id
    normalized.pop("from", None)
    normalized.pop("to", None)
    normalized["from_identity_id"] = runtime_files.require_id(str(from_identity_id or ""), "message.from_identity_id")
    normalized["to_identity_id"] = runtime_files.require_id(str(to_identity_id or ""), "message.to_identity_id")
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
    owner_identity_id = state.get("owner_identity_id")
    if owner_identity_id is None:
        owner_identity_id = im_identity_id_for_row(state.get("participant"), "state.owner_identity_id")
    disposition = state.get("disposition")
    if disposition not in _VALID_DISPOSITIONS:
        raise ValueError("state.disposition must be one of absorbed, needs_parent, replied, unseen")
    normalized = dict(state)
    normalized["message_id"] = message_id
    normalized.pop("participant", None)
    normalized["owner_identity_id"] = runtime_files.require_id(str(owner_identity_id or ""), "state.owner_identity_id")
    _require_im_write_root()
    runtime_files.write_json_object(
        _im_dir("message_states") / f"{message_id}--{_identity_filename_key(normalized['owner_identity_id'])}.json",
        normalized,
    )
    return normalized


def get_im_message_state(message_id: str, participant: dict[str, Any] | str) -> dict[str, Any] | None:
    normalized_id = runtime_files.require_id(message_id, "message_id")
    identity_id = im_identity_id_for_row(participant, "state.owner_identity_id")
    path = _im_dir("message_states") / f"{normalized_id}--{_identity_filename_key(identity_id)}.json"
    if not path.exists():
        return None
    return runtime_files.read_json_object(path)


def save_im_event(event: dict[str, Any]) -> dict[str, Any]:
    event_id = runtime_files.require_id(str(event.get("event_id") or ""), "event.event_id")
    message_id = runtime_files.require_id(str(event.get("message_id") or ""), "event.message_id")
    conversation_id = runtime_files.require_id(str(event.get("conversation_id") or ""), "event.conversation_id")
    from_identity_id = event.get("from_identity_id")
    if from_identity_id is None:
        from_identity_id = im_identity_id_for_row(event.get("from"), "event.from_identity_id")
    to_identity_id = event.get("to_identity_id")
    if to_identity_id is None:
        recipients = event.get("to")
        if not isinstance(recipients, list) or len(recipients) != 1:
            raise ValueError("event.to_identity_id must be provided")
        to_identity_id = im_identity_id_for_row(recipients[0], "event.to_identity_id")
    visible_to_identity_id = event.get("visible_to_identity_id")
    if visible_to_identity_id is None:
        visible_to_identity_id = im_identity_id_for_row(event.get("participant"), "event.visible_to_identity_id")
    normalized = dict(event)
    normalized["event_id"] = event_id
    normalized["message_id"] = message_id
    normalized["conversation_id"] = conversation_id
    normalized.pop("from", None)
    normalized.pop("to", None)
    normalized["from_identity_id"] = runtime_files.require_id(str(from_identity_id or ""), "event.from_identity_id")
    normalized["to_identity_id"] = runtime_files.require_id(str(to_identity_id or ""), "event.to_identity_id")
    normalized.pop("participant", None)
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


def list_im_events_for_participant(participant: dict[str, Any]) -> list[dict[str, Any]]:
    participant_ref = im_participant_ref(participant)
    identity_id = im_identity_id_for_participant(participant_ref)
    rows: list[dict[str, Any]] = []
    events_dir = _im_dir("events")
    if events_dir.is_dir():
        for path in events_dir.glob("*.json"):
            row = runtime_files.read_json_object(path)
            try:
                if "visible_to_identity_id" in row:
                    if im_identity_id_for_row(row.get("visible_to_identity_id"), "event.visible_to_identity_id") != identity_id:
                        continue
                elif im_participant_ref(row.get("participant") if isinstance(row.get("participant"), dict) else {}) != participant_ref:
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
