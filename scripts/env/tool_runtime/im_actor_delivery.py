#!/usr/bin/env python3
"""IM-owned actor delivery over generic daemon communication primitives."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any
import uuid


SCRIPTS = Path(__file__).resolve().parents[2]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.domain.identity import ACTOR_ID_PATTERN, ROLE_ID_PATTERN  # noqa: E402
from env.repos import identities as identity_repo  # noqa: E402
from env.repos import runtime_files  # noqa: E402
from env.tool_runtime import daemon_client  # noqa: E402


def _non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _actor_identity_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or ACTOR_ID_PATTERN.fullmatch(value.strip()) is None:
        raise ValueError(f"{field} must be a valid actor identity id")
    return value.strip()


def _role_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or ROLE_ID_PATTERN.fullmatch(value.strip()) is None:
        raise ValueError(f"{field} must be a valid role id")
    return value.strip()


def deliver(
    payload: dict[str, Any],
    *,
    check_reachability_fn: Any | None = None,
    request_mailbox_fn: Any | None = None,
    socket_path: Path | None = None,
) -> dict[str, Any]:
    """Deliver a durable Central IM event to the target actor mailbox."""

    try:
        if not isinstance(payload, dict):
            raise ValueError("IM delivery payload must be an object")
        if payload.get("type") != "im.message.created":
            return {
                "actor_handling_status": "not_applicable",
                "runtime_target": "none",
                "error": "unsupported IM delivery type",
            }
        if "target_role_id" in payload:
            raise ValueError("target_role_id is not accepted for im.message.created actor handling")
        target_identity_id = _actor_identity_id(payload.get("target_identity_id"), "target_identity_id")
        message_id = _non_empty_text(payload.get("message_id"), "message_id")
        conversation_id = _non_empty_text(payload.get("conversation_id"), "conversation_id")
        event_id = _non_empty_text(payload.get("event_id"), "event_id")
        delivery_id = _non_empty_text(
            payload.get("wake_id") or f"imwake-{uuid.uuid4().hex[:12]}",
            "wake_id",
        )
    except Exception as exc:
        return {"actor_handling_status": "handling_failed", "runtime_target": "none", "error": str(exc)}

    profile = identity_repo.get_actor_identity_profile(target_identity_id)
    if not isinstance(profile, dict):
        return {
            "actor_handling_status": "handling_failed",
            "runtime_target": "none",
            "error": f"actor identity profile not found: {target_identity_id}",
        }
    try:
        target_role_id = _role_id(profile.get("role_id"), "actor identity profile role_id")
    except Exception as exc:
        return {"actor_handling_status": "handling_failed", "runtime_target": "none", "error": str(exc)}

    reachability_call = check_reachability_fn or daemon_client.check_reachability
    mailbox_call = request_mailbox_fn or daemon_client.request_mailbox
    try:
        reachability = reachability_call(
            target_identity_id=target_identity_id,
            socket_path=socket_path,
        )
    except Exception as exc:
        return {"actor_handling_status": "handling_failed", "runtime_target": "none", "error": str(exc)}
    if not isinstance(reachability, dict):
        return {
            "actor_handling_status": "handling_failed",
            "runtime_target": "none",
            "error": "reachability response must be an object",
        }
    if reachability.get("reachability_status") != "online":
        status = reachability.get("reachability_status")
        return {
            "actor_handling_status": "target_not_online",
            "runtime_target": "none",
            "error": f"target identity is not online: {status}",
            "reachability_status": status,
        }

    record = reachability.get("record")
    endpoint = record.get("endpoint") if isinstance(record, dict) else None
    if not isinstance(endpoint, dict) or endpoint.get("kind") != "daemon_mailbox_socket":
        return {
            "actor_handling_status": "handling_failed",
            "runtime_target": "none",
            "error": "target endpoint is not daemon_mailbox_socket",
        }
    mailbox_socket = endpoint.get("socket_path")
    if not isinstance(mailbox_socket, str) or not mailbox_socket.strip():
        return {
            "actor_handling_status": "handling_failed",
            "runtime_target": "none",
            "error": "target mailbox socket_path is required",
        }

    try:
        envelope = mailbox_call(
            "mailbox.local_trigger",
            {
                "identity_id": target_identity_id,
                "role_id": target_role_id,
                "type": "im.message.created",
                "payload": {
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "event_id": event_id,
                },
                "origin_id": message_id,
                "correlation_id": delivery_id,
                "source_context": {"source": "central_im"},
            },
            socket_path=Path(mailbox_socket),
        )
    except Exception as exc:
        return {"actor_handling_status": "handling_failed", "runtime_target": "none", "error": str(exc)}
    if not isinstance(envelope, dict):
        return {
            "actor_handling_status": "handling_failed",
            "runtime_target": "none",
            "error": "mailbox response must be an object",
        }
    if envelope.get("ok") is not True:
        error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
        message = error.get("message") if isinstance(error.get("message"), str) else "mailbox local trigger failed"
        return {"actor_handling_status": "handling_failed", "runtime_target": "none", "error": message}
    result = envelope.get("result") if isinstance(envelope.get("result"), dict) else {}
    return {
        "actor_handling_status": "submitted",
        "runtime_target": "daemon_mailbox",
        "error": None,
        "handling_status": result.get("handling_status") if isinstance(result.get("handling_status"), str) else None,
    }
