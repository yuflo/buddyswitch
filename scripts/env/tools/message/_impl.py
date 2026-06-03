#!/usr/bin/env python3
"""Runless message services for broker-routed env.tool operations."""

from __future__ import annotations

import time
from typing import Any, TypedDict

from .tool import DEFINITION
from env.tool_runtime import results as tool_results


MESSAGE_MUTATION_RETRY_DELAYS_SECONDS = (0.0, 0.1, 0.25)


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


class MessageServiceContext(TypedDict):
    active_role: str
    actor_id: str
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


def _guess_correctable_fields(message: str) -> list[str] | None:
    if "unsupported payload fields:" in message:
        suffix = message.split("unsupported payload fields:", 1)[1].strip()
        if suffix:
            return [row.strip() for row in suffix.split(",") if row.strip()]
    for field in ("target_actor_address", "content", "reply_to", "message_id", "disposition", "reason", "role", "q", "limit"):
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
            "Use message.list to view available inbox messages.",
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


def _reject_delivery_cleaned(
    *,
    action: str,
    active_actor: dict[str, Any],
    active_role: str,
    delivery_status: str,
    signal_error: str | None,
    target_actor_address: dict[str, Any],
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="message",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
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
    active_actor: dict[str, Any],
    active_role: str,
    message_id: str,
    delivery_status: str,
    signal_error: str | None,
    cleanup_error: str,
    target_actor_address: dict[str, Any],
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="message",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
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


def _manifest_role_ids(context: MessageServiceContext) -> set[str]:
    return context.rules.message.manifest_role_ids(context.get("manifest"))


def _allowed_fields(action_name: str) -> set[str]:
    for row in _ACTION_DEFINITION_MAP.get("actions", []):
        if isinstance(row, dict) and row.get("name") == action_name:
            return {field for field in row.get("payload_fields", []) if isinstance(field, str)}
    return set()


def contacts_message(*, args: dict[str, Any], context: MessageServiceContext) -> dict[str, Any]:
    action = "message.contacts"
    active_actor = context["active_actor"]
    active_role = context["active_role"]
    manifest_roles = _manifest_role_ids(context)

    try:
        context.rules.message.ensure_active_role_is_manifest_declared(
            active_role=active_role,
            manifest_role_ids=manifest_roles,
        )
        request = context.rules.message.prepare_contacts_request(
            args=args,
            manifest_role_ids=manifest_roles,
            allowed_fields=_allowed_fields("contacts"),
        )
    except context.rules.message.MessagePayloadError as exc:
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
        )
    except context.rules.message.MessageScopeError as exc:
        return _reject_scope(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            code=exc.code,
            message=str(exc),
            permission_boundary=exc.permission_boundary,
            human_summary=exc.human_summary,
            why_blocked=exc.why_blocked,
            retryable=exc.retryable,
            correctable_fields=exc.correctable_fields,
        )

    try:
        raw_contacts = context.daemon.list_contacts(role_id=request["role"])
    except Exception as exc:
        return tool_results.rejection(
            tool="message",
            action=action,
            active_actor=active_actor,
            active_role=active_role,
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
        active_actor=active_actor,
        active_role=active_role,
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
            "filters": {"role": request["role"]},
        },
    )


