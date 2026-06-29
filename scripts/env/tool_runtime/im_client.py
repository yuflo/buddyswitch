#!/usr/bin/env python3
"""Actor-side projection client for the Central IM product service."""

from __future__ import annotations

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
            actor_address = ActorAddress.from_payload(row["actor_address"]).to_payload()
            actors.append(
                {
                    "identity": {"id": actor_address["actor_id"], "type": "actor"},
                    "identity_id": actor_address["actor_id"],
                    "role_id": actor_address["role_id"],
                    "reachability_status": row.get("status") if isinstance(row.get("status"), str) else "online",
                }
            )
        return {"ok": True, "action": "message.contacts", "actors": actors, "count": len(actors)}

    def send(self, args: dict[str, Any]) -> dict[str, Any]:
        target_response = self._target_participant(args.get("target_identity_id"), require_reachable_actor=True)
        if target_response.get("ok") is not True:
            if isinstance(args.get("reply_to"), str):
                target = None
            else:
                return target_response
        else:
            target = target_response["participant"]
        return message_service.send_im_message(
            sender_participant=self._actor,
            to=target if isinstance(target, dict) else None,
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
        target_response = self._target_participant(args.get("target_identity_id"), require_reachable_actor=False)
        if target_response.get("ok") is not True:
            return target_response
        return message_service.get_im_direct_conversation(
            participant=self._actor,
            target=target_response["participant"],
            limit=args.get("limit") if isinstance(args.get("limit"), int) else 20,
        )

    def mark(self, args: dict[str, Any]) -> dict[str, Any]:
        if args.get("disposition") == "needs_parent":
            return self._reject_message_payload(
                message="needs_parent message disposition was replaced by task_sys.need_parent from a task_sys.side_frame",
                correctable_fields=["disposition"],
            )
        return message_service.update_im_disposition(
            participant=self._actor,
            message_id=str(args.get("message_id") or ""),
            disposition=str(args.get("disposition") or ""),
            reason=args.get("reason") if isinstance(args.get("reason"), str) else None,
        )

    def _wake_actor(self, payload: dict[str, Any]) -> dict[str, Any]:
        wake = getattr(self._context.daemon, "wake_im_actor", None)
        if callable(wake):
            return wake(payload)
        return {"wake_status": "submitted", "runtime_target": "parent", "error": None}

    def _target_participant(self, value: Any, *, require_reachable_actor: bool) -> dict[str, Any]:
        identity_id = value.strip() if isinstance(value, str) and value.strip() else ""
        if not identity_id:
            return {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "target_identity_id is required"}}
        if identity_id == self._active_actor_payload().get("actor_id"):
            return {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "target_identity_id must not be the active actor identity"}}

        if not require_reachable_actor:
            from env.repos import messages as message_repo

            external = message_repo.get_im_external_participant(identity_id)
            if external is not None:
                return {"ok": True, "participant": external}

        actor = self._actor_participant_for_identity(identity_id)
        if actor is None:
            return {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": f"target_identity_id is not a reachable actor identity: {identity_id}"}}
        return {"ok": True, "participant": actor}

    def _actor_participant_for_identity(self, identity_id: str) -> dict[str, Any] | None:
        list_contacts = getattr(self._context.daemon, "list_contacts", None)
        if not callable(list_contacts):
            return None
        try:
            raw = list_contacts(role_id=None)
        except Exception:
            return None
        rows = raw.get("contacts") if isinstance(raw, dict) and isinstance(raw.get("contacts"), list) else []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("actor_address"), dict):
                continue
            try:
                actor_address = ActorAddress.from_payload(row["actor_address"]).to_payload()
            except ValueError:
                continue
            if actor_address["actor_id"] == identity_id:
                return {"kind": "actor", "actor_address": actor_address}
        return None

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
