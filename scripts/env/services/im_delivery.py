#!/usr/bin/env python3
"""Post-write delivery helpers for Central IM messages."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from env.domain.identity import IdentityRef


ActorDeliveryHandler = Callable[[dict[str, Any]], dict[str, Any]]


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