def send_message(*, args: dict[str, Any], context: MessageServiceContext) -> dict[str, Any]:
    action = "message.send"
    active_actor = context["active_actor"]
    active_role = context["active_role"]
    manifest_roles = _manifest_role_ids(context)
    source_actor_address = context.actor_address

    try:
        context.rules.message.ensure_active_role_is_manifest_declared(
            active_role=active_role,
            manifest_role_ids=manifest_roles,
        )
        request = context.rules.message.prepare_send_request(
            args=args,
            source_actor_address=source_actor_address,
            manifest_role_ids=manifest_roles,
            get_message=context.repos.message.get_message,
            allowed_fields=_allowed_fields("send"),
        )
    except context.rules.message.MessagePayloadError as exc:
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
        )
    except context.rules.message.MessageScopeError as exc:
        return _reject_scope(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
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
            active_actor=active_actor,
            active_role=active_role,
            reachability_status="unavailable",
            target_actor_address=target_payload,
            message=f"target reachability check failed: {exc}",
        )
    reachability_status = reachability.get("reachability_status")
    if reachability_status != "online":
        status = reachability_status if isinstance(reachability_status, str) and reachability_status else "unavailable"
        return _reject_reachability(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
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
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message=str(exc))

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
                active_actor=active_actor,
                active_role=active_role,
                message_id=message["id"],
                delivery_status=delivery_status,
                signal_error=signal_error,
                cleanup_error=str(exc),
                target_actor_address=target_payload,
            )
        return _reject_delivery_cleaned(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            delivery_status=delivery_status,
            signal_error=signal_error,
            target_actor_address=target_payload,
        )

    reply_to_message = request["reply_to_message"]
    reply_to_updated: dict[str, Any] | None = None
    if reply_to_message is not None:
        original_previous_disposition = str(reply_to_message.get("disposition") or "unseen")
        try:
            updated_reply_to = context.rules.message.transition_message_disposition(
                message=reply_to_message,
                active_actor_address=context.actor_address,
                disposition="replied",
                reason=None,
                now=context.repos.runtime_files.now_iso(),
            )
        except (context.rules.message.MessagePayloadError, context.rules.message.MessageScopeError) as exc:
            return _reject_scope(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                code=getattr(exc, "code", "E_MESSAGE_SCOPE"),
                message=str(exc),
                permission_boundary=getattr(exc, "permission_boundary", "message.disposition"),
                human_summary=getattr(exc, "human_summary", "Message disposition transition failed."),
                why_blocked=getattr(exc, "why_blocked", str(exc)),
                retryable=getattr(exc, "retryable", False),
                correctable_fields=getattr(exc, "correctable_fields", ["reply_to"]),
            )
        try:
            reply_to_updated = _run_message_mutation_with_retry(
                lambda: context.repos.message.save_message(updated_reply_to)
            )
        except Exception as exc:
            final_message = context.repos.message.get_message(reply_to_message["id"]) or reply_to_message
            original_final_disposition = str(final_message.get("disposition") or original_previous_disposition)
            return tool_results.rejection(
                tool="message",
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                code="E_MESSAGE_REPLY_DISPOSITION_SAVE_FAILED",
                message=str(exc),
                permission_boundary="message.reply_disposition",
                human_summary="Reply was delivered, but the original message disposition could not be saved.",
                why_blocked="The reply message is durable and delivered, but saving the original message as replied failed.",
                impact="The reply exists and was delivered; the original message remains in its previous disposition.",
                state_changed=True,
                durability="durable",
                retryable=True,
                retry_guidance="Do not blindly send another reply. Inspect the original message state before deciding whether any follow-up is needed.",
                allowed_next_actions=[
                    "Use message.get to inspect the original processable message if it is still available.",
                    "Use message.conversation to inspect whether the delivered reply already covers the message.",
                ],
                extra={
                    "message_id": message["id"],
                    "reply_message_id": message["id"],
                    "delivery_status": "delivered",
                    "reply_to": request["reply_to"],
                    "original_message_id": reply_to_message["id"],
                    "original_previous_disposition": original_previous_disposition,
                    "original_final_disposition": original_final_disposition,
                    "target_actor_address": target_payload,
                },
            )

    handling_status = delivery.get("handling_status") if isinstance(delivery.get("handling_status"), str) else None
    state_changes = [{"object_type": "message", "change": "sent", "message_id": message["id"]}]
    extra: dict[str, Any] = {
        "message_id": message["id"],
        "delivery_status": "delivered",
        "handling_status": handling_status,
        "target_actor_address": target_payload,
    }
    updated_ids: list[str] | None = None
    if reply_to_message is not None and reply_to_updated is not None:
        state_changes.append(
            {
                "object_type": "message",
                "change": "marked_replied",
                "message_id": reply_to_updated["id"],
            }
        )
        updated_ids = [reply_to_updated["id"]]
        extra.update(
            {
                "reply_to": request["reply_to"],
                "original_message_id": reply_to_updated["id"],
                "original_previous_disposition": original_previous_disposition,
                "original_final_disposition": reply_to_updated["disposition"],
                "original_message": reply_to_updated,
            }
        )
    return tool_results.success(
        tool="message",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        effect_summary=(
            f"Sent one durable direct message from actor "
            f"'{source_actor_address.actor_id}' to '{target_actor.actor_id}'."
        ),
        state_changed=True,
        durability="durable",
        created_ids=[message["id"]],
        updated_ids=updated_ids,
        state_changes=state_changes,
        allowed_next_actions=[
            "Use message.list to inspect delivered inbox messages when needed.",
        ],
        extra=extra,
    )


