#!/usr/bin/env python3
"""Runless message services for broker-routed env.tool operations."""

from __future__ import annotations

from typing import Any, TypedDict

from .tool import DEFINITION
from env.tool_runtime import results as tool_results


_ACTION_DEFINITION_MAP = {
    'actions': [
        {
            'name': row.name,
            'payload_fields': [
                field
                for field in (row.input_schema.get('properties') or {})
                if isinstance(field, str)
            ],
        }
        for row in DEFINITION.actions
    ]
}


class MessageServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


def _guess_correctable_fields(message: str) -> list[str] | None:
    if "unsupported payload fields:" in message:
        suffix = message.split("unsupported payload fields:", 1)[1].strip()
        if suffix:
            return [row.strip() for row in suffix.split(",") if row.strip()]
    for field in ("target_actor_address", "content", "reply_to", "buddy", "q", "limit"):
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
    return tool_results.rejection(
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
            "Use message.contacts to discover online target actor addresses.",
            "Retry with only documented message payload fields.",
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
    return tool_results.rejection(
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
            "Use message.contacts to discover online target actor addresses.",
            "Use message.list to view available inbox messages.",
        ],
        correctable_fields=correctable_fields,
    )


def _reject_reachability(
    *,
    action: str,
    active_buddy: str,
    reachability_status: str,
    target_actor_address: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="message",
        action=action,
        active_buddy=active_buddy,
        code="E_MESSAGE_TARGET_NOT_ONLINE",
        message=message,
        permission_boundary="message.reachability",
        human_summary="Target actor is not currently reachable.",
        why_blocked=message,
        impact="No readable message was created.",
        state_changed=False,
        durability="none",
        retryable=True,
        retry_guidance="Refresh message.contacts or retry after the target daemon is online.",
        allowed_next_actions=[
            "Use message.contacts to refresh the target actor address.",
            "Retry message.send only after target reachability is online.",
        ],
        correctable_fields=["target_actor_address"],
        extra={
            "reachability_status": reachability_status,
            "target_actor_address": target_actor_address,
        },
    )


def _reject_delivery_cleaned(
    *,
    action: str,
    active_buddy: str,
    delivery_status: str,
    signal_error: str | None,
    target_actor_address: dict[str, Any],
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="message",
        action=action,
        active_buddy=active_buddy,
        code="E_MESSAGE_DELIVERY_FAILED",
        message="message.available signal delivery failed",
        permission_boundary="message.delivery",
        human_summary="Signal delivery failed after message creation, and the created message was cleaned up.",
        why_blocked="Target daemon was online, but message.available signal delivery failed.",
        impact="No readable message was created; the failed send was cleaned up.",
        state_changed=False,
        durability="none",
        retryable=True,
        retry_guidance="Retry message.send after rechecking message.contacts or target reachability.",
        allowed_next_actions=[
            "Use message.contacts to refresh the target actor address.",
            "Retry message.send with the same target_actor_address if it is still online.",
        ],
        extra={
            "delivery_status": delivery_status,
            "cleanup_status": "cleaned",
            "signal_error": signal_error,
            "target_actor_address": target_actor_address,
        },
    )


def _reject_delivery_indeterminate(
    *,
    action: str,
    active_buddy: str,
    message_id: str,
    delivery_status: str,
    signal_error: str | None,
    cleanup_error: str,
    target_actor_address: dict[str, Any],
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="message",
        action=action,
        active_buddy=active_buddy,
        code="E_MESSAGE_SEND_INDETERMINATE",
        message="signal delivery failed and message cleanup failed",
        permission_boundary="message.delivery_cleanup",
        human_summary="Message send state is indeterminate.",
        why_blocked="Signal delivery failed and cleanup of the created message also failed.",
        impact="A message may still exist without target notification.",
        state_changed=True,
        durability="uncertain",
        retryable=False,
        retry_guidance="Do not blindly retry. Use context.get or message.list to inspect current state before deciding.",
        allowed_next_actions=[
            "Use context.get to inspect message recovery warnings.",
            "Use message.list from the target actor if available to check whether the message is visible.",
        ],
        extra={
            "message_id": message_id,
            "delivery_status": delivery_status,
            "cleanup_status": "failed",
            "signal_error": signal_error,
            "cleanup_error": cleanup_error,
            "target_actor_address": target_actor_address,
        },
    )


def _manifest_buddy_ids(context: MessageServiceContext) -> set[str]:
    return context.rules.message.manifest_buddy_ids(context.get("manifest"))


def _allowed_fields(action_name: str) -> set[str]:
    for row in _ACTION_DEFINITION_MAP.get("actions", []):
        if isinstance(row, dict) and row.get("name") == action_name:
            return {field for field in row.get("payload_fields", []) if isinstance(field, str)}
    return set()


