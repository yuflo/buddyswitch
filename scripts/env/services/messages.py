#!/usr/bin/env python3
"""Public message send service."""

from __future__ import annotations

import hashlib
import secrets
import time
import uuid
from typing import Any

from env.domain.identity import ACTOR_ID_PATTERN, IdentityRef, ROLE_ID_PATTERN
from env.domain.identity import actor_identity
from env.domain.identity import external_identity


def _im_payload_error(message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": message}}


_BLOCKED_ACTOR_CONTACT_STATUSES = {"offline", "registered_offline", "inactive", "unreachable", "target_not_online"}


def _identity_ref(value: Any, field: str = "identity") -> dict[str, str]:
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


def _identity_id(value: Any, field: str = "identity") -> str:
    return _identity_ref(value, field)["id"]


def _actor_contact_from_runtime_row(row: Any) -> dict[str, str] | None:
    if not isinstance(row, dict):
        return None
    identity_id = row.get("identity_id")
    role_id = row.get("role_id")
    if not isinstance(identity_id, str) or ACTOR_ID_PATTERN.fullmatch(identity_id) is None:
        return None
    if not isinstance(role_id, str) or ROLE_ID_PATTERN.fullmatch(role_id) is None:
        return None
    return {"identity_id": identity_id, "role_id": role_id}


def _actor_status_from_runtime_row(row: dict[str, Any]) -> str:
    status = row.get("status")
    return status if isinstance(status, str) and status.strip() else "online"


def list_im_actor_contacts(actor_rows: list[dict[str, Any]], role_id: str | None = None) -> dict[str, Any]:
    normalized_role = role_id.strip() if isinstance(role_id, str) and role_id.strip() else None
    actors: list[dict[str, Any]] = []
    for row in actor_rows:
        actor = _actor_contact_from_runtime_row(row)
        if actor is None:
            continue
        if normalized_role is not None and actor["role_id"] != normalized_role:
            continue
        status = _actor_status_from_runtime_row(row)
        if status in _BLOCKED_ACTOR_CONTACT_STATUSES:
            continue
        actors.append(
            {
                "identity": {"id": actor["identity_id"], "type": "actor"},
                "identity_id": actor["identity_id"],
                "role_id": actor["role_id"],
                "reachability_status": status,
            }
        )
    return {"ok": True, "actors": actors, "count": len(actors)}


def actor_identity_for_current_send_target(
    actor_rows: list[dict[str, Any]],
    target_identity_id: Any,
    *,
    field: str = "target_identity_id",
    active_identity_id: str | None = None,
) -> dict[str, Any]:
    identity_id = target_identity_id.strip() if isinstance(target_identity_id, str) and target_identity_id.strip() else ""
    if not identity_id:
        return _im_payload_error(f"{field} is required")
    if isinstance(active_identity_id, str) and active_identity_id.strip() and identity_id == active_identity_id.strip():
        return _im_payload_error(f"{field} must not be the current actor identity")
    for row in actor_rows:
        actor = _actor_contact_from_runtime_row(row)
        if actor is None:
            continue
        status = _actor_status_from_runtime_row(row)
        if status in _BLOCKED_ACTOR_CONTACT_STATUSES:
            continue
        if actor["identity_id"] == identity_id:
            return {"ok": True, "identity": actor_identity(identity_id).to_payload(), "role_id": actor["role_id"]}
    return _im_payload_error(f"{field} is not a reachable actor identity: {identity_id}")


def create_external_connection(*, display_name: str) -> dict[str, Any]:
    from env.repos import identities as identity_repo
    from env.repos import messages as message_repo

    normalized_display_name = display_name.strip() if isinstance(display_name, str) else ""
    if not normalized_display_name:
        return {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "display_name must be a non-empty string"}}

    external_identity_id = f"ext-{uuid.uuid4().hex[:12]}"
    now = message_repo.runtime_files.now_iso()
    identity_repo.save_external_profile(
        {
            "identity": {"id": external_identity_id, "type": "external"},
            "display_name": normalized_display_name,
            "created_at": now,
        }
    )
    external_connection = {
        "external_identity_id": external_identity_id,
        "display_name": normalized_display_name,
        "created_at": now,
        "last_seen_at": now,
    }
    connection_key = f"imck-{secrets.token_hex(24)}"
    connection_key_hash = _im_connection_key_hash(connection_key)
    message_repo.save_im_connection(
        {
            "connection_key_hash": connection_key_hash,
            "identity_id": external_identity_id,
            "display_name": normalized_display_name,
            "last_event_id": message_repo.INITIAL_IM_EVENT_CURSOR,
            "created_at": now,
            "last_used_at": now,
        }
    )
    return {
        "ok": True,
        "connection_key": connection_key,
        "identity": {"id": external_identity_id, "type": "external"},
        "external_connection": external_connection,
    }


