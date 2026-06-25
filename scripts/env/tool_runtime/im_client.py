#!/usr/bin/env python3
"""Actor-side projection client for the Central IM product service."""

from __future__ import annotations

import json
from typing import Any

from env.services import messages as message_service
from env.tool_runtime import results as tool_results
from env.tool_runtime.actor_profile import ActorAddress


class ActorImClient:
    def __init__(self, context: Any) -> None:
        self._context = context
        self._actor = self._actor_participant()

    def _actor_participant(self) -> dict[str, Any]:
        value = getattr(self._context, "actor_address", None)
        if isinstance(value, ActorAddress):
            actor_address = value.to_payload()
        elif isinstance(value, dict):
            actor_address = ActorAddress.from_payload(value).to_payload()
        else:
            actor_payload = self._context.get("active_actor") if isinstance(self._context, dict) else None
            actor_address = ActorAddress.from_payload(actor_payload).to_payload()
        return {"kind": "actor", "actor_address": actor_address}

    def contacts(self, args: dict[str, Any]) -> dict[str, Any]:
        role = args.get("role")
        try:
            raw = self._context.daemon.list_contacts(role_id=role if isinstance(role, str) and role.strip() else None)
        except Exception as exc:
            return {"ok": False, "error": {"code": "E_IM_CONTACTS", "message": str(exc)}}
        rows = raw.get("contacts") if isinstance(raw, dict) and isinstance(raw.get("contacts"), list) else []
        actors = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("actor_address"), dict):
                continue
            actors.append(
                {
                    "participant": {"kind": "actor", "actor_address": dict(row["actor_address"])},
                    "reachability_status": row.get("status") if isinstance(row.get("status"), str) else "online",
                }
            )
        return {"ok": True, "action": "message.contacts", "actors": actors, "count": len(actors)}

    def send(self, args: dict[str, Any]) -> dict[str, Any]:
        target = args.get("target_actor_address")
        to = {"kind": "actor", "actor_address": target} if isinstance(target, dict) else target
        return message_service.send_im_message(
            sender_participant=self._actor,
            to=to if isinstance(to, dict) else {},
            content=str(args.get("content") or ""),
            reply_to=args.get("reply_to") if isinstance(args.get("reply_to"), str) else None,
            wake_actor=self._wake_actor,
        )

    def get(self, args: dict[str, Any]) -> dict[str, Any]:
        return message_service.get_im_message(
            participant=self._actor,
            message_id=str(args.get("message_id") or ""),
        )

    def list(self, args: dict[str, Any]) -> dict[str, Any]:
        return message_service.read_im_events(
            participant=self._actor,
            cursor=str(args.get("cursor") or "imev-000000000000"),
            limit=args.get("limit") if isinstance(args.get("limit"), int) else 20,
            wait_ms=0,
        )

    def conversation(self, args: dict[str, Any]) -> dict[str, Any]:
        target = args.get("target_actor_address")
        if not isinstance(target, dict):
            return {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "target_actor_address is required"}}
        return message_service.get_im_direct_conversation(
            participant=self._actor,
            target={"kind": "actor", "actor_address": target},
            limit=args.get("limit") if isinstance(args.get("limit"), int) else 20,
        )

    def mark(self, args: dict[str, Any]) -> dict[str, Any]:
        if args.get("disposition") == "needs_parent":
            return self._mark_needs_parent(args)
        return message_service.update_im_disposition(
            participant=self._actor,
            message_id=str(args.get("message_id") or ""),
            disposition=str(args.get("disposition") or ""),
            reason=args.get("reason") if isinstance(args.get("reason"), str) else None,
        )

    def _mark_needs_parent(self, args: dict[str, Any]) -> dict[str, Any]:
        from env.repos import messages as message_repo

        message_id = str(args.get("message_id") or "")
        reason = args.get("reason") if isinstance(args.get("reason"), str) else None
        if not reason or not reason.strip():
            return self._reject_message_payload(
                message="reason is required when disposition is needs_parent",
                correctable_fields=["reason"],
            )
        message_response = message_service.get_im_message(participant=self._actor, message_id=message_id)
        if message_response.get("ok") is not True:
            return message_response
        message = message_response["message"]
        current_state = message_repo.get_im_message_state(message_id, self._actor)
        if current_state is None:
            return {"ok": False, "error": {"code": "E_IM_SCOPE", "message": "participant has no state for this message"}}
        original_previous_disposition = str(current_state.get("disposition") or "unseen")
        prompt = self._render_parent_required_prompt(message=message, reason=reason.strip())
        try:
            parent_request = self._request_parent_message_handling(message_id=message_id, prompt=prompt)
        except Exception as exc:
            final_state = message_repo.get_im_message_state(message_id, self._actor) or current_state
            original_final_disposition = str(final_state.get("disposition") or original_previous_disposition)
            return tool_results.rejection(
                tool="message",
                action="message.mark",
                active_actor=self._active_actor_payload(),
                active_role=self._active_role(),
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
                    "message_id": message_id,
                    "original_message_id": message_id,
                    "original_previous_disposition": original_previous_disposition,
                    "original_final_disposition": original_final_disposition,
                    "parent_prompt_submitted": False,
                    "message": message,
                },
            )

        update_response = message_service.update_im_disposition(
            participant=self._actor,
            message_id=message_id,
            disposition="needs_parent",
            reason=reason.strip(),
        )
        if update_response.get("ok") is not True:
            final_state = message_repo.get_im_message_state(message_id, self._actor) or current_state
            original_final_disposition = str(final_state.get("disposition") or original_previous_disposition)
            return tool_results.rejection(
                tool="message",
                action="message.mark",
                active_actor=self._active_actor_payload(),
                active_role=self._active_role(),
                code="E_MESSAGE_NEEDS_PARENT_DISPOSITION_SAVE_FAILED",
                message=str((update_response.get("error") or {}).get("message") or "needs_parent disposition save failed"),
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
                    "message_id": message_id,
                    "original_message_id": message_id,
                    "original_previous_disposition": original_previous_disposition,
                    "original_final_disposition": original_final_disposition,
                    "parent_prompt_submitted": True,
                    "parent_request": parent_request,
                    "message": message,
                },
            )

        return tool_results.success(
            tool="message",
            action="message.mark",
            active_actor=self._active_actor_payload(),
            active_role=self._active_role(),
            effect_summary=f"Marked message '{message_id}' as needs_parent.",
            state_changed=True,
            durability="durable",
            updated_ids=[message_id],
            state_changes=[
                {
                    "object_type": "message",
                    "change": "marked_needs_parent",
                    "message_id": message_id,
                }
            ],
            allowed_next_actions=[
                "Finish after this disposition path succeeds.",
            ],
            extra={
                "message_id": message_id,
                "disposition": "needs_parent",
                "participant": self._actor,
                "parent_request": parent_request,
                "parent_prompt_submitted": True,
                "original_previous_disposition": original_previous_disposition,
            },
        )

    def _wake_actor(self, payload: dict[str, Any]) -> dict[str, Any]:
        wake = getattr(self._context.daemon, "wake_im_actor", None)
        if callable(wake):
            return wake(payload)
        return {"wake_status": "submitted", "runtime_target": "parent", "error": None}

    def _request_parent_message_handling(self, *, message_id: str, prompt: str) -> dict[str, Any]:
        request_parent = getattr(self._context.daemon, "request_parent_message_handling", None)
        if not callable(request_parent):
            raise RuntimeError("parent message handling is unavailable")
        return request_parent(message_id=message_id, prompt=prompt)

    def _render_parent_required_prompt(self, *, message: dict[str, Any], reason: str) -> str:
        from_participant = message.get("from") if isinstance(message.get("from"), dict) else {}
        to_participants = message.get("to") if isinstance(message.get("to"), list) else []
        return "\n\n".join(
            (
                "[MESSAGE NEEDS PARENT]",
                f"Message id: {message.get('id')}",
                f"From: {json.dumps(from_participant, ensure_ascii=True, sort_keys=True)}",
                f"To: {json.dumps(to_participants, ensure_ascii=True, sort_keys=True)}",
                f"Reason from side triage:\n{reason}",
                "A side thread reviewed this IM message and determined that parent processing is required.",
                "Required action:\nProcess this exact message. Do not assume a reply is required.",
                "Use only message tools to inspect, reply to, or mark this message.",
            )
        )

    def _reject_message_payload(self, *, message: str, correctable_fields: list[str]) -> dict[str, Any]:
        return tool_results.rejection(
            tool="message",
            action="message.mark",
            active_actor=self._active_actor_payload(),
            active_role=self._active_role(),
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
                "Use message.get to inspect the original processable message.",
            ],
            correctable_fields=correctable_fields,
        )

    def _active_actor_payload(self) -> dict[str, Any]:
        actor_address = self._actor.get("actor_address")
        if isinstance(actor_address, dict):
            return dict(actor_address)
        active_actor = self._context.get("active_actor") if isinstance(self._context, dict) else None
        if isinstance(active_actor, dict):
            return dict(active_actor)
        raise ValueError("active actor address is unavailable")

    def _active_role(self) -> str:
        active_actor = self._active_actor_payload()
        role_id = active_actor.get("role_id")
        if isinstance(role_id, str) and role_id.strip():
            return role_id
        raise ValueError("active role is unavailable")
