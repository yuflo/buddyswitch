"""Communication-owned Message semantics."""

from __future__ import annotations

import hashlib
import secrets
import time
import uuid
from collections.abc import Callable
from typing import Any

from buddyswitch.env.domain.identity import ACTOR_ID_PATTERN, IdentityRef, ROLE_ID_PATTERN
from buddyswitch.env.domain.identity import actor_identity
from buddyswitch.env.domain.identity import external_identity


def _im_payload_error(message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": message}}


_BLOCKED_ACTOR_CONTACT_STATUSES = {"offline", "registered_offline", "inactive", "unreachable", "target_not_online"}
ActorDeliveryHandler = Callable[[dict[str, Any]], dict[str, Any]]
ActorReachabilityChecker = Callable[..., dict[str, Any]]


def _im_target_error(message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": "E_IM_TARGET", "message": message}}


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


def _actor_profile_exists(identity_id: str) -> bool:
    from buddyswitch.env.repos import identities as identity_repo

    return isinstance(identity_repo.get_actor_identity_profile(identity_id), dict)


def _external_profile_exists(identity_id: str) -> bool:
    from buddyswitch.env.repos import identities as identity_repo

    return isinstance(identity_repo.get_external_profile(identity_id), dict)


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


def resolve_im_send_target(
    *,
    sender_identity: dict[str, Any],
    target_identity_id: Any,
    actor_reachability_checker: ActorReachabilityChecker | None = None,
) -> dict[str, Any]:
    try:
        sender = _identity_ref(sender_identity, "sender_identity")
    except ValueError as exc:
        return _im_payload_error(str(exc))
    identity_id = target_identity_id.strip() if isinstance(target_identity_id, str) and target_identity_id.strip() else ""
    if not identity_id:
        return _im_payload_error("target_identity_id is required")
    if identity_id == sender["id"]:
        return _im_payload_error("target_identity_id must not be the sender identity")
    try:
        target = _identity_ref(identity_id, "target_identity_id")
    except ValueError as exc:
        return _im_payload_error(str(exc))
    if target["type"] == "external":
        if not _external_profile_exists(target["id"]):
            return _im_target_error(f"external identity profile not found: {target['id']}")
        return {"ok": True, "target_identity": target}
    if target["type"] == "actor":
        if not _actor_profile_exists(target["id"]):
            return _im_target_error(f"actor identity profile not found: {target['id']}")
        if actor_reachability_checker is None:
            return _im_target_error("actor reachability checker is required for actor targets")
        try:
            reachability = actor_reachability_checker(target_identity_id=target["id"])
        except Exception as exc:
            return _im_target_error(str(exc))
        if not isinstance(reachability, dict):
            return _im_target_error("actor reachability response must be an object")
        if reachability.get("reachability_status") != "online":
            status = reachability.get("reachability_status")
            return _im_target_error(f"actor target is not online: {status}")
        return {"ok": True, "target_identity": target}
    return _im_payload_error("target_identity_id must be actor or external identity")


def identity_target_for_direct_conversation(target_identity_id: Any, *, field: str = "target_identity_id") -> dict[str, Any]:
    identity_id = target_identity_id.strip() if isinstance(target_identity_id, str) and target_identity_id.strip() else ""
    if not identity_id:
        return _im_payload_error(f"{field} is required")
    try:
        target = _identity_ref(identity_id, "target_identity_id")
    except ValueError as exc:
        return _im_payload_error(str(exc))
    if target["type"] == "actor" and not _actor_profile_exists(target["id"]):
        return _im_target_error(f"actor identity profile not found: {target['id']}")
    if target["type"] == "external" and not _external_profile_exists(target["id"]):
        return _im_target_error(f"external identity profile not found: {target['id']}")
    return {"ok": True, "identity": target}


def create_external_session(*, display_name: str) -> dict[str, Any]:
    from buddyswitch.env.repos import identities as identity_repo
    from buddyswitch.modules.communication.private.state import messages as message_repo

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
    external_session_key = f"imsk-{secrets.token_hex(24)}"
    external_session_key_hash = _external_session_key_hash(external_session_key)
    message_repo.save_external_session(
        {
            "external_session_key_hash": external_session_key_hash,
            "identity_id": external_identity_id,
            "display_name": normalized_display_name,
            "last_event_id": message_repo.INITIAL_IM_EVENT_CURSOR,
            "created_at": now,
            "last_used_at": now,
        }
    )
    return {
        "ok": True,
        "external_session_key": external_session_key,
        "identity": {"id": external_identity_id, "type": "external"},
    }


def _external_session_key_hash(external_session_key: str) -> str:
    return "sha256:" + hashlib.sha256(external_session_key.encode("utf-8")).hexdigest()


def authenticate_external_session_key(external_session_key: str) -> dict[str, Any]:
    from buddyswitch.modules.communication.private.state import messages as message_repo

    if not isinstance(external_session_key, str) or not external_session_key.strip():
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": "external_session_key is required"}}
    external_session = message_repo.get_external_session_by_key_hash(
        _external_session_key_hash(external_session_key.strip())
    )
    if external_session is None:
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": "external_session_key is invalid"}}
    try:
        identity = _identity_ref(external_session.get("identity_id"), "external_session.identity_id")
    except ValueError as exc:
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": str(exc)}}
    updated = dict(external_session)
    updated["identity_id"] = identity["id"]
    updated["last_used_at"] = message_repo.runtime_files.now_iso()
    saved = message_repo.save_external_session(updated)
    return {
        "ok": True,
        "identity": identity,
        "external_session": saved,
    }


def _new_im_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _im_reply_target_error(message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": "E_IM_REPLY_TARGET", "message": message}}


def _resolve_reply_target_identity_id(
    *,
    message_repo: Any,
    sender: dict[str, str],
    reply_to_id: str,
) -> dict[str, Any]:
    original_message = message_repo.get_im_message(reply_to_id)
    if original_message is None:
        return _im_reply_target_error("reply_to message not found")
    try:
        original_sender = _identity_ref(original_message.get("sender_identity"), "reply_to.sender_identity")
        original_target = _identity_ref(original_message.get("target_identity"), "reply_to.target_identity")
    except ValueError as exc:
        return _im_reply_target_error(str(exc))
    if original_target["id"] != sender["id"]:
        return _im_reply_target_error("reply_to message is not addressed to the sender identity")
    original_id = original_message.get("id")
    if not isinstance(original_id, str) or not original_id.strip():
        return _im_reply_target_error("reply_to message id is invalid")
    return {
        "ok": True,
        "target_identity_id": original_sender["id"],
        "reply_to": original_id.strip(),
    }


def send_im_message(
    *,
    sender_identity: dict[str, Any],
    target_identity: dict[str, Any],
    content: str,
    reply_to: str | None = None,
) -> dict[str, Any]:
    from buddyswitch.modules.communication.private.state import messages as message_repo

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
        target = _identity_ref(target_identity, "target_identity")
    except ValueError as exc:
        return _im_payload_error(str(exc))
    if target["id"] == sender["id"]:
        return _im_payload_error("target_identity must not be the sender identity")

    now = message_repo.runtime_files.now_iso()
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

    response = {
        "ok": True,
        "message": {
            "id": message["id"],
            "conversation_id": conversation["id"],
            "reply_to": message["reply_to"],
        },
        "target_identity": dict(target),
        "event_id": event_id,
        "delivery_status": "accepted",
        "next_cursor": event_id,
    }
    return response


def send_im_reply(
    *,
    sender_identity: dict[str, Any],
    reply_to: str,
    content: str,
    actor_reachability_checker: ActorReachabilityChecker | None = None,
) -> dict[str, Any]:
    from buddyswitch.modules.communication.private.state import messages as message_repo

    try:
        sender = _identity_ref(sender_identity, "sender_identity")
    except ValueError as exc:
        return _im_payload_error(str(exc))
    reply_to_id = reply_to.strip() if isinstance(reply_to, str) and reply_to.strip() else ""
    if not reply_to_id:
        return _im_payload_error("reply_to must be a non-empty string")
    reply_target = _resolve_reply_target_identity_id(
        message_repo=message_repo,
        sender=sender,
        reply_to_id=reply_to_id,
    )
    if reply_target.get("ok") is not True:
        return reply_target
    target_response = resolve_im_send_target(
        sender_identity=sender,
        target_identity_id=reply_target["target_identity_id"],
        actor_reachability_checker=actor_reachability_checker,
    )
    if target_response.get("ok") is not True:
        return target_response
    result = send_im_message(
        sender_identity=sender,
        target_identity=target_response["target_identity"],
        content=content,
        reply_to=reply_target["reply_to"],
    )
    if result.get("ok") is not True:
        return result
    response = dict(result)
    response["original_message_id"] = reply_target["reply_to"]
    return response


def attach_post_write_delivery_status(
    result: dict[str, Any],
    *,
    target_identity: dict[str, Any] | None = None,
    actor_delivery_handler: ActorDeliveryHandler | None = None,
) -> dict[str, Any]:
    if result.get("ok") is not True:
        return result
    target = _delivery_target(result, target_identity)
    if target is None or target.get("type") != "actor":
        result["actor_handling_status"] = "not_applicable"
        return result
    if actor_delivery_handler is None:
        result["actor_handling_status"] = "handling_failed"
        return result
    try:
        payload = _actor_message_created_payload(result, target)
    except ValueError:
        result["actor_handling_status"] = "handling_failed"
        return result
    handling = actor_delivery_handler(payload)
    if isinstance(handling, dict) and isinstance(handling.get("actor_handling_status"), str):
        result["actor_handling_status"] = handling["actor_handling_status"]
    else:
        result["actor_handling_status"] = "handling_failed"
    return result


def _delivery_target(
    result: dict[str, Any],
    explicit_target: dict[str, Any] | None,
) -> dict[str, str] | None:
    for candidate in (explicit_target, result.get("target_identity")):
        if isinstance(candidate, dict):
            try:
                return IdentityRef.from_payload(candidate).to_payload()
            except ValueError:
                continue
    return None


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _actor_message_created_payload(result: dict[str, Any], target: dict[str, str]) -> dict[str, Any]:
    message = result.get("message")
    if not isinstance(message, dict):
        raise ValueError("post-write IM delivery requires message refs")
    return {
        "type": "im.message.created",
        "target_identity_id": target["id"],
        "message_id": _required_text(message.get("id"), "message.id"),
        "conversation_id": _required_text(message.get("conversation_id"), "message.conversation_id"),
        "event_id": _required_text(result.get("event_id"), "event_id"),
    }


def _external_session_identity_ref(external_session: dict[str, Any]) -> dict[str, str]:
    identity_id = external_session.get("identity_id")
    return _identity_ref(identity_id, "external_session.identity_id")


def _save_external_session_last_event(external_session: dict[str, Any], event_id: str) -> dict[str, Any]:
    from buddyswitch.modules.communication.private.state import messages as message_repo

    updated = dict(external_session)
    updated["last_event_id"] = str(event_id)
    updated["last_used_at"] = message_repo.runtime_files.now_iso()
    saved = message_repo.save_external_session(updated)
    external_session.clear()
    external_session.update(saved)
    return saved


def send_external_session_message(
    *,
    external_session: dict[str, Any],
    target_identity: dict[str, Any],
    content: str,
) -> dict[str, Any]:
    try:
        sender = _external_session_identity_ref(external_session)
    except ValueError as exc:
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": str(exc)}}
    try:
        target = _identity_ref(target_identity, "target_identity")
    except ValueError as exc:
        return _im_payload_error(str(exc))
    result = send_im_message(
        sender_identity=sender,
        target_identity=target,
        content=content,
    )
    external_response = dict(result)
    external_response.pop("next_cursor", None)
    return external_response


def send_external_session_reply(
    *,
    external_session: dict[str, Any],
    reply_to: str,
    content: str,
    actor_reachability_checker: ActorReachabilityChecker | None = None,
) -> dict[str, Any]:
    try:
        sender = _external_session_identity_ref(external_session)
    except ValueError as exc:
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": str(exc)}}
    result = send_im_reply(
        sender_identity=sender,
        reply_to=reply_to,
        content=content,
        actor_reachability_checker=actor_reachability_checker,
    )
    external_response = dict(result)
    external_response.pop("next_cursor", None)
    return external_response


def read_external_session_events(
    *,
    external_session: dict[str, Any],
    limit: int = 50,
    wait_ms: int = 0,
) -> dict[str, Any]:
    from buddyswitch.modules.communication.private.state import messages as message_repo

    try:
        identity = _external_session_identity_ref(external_session)
    except ValueError as exc:
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": str(exc)}}
    last_event_id = external_session.get("last_event_id")
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


def ack_external_session_event(
    *,
    external_session: dict[str, Any],
    event_id: str,
) -> dict[str, Any]:
    from buddyswitch.modules.communication.private.state import messages as message_repo

    try:
        identity = _external_session_identity_ref(external_session)
    except ValueError as exc:
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": str(exc)}}
    normalized_event_id = event_id.strip() if isinstance(event_id, str) else ""
    if not normalized_event_id:
        return _im_payload_error("event_id must be a non-empty string")

    events = message_repo.list_im_events_for_identity(identity)
    visible_index_by_id = {str(event.get("event_id") or ""): index for index, event in enumerate(events)}
    event_index = visible_index_by_id.get(normalized_event_id)
    if event_index is None:
        return _im_scope_error("event is not visible to the external session")
    event = events[event_index]
    identity_id = identity["id"]
    sender_identity = event.get("sender_identity") if isinstance(event.get("sender_identity"), dict) else {}
    if sender_identity.get("id") == identity_id:
        return _im_scope_error("event is not consumable by the external session")

    last_event_id = external_session.get("last_event_id")
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
                "message": "event_id is not the next unacknowledged event for the external session",
            },
        }

    saved = _save_external_session_last_event(external_session, normalized_event_id)
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
    from buddyswitch.modules.communication.private.state import messages as message_repo

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
    from buddyswitch.modules.communication.private.state import messages as message_repo

    identity_ref = _identity_ref(identity)
    message = message_repo.get_im_message(message_id)
    if message is None:
        return _im_not_found(f"message not found: {message_id}")
    if not _identity_can_see_message(message_repo, identity_ref, message):
        return _im_scope_error("identity is not in the message conversation")
    return {"ok": True, "message": message}


def get_im_event(*, identity: dict[str, Any], event_id: str) -> dict[str, Any]:
    from buddyswitch.modules.communication.private.state import messages as message_repo

    identity_ref = _identity_ref(identity)
    event = message_repo.get_im_event(event_id, identity_ref)
    if event is None:
        return _im_not_found(f"event not found: {event_id}")
    return {"ok": True, "event": event}


def list_im_replies(*, identity: dict[str, Any], message_id: str) -> dict[str, Any]:
    from buddyswitch.modules.communication.private.state import messages as message_repo

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
    from buddyswitch.modules.communication.private.state import messages as message_repo

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
