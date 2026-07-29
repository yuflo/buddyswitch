"""Daemon trigger handler for Central IM runtime wake."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


from buddyswitch.launcher import daemon_contracts  # noqa: E402
from buddyswitch.env.repos import runtime_files  # noqa: E402
from buddyswitch.env.services import messages as message_service  # noqa: E402
from buddyswitch.modules.demand import public as demand_public  # noqa: E402


IM_MESSAGE_CREATED_EVENT_TYPE = "im.message.created"


def _context_identity_route(context: Any) -> dict[str, str]:
    return {
        "identity_id": runtime_files.require_id(getattr(context, "actor_id", ""), "context.actor_id"),
        "role_id": runtime_files.require_id(getattr(context, "role", ""), "context.role"),
    }


def _payload_id(trigger: Any, field: str) -> str:
    payload = getattr(trigger, "payload", None)
    if not isinstance(payload, dict):
        raise ValueError("IM wake payload must be an object")
    return runtime_files.require_id(payload.get(field), field)


def _service_row(response: Any, field: str) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise ValueError(f"IM {field} read returned a non-object response")
    if response.get("ok") is not True:
        error = response.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            raise ValueError(error["message"])
        raise ValueError(f"IM {field} read failed")
    row = response.get(field)
    if not isinstance(row, dict):
        raise ValueError(f"IM {field} read returned no {field} object")
    return row


def _actor_identity(actor_id: str) -> dict[str, str]:
    return {"id": runtime_files.require_id(actor_id, "actor identity id"), "type": "actor"}


class ImMessageCreatedHandler:
    name = "im_message_created"

    def handles(self, trigger: Any) -> bool:
        return getattr(trigger, "type", None) == IM_MESSAGE_CREATED_EVENT_TYPE

    def handle(
        self,
        context: Any,
        state: Any,
        runtime: Any,
        trigger: Any,
    ) -> Any:
        if not self.handles(trigger):
            return daemon_contracts.HandlerResult.ignored()
        try:
            local_route = _context_identity_route(context)
            target_route = {
                "identity_id": runtime_files.require_id(getattr(trigger, "target_identity_id", ""), "trigger.target_identity_id"),
                "role_id": runtime_files.require_id(getattr(trigger, "target_role_id", ""), "trigger.target_role_id"),
            }
            if target_route != local_route:
                raise PermissionError("wrong target identity for IM wake")
            message_id = _payload_id(trigger, "message_id")
            conversation_id = _payload_id(trigger, "conversation_id")
            event_id = _payload_id(trigger, "event_id")
            local_identity = _actor_identity(local_route["identity_id"])
            message = _service_row(
                message_service.get_im_message(
                    identity=local_identity,
                    message_id=message_id,
                ),
                "message",
            )
            event = _service_row(
                message_service.get_im_event(
                    identity=local_identity,
                    event_id=event_id,
                ),
                "event",
            )
            if message.get("id") != message_id:
                raise ValueError("IM message id does not match trigger")
            if message.get("conversation_id") != conversation_id:
                raise ValueError("IM message conversation does not match trigger")
            if message.get("target_identity") != local_identity:
                raise PermissionError("IM message target is not the local actor")
            if event.get("event_id") != event_id:
                raise ValueError("IM event id does not match trigger")
            if event.get("type") != "message.created":
                raise ValueError("IM event type must be message.created")
            if event.get("message_id") != message_id:
                raise ValueError("IM event message does not match trigger")
            if event.get("conversation_id") != conversation_id:
                raise ValueError("IM event conversation does not match trigger")
            if event.get("target_identity") != message.get("target_identity"):
                raise ValueError("IM event target does not match message target")
            if event.get("visible_to_identity_id") != local_route["identity_id"]:
                raise PermissionError("IM event is not visible to the local actor")
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("IM message content must be a non-empty string")
            normalized_content = content.strip()
            demand_public.enqueue_inbound(
                state,
                source_key=f"im.message.created:{message_id}",
                description=normalized_content,
                detail=normalized_content,
                source_refs=[{
                    "type": IM_MESSAGE_CREATED_EVENT_TYPE,
                    "ref": {
                        "message_id": message_id,
                        "conversation_id": conversation_id,
                        "event_id": event_id,
                    },
                }],
            )
            return daemon_contracts.HandlerResult.handled()
        except Exception as exc:
            return daemon_contracts.HandlerResult.failed(str(exc))


if __name__ == "__main__":
    raise SystemExit("im_wake_handler is not a standalone command")
