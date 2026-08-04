"""Four exact Communication operations earned by current consumers."""

from __future__ import annotations

from typing import Any

from buddyswitch.modules.communication.private.domain import (
    messages as message_service,
)
from buddyswitch.modules.communication.private.state import (
    messages as message_state,
)


def get_im_message(
    *,
    identity: dict[str, Any],
    message_id: str,
) -> dict[str, Any]:
    return message_service.get_im_message(
        identity=identity,
        message_id=message_id,
    )


def list_im_replies(
    *,
    identity: dict[str, Any],
    message_id: str,
) -> dict[str, Any]:
    return message_service.list_im_replies(
        identity=identity,
        message_id=message_id,
    )


def send_im_message(
    *,
    sender_identity: dict[str, Any],
    target_identity: dict[str, Any],
    content: str,
    reply_to: str | None = None,
) -> dict[str, Any]:
    return message_service.send_im_message(
        sender_identity=sender_identity,
        target_identity=target_identity,
        content=content,
        reply_to=reply_to,
    )


def list_im_events_for_identity(
    identity: dict[str, Any] | str,
) -> list[dict[str, Any]]:
    return message_state.list_im_events_for_identity(identity)
