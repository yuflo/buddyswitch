#!/usr/bin/env python3
"""Message domain rules for payload/scope validation and inbox filtering."""

from __future__ import annotations

from typing import Any, Callable, Optional, TypedDict

from env.tool_runtime.actor_profile import ActorAddress


class MessagePayloadError(ValueError):
    def __init__(self, message: str, *, correctable_fields: list[str] | None = None) -> None:
        super().__init__(message)
        self.correctable_fields = correctable_fields


class MessageScopeError(ValueError):
    def __init__(
        self,
        *,
        message: str,
        permission_boundary: str,
        human_summary: str,
        why_blocked: str,
        retryable: bool = True,
        correctable_fields: list[str] | None = None,
        code: str = "E_MESSAGE_SCOPE",
    ) -> None:
        super().__init__(message)
        self.permission_boundary = permission_boundary
        self.human_summary = human_summary
        self.why_blocked = why_blocked
        self.retryable = retryable
        self.correctable_fields = correctable_fields
        self.code = code


class ContactsRequest(TypedDict):
    role: str | None


class SendRequest(TypedDict):
    target_actor_address: ActorAddress
    content: str
    reply_to: str | None


class ListRequest(TypedDict):
    role: str | None
    q: str | None
    limit: int


class ConversationRequest(TypedDict):
    target_actor_address: ActorAddress | None
    role: str | None
    q: str | None
    limit: int


GetMessage = Callable[[str], Optional[dict[str, Any]]]


def manifest_role_ids(manifest: dict[str, Any] | None) -> set[str]:
    if not isinstance(manifest, dict):
        return set()
    roles = manifest.get("roles")
    if not isinstance(roles, list):
        return set()
    return {
        role.get("id")
        for role in roles
        if isinstance(role, dict) and isinstance(role.get("id"), str) and role.get("id")
    }


def ensure_active_role_is_manifest_declared(*, active_role: str, manifest_role_ids: set[str]) -> None:
    if active_role in manifest_role_ids:
        return
    raise MessageScopeError(
        message=f"active role '{active_role}' is not declared in manifest",
        permission_boundary="message.manifest_role",
        human_summary="Active role is not part of the manifest-declared message scope.",
        why_blocked="message actions require active_role to be declared in manifest.roles.",
        retryable=False,
        correctable_fields=None,
    )


def _address_payload(value: ActorAddress | dict[str, Any], field: str) -> dict[str, str]:
    try:
        if isinstance(value, ActorAddress):
            return value.to_payload()
        return ActorAddress.from_payload(value).to_payload()
    except Exception as exc:
        raise MessagePayloadError(
            f"{field} must be a valid ActorAddress: {exc}",
            correctable_fields=[field],
        ) from exc


def _message_actor(message: dict[str, Any], field: str) -> ActorAddress:
    try:
        return ActorAddress.from_payload(message.get(field))
    except Exception as exc:
        raise MessageScopeError(
            message=f"message '{message.get('id')}' has invalid {field}: {exc}",
            permission_boundary="message.actor_address",
            human_summary="Referenced message has invalid actor-address data.",
            why_blocked="message reply scope can only be checked for actor-address message rows.",
            retryable=False,
            correctable_fields=None,
            code="E_MESSAGE_DATA",
        ) from exc


def _message_visible_to_actor(message: dict[str, Any], actor_address: ActorAddress) -> bool:
    return _message_actor(message, "from_actor_address") == actor_address or _message_actor(message, "to_actor_address") == actor_address


def _same_actor_pair(message: dict[str, Any], source_actor: ActorAddress, target_actor: ActorAddress) -> bool:
    participants = {
        (_message_actor(message, "from_actor_address").role_id, _message_actor(message, "from_actor_address").actor_id),
        (_message_actor(message, "to_actor_address").role_id, _message_actor(message, "to_actor_address").actor_id),
    }
    expected = {
        (source_actor.role_id, source_actor.actor_id),
        (target_actor.role_id, target_actor.actor_id),
    }
    return participants == expected


def _reject_unknown_fields(args: dict[str, Any], allowed_fields: set[str]) -> None:
    unknown = sorted(key for key in args if key not in allowed_fields)
    if unknown:
        raise MessagePayloadError(
            f"unsupported payload fields: {', '.join(unknown)}",
            correctable_fields=unknown,
        )


def prepare_contacts_request(
    *,
    args: dict[str, Any],
    manifest_role_ids: set[str],
    allowed_fields: set[str],
) -> ContactsRequest:
    _reject_unknown_fields(args, allowed_fields)
    role_filter = args.get("role")
    normalized_role: str | None = None
    if role_filter is not None:
        if not isinstance(role_filter, str):
            raise MessagePayloadError("role must be a non-empty string when provided", correctable_fields=["role"])
        candidate = role_filter.strip()
        if candidate:
            if candidate not in manifest_role_ids:
                raise MessagePayloadError(f"unknown role filter: {candidate}", correctable_fields=["role"])
            normalized_role = candidate
    return {"role": normalized_role}