def contacts_message(*, args: dict[str, Any], context: MessageServiceContext) -> dict[str, Any]:
    action = "message.contacts"
    active_buddy = context["active_buddy"]
    manifest_buddies = _manifest_buddy_ids(context)

    try:
        context.rules.message.ensure_active_buddy_is_manifest_declared(
            active_buddy=active_buddy,
            manifest_buddy_ids=manifest_buddies,
        )
        request = context.rules.message.prepare_contacts_request(
            args=args,
            manifest_buddy_ids=manifest_buddies,
            allowed_fields=_allowed_fields("contacts"),
        )
    except context.rules.message.MessagePayloadError as exc:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
        )
    except context.rules.message.MessageScopeError as exc:
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
        raw_contacts = context.daemon.list_contacts(buddy_id=request["buddy"])
    except Exception as exc:
        return tool_results.rejection(
            tool="message",
            action=action,
            active_buddy=active_buddy,
            code="E_MESSAGE_CONTACTS_UNAVAILABLE",
            message=str(exc),
            permission_boundary="message.contacts",
            human_summary="Online actor contacts are unavailable.",
            why_blocked="The central daemon contacts endpoint could not be reached.",
            impact="No messages were created or changed.",
            state_changed=False,
            retryable=True,
            retry_guidance="Retry message.contacts after the central daemon is available.",
            allowed_next_actions=[
                "Retry message.contacts after the daemon is running.",
            ],
        )
    rows = raw_contacts.get("contacts") if isinstance(raw_contacts.get("contacts"), list) else []
    contacts = context.rules.message.normalize_contact_rows(rows, active_actor_address=context.actor_address)
    sendable_count = sum(1 for row in contacts if row.get("sendable") is True)
    return tool_results.success(
        tool="message",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Returned {len(contacts)} online actor contact(s).",
        state_changed=False,
        durability="none",
        read_scope="online actor contacts from central daemon",
        allowed_next_actions=[
            "Use message.send with contact.actor_address copied into target_actor_address.",
        ],
        extra={
            "contacts": contacts,
            "count": len(contacts),
            "sendable_count": sendable_count,
            "filters": {"buddy": request["buddy"]},
        },
    )


def send_message(*, args: dict[str, Any], context: MessageServiceContext) -> dict[str, Any]:
    action = "message.send"
    active_buddy = context["active_buddy"]
    manifest_buddies = _manifest_buddy_ids(context)
    source_actor_address = context.actor_address

    try:
        context.rules.message.ensure_active_buddy_is_manifest_declared(
            active_buddy=active_buddy,
            manifest_buddy_ids=manifest_buddies,
        )
        request = context.rules.message.prepare_send_request(
            args=args,
            source_actor_address=source_actor_address,
            manifest_buddy_ids=manifest_buddies,
            get_message=context.repos.message.get_message,
            allowed_fields=_allowed_fields("send"),
        )
    except context.rules.message.MessagePayloadError as exc:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
        )
    except context.rules.message.MessageScopeError as exc:
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

    target_actor = request["target_actor_address"]
    target_payload = target_actor.to_payload()
    try:
        reachability = context.daemon.check_reachability(target_actor_address=target_actor)
    except Exception as exc:
        return _reject_reachability(
            action=action,
            active_buddy=active_buddy,
            reachability_status="unavailable",
            target_actor_address=target_payload,
            message=f"target reachability check failed: {exc}",
        )
    reachability_status = reachability.get("reachability_status")
    if reachability_status != "online":
        status = reachability_status if isinstance(reachability_status, str) and reachability_status else "unavailable"
        return _reject_reachability(
            action=action,
            active_buddy=active_buddy,
            reachability_status=status,
            target_actor_address=target_payload,
            message=f"target actor is not online: {status}",
        )

    try:
        message = context.repos.message.create_message(
            from_actor_address=source_actor_address,
            to_actor_address=target_actor,
            content=request["content"],
            reply_to=request["reply_to"],
        )
    except (ValueError, OSError) as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    try:
        delivery = context.daemon.deliver_message_available(
            message_id=message["id"],
            target_actor_address=target_actor,
        )
    except Exception as exc:
        delivery = {
            "delivery_status": "delivery_failed",
            "signal_error": str(exc),
        }
    delivery_status = delivery.get("delivery_status") if isinstance(delivery.get("delivery_status"), str) else "delivery_failed"
    if delivery_status != "delivered":
        signal_error = delivery.get("signal_error") if isinstance(delivery.get("signal_error"), str) else None
        try:
            context.repos.message.delete_message(message["id"])
        except Exception as exc:
            return _reject_delivery_indeterminate(
                action=action,
                active_buddy=active_buddy,
                message_id=message["id"],
                delivery_status=delivery_status,
                signal_error=signal_error,
                cleanup_error=str(exc),
                target_actor_address=target_payload,
            )
        return _reject_delivery_cleaned(
            action=action,
            active_buddy=active_buddy,
            delivery_status=delivery_status,
            signal_error=signal_error,
            target_actor_address=target_payload,
        )

    handling_status = delivery.get("handling_status") if isinstance(delivery.get("handling_status"), str) else None
    return tool_results.success(
        tool="message",
        action=action,
        active_buddy=active_buddy,
        effect_summary=(
            f"Sent one durable direct message from actor "
            f"'{source_actor_address.instance_id}' to '{target_actor.instance_id}'."
        ),
        state_changed=True,
        durability="durable",
        created_ids=[message["id"]],
        state_changes=[{"object_type": "message", "change": "sent", "message_id": message["id"]}],
        allowed_next_actions=[
            "Use message.list to inspect delivered inbox messages when needed.",
        ],
        extra={
            "message_id": message["id"],
            "delivery_status": "delivered",
            "handling_status": handling_status,
            "target_actor_address": target_payload,
        },
    )


