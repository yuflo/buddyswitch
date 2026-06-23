#!/usr/bin/env python3
"""Message domain rules for payload/scope validation and inbox filtering."""

from __future__ import annotations

import json
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
    reply_to_message: dict[str, Any] | None


class GetRequest(TypedDict):
    message_id: str


class MarkRequest(TypedDict):
    message_id: str
    disposition: str
    reason: str | None


class ListRequest(TypedDict):
    role: str | None
    q: str | None
    limit: int


class ConversationRequest(TypedDict):
    target_actor_address: ActorAddress
    q: str | None
    limit: int


GetMessage = Callable[[str], Optional[dict[str, Any]]]
PROCESSABLE_DISPOSITIONS = {"unseen", "needs_parent"}
VALID_DISPOSITIONS = {"unseen", "absorbed", "replied", "needs_parent"}
VALID_TRANSITIONS = {
    ("unseen", "absorbed"),
    ("unseen", "replied"),
    ("unseen", "needs_parent"),
    ("needs_parent", "absorbed"),
    ("needs_parent", "replied"),
}
EXTERNAL_MESSAGE_ROLE_IDS = {"user"}


def message_participant_role_ids(manifest_role_ids: set[str]) -> set[str]:
    return set(manifest_role_ids) | EXTERNAL_MESSAGE_ROLE_IDS


def _format_actor_address(actor_address: ActorAddress | dict[str, Any]) -> str:
    payload = actor_address.to_payload() if isinstance(actor_address, ActorAddress) else ActorAddress.from_payload(actor_address).to_payload()
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _message_header(
    title: str,
    message_id: str,
    source_actor_address: ActorAddress | dict[str, Any],
    target_actor_address: ActorAddress | dict[str, Any],
) -> str:
    return (
        f"[{title}]\n\n"
        f"Message id: {message_id}\n"
        f"From: {_format_actor_address(source_actor_address)}\n"
        f"To: {_format_actor_address(target_actor_address)}"
    )


def _message_side_work_demand_tips() -> str:
    return "Side triage should not silently convert parent-level work into a lightweight acknowledgement."


def _message_runtime_context(*, side: bool = False, parent_required: bool = False) -> str:
    if parent_required:
        return (
            "Runtime context:\n"
            "This message already crossed the side-triage threshold.\n"
            "It may require active-work adjustment, a decision, durable task capture, or substantive follow-through before reply."
        )
    if side:
        return (
            "Runtime context:\n"
            "A direct message may be simple communication, status sync, clarification, or a concrete work demand.\n"
            f"{_message_side_work_demand_tips()}"
        )
    return (
        "Runtime context:\n"
        "A direct message may be simple communication, status sync, clarification, or a concrete work demand for this actor.\n"
        "After reading the message, decide what kind of attention it needs."
    )


def _message_parent_work_demand_tips(*, parent_required: bool = False) -> str:
    if parent_required:
        return (
            "Work-demand guidance:\n"
            "If the message assigns concrete work to this actor, acknowledgement alone is usually not completion.\n"
            "Consider task.current and task.capture/task.select when the work should become durable actor work.\n"
            "If the requested work is small enough to complete now, do the smallest substantive work and send the result.\n"
            "If only coordination is needed, reply normally."
        )
    return (
        "Work-demand guidance:\n"
        "If the message assigns concrete work to this actor, acknowledgement alone is usually not completion.\n"
        "For durable actor work, consider task.current and task.capture/task.select before finishing.\n"
        "If the requested work is small enough to complete now, do the smallest substantive work and send the result instead of only saying you will do it.\n"
        "If the message is only FYI, status sync, or lightweight clarification, reply or mark absorbed normally."
    )


def _message_parent_steps(message_id: str) -> str:
    return (
        "Steps:\n"
        f"1. Call message__get with message_id=\"{message_id}\".\n"
        "2. Read the message content and sender.\n"
        "3. If prior context is needed, call message__conversation with the sender actor address.\n"
        "4. If the message contains concrete work that should be tracked, consider task.current and task.capture/task.select.\n"
        "5. If a reply is needed, call message__send with:\n"
        "   - target_actor_address = the sender actor address from the message\n"
        "   - content = your reply\n"
        f"   - reply_to = \"{message_id}\"\n"
        "6. If no reply is needed, call message__mark with:\n"
        f"   - message_id = \"{message_id}\"\n"
        "   - disposition = \"absorbed\""
    )