def prepare_send_request(
    *,
    args: dict[str, Any],
    source_actor_address: ActorAddress,
    manifest_role_ids: set[str],
    get_message: GetMessage,
    allowed_fields: set[str],
) -> SendRequest:
    _reject_unknown_fields(args, allowed_fields)

    target_raw = args.get("target_actor_address")
    try:
        target_actor = ActorAddress.from_payload(target_raw)
    except Exception as exc:
        raise MessagePayloadError(
            f"target_actor_address must be a valid ActorAddress: {exc}",
            correctable_fields=["target_actor_address"],
        ) from exc

    if target_actor.role_id not in manifest_role_ids:
        raise MessagePayloadError(
            f"unknown target actor role: {target_actor.role_id}",
            correctable_fields=["target_actor_address"],
        )
    if target_actor.actor_id == source_actor_address.actor_id:
        raise MessageScopeError(
            message="cannot send a message to the same actor",
            permission_boundary="message.self_send",
            human_summary="Self-send messages are not allowed.",
            why_blocked="message.send requires target_actor_address.actor_id to differ from the active actor.",
            retryable=True,
            correctable_fields=["target_actor_address"],
        )

    content = args.get("content")
    if not isinstance(content, str) or not content.strip():
        raise MessagePayloadError(
            "content must be a non-empty string after trimming",
            correctable_fields=["content"],
        )
    content = content.strip()

    reply_to = args.get("reply_to")
    reply_to_id: str | None = None
    if reply_to is not None:
        if not isinstance(reply_to, str) or not reply_to.strip():
            raise MessagePayloadError(
                "reply_to must be a non-empty string when provided",
                correctable_fields=["reply_to"],
            )
        reply_to_id = reply_to.strip()
        referenced = get_message(reply_to_id)
        if referenced is None:
            raise MessageScopeError(
                message=f"reply_to references a message that does not exist: {reply_to_id}",
                permission_boundary="message.reply_to_scope",
                human_summary="The referenced message was not found.",
                why_blocked="reply_to must reference an existing message.",
                retryable=True,
                correctable_fields=["reply_to"],
            )
        if not _message_visible_to_actor(referenced, source_actor_address):
            raise MessageScopeError(
                message=f"reply_to message '{reply_to_id}' is not visible to active actor",
                permission_boundary="message.reply_to_scope",
                human_summary="Active actor is not a participant in the referenced conversation.",
                why_blocked="Active actor must be a participant in the referenced message conversation.",
                retryable=True,
                correctable_fields=["reply_to"],
            )
        if not _same_actor_pair(referenced, source_actor_address, target_actor):
            raise MessageScopeError(
                message=f"reply_to message '{reply_to_id}' is from a different actor conversation pair",
                permission_boundary="message.reply_to_scope",
                human_summary="Reply must stay in the same two-actor conversation.",
                why_blocked="reply_to must reference a message in the same actor-address conversation.",
                retryable=True,
                correctable_fields=["reply_to", "target_actor_address"],
            )

    return {
        "target_actor_address": target_actor,
        "content": content,
        "reply_to": reply_to_id,
    }


def prepare_list_request(*, args: dict[str, Any], manifest_role_ids: set[str], allowed_fields: set[str]) -> ListRequest:
    _reject_unknown_fields(args, allowed_fields)

    role_filter = args.get("role")
    normalized_role: str | None = None
    if role_filter is not None:
        if not isinstance(role_filter, str):
            raise MessagePayloadError("role must be a non-empty string when provided", correctable_fields=["role"])
        candidate = role_filter.strip()
        if candidate:
            if candidate not in manifest_role_ids:
                raise MessagePayloadError(f"unknown role filter: {candidate}", correctable_fields=["role"])
            normalized_role = candidate

    q_raw = args.get("q")
    q: str | None = None
    if q_raw is not None:
        if not isinstance(q_raw, str):
            raise MessagePayloadError("q must be a string", correctable_fields=["q"])
        q = q_raw.strip().lower() or None

    limit_raw = args.get("limit", 20)
    if not isinstance(limit_raw, int) or limit_raw <= 0:
        raise MessagePayloadError("limit must be a positive integer", correctable_fields=["limit"])

    return {"role": normalized_role, "q": q, "limit": limit_raw}


