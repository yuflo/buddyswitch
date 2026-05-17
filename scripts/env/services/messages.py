#!/usr/bin/env python3
"""Runless message services for broker-routed env.tool operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

import env_store
from env.tools import responses as tool_responses


class MessageServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


_SEND_FIELDS = {"to_buddy", "content", "reply_to"}
_LIST_FIELDS = {"buddy"}


def _allowed(action: str) -> set[str]:
    if action == "message.send":
        return _SEND_FIELDS
    if action == "message.list":
        return _LIST_FIELDS
    return set()


def _buddy_ids(context: MessageServiceContext) -> set[str]:
    manifest = context.get("manifest")
    if isinstance(manifest, dict):
        buddies = manifest.get("buddies")
        if isinstance(buddies, list):
            return {
                buddy["id"]
                for buddy in buddies
                if isinstance(buddy, dict) and isinstance(buddy.get("id"), str)
            }
    return set()


def _reject_payload(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    correctable_fields: list[str] | None = None
    if "unsupported payload fields:" in message:
        suffix = message.split("unsupported payload fields:", 1)[1].strip()
        if suffix:
            correctable_fields = [row.strip() for row in suffix.split(",") if row.strip()]
    elif "to_buddy" in message:
        correctable_fields = ["to_buddy"]
    elif "content" in message:
        correctable_fields = ["content"]
    elif "reply_to" in message:
        correctable_fields = ["reply_to"]
    elif "buddy" in message:
        correctable_fields = ["buddy"]
    return tool_responses.rejection(
        tool="message",
        action=action,
        active_buddy=active_buddy,
        code="E_MESSAGE_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Message request payload is invalid.",
        why_blocked=message,
        impact="No messages were created or changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix the message payload fields and retry.",
        allowed_next_actions=[
            "Use message.list to view inbox messages.",
            "Retry with only documented message.send payload fields.",
        ],
        correctable_fields=correctable_fields,
    )


def _reject_scope(
    *,
    action: str,
    active_buddy: str,
    code: str,
    message: str,
    permission_boundary: str,
    human_summary: str,
    why_blocked: str,
    retryable: bool = True,
    correctable_fields: list[str] | None = None,
) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="message",
        action=action,
        active_buddy=active_buddy,
        code=code,
        message=message,
        permission_boundary=permission_boundary,
        human_summary=human_summary,
        why_blocked=why_blocked,
        impact="No messages were created or changed.",
        state_changed=False,
        retryable=retryable,
        retry_guidance="Fix the scope issue and retry." if retryable else "This action cannot be retried as-is.",
        allowed_next_actions=[
            "Use message.list to view available inbox messages.",
        ],
        correctable_fields=correctable_fields,
    )


def _normalize_content(value: Any, action: str, active_buddy: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("content must be a non-empty string after trimming")
    return value.strip()


def _message_visible_to_active(message: dict[str, Any], active_buddy: str) -> bool:
    return message.get("from_buddy") == active_buddy or message.get("to_buddy") == active_buddy


def _same_pair(message: dict[str, Any], active_buddy: str, to_buddy: str) -> bool:
    participants = {message.get("from_buddy"), message.get("to_buddy")}
    return participants == {active_buddy, to_buddy}


def send_message(*, args: dict[str, Any], context: MessageServiceContext) -> dict[str, Any]:
    action = "message.send"
    active_buddy = context["active_buddy"]

    unknown = sorted(key for key in args if key not in _allowed(action))
    if unknown:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"unsupported payload fields: {', '.join(unknown)}",
        )

    to_buddy = args.get("to_buddy")
    if not isinstance(to_buddy, str) or not to_buddy.strip():
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="to_buddy must be a non-empty string",
        )
    to_buddy = to_buddy.strip()

    valid_buddies = _buddy_ids(context)
    if to_buddy not in valid_buddies:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"unknown target buddy: {to_buddy}",
        )

    if to_buddy == active_buddy:
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            code="E_MESSAGE_SCOPE",
            message="cannot send a message to yourself",
            permission_boundary="message.self_send",
            human_summary="Self-send messages are not allowed.",
            why_blocked="message.send requires distinct sender and recipient buddies.",
            retryable=True,
            correctable_fields=["to_buddy"],
        )

    content_value = args.get("content")
    if not isinstance(content_value, str) or not content_value.strip():
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="content must be a non-empty string after trimming",
        )

    reply_to = args.get("reply_to")
    reply_to_id: str | None = None
    if reply_to is not None:
        if not isinstance(reply_to, str) or not reply_to.strip():
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message="reply_to must be a non-empty string when provided",
            )
        reply_to_id = reply_to.strip()
        referenced = env_store.get_message(reply_to_id)
        if referenced is None:
            return _reject_scope(
                action=action,
                active_buddy=active_buddy,
                code="E_MESSAGE_SCOPE",
                message=f"reply_to references a message that does not exist: {reply_to_id}",
                permission_boundary="message.reply_to_scope",
                human_summary="The referenced message was not found.",
                why_blocked="reply_to must reference an existing message.",
                retryable=True,
                correctable_fields=["reply_to"],
            )
        if not _message_visible_to_active(referenced, active_buddy):
            return _reject_scope(
                action=action,
                active_buddy=active_buddy,
                code="E_MESSAGE_SCOPE",
                message=f"reply_to message '{reply_to_id}' is not visible to active buddy",
                permission_boundary="message.reply_to_scope",
                human_summary="Active buddy is not a participant in the referenced conversation.",
                why_blocked="Active buddy must be a participant in the referenced message conversation.",
                retryable=True,
                correctable_fields=["reply_to"],
            )
        if not _same_pair(referenced, active_buddy, to_buddy):
            return _reject_scope(
                action=action,
                active_buddy=active_buddy,
                code="E_MESSAGE_SCOPE",
                message=f"reply_to message '{reply_to_id}' is from a different conversation pair",
                permission_boundary="message.reply_to_scope",
                human_summary="Reply must stay in the same two-buddy conversation.",
                why_blocked="reply_to must reference a message in the same {active_buddy, to_buddy} conversation.",
                retryable=True,
                correctable_fields=["reply_to", "to_buddy"],
            )

    try:
        message = env_store.create_message(
            from_buddy=active_buddy,
            to_buddy=to_buddy,
            content=content_value.strip(),
            reply_to=reply_to_id,
        )
    except (ValueError, OSError) as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    return tool_responses.success(
        tool="message",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Sent one durable direct message from '{active_buddy}' to '{to_buddy}'.",
        state_changed=True,
        durability="durable",
        created_ids=[message["id"]],
        state_changes=[{"object_type": "message", "change": "sent", "message_id": message["id"]}],
        allowed_next_actions=[
            "Use message.list to read your inbox.",
        ],
        extra={"message_id": message["id"], "message": message},
    )


def list_messages(*, args: dict[str, Any], context: MessageServiceContext) -> dict[str, Any]:
    action = "message.list"
    active_buddy = context["active_buddy"]

    unknown = sorted(key for key in args if key not in _allowed(action))
    if unknown:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"unsupported payload fields: {', '.join(unknown)}",
        )

    all_messages = env_store.list_messages()
    inbox = [msg for msg in all_messages if msg.get("to_buddy") == active_buddy]

    buddy_filter = args.get("buddy")
    if isinstance(buddy_filter, str) and buddy_filter.strip():
        valid_buddies = _buddy_ids(context)
        if buddy_filter.strip() not in valid_buddies:
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message=f"unknown buddy filter: {buddy_filter.strip()}",
            )
        inbox = [msg for msg in inbox if msg.get("from_buddy") == buddy_filter.strip()]

    return tool_responses.success(
        tool="message",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Returned {len(inbox)} inbox message(s) for active buddy '{active_buddy}'.",
        state_changed=False,
        durability="none",
        read_scope="active-buddy inbox messages",
        allowed_next_actions=[
            "Use message.send to reply to a message.",
        ],
        extra={"messages": inbox, "discovery_summary": {"count": len(inbox)}},
    )