def _im_connection_key_hash(connection_key: str) -> str:
    return "sha256:" + hashlib.sha256(connection_key.encode("utf-8")).hexdigest()


def authenticate_external_connection_key(connection_key: str) -> dict[str, Any]:
    from env.repos import messages as message_repo

    if not isinstance(connection_key, str) or not connection_key.strip():
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": "connection_key is required"}}
    connection = message_repo.get_im_connection_by_key_hash(_im_connection_key_hash(connection_key.strip()))
    if connection is None:
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": "connection_key is invalid"}}
    try:
        identity = _identity_ref(connection.get("identity_id"), "connection.identity_id")
    except ValueError as exc:
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": str(exc)}}
    updated = dict(connection)
    updated["identity_id"] = identity["id"]
    updated["last_used_at"] = message_repo.runtime_files.now_iso()
    saved = message_repo.save_im_connection(updated)
    return {
        "ok": True,
        "identity": identity,
        "connection": saved,
    }


def _new_im_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _im_reply_target_error(message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": "E_IM_REPLY_TARGET", "message": message}}


def _direct_conversation_identity_ids(message_repo: Any, conversation: dict[str, Any]) -> list[str] | None:
    if conversation.get("type") != "direct":
        return None
    identity_ids = conversation.get("identity_ids")
    if isinstance(identity_ids, list) and len(identity_ids) == 2:
        try:
            return [message_repo.im_identity_id_for_row(row, "conversation.identity_ids[]") for row in identity_ids]
        except ValueError:
            return None
    return None


def _resolve_reply_conversation(
    *,
    message_repo: Any,
    sender: dict[str, Any],
    target: dict[str, Any] | None,
    reply_to_id: str,
) -> dict[str, Any]:
    original_message = message_repo.get_im_message(reply_to_id)
    if original_message is None:
        return _im_reply_target_error("reply_to message not found")
    conversation = message_repo.get_im_conversation(str(original_message.get("conversation_id") or ""))
    if conversation is None:
        return _im_reply_target_error("reply_to conversation not found")
    identity_ids = _direct_conversation_identity_ids(message_repo, conversation)
    if identity_ids is None:
        return _im_reply_target_error("reply_to conversation is not a direct conversation")
    sender_key = _identity_id(sender)
    identity_set = set(identity_ids)
    if sender_key not in identity_set:
        return _im_reply_target_error("active sender is not in the reply_to conversation")
    if target is None:
        other = [row for row in identity_ids if row != sender_key]
        if len(other) != 1:
            return _im_reply_target_error("reply target cannot be derived from the direct conversation")
        target = _identity_ref(other[0], "reply target")
    else:
        target_key = _identity_id(target)
        if {sender_key, target_key} != identity_set:
            return _im_reply_target_error("reply_to must stay in the same direct conversation")
    return {
        "ok": True,
        "target": target,
        "conversation_id": str(conversation["id"]),
        "created_at": str(conversation.get("created_at") or message_repo.runtime_files.now_iso()),
    }


def _mark_reply_source_replied(
    *,
    message_repo: Any,
    identity: dict[str, Any],
    message_id: str,
) -> dict[str, Any] | None:
    current = message_repo.get_im_message_state(message_id, _identity_id(identity))
    if current is None:
        return None
    updated = dict(current)
    updated["disposition"] = "replied"
    updated["reason"] = None
    updated["updated_at"] = message_repo.runtime_files.now_iso()
    return message_repo.save_im_message_state(updated)


def send_im_message(
    *,
    sender_identity: dict[str, Any],
    to: dict[str, Any] | None,
    target_role_id: str | None = None,
    content: str,
    reply_to: str | None = None,
    wake_actor: Any | None = None,
) -> dict[str, Any]:
    from env.repos import messages as message_repo

    try:
        sender = _identity_ref(sender_identity, "sender_identity")
    except ValueError as exc:
        return _im_payload_error(str(exc))
    normalized_content = content.strip() if isinstance(content, str) else ""
    if not normalized_content:
        return _im_payload_error("content must be a non-empty string")
    if reply_to is not None and (not isinstance(reply_to, str) or not reply_to.strip()):
        return _im_payload_error("reply_to must be a non-empty string")
    reply_to_id = reply_to.strip() if isinstance(reply_to, str) else None
    try:
        target = _identity_ref(to, "target_identity") if isinstance(to, dict) and to else None
    except ValueError as exc:
        return _im_payload_error(str(exc))

    now = message_repo.runtime_files.now_iso()
    if reply_to_id is not None:
        resolved = _resolve_reply_conversation(
            message_repo=message_repo,
            sender=sender,
            target=target,
            reply_to_id=reply_to_id,
        )
        if resolved.get("ok") is not True:
            return resolved
        target = resolved["target"]
        conversation_id = str(resolved["conversation_id"])
        created_at = str(resolved.get("created_at") or now)
    else:
        if target is None:
            return _im_payload_error("to is required for a new message")
        existing = message_repo.find_im_direct_conversation([sender, target])
        if existing is None:
            conversation_id = _new_im_id("conv")
            created_at = now
        else:
            conversation_id = str(existing["id"])
            created_at = str(existing.get("created_at") or now)
    message_id = _new_im_id("msg")
    event_id = _new_im_id("imev")
    sequence = message_repo.next_im_sequence()
    conversation = message_repo.save_im_conversation(
        {
            "id": conversation_id,
            "type": "direct",
            "identity_ids": [sender["id"], target["id"]],
            "created_at": created_at,
            "updated_at": now,
            "last_message_id": message_id,
            "last_sequence": sequence,
        }
    )
    message = message_repo.save_im_message(
        {
            "id": message_id,
            "conversation_id": conversation_id,
            "sender_identity": sender,
            "target_identity": target,
            "content": normalized_content,
            "reply_to": reply_to_id,
            "created_at": now,
            "sequence": sequence,
        }
    )
    message_repo.save_im_message_state(
        {
            "message_id": message_id,
            "owner_identity_id": target["id"],
            "disposition": "unseen",
            "reason": None,
            "processed_by": None,
            "updated_at": now,
        }
    )
    for visible_identity in (sender, target):
        message_repo.save_im_event(
            {
                "event_id": event_id,
                "type": "message.created",
                "message_id": message_id,
                "conversation_id": conversation_id,
                "sender_identity": sender,
                "target_identity": target,
                "visible_to_identity_id": visible_identity["id"],
                "reply_to": reply_to_id,
                "created_at": now,
                "sequence": sequence,
            }
        )
    original_reply_state = None
    if reply_to_id is not None:
        original_reply_state = _mark_reply_source_replied(
            message_repo=message_repo,
            identity=sender,
            message_id=reply_to_id,
        )

    wake_status = "not_applicable"
    if target.get("type") == "actor" and isinstance(target_role_id, str) and target_role_id.strip():
        wake_payload = {
            "type": "im.message.created",
            "wake_id": _new_im_id("imwake"),
            "target_identity_id": target["id"],
            "target_role_id": target_role_id.strip(),
            "message_id": message_id,
            "conversation_id": conversation_id,
            "event_id": event_id,
            "created_at": now,
        }
        if wake_actor is None:
            wake_status = "submitted"
        else:
            try:
                wake_result = wake_actor(wake_payload)
            except Exception:
                wake_status = "wake_failed"
            else:
                candidate = wake_result.get("wake_status") if isinstance(wake_result, dict) else None
                wake_status = candidate if candidate in {"submitted", "target_not_online", "wake_failed", "not_applicable"} else "wake_failed"

    response = {
        "ok": True,
        "message": {
            "id": message["id"],
            "conversation_id": conversation["id"],
            "reply_to": message["reply_to"],
        },
        "event_id": event_id,
        "delivery_status": "accepted",
        "wake_status": wake_status,
        "next_cursor": event_id,
    }
    if reply_to_id is not None:
        response["original_message_id"] = reply_to_id
        response["original_final_disposition"] = (
            original_reply_state.get("disposition") if isinstance(original_reply_state, dict) else None
        )
    return response


def _connection_identity_ref(connection: dict[str, Any]) -> dict[str, str]:
    identity_id = connection.get("identity_id")
    return _identity_ref(identity_id, "connection.identity_id")


def _save_connection_last_event(connection: dict[str, Any], event_id: str) -> dict[str, Any]:
    from env.repos import messages as message_repo

    updated = dict(connection)
    updated["last_event_id"] = str(event_id)
    updated["last_used_at"] = message_repo.runtime_files.now_iso()
    saved = message_repo.save_im_connection(updated)
    connection.clear()
    connection.update(saved)
    return saved


def send_external_connection_message(
    *,
    connection: dict[str, Any],
    target_identity: dict[str, Any],
    target_role_id: str,
    content: str,
    reply_to: str | None = None,
    wake_actor: Any | None = None,
) -> dict[str, Any]:
    try:
        sender = _connection_identity_ref(connection)
    except ValueError as exc:
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": str(exc)}}
    normalized_target_role_id = target_role_id.strip() if isinstance(target_role_id, str) else ""
    if (
        isinstance(target_identity, dict)
        and target_identity.get("type") == "actor"
        and not normalized_target_role_id
    ):
        return _im_payload_error("target_role_id is required for actor target_identity")
    try:
        target = _identity_ref(target_identity, "target_identity")
    except ValueError as exc:
        return _im_payload_error(str(exc))
    if target["type"] == "actor" and not normalized_target_role_id:
        return _im_payload_error("target_role_id is required for actor target_identity")
    result = send_im_message(
        sender_identity=sender,
        to=target,
        target_role_id=normalized_target_role_id or None,
        content=content,
        reply_to=reply_to,
        wake_actor=wake_actor,
    )
    external_response = dict(result)
    external_response.pop("next_cursor", None)
    return external_response


def read_external_connection_events(
    *,
    connection: dict[str, Any],
    limit: int = 50,
    wait_ms: int = 0,
) -> dict[str, Any]:
    from env.repos import messages as message_repo

    try:
        identity = _connection_identity_ref(connection)
    except ValueError as exc:
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": str(exc)}}
    last_event_id = connection.get("last_event_id")
    cursor = last_event_id if isinstance(last_event_id, str) and last_event_id.strip() else message_repo.INITIAL_IM_EVENT_CURSOR
    normalized_limit = limit if isinstance(limit, int) and limit > 0 else 50
    wait_seconds = min(wait_ms if isinstance(wait_ms, int) and wait_ms > 0 else 0, 30000) / 1000
    deadline = time.monotonic() + wait_seconds
    while True:
        events = _external_consumable_events_after_cursor(
            message_repo=message_repo,
            identity=identity,
            cursor=cursor,
            limit=normalized_limit,
        )
        if events or wait_seconds <= 0 or time.monotonic() >= deadline:
            break
        time.sleep(min(0.05, max(0.001, deadline - time.monotonic())))
    return {"ok": True, "events": events}


def ack_external_connection_event(
    *,
    connection: dict[str, Any],
    event_id: str,
) -> dict[str, Any]:
    from env.repos import messages as message_repo

    try:
        identity = _connection_identity_ref(connection)
    except ValueError as exc:
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": str(exc)}}
    normalized_event_id = event_id.strip() if isinstance(event_id, str) else ""
    if not normalized_event_id:
        return _im_payload_error("event_id must be a non-empty string")

    events = message_repo.list_im_events_for_identity(identity)
    visible_index_by_id = {str(event.get("event_id") or ""): index for index, event in enumerate(events)}
    event_index = visible_index_by_id.get(normalized_event_id)
    if event_index is None:
        return _im_scope_error("event is not visible to the connection")
    event = events[event_index]
    identity_id = identity["id"]
    sender_identity = event.get("sender_identity") if isinstance(event.get("sender_identity"), dict) else {}
    if sender_identity.get("id") == identity_id:
        return _im_scope_error("event is not consumable by the connection")

    last_event_id = connection.get("last_event_id")
    cursor = last_event_id if isinstance(last_event_id, str) and last_event_id.strip() else message_repo.INITIAL_IM_EVENT_CURSOR
    cursor_index = visible_index_by_id.get(cursor)
    if cursor == normalized_event_id or (cursor_index is not None and event_index <= cursor_index):
        return {
            "ok": True,
            "event_id": normalized_event_id,
            "last_event_id": cursor,
            "state_changed": False,
        }

    next_events = _external_consumable_events_after_cursor(
        message_repo=message_repo,
        identity=identity,
        cursor=cursor,
        limit=1,
    )
    next_event_id = str(next_events[0].get("event_id") or "") if next_events else ""
    if next_event_id != normalized_event_id:
        return {
            "ok": False,
            "error": {
                "code": "E_IM_CURSOR",
                "message": "event_id is not the next unacknowledged event for the connection",
            },
        }

    saved = _save_connection_last_event(connection, normalized_event_id)
    return {
        "ok": True,
        "event_id": normalized_event_id,
        "last_event_id": saved["last_event_id"],
        "state_changed": True,
    }


def _external_consumable_events_after_cursor(
    *,
    message_repo: Any,
    identity: dict[str, Any],
    cursor: str,
    limit: int,
) -> list[dict[str, Any]]:
    identity_id = _identity_id(identity)
    events = message_repo.list_im_events_for_identity(identity)
    after_cursor = _events_after_cursor(events, cursor=cursor, initial_cursor=message_repo.INITIAL_IM_EVENT_CURSOR)
    consumable: list[dict[str, Any]] = []
    for event in after_cursor:
        sender_identity = event.get("sender_identity") if isinstance(event.get("sender_identity"), dict) else {}
        if sender_identity.get("id") == identity_id:
            continue
        consumable.append(event)
        if len(consumable) >= limit:
            break
    return consumable


def _events_after_cursor(events: list[dict[str, Any]], *, cursor: str, initial_cursor: str) -> list[dict[str, Any]]:
    if cursor == initial_cursor:
        return list(events)
    visible: list[dict[str, Any]] = []
    seen_cursor = False
    for event in events:
        if seen_cursor:
            visible.append(event)
        elif event.get("event_id") == cursor:
            seen_cursor = True
    return visible


def read_im_events(
    *,
    identity: dict[str, Any],
    cursor: str,
    limit: int = 50,
    wait_ms: int = 0,
) -> dict[str, Any]:
    from env.repos import messages as message_repo

    identity_ref = _identity_ref(identity)
    normalized_cursor = cursor.strip() if isinstance(cursor, str) and cursor.strip() else message_repo.INITIAL_IM_EVENT_CURSOR
    normalized_limit = limit if isinstance(limit, int) and limit > 0 else 50
    wait_seconds = min(wait_ms if isinstance(wait_ms, int) and wait_ms > 0 else 0, 30000) / 1000
    deadline = time.monotonic() + wait_seconds
    while True:
        events = message_repo.list_im_events_for_identity(identity_ref)
        if normalized_cursor == message_repo.INITIAL_IM_EVENT_CURSOR:
            visible = events[:normalized_limit]
        else:
            visible = []
            seen_cursor = False
            for event in events:
                if seen_cursor:
                    visible.append(event)
                    if len(visible) >= normalized_limit:
                        break
                elif event.get("event_id") == normalized_cursor:
                    seen_cursor = True
        next_cursor = normalized_cursor
        if visible:
            next_cursor = str(visible[-1]["event_id"])
            break
        if wait_seconds <= 0 or time.monotonic() >= deadline:
            break
        time.sleep(min(0.05, max(0.001, deadline - time.monotonic())))
    return {
        "ok": True,
        "events": visible,
        "next_cursor": next_cursor,
        "identity": identity_ref,
    }


def _im_scope_error(message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": "E_IM_SCOPE", "message": message}}


def _im_not_found(message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": "E_IM_NOT_FOUND", "message": message}}


def _identity_can_see_message(message_repo: Any, identity: dict[str, Any], message: dict[str, Any]) -> bool:
    conversation = message_repo.get_im_conversation(str(message.get("conversation_id") or ""))
    if conversation is None:
        return False
    identity_id = _identity_id(identity)
    if isinstance(conversation.get("identity_ids"), list):
        return identity_id in {
            message_repo.im_identity_id_for_row(row, "conversation.identity_ids[]")
            for row in conversation["identity_ids"]
        }
    return False


def get_im_message(*, identity: dict[str, Any], message_id: str) -> dict[str, Any]:
    from env.repos import messages as message_repo

    identity_ref = _identity_ref(identity)
    message = message_repo.get_im_message(message_id)
    if message is None:
        return _im_not_found(f"message not found: {message_id}")
    if not _identity_can_see_message(message_repo, identity_ref, message):
        return _im_scope_error("identity is not in the message conversation")
    return {"ok": True, "message": message}


def list_im_replies(*, identity: dict[str, Any], message_id: str) -> dict[str, Any]:
    from env.repos import messages as message_repo

    identity_ref = _identity_ref(identity)
    root_response = get_im_message(identity=identity_ref, message_id=message_id)
    if root_response.get("ok") is not True:
        return root_response
    replies = [
        row
        for row in message_repo.list_im_messages()
        if row.get("reply_to") == message_id and _identity_can_see_message(message_repo, identity_ref, row)
    ]
    return {
        "ok": True,
        "message_id": message_id,
        "replies": replies,
        "count": len(replies),
    }


def get_im_direct_conversation(
    *,
    identity: dict[str, Any],
    target: dict[str, Any],
    limit: int = 20,
) -> dict[str, Any]:
    from env.repos import messages as message_repo

    identity_ref = _identity_ref(identity)
    target_ref = _identity_ref(target)
    conversation = message_repo.find_im_direct_conversation([identity_ref, target_ref])
    if conversation is None:
        return _im_not_found("direct conversation not found")
    messages = [
        row
        for row in message_repo.list_im_messages()
        if row.get("conversation_id") == conversation.get("id")
        and _identity_can_see_message(message_repo, identity_ref, row)
    ]
    normalized_limit = limit if isinstance(limit, int) and limit > 0 else 20
    return {
        "ok": True,
        "conversation": conversation,
        "messages": messages[-normalized_limit:],
        "count": min(len(messages), normalized_limit),
    }


def update_im_disposition(
    *,
    identity: dict[str, Any],
    message_id: str,
    disposition: str,
    reason: str | None = None,
) -> dict[str, Any]:
    from env.repos import messages as message_repo

    identity_ref = _identity_ref(identity)
    message_response = get_im_message(identity=identity_ref, message_id=message_id)
    if message_response.get("ok") is not True:
        return message_response
    if disposition not in {"absorbed", "replied", "needs_parent"}:
        return {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "invalid disposition"}}
    current = message_repo.get_im_message_state(message_id, identity_ref["id"])
    if current is None:
        return _im_scope_error("identity has no state for this message")
    previous = current.get("disposition")
    updated = dict(current)
    updated["disposition"] = disposition
    updated["reason"] = reason.strip() if isinstance(reason, str) and reason.strip() else None
    updated["updated_at"] = message_repo.runtime_files.now_iso()
    message_repo.save_im_message_state(updated)
    return {
        "ok": True,
        "message_id": message_id,
        "identity": identity_ref,
        "disposition": disposition,
        "state_changed": previous != disposition or current.get("reason") != updated["reason"],
    }
