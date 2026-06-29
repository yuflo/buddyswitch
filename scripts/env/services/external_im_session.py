#!/usr/bin/env python3
"""External IM Session application boundary."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from env.services import messages as message_service
from env.tool_runtime.actor_profile import ActorAddress


ActorLister = Callable[[str | None], list[dict[str, Any]]]
WakeActor = Callable[[dict[str, Any]], dict[str, Any]]
BLOCKED_ACTOR_STATUSES = {"offline", "registered_offline", "inactive", "unreachable", "target_not_online"}


def _payload_error(message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": message}}


def _auth_error(message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": "E_IM_AUTH", "message": message}}


def _external_participant_from_connection(connection: dict[str, Any]) -> dict[str, Any]:
    identity_id = connection.get("identity_id")
    if isinstance(identity_id, str) and identity_id.strip():
        return {"ok": True, "participant": {"kind": "external", "external_id": identity_id.strip()}}
    participant = connection.get("participant")
    if isinstance(participant, dict):
        external_id = participant.get("external_id")
        if isinstance(external_id, str) and external_id.strip():
            return {"ok": True, "participant": {"kind": "external", "external_id": external_id.strip()}}
    return _auth_error("connection.identity_id must be a non-empty string")


class ExternalImSession:
    def __init__(
        self,
        *,
        actor_lister: ActorLister | None = None,
        wake_actor: WakeActor | None = None,
    ) -> None:
        self._actor_lister = actor_lister or (lambda _role_id: [])
        self._wake_actor = wake_actor or (lambda _payload: {"wake_status": "submitted"})

    def create_connection(self, *, display_name: str) -> dict[str, Any]:
        return message_service.create_external_connection(display_name=display_name)

    def authenticate(self, connection_key: str) -> dict[str, Any]:
        return message_service.authenticate_external_connection_key(connection_key)

    def list_actors(self, *, role_id: str | None = None) -> dict[str, Any]:
        actors: list[dict[str, Any]] = []
        for row in self._actor_lister(role_id):
            actor_address = row.get("actor_address") if isinstance(row, dict) else None
            if not isinstance(actor_address, dict):
                continue
            try:
                normalized_address = ActorAddress.from_payload(actor_address).to_payload()
            except ValueError:
                continue
            status = row.get("status") if isinstance(row.get("status"), str) else "online"
            if status in BLOCKED_ACTOR_STATUSES:
                continue
            actors.append(
                {
                    "identity": {"id": normalized_address["actor_id"], "type": "actor"},
                    "identity_id": normalized_address["actor_id"],
                    "role_id": normalized_address["role_id"],
                    "reachability_status": status,
                }
            )
        return {"ok": True, "actors": actors, "count": len(actors)}

    def send_message(
        self,
        *,
        connection: dict[str, Any],
        target_identity_id: Any,
        content: str,
        reply_to: Any = None,
    ) -> dict[str, Any]:
        target_response = self._actor_participant_for_identity(target_identity_id, field="target_identity_id")
        if target_response.get("ok") is not True:
            return target_response
        return message_service.send_external_connection_message(
            connection=connection,
            to=target_response["participant"],
            content=content,
            reply_to=reply_to if reply_to is not None else None,
            wake_actor=self._wake_actor,
        )

    def read_events(self, *, connection: dict[str, Any], limit: int = 50, wait_ms: int = 0) -> dict[str, Any]:
        return message_service.read_external_connection_events(
            connection=connection,
            limit=limit,
            wait_ms=wait_ms,
        )

    def get_direct_conversation(
        self,
        *,
        connection: dict[str, Any],
        identity_id: Any,
        limit: int = 20,
    ) -> dict[str, Any]:
        participant_response = _external_participant_from_connection(connection)
        if participant_response.get("ok") is not True:
            return participant_response
        target_response = self._actor_participant_for_identity(identity_id, field="identity_id")
        if target_response.get("ok") is not True:
            return target_response
        return message_service.get_im_direct_conversation(
            participant=participant_response["participant"],
            target=target_response["participant"],
            limit=limit,
        )

    def get_message(self, *, connection: dict[str, Any], message_id: str) -> dict[str, Any]:
        participant_response = _external_participant_from_connection(connection)
        if participant_response.get("ok") is not True:
            return participant_response
        return message_service.get_im_message(
            participant=participant_response["participant"],
            message_id=message_id,
        )

    def list_replies(self, *, connection: dict[str, Any], message_id: str) -> dict[str, Any]:
        participant_response = _external_participant_from_connection(connection)
        if participant_response.get("ok") is not True:
            return participant_response
        return message_service.list_im_replies(
            participant=participant_response["participant"],
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
        participant_response = _external_participant_from_connection(connection)
        if participant_response.get("ok") is not True:
            return participant_response
        return message_service.update_im_disposition(
            participant=participant_response["participant"],
            message_id=message_id,
            disposition=disposition,
            reason=reason,
        )

    def _actor_participant_for_identity(self, value: Any, *, field: str) -> dict[str, Any]:
        identity_id = value.strip() if isinstance(value, str) and value.strip() else ""
        if not identity_id:
            return _payload_error(f"{field} is required")
        for row in self._actor_lister(None):
            actor_address = row.get("actor_address") if isinstance(row, dict) else None
            if not isinstance(actor_address, dict):
                continue
            try:
                normalized_address = ActorAddress.from_payload(actor_address).to_payload()
            except ValueError:
                continue
            status = row.get("status") if isinstance(row.get("status"), str) else "online"
            if status in BLOCKED_ACTOR_STATUSES:
                continue
            if normalized_address["actor_id"] == identity_id:
                return {"ok": True, "participant": {"kind": "actor", "actor_address": normalized_address}}
        return _payload_error(f"{field} is not a reachable actor identity: {identity_id}")
