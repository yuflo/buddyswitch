"""Actor-side projection client for the Central IM product service."""

from __future__ import annotations

from typing import Any

from env.services import messages as message_service
from env.tool_runtime import results as tool_results


class ActorImClient:
    def __init__(self, context: Any) -> None:
        self._context = context
        self._identity = self._current_identity_payload()

    def contacts(self, args: dict[str, Any]) -> dict[str, Any]:
        role = args.get("role")
        try:
            actor_rows = self._online_actor_rows(role_id=role if isinstance(role, str) and role.strip() else None)
        except Exception as exc:
            return {"ok": False, "error": {"code": "E_IM_CONTACTS", "message": str(exc)}}
        response = message_service.list_im_actor_contacts(
            actor_rows,
            role_id=role if isinstance(role, str) and role.strip() else None,
        )
        if response.get("ok") is not True:
            return response
        return {
            "ok": True,
            "action": "message.contacts",
            "actors": response.get("actors") if isinstance(response.get("actors"), list) else [],
            "count": response.get("count") if isinstance(response.get("count"), int) else 0,
        }

    def send(self, args: dict[str, Any]) -> dict[str, Any]:
        target_identity_id = args.get("target_identity_id")
        reply_to = args.get("reply_to")
        has_target = isinstance(target_identity_id, str) and bool(target_identity_id.strip())
        has_reply = isinstance(reply_to, str) and bool(reply_to.strip())
        if has_target and has_reply:
            return {
                "ok": False,
                "error": {
                    "code": "E_IM_PAYLOAD",
                    "message": "message.send accepts either target_identity_id or reply_to, not both",
                },
            }
        explicit_target: dict[str, Any] | None = None
        if has_reply:
            result = message_service.send_im_reply(
                sender_identity=self._identity,
                reply_to=reply_to.strip(),
                content=str(args.get("content") or ""),
                actor_reachability_checker=self._context.actor_directory.check_reachability,
            )
        else:
            target_response = self._send_target_identity(target_identity_id)
            if target_response.get("ok") is not True:
                return target_response
            explicit_target = target_response["target_identity"]
            result = message_service.send_im_message(
                sender_identity=self._identity,
                target_identity=explicit_target,
                content=str(args.get("content") or ""),
            )
        return message_service.attach_post_write_delivery_status(
            result,
            target_identity=self._result_target_identity(result, explicit_target),
            actor_delivery_handler=self._context.im_actor_delivery.deliver,
        )

    def get(self, args: dict[str, Any]) -> dict[str, Any]:
        return message_service.get_im_message(
            identity=self._identity,
            message_id=str(args.get("message_id") or ""),
        )

    def list(self, args: dict[str, Any]) -> dict[str, Any]:
        return message_service.read_im_events(
            identity=self._identity,
            cursor=str(args.get("cursor") or "imev-000000000000"),
            limit=args.get("limit") if isinstance(args.get("limit"), int) else 20,
            wait_ms=0,
        )

    def conversation(self, args: dict[str, Any]) -> dict[str, Any]:
        target_response = self._conversation_target_identity(args.get("target_identity_id"))
        if target_response.get("ok") is not True:
            return target_response
        return message_service.get_im_direct_conversation(
            identity=self._identity,
            target=target_response["identity"],
            limit=args.get("limit") if isinstance(args.get("limit"), int) else 20,
        )

    def mark(self, args: dict[str, Any]) -> dict[str, Any]:
        if args.get("disposition") == "needs_parent":
            return self._reject_message_payload(
                message="needs_parent message disposition was replaced by task_sys.need_parent from a task_sys.side_frame",
                correctable_fields=["disposition"],
            )
        return message_service.update_im_disposition(
            identity=self._identity,
            message_id=str(args.get("message_id") or ""),
            disposition=str(args.get("disposition") or ""),
            reason=args.get("reason") if isinstance(args.get("reason"), str) else None,
        )

    def _send_target_identity(self, value: Any) -> dict[str, Any]:
        return message_service.resolve_im_send_target(
            sender_identity=self._identity,
            target_identity_id=value,
            actor_reachability_checker=self._context.actor_directory.check_reachability,
        )

    def _result_target_identity(self, result: dict[str, Any], explicit_target: dict[str, Any] | None) -> dict[str, Any] | None:
        if isinstance(explicit_target, dict):
            return explicit_target
        target = result.get("target_identity")
        if isinstance(target, dict) and isinstance(target.get("id"), str) and isinstance(target.get("type"), str):
            return {"id": target["id"], "type": target["type"]}
        return None

    def _conversation_target_identity(self, value: Any) -> dict[str, Any]:
        identity_id = value.strip() if isinstance(value, str) and value.strip() else ""
        if not identity_id:
            return {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "target_identity_id is required"}}
        if identity_id == self._current_identity_payload().get("id"):
            return {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "target_identity_id must not be the active actor identity"}}
        return message_service.identity_target_for_direct_conversation(identity_id)

    def _online_actor_rows(self, *, role_id: str | None) -> list[dict[str, Any]]:
        try:
            raw = self._context.actor_directory.list_online_actors(role_id=role_id)
        except Exception:
            return []
        return raw.get("actors") if isinstance(raw, dict) and isinstance(raw.get("actors"), list) else []

    def _reject_message_payload(self, *, message: str, correctable_fields: list[str]) -> dict[str, Any]:
        return tool_results.rejection(
            tool="message",
            action="message.mark",
            current_identity=self._current_identity_payload(),
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

    def _current_identity_payload(self) -> dict[str, Any]:
        value = self._context.get("current_identity") if hasattr(self._context, "get") else getattr(self._context, "current_identity", None)
        if isinstance(value, dict) and isinstance(value.get("id"), str) and isinstance(value.get("type"), str):
            return {"id": value["id"], "type": value["type"]}
        to_payload = getattr(value, "to_payload", None)
        if callable(to_payload):
            payload = to_payload()
            if isinstance(payload, dict) and isinstance(payload.get("id"), str) and isinstance(payload.get("type"), str):
                return {"id": payload["id"], "type": payload["type"]}
        raise ValueError("current identity is unavailable")

    def _active_role(self) -> str:
        role_id = self._context.get("active_role") if hasattr(self._context, "get") else getattr(self._context, "role_id", None)
        if isinstance(role_id, str) and role_id.strip():
            return role_id
        raise ValueError("active role is unavailable")