def _message_side_triage_steps(message_id: str) -> str:
    return (
        "Steps:\n"
        f"1. Call message__get with message_id=\"{message_id}\".\n"
        "2. Read the message content and sender.\n"
        "3. If prior context is needed, call message__conversation with the sender actor address.\n"
        "4. Decide one outcome.\n\n"
        "Outcome A: You can handle it independently.\n"
        "Use this for FYI, status checks, simple clarification, or messages that can be answered from visible runtime state.\n"
        "- If a reply is needed, call message__send with:\n"
        "  - target_actor_address = the sender actor address from the message\n"
        "  - content = your reply\n"
        f"  - reply_to = \"{message_id}\"\n"
        "- If no reply is needed, call message__mark with:\n"
        f"  - message_id = \"{message_id}\"\n"
        "  - disposition = \"absorbed\"\n\n"
        "Outcome B: Parent must process it.\n"
        "Use needs_parent when the message requires parent-thread action on active work.\n"
        "Mark needs_parent only if at least one condition is true:\n"
        "1. The message changes active work: start, stop, pause, resume, reprioritize, redirect, narrow, expand, or replace current task/scope/next action.\n"
        "2. The message blocks or unblocks active work: blocker, failure, missing dependency, deadline, external decision, or new constraint.\n"
        "3. The message requires a parent decision or commitment.\n"
        "4. The message is an instruction from a coordinating actor that should become active parent-thread input.\n"
        "5. The message assigns concrete work to this actor that should not be completed as a side-triage acknowledgement.\n\n"
        "If marking needs_parent, the reason must cite the specific condition.\n"
        "Call message__mark with:\n"
        f"- message_id = \"{message_id}\"\n"
        "- disposition = \"needs_parent\"\n"
        "- reason = a concise explanation\n\n"
        "Use only the message tools named in this prompt."
    )


def _message_finish(*, side: bool = False) -> str:
    if side:
        return "Finish:\nFinish after exactly one disposition path succeeds."
    return 'Finish:\nFinish after the message is marked "absorbed" or "replied".'


def render_parent_message_prompt(
    message_id: str,
    source_actor_address: ActorAddress | dict[str, Any],
    target_actor_address: ActorAddress | dict[str, Any],
) -> str:
    return "\n\n".join(
        (
            _message_header("MESSAGE AVAILABLE", message_id, source_actor_address, target_actor_address),
            "A direct message is available for this actor.",
            "Required action:\nProcess this exact message. Do not assume a reply is required.",
            _message_runtime_context(),
            _message_parent_work_demand_tips(),
            _message_parent_steps(message_id),
            _message_finish(),
        )
    )


def render_side_triage_prompt(
    message_id: str,
    source_actor_address: ActorAddress | dict[str, Any],
    target_actor_address: ActorAddress | dict[str, Any],
) -> str:
    return "\n\n".join(
        (
            _message_header("MESSAGE TRIAGE", message_id, source_actor_address, target_actor_address),
            "A direct message arrived while the parent thread is running.",
            "Required action:\nProcess this exact message without interrupting the parent unless parent involvement is necessary.",
            _message_runtime_context(side=True),
            _message_side_triage_steps(message_id),
            _message_finish(side=True),
        )
    )


def render_parent_required_prompt(
    message_id: str,
    source_actor_address: ActorAddress | dict[str, Any],
    target_actor_address: ActorAddress | dict[str, Any],
    reason: str,
) -> str:
    return "\n\n".join(
        (
            _message_header("MESSAGE NEEDS PARENT", message_id, source_actor_address, target_actor_address),
            f"Reason from side triage:\n{reason}",
            "A side thread reviewed this message and determined that parent processing is required.",
            "Required action:\nProcess this exact message. Do not assume a reply is required.",
            _message_runtime_context(parent_required=True),
            _message_parent_work_demand_tips(parent_required=True),
            _message_parent_steps(message_id),
            _message_finish(),
        )
    )


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


