#!/usr/bin/env python3
"""Public message send service."""

from __future__ import annotations

import hashlib
import secrets
import time
import uuid
from typing import Any, Protocol

from env.tool_runtime import results as tool_results


MESSAGE_MUTATION_RETRY_DELAYS_SECONDS = (0.0, 0.1, 0.25)
SEND_ALLOWED_FIELDS = {"target_actor_address", "content", "reply_to"}


class MessageSendContext(Protocol):
    actor_address: Any
    daemon: Any
    manifest: dict[str, Any]
    repos: Any
    rules: Any

    def __getitem__(self, key: str) -> Any: ...

    def get(self, key: str, default: Any = None) -> Any: ...


def _sleep_for_message_mutation_retry(seconds: float) -> None:
    time.sleep(seconds)


def _run_message_mutation_with_retry(operation: Any) -> Any:
    last_exc: Exception | None = None
    for delay in MESSAGE_MUTATION_RETRY_DELAYS_SECONDS:
        if delay > 0:
            _sleep_for_message_mutation_retry(delay)
        try:
            return operation()
        except Exception as exc:
            last_exc = exc
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("message mutation retry did not run")


def _guess_correctable_fields(message: str) -> list[str] | None:
    if "unsupported payload fields:" in message:
        suffix = message.split("unsupported payload fields:", 1)[1].strip()
        if suffix:
            return [row.strip() for row in suffix.split(",") if row.strip()]
    for field in ("target_actor_address", "content", "reply_to"):
        if field in message:
            return [field]
    return None


def _reject_payload(
    *,
    action: str,
    active_actor: dict[str, Any],
    active_role: str,
    message: str,
    correctable_fields: list[str] | None = None,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="message",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
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
    active_actor: dict[str, Any],
    active_role: str,
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
        active_actor=active_actor,
        active_role=active_role,
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
            "Use message.list to view visible Central IM events.",
        ],
        correctable_fields=correctable_fields,
    )


def _reject_reachability(
    *,
    action: str,
    active_actor: dict[str, Any],
    active_role: str,
    reachability_status: str,
    target_actor_address: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="message",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
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


def _im_payload_error(message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": message}}


def _manifest_role_ids(context: MessageSendContext) -> set[str]:
    return context.rules.message.manifest_role_ids(context.get("manifest"))


def _actor_address_from_any(context: MessageSendContext, value: Any) -> Any:
    if hasattr(value, "to_payload"):
        return value
    return context.rules.message.ActorAddress.from_payload(value)


def register_external_participant(*, client_kind: str, display_name: str) -> dict[str, Any]:
    from env.repos import messages as message_repo

    normalized_client_kind = client_kind.strip() if isinstance(client_kind, str) else ""
    normalized_display_name = display_name.strip() if isinstance(display_name, str) else ""
    if not normalized_client_kind:
        return {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "client_kind must be a non-empty string"}}
    if not normalized_display_name:
        return {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "display_name must be a non-empty string"}}

    external_id = f"ext-{uuid.uuid4().hex[:12]}"
    participant = {
        "kind": "external",
        "external_id": external_id,
        "client_kind": normalized_client_kind,
        "display_name": normalized_display_name,
        "created_at": message_repo.runtime_files.now_iso(),
        "last_seen_at": message_repo.runtime_files.now_iso(),
    }
    participant_token = f"impt-{secrets.token_hex(24)}"
    token_hash = "sha256:" + hashlib.sha256(participant_token.encode("utf-8")).hexdigest()
    message_repo.save_im_participant(participant)
    message_repo.save_im_session(
        {
            "token_hash": token_hash,
            "participant": {"kind": "external", "external_id": external_id},
            "created_at": participant["created_at"],
            "last_used_at": participant["created_at"],
        }
    )
    message_repo.save_im_cursor(
        {
            "participant": {"kind": "external", "external_id": external_id},
            "last_event_id": message_repo.INITIAL_IM_EVENT_CURSOR,
            "updated_at": participant["created_at"],
        }
    )
    return {
        "ok": True,
        "participant": {
            "kind": "external",
            "external_id": external_id,
            "client_kind": normalized_client_kind,
            "display_name": normalized_display_name,
        },
        "participant_token": participant_token,
        "event_cursor": message_repo.INITIAL_IM_EVENT_CURSOR,
    }


def _im_token_hash(participant_token: str) -> str:
    return "sha256:" + hashlib.sha256(participant_token.encode("utf-8")).hexdigest()


def authenticate_im_token(participant_token: str) -> dict[str, Any]:
    from env.repos import messages as message_repo

    if not isinstance(participant_token, str) or not participant_token.strip():
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": "participant token is required"}}
    session = message_repo.get_im_session_by_token_hash(_im_token_hash(participant_token.strip()))
    if session is None:
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": "participant token is invalid"}}
    participant = session.get("participant")
    if not isinstance(participant, dict):
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": "participant session is invalid"}}
    try:
        participant_ref = message_repo.im_participant_ref(participant)
    except ValueError as exc:
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": str(exc)}}
    session["last_used_at"] = message_repo.runtime_files.now_iso()
    message_repo.save_im_session(session)
    return {"ok": True, "participant": participant_ref}


