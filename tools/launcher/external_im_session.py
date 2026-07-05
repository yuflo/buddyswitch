#!/usr/bin/env python3
"""External IM Session application boundary."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Optional

from env.services import im_delivery
from env.services import messages as message_service


ActorLister = Callable[[Optional[str]], list[dict[str, Any]]]
ActorDeliveryHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _auth_error(message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": "E_IM_AUTH", "message": message}}


def _external_identity_from_connection(connection: dict[str, Any]) -> dict[str, Any]:
    identity_id = connection.get("identity_id")
    if isinstance(identity_id, str) and identity_id.strip():
        return {"ok": True, "identity": {"id": identity_id.strip(), "type": "external"}}
    return _auth_error("connection.identity_id must be a non-empty string")


class ExternalImSession:
    def __init__(
        self,
        *,
        actor_lister: ActorLister | None = None,
        actor_delivery_handler: ActorDeliveryHandler | None = None,
    ) -> None:
        self._actor_lister = actor_lister or (lambda _role_id: [])
        self._actor_delivery_handler = actor_delivery_handler

    def create_connection(self, *, display_name: str) -> dict[str, Any]:
        return message_service.create_external_connection(display_name=display_name)

    def authenticate(self, connection_key: str) -> dict[str, Any]:
        return message_service.authenticate_external_connection_key(connection_key)

    def list_actors(self, *, role_id: str | None = None) -> dict[str, Any]:
        return message_service.list_im_actor_contacts(self._actor_lister(role_id), role_id=role_id)

    def send_message(
        self,
        *,
        connection: dict[str, Any],
        target_identity_id: Any,
        content: str,
        reply_to: Any = None,
    ) -> dict[str, Any]:
        target_response = self._actor_target_identity(target_identity_id, field="target_identity_id")
        if target_response.get("ok") is not True:
            return target_response
        result = message_service.send_external_connection_message(
            connection=connection,
            target_identity=target_response["identity"],
            content=content,
            reply_to=reply_to if reply_to is not None else None,
        )
        result_target = result.get("target_identity")
        handling_target = (
            {"id": result_target["id"], "type": result_target["type"]}
            if isinstance(result_target, dict)
            and isinstance(result_target.get("id"), str)
            and isinstance(result_target.get("type"), str)
            else target_response["identity"]
        )
        return im_delivery.attach_post_write_delivery_status(
            result,
            target_identity=handling_target,
            actor_delivery_handler=self._actor_delivery_handler,
        )

    def read_events(self, *, connection: dict[str, Any], limit: int = 50, wait_ms: int = 0) -> dict[str, Any]:
        return message_service.read_external_connection_events(
            connection=connection,
            limit=limit,
            wait_ms=wait_ms,
        )

    def ack_event(self, *, connection: dict[str, Any], event_id: str) -> dict[str, Any]:
        return message_service.ack_external_connection_event(
            connection=connection,
            event_id=event_id,
        )

    def get_direct_conversation(
        self,
        *,
        connection: dict[str, Any],
        identity_id: Any,
        limit: int = 20,
    ) -> dict[str, Any]:
        identity_response = _external_identity_from_connection(connection)
        if identity_response.get("ok") is not True:
            return identity_response
        target_response = self._actor_target_identity(identity_id, field="identity_id")
        if target_response.get("ok") is not True:
            return target_response
        return message_service.get_im_direct_conversation(
            identity=identity_response["identity"],
            target=target_response["identity"],
            limit=limit,
        )

    def get_message(self, *, connection: dict[str, Any], message_id: str) -> dict[str, Any]:
        identity_response = _external_identity_from_connection(connection)
        if identity_response.get("ok") is not True:
            return identity_response
        return message_service.get_im_message(
            identity=identity_response["identity"],
            message_id=message_id,
        )

    def list_replies(self, *, connection: dict[str, Any], message_id: str) -> dict[str, Any]:
        identity_response = _external_identity_from_connection(connection)
        if identity_response.get("ok") is not True:
            return identity_response
        return message_service.list_im_replies(
            identity=identity_response["identity"],
            message_id=message_id,
        )

    def update_disposition(
        self,
        *,
        connection: dict[str, Any],
        message_id: str,
        disposition: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        identity_response = _external_identity_from_connection(connection)
        if identity_response.get("ok") is not True:
            return identity_response
        return message_service.update_im_disposition(
            identity=identity_response["identity"],
            message_id=message_id,
            disposition=disposition,
            reason=reason,
        )

    def _actor_target_identity(self, value: Any, *, field: str) -> dict[str, Any]:
        return message_service.identity_for_current_send_target(
            self._actor_lister(None),
            value,
            field=field,
        )