def prepare_conversation_request(
    *,
    args: dict[str, Any],
    source_actor_address: ActorAddress,
    manifest_role_ids: set[str],
    allowed_fields: set[str],
) -> ConversationRequest:
    _reject_unknown_fields(args, allowed_fields)

    has_target_actor = "target_actor_address" in args and args.get("target_actor_address") is not None
    has_role = "role" in args and args.get("role") is not None
    if has_target_actor == has_role:
        raise MessagePayloadError(
            "exactly one of target_actor_address or role is required",
            correctable_fields=["target_actor_address", "role"],
        )

    target_actor: ActorAddress | None = None
    role: str | None = None
    if has_target_actor:
        try:
            target_actor = ActorAddress.from_payload(args.get("target_actor_address"))
        except Exception as exc:
            raise MessagePayloadError(
                f"target_actor_address must be a valid ActorAddress: {exc}",
                correctable_fields=["target_actor_address"],
            ) from exc
        if target_actor.role_id not in manifest_role_ids:
            raise MessagePayloadError(
                f"unknown target actor role: {target_actor.role_id}",
                correctable_fields=["target_actor_address"],
            )
        if target_actor.actor_id == source_actor_address.actor_id:
            raise MessageScopeError(
                message="cannot read a message conversation with the same actor",
                permission_boundary="message.self_conversation",
                human_summary="Self-conversation is not supported.",
                why_blocked="message.conversation requires the selected target actor to differ from the active actor.",
                retryable=True,
                correctable_fields=["target_actor_address"],
            )
    else:
        role_raw = args.get("role")
        if not isinstance(role_raw, str) or not role_raw.strip():
            raise MessagePayloadError("role must be a non-empty string when provided", correctable_fields=["role"])
        role = role_raw.strip()
        if role not in manifest_role_ids:
            raise MessagePayloadError(f"unknown role selector: {role}", correctable_fields=["role"])

    q_raw = args.get("q")
    q: str | None = None
    if q_raw is not None:
        if not isinstance(q_raw, str):
            raise MessagePayloadError("q must be a string", correctable_fields=["q"])
        q = q_raw.strip().lower() or None

    limit_raw = args.get("limit", 20)
    if not isinstance(limit_raw, int) or limit_raw <= 0:
        raise MessagePayloadError("limit must be a positive integer", correctable_fields=["limit"])

    return {
        "target_actor_address": target_actor,
        "role": role,
        "q": q,
        "limit": limit_raw,
    }


def filter_inbox_messages(
    *,
    messages: list[dict[str, Any]],
    active_actor_address: ActorAddress,
    sender_role: str | None = None,
    q: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    inbox = [
        message
        for message in messages
        if _message_actor(message, "to_actor_address") == active_actor_address
    ]
    if sender_role is not None:
        inbox = [
            message
            for message in inbox
            if _message_actor(message, "from_actor_address").role_id == sender_role
        ]
    if q:
        inbox = [message for message in inbox if q in str(message.get("content") or "").lower()]
    inbox.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")), reverse=True)
    return inbox[:limit]


def filter_conversation_messages(
    *,
    messages: list[dict[str, Any]],
    active_actor_address: ActorAddress,
    target_actor_address: ActorAddress | None = None,
    target_role: str | None = None,
    q: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    conversation: list[dict[str, Any]] = []
    for message in messages:
        from_actor = _message_actor(message, "from_actor_address")
        to_actor = _message_actor(message, "to_actor_address")
        if from_actor == active_actor_address:
            other_actor = to_actor
        elif to_actor == active_actor_address:
            other_actor = from_actor
        else:
            continue
        if target_actor_address is not None and other_actor != target_actor_address:
            continue
        if target_role is not None and other_actor.role_id != target_role:
            continue
        if q and q not in str(message.get("content") or "").lower():
            continue
        conversation.append(message)

    conversation.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")), reverse=True)
    limited = conversation[:limit]
    limited.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")))
    return limited


def normalize_contact_rows(
    rows: list[dict[str, Any]],
    *,
    active_actor_address: ActorAddress,
) -> list[dict[str, Any]]:
    contacts: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            actor_address = ActorAddress.from_payload(row.get("actor_address")).to_payload()
        except Exception:
            continue
        status = row.get("status")
        contact_status = status if isinstance(status, str) and status else "online"
        why_not_sendable: str | None = None
        sendable = contact_status == "online"
        if actor_address["actor_id"] == active_actor_address.actor_id:
            sendable = False
            why_not_sendable = "message.send rejects the active actor itself as a target"
        elif contact_status != "online":
            why_not_sendable = f"contact_status is {contact_status}"
        contact = {
            "role_id": actor_address["role_id"],
            "actor_address": actor_address,
            "contact_status": contact_status,
            "sendable": sendable,
            "last_seen_at": row.get("last_seen_at") if isinstance(row.get("last_seen_at"), str) else None,
        }
        if why_not_sendable is not None:
            contact["why_not_sendable"] = why_not_sendable
        contacts.append(contact)
    return contacts