def _new_im_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _im_reply_target_error(message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": "E_IM_REPLY_TARGET", "message": message}}


def _direct_conversation_participants(message_repo: Any, conversation: dict[str, Any]) -> list[dict[str, Any]] | None:
    if conversation.get("type") != "direct":
        return None
    participants = conversation.get("participants")
    if not isinstance(participants, list) or len(participants) != 2:
        return None
    try:
        return [message_repo.im_participant_ref(row) for row in participants if isinstance(row, dict)]
    except ValueError:
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
    participants = _direct_conversation_participants(message_repo, conversation)
    if participants is None:
        return _im_reply_target_error("reply_to conversation is not a direct conversation")
    sender_key = message_repo.im_participant_key(sender)
    participant_keys = {message_repo.im_participant_key(row) for row in participants}
    if sender_key not in participant_keys:
        return _im_reply_target_error("active sender is not a participant in the reply_to conversation")
    if target is None:
        other = [row for row in participants if message_repo.im_participant_key(row) != sender_key]
        if len(other) != 1:
            return _im_reply_target_error("reply target cannot be derived from the direct conversation")
        target = other[0]
    else:
        target_key = message_repo.im_participant_key(target)
        if {sender_key, target_key} != participant_keys:
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
    participant: dict[str, Any],
    message_id: str,
) -> dict[str, Any] | None:
    current = message_repo.get_im_message_state(message_id, participant)
    if current is None:
        return None
    updated = dict(current)
    updated["disposition"] = "replied"
    updated["reason"] = None
    updated["updated_at"] = message_repo.runtime_files.now_iso()
    return message_repo.save_im_message_state(updated)


def send_im_message(
    *,
    sender_participant: dict[str, Any],
    to: dict[str, Any] | None,
    content: str,
    reply_to: str | None = None,
    wake_actor: Any | None = None,
) -> dict[str, Any]:
    from env.repos import messages as message_repo

    try:
        sender = message_repo.im_participant_ref(sender_participant)
    except ValueError as exc:
        return _im_payload_error(str(exc))
    normalized_content = content.strip() if isinstance(content, str) else ""
    if not normalized_content:
        return _im_payload_error("content must be a non-empty string")
    if reply_to is not None and (not isinstance(reply_to, str) or not reply_to.strip()):
        return _im_payload_error("reply_to must be a non-empty string")
    reply_to_id = reply_to.strip() if isinstance(reply_to, str) else None
    try:
        target = message_repo.im_participant_ref(to) if isinstance(to, dict) and to else None
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
            "participants": [sender, target],
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
            "from": sender,
            "to": [target],
            "content": normalized_content,
            "reply_to": reply_to_id,
            "created_at": now,
            "sequence": sequence,
        }
    )
    message_repo.save_im_message_state(
        {
            "message_id": message_id,
            "participant": target,
            "disposition": "unseen",
            "reason": None,
            "processed_by": None,
            "updated_at": now,
        }
    )
    for participant in (sender, target):
        message_repo.save_im_event(
            {
                "event_id": event_id,
                "type": "message.created",
                "participant": participant,
                "message_id": message_id,
                "conversation_id": conversation_id,
                "from": sender,
                "to": [target],
                "reply_to": reply_to_id,
                "created_at": now,
                "sequence": sequence,
            }
        )
    message_repo.save_im_cursor(
        {
            "participant": sender,
            "last_event_id": event_id,
            "updated_at": now,
        }
    )
    original_reply_state = None
    if reply_to_id is not None:
        original_reply_state = _mark_reply_source_replied(
            message_repo=message_repo,
            participant=sender,
            message_id=reply_to_id,
        )

    wake_status = "not_applicable"
    if target.get("kind") == "actor":
        wake_payload = {
            "type": "im.message.created",
            "wake_id": _new_im_id("imwake"),
            "target_actor_address": target["actor_address"],
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


def read_im_events(
    *,
    participant: dict[str, Any],
    cursor: str,
    limit: int = 50,
    wait_ms: int = 0,
) -> dict[str, Any]:
    from env.repos import messages as message_repo

    participant_ref = message_repo.im_participant_ref(participant)
    normalized_cursor = cursor.strip() if isinstance(cursor, str) and cursor.strip() else message_repo.INITIAL_IM_EVENT_CURSOR
    normalized_limit = limit if isinstance(limit, int) and limit > 0 else 50
    wait_seconds = min(wait_ms if isinstance(wait_ms, int) and wait_ms > 0 else 0, 30000) / 1000
    deadline = time.monotonic() + wait_seconds
    while True:
        events = message_repo.list_im_events_for_participant(participant_ref)
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
        "participant": participant_ref,
    }