def _message_inbound_to_actor(message: dict[str, Any], actor_address: ActorAddress) -> bool:
    return _message_actor(message, "to_actor_address") == actor_address


def _message_disposition(message: dict[str, Any]) -> str:
    disposition = message.get("disposition", "unseen")
    if not isinstance(disposition, str) or disposition not in VALID_DISPOSITIONS:
        raise MessageScopeError(
            message=f"message '{message.get('id')}' has invalid disposition",
            permission_boundary="message.disposition",
            human_summary="Referenced message has invalid disposition metadata.",
            why_blocked="Message processing requires a durable disposition.",
            retryable=False,
            correctable_fields=None,
            code="E_MESSAGE_DATA",
        )
    return disposition


def ensure_processable_inbound_message(
    *,
    message_id: str,
    message: dict[str, Any] | None,
    active_actor_address: ActorAddress,
) -> dict[str, Any]:
    if message is None:
        raise MessageScopeError(
            message=f"message not found: {message_id}",
            permission_boundary="message.processable",
            human_summary="The requested message was not found.",
            why_blocked="Exact message processing requires an existing message id.",
            retryable=True,
            correctable_fields=["message_id"],
            code="E_MESSAGE_NOT_FOUND",
        )
    if not _message_inbound_to_actor(message, active_actor_address):
        raise MessageScopeError(
            message=f"message '{message_id}' is not addressed to the active actor",
            permission_boundary="message.processable",
            human_summary="The requested message is not processable by this actor.",
            why_blocked="Exact message processing requires a message in the active actor inbox.",
            retryable=False,
            correctable_fields=["message_id"],
            code="E_MESSAGE_NOT_PROCESSABLE",
        )
    disposition = _message_disposition(message)
    if disposition not in PROCESSABLE_DISPOSITIONS:
        raise MessageScopeError(
            message=f"message '{message_id}' is already processed with disposition {disposition}",
            permission_boundary="message.disposition",
            human_summary="The requested message has already been processed.",
            why_blocked="Only unseen or needs_parent messages can be processed.",
            retryable=False,
            correctable_fields=["message_id"],
            code="E_MESSAGE_ALREADY_PROCESSED",
        )
    return message


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
    participant_roles = message_participant_role_ids(manifest_role_ids)
    role_filter = args.get("role")
    normalized_role: str | None = None
    if role_filter is not None:
        if not isinstance(role_filter, str):
            raise MessagePayloadError("role must be a non-empty string when provided", correctable_fields=["role"])
        candidate = role_filter.strip()
        if candidate:
            if candidate not in participant_roles:
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
    participant_roles = message_participant_role_ids(manifest_role_ids)

    target_raw = args.get("target_actor_address")
    try:
        target_actor = ActorAddress.from_payload(target_raw)
    except Exception as exc:
        raise MessagePayloadError(
            f"target_actor_address must be a valid ActorAddress: {exc}",
            correctable_fields=["target_actor_address"],
        ) from exc

    if target_actor.role_id not in participant_roles:
        raise MessagePayloadError(
            f"unknown target actor role: {target_actor.role_id}",
            correctable_fields=["target_actor_address"],
        )
    if target_actor == source_actor_address:
        raise MessageScopeError(
            message="cannot send a message to the same full actor address",
            permission_boundary="message.self_send",
            human_summary="Self-send messages are not allowed.",
            why_blocked="message.send requires target_actor_address to differ from the active full ActorAddress.",
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
    reply_to_message: dict[str, Any] | None = None
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
        ensure_processable_inbound_message(
            message_id=reply_to_id,
            message=referenced,
            active_actor_address=source_actor_address,
        )
        reply_to_message = referenced

    return {
        "target_actor_address": target_actor,
        "content": content,
        "reply_to": reply_to_id,
        "reply_to_message": reply_to_message,
    }


def prepare_get_request(*, args: dict[str, Any], allowed_fields: set[str]) -> GetRequest:
    _reject_unknown_fields(args, allowed_fields)
    message_id = args.get("message_id")
    if not isinstance(message_id, str) or not message_id.strip():
        raise MessagePayloadError("message_id must be a non-empty string", correctable_fields=["message_id"])
    return {"message_id": message_id.strip()}


def prepare_mark_request(*, args: dict[str, Any], allowed_fields: set[str]) -> MarkRequest:
    _reject_unknown_fields(args, allowed_fields)
    message_id = args.get("message_id")
    if not isinstance(message_id, str) or not message_id.strip():
        raise MessagePayloadError("message_id must be a non-empty string", correctable_fields=["message_id"])
    disposition = args.get("disposition")
    if disposition not in {"absorbed", "needs_parent"}:
        raise MessagePayloadError("disposition must be absorbed or needs_parent", correctable_fields=["disposition"])
    reason_raw = args.get("reason")
    reason: str | None = None
    if reason_raw is not None:
        if not isinstance(reason_raw, str):
            raise MessagePayloadError("reason must be a string", correctable_fields=["reason"])
        reason = reason_raw.strip() or None
    if disposition == "needs_parent" and reason is None:
        raise MessagePayloadError("reason is required when disposition is needs_parent", correctable_fields=["reason"])
    return {"message_id": message_id.strip(), "disposition": disposition, "reason": reason}


def transition_message_disposition(
    *,
    message: dict[str, Any],
    active_actor_address: ActorAddress,
    disposition: str,
    reason: str | None,
    now: str,
) -> dict[str, Any]:
    current = _message_disposition(message)
    if (current, disposition) not in VALID_TRANSITIONS:
        raise MessageScopeError(
            message=f"invalid message disposition transition: {current} -> {disposition}",
            permission_boundary="message.disposition",
            human_summary="Message disposition transition is not allowed.",
            why_blocked="Allowed transitions are unseen to absorbed/replied/needs_parent and needs_parent to absorbed/replied.",
            retryable=False,
            correctable_fields=["message_id", "disposition"],
            code="E_MESSAGE_DISPOSITION",
        )
    updated = dict(message)
    updated["disposition"] = disposition
    updated["disposition_reason"] = reason if disposition == "needs_parent" else None
    updated["disposition_updated_at"] = now
    updated["processed_by_actor_address"] = active_actor_address.to_payload()
    return updated


def prepare_list_request(*, args: dict[str, Any], manifest_role_ids: set[str], allowed_fields: set[str]) -> ListRequest:
    _reject_unknown_fields(args, allowed_fields)
    participant_roles = message_participant_role_ids(manifest_role_ids)

    role_filter = args.get("role")
    normalized_role: str | None = None
    if role_filter is not None:
        if not isinstance(role_filter, str):
            raise MessagePayloadError("role must be a non-empty string when provided", correctable_fields=["role"])
        candidate = role_filter.strip()
        if candidate:
            if candidate not in participant_roles:
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
    participant_roles = message_participant_role_ids(manifest_role_ids)

    if "target_actor_address" not in args or args.get("target_actor_address") is None:
        raise MessagePayloadError("target_actor_address is required", correctable_fields=["target_actor_address"])
    try:
        target_actor = ActorAddress.from_payload(args.get("target_actor_address"))
    except Exception as exc:
        raise MessagePayloadError(
            f"target_actor_address must be a valid ActorAddress: {exc}",
            correctable_fields=["target_actor_address"],
        ) from exc
    if target_actor.role_id not in participant_roles:
        raise MessagePayloadError(
            f"unknown target actor role: {target_actor.role_id}",
            correctable_fields=["target_actor_address"],
        )
    if target_actor == source_actor_address:
        raise MessageScopeError(
            message="cannot read a message conversation with the same full actor address",
            permission_boundary="message.self_conversation",
            human_summary="Self-conversation is not supported.",
            why_blocked="message.conversation requires the selected target ActorAddress to differ from the active full ActorAddress.",
            retryable=True,
            correctable_fields=["target_actor_address"],
        )

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
    target_actor_address: ActorAddress,
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
        if other_actor != target_actor_address:
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
            row_actor_address = ActorAddress.from_payload(row.get("actor_address"))
            actor_address = row_actor_address.to_payload()
        except Exception:
            continue
        status = row.get("status")
        contact_status = status if isinstance(status, str) and status else "online"
        why_not_sendable: str | None = None
        sendable = contact_status == "online"
        if row_actor_address == active_actor_address:
            sendable = False
            why_not_sendable = "message.send rejects the active full ActorAddress itself as a target"
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