def get_message(*, args: dict[str, Any], context: MessageServiceContext) -> dict[str, Any]:
    action = "message.get"
    active_actor = context["active_actor"]
    active_role = context["active_role"]
    manifest_roles = _manifest_role_ids(context)

    try:
        context.rules.message.ensure_active_role_is_manifest_declared(
            active_role=active_role,
            manifest_role_ids=manifest_roles,
        )
        request = context.rules.message.prepare_get_request(
            args=args,
            allowed_fields=_allowed_fields("get"),
        )
        message = context.rules.message.ensure_processable_inbound_message(
            message_id=request["message_id"],
            message=context.repos.message.get_message(request["message_id"]),
            active_actor_address=context.actor_address,
        )
    except context.rules.message.MessagePayloadError as exc:
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
        )
    except context.rules.message.MessageScopeError as exc:
        return _reject_scope(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            code=exc.code,
            message=str(exc),
            permission_boundary=exc.permission_boundary,
            human_summary=exc.human_summary,
            why_blocked=exc.why_blocked,
            retryable=exc.retryable,
            correctable_fields=exc.correctable_fields,
        )

    return tool_results.success(
        tool="message",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        effect_summary=f"Returned exact message '{message['id']}' for active actor '{context.actor_address.actor_id}'.",
        state_changed=False,
        durability="none",
        read_scope="active actor exact processable inbound message",
        allowed_next_actions=[
            "Use message.send with reply_to to reply.",
            "Use message.mark to finish without a reply.",
        ],
        extra={
            "message_id": message["id"],
            "message": message,
            "from_actor_address": message["from_actor_address"],
            "to_actor_address": message["to_actor_address"],
            "reply_to": message["reply_to"],
            "disposition": message["disposition"],
            "disposition_reason": message["disposition_reason"],
            "disposition_updated_at": message["disposition_updated_at"],
            "processed_by_actor_address": message["processed_by_actor_address"],
        },
    )


def mark_message(*, args: dict[str, Any], context: MessageServiceContext) -> dict[str, Any]:
    action = "message.mark"
    active_actor = context["active_actor"]
    active_role = context["active_role"]
    manifest_roles = _manifest_role_ids(context)

    try:
        context.rules.message.ensure_active_role_is_manifest_declared(
            active_role=active_role,
            manifest_role_ids=manifest_roles,
        )
        request = context.rules.message.prepare_mark_request(
            args=args,
            allowed_fields=_allowed_fields("mark"),
        )
        current_message = context.rules.message.ensure_processable_inbound_message(
            message_id=request["message_id"],
            message=context.repos.message.get_message(request["message_id"]),
            active_actor_address=context.actor_address,
        )
        updated_message = context.rules.message.transition_message_disposition(
            message=current_message,
            active_actor_address=context.actor_address,
            disposition=request["disposition"],
            reason=request["reason"],
            now=context.repos.runtime_files.now_iso(),
        )
    except context.rules.message.MessagePayloadError as exc:
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
        )
    except context.rules.message.MessageScopeError as exc:
        return _reject_scope(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            code=exc.code,
            message=str(exc),
            permission_boundary=exc.permission_boundary,
            human_summary=exc.human_summary,
            why_blocked=exc.why_blocked,
            retryable=exc.retryable,
            correctable_fields=exc.correctable_fields,
        )

    parent_request: dict[str, Any] | None = None
    if request["disposition"] == "needs_parent":
        original_previous_disposition = str(current_message.get("disposition") or "unseen")
        prompt = context.rules.message.render_parent_required_prompt(
            request["message_id"],
            current_message["from_actor_address"],
            current_message["to_actor_address"],
            request["reason"] or "",
        )
        try:
            parent_request = _run_message_mutation_with_retry(
                lambda: context.daemon.request_parent_message_handling(
                    message_id=request["message_id"],
                    prompt=prompt,
                )
            )
        except Exception as exc:
            final_message = context.repos.message.get_message(request["message_id"]) or current_message
            original_final_disposition = str(final_message.get("disposition") or original_previous_disposition)
            return tool_results.rejection(
                tool="message",
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                code="E_MESSAGE_PARENT_REQUIRED_SUBMIT_FAILED",
                message=str(exc),
                permission_boundary="message.needs_parent_runtime",
                human_summary="Parent-required message handoff failed.",
                why_blocked="The parent prompt could not be submitted, so the message was not marked needs_parent.",
                impact="No message disposition changed; the original message remains in its previous disposition.",
                state_changed=False,
                durability="none",
                retryable=True,
                retry_guidance="Retry message.mark(needs_parent) after parent runtime availability is restored.",
                allowed_next_actions=[
                    "Use message.get to inspect the original processable message.",
                ],
                extra={
                    "message_id": current_message["id"],
                    "original_message_id": current_message["id"],
                    "original_previous_disposition": original_previous_disposition,
                    "original_final_disposition": original_final_disposition,
                    "parent_prompt_submitted": False,
                    "message": final_message,
                },
            )
        try:
            saved_message = _run_message_mutation_with_retry(
                lambda: context.repos.message.save_message(updated_message)
            )
        except Exception as exc:
            final_message = context.repos.message.get_message(request["message_id"]) or current_message
            original_final_disposition = str(final_message.get("disposition") or original_previous_disposition)
            return tool_results.rejection(
                tool="message",
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                code="E_MESSAGE_NEEDS_PARENT_DISPOSITION_SAVE_FAILED",
                message=str(exc),
                permission_boundary="message.needs_parent_disposition",
                human_summary="Parent prompt was submitted, but the message disposition could not be saved.",
                why_blocked="The parent prompt was submitted, but the needs_parent disposition save failed.",
                impact="Parent handling was requested; the original message remains in its previous disposition.",
                state_changed=True,
                durability="durable",
                retryable=True,
                retry_guidance="Inspect message state before repeating the parent handoff; the parent prompt was already submitted.",
                allowed_next_actions=[
                    "Use message.get to inspect the original processable message if it is still available.",
                    "Inspect parent runtime state before repeating message.mark(needs_parent).",
                ],
                extra={
                    "message_id": current_message["id"],
                    "original_message_id": current_message["id"],
                    "original_previous_disposition": original_previous_disposition,
                    "original_final_disposition": original_final_disposition,
                    "parent_prompt_submitted": True,
                    "parent_request": parent_request,
                    "message": final_message,
                },
            )
    else:
        try:
            saved_message = context.repos.message.save_message(updated_message)
        except (ValueError, OSError) as exc:
            return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message=str(exc))

    state_change = {
        "object_type": "message",
        "change": f"marked_{saved_message['disposition']}",
        "message_id": saved_message["id"],
    }
    extra: dict[str, Any] = {
        "message_id": saved_message["id"],
        "disposition": saved_message["disposition"],
        "message": saved_message,
        "disposition_reason": saved_message["disposition_reason"],
        "disposition_updated_at": saved_message["disposition_updated_at"],
        "processed_by_actor_address": saved_message["processed_by_actor_address"],
    }
    if parent_request is not None:
        extra["parent_request"] = parent_request
        extra["parent_prompt_submitted"] = True
    return tool_results.success(
        tool="message",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        effect_summary=f"Marked message '{saved_message['id']}' as {saved_message['disposition']}.",
        state_changed=True,
        durability="durable",
        state_changes=[state_change],
        allowed_next_actions=[
            "Finish after this disposition path succeeds.",
        ],
        extra=extra,
    )