def _im_scope_error(message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": "E_IM_SCOPE", "message": message}}


def _im_not_found(message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": "E_IM_NOT_FOUND", "message": message}}


def _participant_can_see_message(message_repo: Any, participant: dict[str, Any], message: dict[str, Any]) -> bool:
    conversation = message_repo.get_im_conversation(str(message.get("conversation_id") or ""))
    if conversation is None:
        return False
    rows = conversation.get("participants")
    if not isinstance(rows, list):
        return False
    participant_key = message_repo.im_participant_key(participant)
    return participant_key in {message_repo.im_participant_key(row) for row in rows if isinstance(row, dict)}


def get_im_message(*, participant: dict[str, Any], message_id: str) -> dict[str, Any]:
    from env.repos import messages as message_repo

    participant_ref = message_repo.im_participant_ref(participant)
    message = message_repo.get_im_message(message_id)
    if message is None:
        return _im_not_found(f"message not found: {message_id}")
    if not _participant_can_see_message(message_repo, participant_ref, message):
        return _im_scope_error("participant is not in the message conversation")
    return {"ok": True, "message": message}


def list_im_replies(*, participant: dict[str, Any], message_id: str) -> dict[str, Any]:
    from env.repos import messages as message_repo

    root_response = get_im_message(participant=participant, message_id=message_id)
    if root_response.get("ok") is not True:
        return root_response
    replies = [
        row
        for row in message_repo.list_im_messages()
        if row.get("reply_to") == message_id and _participant_can_see_message(message_repo, participant, row)
    ]
    return {
        "ok": True,
        "message_id": message_id,
        "replies": replies,
        "count": len(replies),
    }


def get_im_direct_conversation(
    *,
    participant: dict[str, Any],
    target: dict[str, Any],
    limit: int = 20,
) -> dict[str, Any]:
    from env.repos import messages as message_repo

    participant_ref = message_repo.im_participant_ref(participant)
    target_ref = message_repo.im_participant_ref(target)
    conversation = message_repo.find_im_direct_conversation([participant_ref, target_ref])
    if conversation is None:
        return _im_not_found("direct conversation not found")
    messages = [
        row
        for row in message_repo.list_im_messages()
        if row.get("conversation_id") == conversation.get("id")
        and _participant_can_see_message(message_repo, participant_ref, row)
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
    participant: dict[str, Any],
    message_id: str,
    disposition: str,
    reason: str | None = None,
) -> dict[str, Any]:
    from env.repos import messages as message_repo

    participant_ref = message_repo.im_participant_ref(participant)
    message_response = get_im_message(participant=participant_ref, message_id=message_id)
    if message_response.get("ok") is not True:
        return message_response
    if disposition not in {"absorbed", "replied", "needs_parent"}:
        return {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "invalid disposition"}}
    current = message_repo.get_im_message_state(message_id, participant_ref)
    if current is None:
        return _im_scope_error("participant has no state for this message")
    previous = current.get("disposition")
    updated = dict(current)
    updated["disposition"] = disposition
    updated["reason"] = reason.strip() if isinstance(reason, str) and reason.strip() else None
    updated["updated_at"] = message_repo.runtime_files.now_iso()
    message_repo.save_im_message_state(updated)
    return {
        "ok": True,
        "message_id": message_id,
        "participant": participant_ref,
        "disposition": disposition,
        "state_changed": previous != disposition or current.get("reason") != updated["reason"],
    }


def send_from_actor(
    *,
    args: dict[str, Any],
    context: MessageSendContext,
    source_actor_address: Any,
    active_actor: dict[str, Any],
    active_role: str,
    require_active_role_manifest: bool = True,
    action: str = "message.send",
) -> dict[str, Any]:
    del action
    manifest_roles = _manifest_role_ids(context)
    source_actor = _actor_address_from_any(context, source_actor_address)
    if require_active_role_manifest and active_role not in manifest_roles:
        return _reject_scope(
            action="message.send",
            active_actor=active_actor,
            active_role=active_role,
            code="E_MESSAGE_SCOPE",
            message=f"active role '{active_role}' is not declared in manifest",
            permission_boundary="message.manifest_role",
            human_summary="Active role is not part of the manifest-declared message scope.",
            why_blocked="message actions require active_role to be declared in manifest.roles.",
            retryable=False,
            correctable_fields=None,
        )
    target = args.get("target_actor_address")
    reply_to = args.get("reply_to") if isinstance(args.get("reply_to"), str) else None
    if not isinstance(target, dict) and reply_to is None:
        return _reject_payload(
            action="message.send",
            active_actor=active_actor,
            active_role=active_role,
            message="target_actor_address is required for a new actor-directed message",
            correctable_fields=["target_actor_address"],
        )
    result = send_im_message(
        sender_participant={"kind": "actor", "actor_address": source_actor.to_payload()},
        to={"kind": "actor", "actor_address": target} if isinstance(target, dict) else None,
        content=str(args.get("content") or ""),
        reply_to=reply_to,
        wake_actor=getattr(context.daemon, "wake_im_actor", None),
    )
    if result.get("ok") is True:
        result["action"] = "message.send"
        result["active_actor"] = active_actor
        result["active_role"] = active_role
    return result