def list_messages(*, args: dict[str, Any], context: MessageServiceContext) -> dict[str, Any]:
    action = "message.list"
    active_buddy = context["active_buddy"]
    manifest_buddies = _manifest_buddy_ids(context)

    try:
        context.rules.message.ensure_active_buddy_is_manifest_declared(
            active_buddy=active_buddy,
            manifest_buddy_ids=manifest_buddies,
        )
        request = context.rules.message.prepare_list_request(
            args=args,
            manifest_buddy_ids=manifest_buddies,
            allowed_fields=_allowed_fields("list"),
        )
    except context.rules.message.MessagePayloadError as exc:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
        )
    except context.rules.message.MessageScopeError as exc:
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

    all_messages = context.repos.message.list_messages()
    inbox = context.rules.message.filter_inbox_messages(
        messages=all_messages,
        active_actor_address=context.actor_address,
        sender_buddy=request["buddy"],
        q=request["q"],
        limit=request["limit"],
    )

    return tool_results.success(
        tool="message",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Returned {len(inbox)} inbox message(s) for active actor '{context.actor_address.instance_id}'.",
        state_changed=False,
        durability="none",
        read_scope="active actor inbox messages",
        allowed_next_actions=[
            "Use message.contacts to discover an online actor address for replies.",
            "Use message.send to reply to a message when the target actor is online.",
        ],
        extra={
            "messages": inbox,
            "actor_address": context.actor_address.to_payload(),
            "discovery_summary": {
                "count": len(inbox),
                "filters": {
                    "buddy": request["buddy"],
                    "q": request["q"],
                    "limit": request["limit"],
                },
            },
        },
    )


def conversation_messages(*, args: dict[str, Any], context: MessageServiceContext) -> dict[str, Any]:
    action = "message.conversation"
    active_buddy = context["active_buddy"]
    manifest_buddies = _manifest_buddy_ids(context)

    try:
        context.rules.message.ensure_active_buddy_is_manifest_declared(
            active_buddy=active_buddy,
            manifest_buddy_ids=manifest_buddies,
        )
        request = context.rules.message.prepare_conversation_request(
            args=args,
            source_actor_address=context.actor_address,
            manifest_buddy_ids=manifest_buddies,
            allowed_fields=_allowed_fields("conversation"),
        )
    except context.rules.message.MessagePayloadError as exc:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
        )
    except context.rules.message.MessageScopeError as exc:
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

    target_actor = request["target_actor_address"]
    target_buddy = request["buddy"]
    messages = context.rules.message.filter_conversation_messages(
        messages=context.repos.message.list_messages(),
        active_actor_address=context.actor_address,
        target_actor_address=target_actor,
        target_buddy=target_buddy,
        q=request["q"],
        limit=request["limit"],
    )
    selector: dict[str, Any]
    if target_actor is not None:
        selector = {"target_actor_address": target_actor.to_payload()}
    else:
        selector = {"buddy": target_buddy}

    return tool_results.success(
        tool="message",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Returned {len(messages)} visible conversation message(s) for active actor '{context.actor_address.instance_id}'.",
        state_changed=False,
        durability="none",
        read_scope="active actor visible direct conversation messages",
        allowed_next_actions=[
            "Use message.list when you only need active actor inbox messages.",
            "Use message.contacts before sending a new direct message.",
        ],
        extra={
            "messages": messages,
            "count": len(messages),
            "selector": selector,
            "actor_address": context.actor_address.to_payload(),
            "filters": {
                "q": request["q"],
                "limit": request["limit"],
            },
        },
    )


_ACTION_HANDLERS = {
    'contacts': contacts_message,
    'conversation': conversation_messages,
    'list': list_messages,
    'send': send_message,
}


def invoke(*, action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"unsupported action: {action}")
    return handler(args=args, context=context)
