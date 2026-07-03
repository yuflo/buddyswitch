#!/usr/bin/env python3
"""Central IM projection for broker-routed message tool operations."""

from __future__ import annotations

from typing import Any

from env.tool_runtime import im_client as im_client_module
from env.tool_runtime import results as tool_results
from .tool import DEFINITION


_ACTION_METHODS = {
    "contacts": "contacts",
    "conversation": "conversation",
    "get": "get",
    "list": "list",
    "mark": "mark",
    "send": "send",
}
_ACTION_ALLOWED_FIELDS = {
    row.name: {
        field
        for field in (row.input_schema.get("properties") or {})
        if isinstance(field, str)
    }
    for row in DEFINITION.actions
}


def _client_for(context: Any) -> Any:
    client = getattr(context, "im_client", None)
    if client is not None:
        return client
    if isinstance(context, dict):
        client = context.get("im_client")
        if client is not None:
            return client
    return im_client_module.ActorImClient(context)


def contacts_message(*, args: dict[str, Any], context: Any) -> dict[str, Any]:
    return _client_for(context).contacts(args)


def send_message(*, args: dict[str, Any], context: Any) -> dict[str, Any]:
    return _client_for(context).send(args)


def get_message(*, args: dict[str, Any], context: Any) -> dict[str, Any]:
    return _client_for(context).get(args)


def list_messages(*, args: dict[str, Any], context: Any) -> dict[str, Any]:
    return _client_for(context).list(args)


def conversation_messages(*, args: dict[str, Any], context: Any) -> dict[str, Any]:
    return _client_for(context).conversation(args)


def mark_message(*, args: dict[str, Any], context: Any) -> dict[str, Any]:
    return _client_for(context).mark(args)


_ACTION_HANDLERS = {
    "contacts": contacts_message,
    "conversation": conversation_messages,
    "get": get_message,
    "list": list_messages,
    "mark": mark_message,
    "send": send_message,
}


def invoke(*, action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"unsupported action: {action}")
    rejection = _reject_unknown_payload_fields(action=action, args=args, context=context)
    if rejection is not None:
        return rejection
    return handler(args=args, context=context)


def _reject_unknown_payload_fields(*, action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any] | None:
    allowed = _ACTION_ALLOWED_FIELDS.get(action, set())
    unknown = sorted(field for field in args if field not in allowed)
    if not unknown:
        return None
    message = f"unsupported payload fields: {', '.join(unknown)}"
    current_identity = context.get("current_identity") if isinstance(context.get("current_identity"), dict) else {}
    active_role = context.get("active_role") if isinstance(context.get("active_role"), str) else ""
    return tool_results.rejection(
        tool="message",
        action=f"message.{action}",
        current_identity=current_identity,
        active_role=active_role,
        code="E_MESSAGE_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Message request payload is invalid.",
        why_blocked=message,
        impact="No messages were created or changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Retry with only documented message payload fields.",
        allowed_next_actions=[
            "Use the message tool schema to select documented payload fields.",
        ],
        correctable_fields=unknown,
    )
