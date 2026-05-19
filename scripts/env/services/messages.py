#!/usr/bin/env python3
"""Runless message services for broker-routed env.tool operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from env.domain import messages as message_domain
from env.repos import messages as message_repo
from env.tools import contracts as tool_contracts
from env.tools import responses as tool_responses


class MessageServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


def _guess_correctable_fields(message: str) -> list[str] | None:
    if "unsupported payload fields:" in message:
        suffix = message.split("unsupported payload fields:", 1)[1].strip()
        if suffix:
            return [row.strip() for row in suffix.split(",") if row.strip()]
    for field in ("to_buddy", "content", "reply_to", "buddy"):
        if field in message:
            return [field]
    return None


def _reject_payload(
    *,
    action: str,
    active_buddy: str,
    message: str,
    correctable_fields: list[str] | None = None,
) -> dict[str, Any]:
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
        correctable_fields=correctable_fields if correctable_fields is not None else _guess_correctable_fields(message),
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
    retryable: bool,
    correctable_fields: list[str] | None,
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


def _manifest_buddy_ids(context: MessageServiceContext) -> set[str]:
    return message_domain.manifest_buddy_ids(context.get("manifest"))


def send_message(*, args: dict[str, Any], context: MessageServiceContext) -> dict[str, Any]:
    action = "message.send"
    active_buddy = context["active_buddy"]
    manifest_buddies = _manifest_buddy_ids(context)

    try:
        message_domain.ensure_active_buddy_is_manifest_declared(
            active_buddy=active_buddy,
            manifest_buddy_ids=manifest_buddies,
        )
        request = message_domain.prepare_send_request(
            args=args,
            active_buddy=active_buddy,
            manifest_buddy_ids=manifest_buddies,
            get_message=message_repo.get_message,
            allowed_fields=tool_contracts.payload_fields_for_action("message", "send"),
        )
    except message_domain.MessagePayloadError as exc:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
        )
    except message_domain.MessageScopeError as exc:
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            code=exc.code,
            message=str(exc),
            permission_boundary=exc.permission_boundary,
            human_summary=exc.human_summary,
            why_blocked=exc.why_blocked,
            retryable=exc.retryable,
            correctable_fields=exc.correctable_fields,
        )

    try:
        message = message_repo.create_message(
            from_buddy=active_buddy,
            to_buddy=request["to_buddy"],
            content=request["content"],
            reply_to=request["reply_to"],
        )
    except (ValueError, OSError) as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    to_buddy = request["to_buddy"]
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
    manifest_buddies = _manifest_buddy_ids(context)

    try:
        message_domain.ensure_active_buddy_is_manifest_declared(
            active_buddy=active_buddy,
            manifest_buddy_ids=manifest_buddies,
        )
        request = message_domain.prepare_list_request(
            args=args,
            manifest_buddy_ids=manifest_buddies,
            allowed_fields=tool_contracts.payload_fields_for_action("message", "list"),
        )
    except message_domain.MessagePayloadError as exc:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
        )
    except message_domain.MessageScopeError as exc:
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            code=exc.code,
            message=str(exc),
            permission_boundary=exc.permission_boundary,
            human_summary=exc.human_summary,
            why_blocked=exc.why_blocked,
            retryable=exc.retryable,
            correctable_fields=exc.correctable_fields,
        )

    all_messages = message_repo.list_messages()
    inbox = message_domain.filter_inbox_messages(
        messages=all_messages,
        active_buddy=active_buddy,
        sender_buddy=request["buddy"],
    )

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
