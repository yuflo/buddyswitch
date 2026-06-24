#!/usr/bin/env python3
"""Public message send service."""

from __future__ import annotations

import time
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


def _manifest_role_ids(context: MessageSendContext) -> set[str]:
    return context.rules.message.manifest_role_ids(context.get("manifest"))


def _actor_address_from_any(context: MessageSendContext, value: Any) -> Any:
    if hasattr(value, "to_payload"):
        return value
    return context.rules.message.ActorAddress.from_payload(value)


def send_from_web_user(
    *,
    context: MessageSendContext,
    target_actor_address: dict[str, Any],
    content: str,
    web_user_actor_address: dict[str, Any],
    reply_to: str | None = None,
) -> dict[str, Any]:
    args: dict[str, Any] = {
        "target_actor_address": target_actor_address,
        "content": content,
    }
    if reply_to is not None:
        args["reply_to"] = reply_to
    return send_from_actor(
        args=args,
        context=context,
        source_actor_address=web_user_actor_address,
        active_actor=dict(web_user_actor_address),
        active_role=str(web_user_actor_address["role_id"]),
        require_active_role_manifest=False,
        action="message.send",
    )


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
    manifest_roles = _manifest_role_ids(context)
    source_actor = _actor_address_from_any(context, source_actor_address)

    try:
        if require_active_role_manifest:
            context.rules.message.ensure_active_role_is_manifest_declared(
                active_role=active_role,
                manifest_role_ids=manifest_roles,
            )
        request = context.rules.message.prepare_send_request(
            args=args,
            source_actor_address=source_actor,
            manifest_role_ids=manifest_roles,
            get_message=context.repos.message.get_message,
            allowed_fields=SEND_ALLOWED_FIELDS,
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
            from_actor_address=source_actor,
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
                active_actor_address=source_actor,
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
        "from_actor_address": source_actor.to_payload(),
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
            f"'{source_actor.actor_id}' to '{target_actor.actor_id}'."
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