def list_messages(*, args: dict[str, Any], context: MessageServiceContext) -> dict[str, Any]:
    action = "message.list"
    active_actor = context["active_actor"]
    active_role = context["active_role"]
    manifest_roles = _manifest_role_ids(context)

    try:
        context.rules.message.ensure_active_role_is_manifest_declared(
            active_role=active_role,
            manifest_role_ids=manifest_roles,
        )
        request = context.rules.message.prepare_list_request(
            args=args,
            manifest_role_ids=manifest_roles,
            allowed_fields=_allowed_fields("list"),
        )
    except context.rules.message.MessagePayloadError as exc:
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
        )
    except context.rules.message.MessageScopeError as exc:
        return _reject_scope(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
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
        sender_role=request["role"],
        q=request["q"],
        limit=request["limit"],
    )

    return tool_results.success(
        tool="message",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        effect_summary=f"Returned {len(inbox)} inbox message(s) for active actor '{context.actor_address.actor_id}'.",
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
                    "role": request["role"],
                    "q": request["q"],
                    "limit": request["limit"],
                },
            },
        },
    )


def conversation_messages(*, args: dict[str, Any], context: MessageServiceContext) -> dict[str, Any]:
    action = "message.conversation"
    active_actor = context["active_actor"]
    active_role = context["active_role"]
    manifest_roles = _manifest_role_ids(context)

    try:
        context.rules.message.ensure_active_role_is_manifest_declared(
            active_role=active_role,
            manifest_role_ids=manifest_roles,
        )
        request = context.rules.message.prepare_conversation_request(
            args=args,
            source_actor_address=context.actor_address,
            manifest_role_ids=manifest_roles,
            allowed_fields=_allowed_fields("conversation"),
        )
    except context.rules.message.MessagePayloadError as exc:
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
        )
    except context.rules.message.MessageScopeError as exc:
        return _reject_scope(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            code=exc.code,
            message=str(exc),
            permission_boundary=exc.permission_boundary,
            human_summary=exc.human_summary,
            why_blocked=exc.why_blocked,
            retryable=exc.retryable,
            correctable_fields=exc.correctable_fields,
        )

    target_actor = request["target_actor_address"]
    messages = context.rules.message.filter_conversation_messages(
        messages=context.repos.message.list_messages(),
        active_actor_address=context.actor_address,
        target_actor_address=target_actor,
        q=request["q"],
        limit=request["limit"],
    )
    selector: dict[str, Any] = {"target_actor_address": target_actor.to_payload()}

    return tool_results.success(
        tool="message",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        effect_summary=f"Returned {len(messages)} visible conversation message(s) for active actor '{context.actor_address.actor_id}'.",
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
    'get': get_message,
    'list': list_messages,
    'mark': mark_message,
    'send': send_message,
}


def invoke(*, action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"unsupported action: {action}")
    return handler(args=args, context=context)
