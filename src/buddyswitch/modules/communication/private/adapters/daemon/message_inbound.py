"""Communication-owned Daemon inbound registration."""

from __future__ import annotations

from typing import Any

from buddyswitch.launcher import notification_center  # noqa: E402
from buddyswitch.modules.communication.private.adapters.daemon import (
    im_wake_handler,
)  # noqa: E402


IM_MESSAGE_CREATED_EVENT_TYPE = "im.message.created"
IM_MESSAGE_CREATED_PAYLOAD_CONTRACT = {"required_fields": ("message_id", "conversation_id", "event_id")}
OWNER_MODULE = "communication"


def im_message_created_registration(
    enqueue_inbound: Any,
) -> notification_center.InboundSourceRegistration:
    def build_handler() -> im_wake_handler.ImMessageCreatedHandler:
        return im_wake_handler.ImMessageCreatedHandler(enqueue_inbound)

    return notification_center.InboundSourceRegistration(
        event_type=IM_MESSAGE_CREATED_EVENT_TYPE,
        payload_contract=IM_MESSAGE_CREATED_PAYLOAD_CONTRACT,
        handler_factory=build_handler,
        owner_module=OWNER_MODULE,
    )


def inbound_registrations(
    enqueue_inbound: Any,
) -> list[notification_center.InboundSourceRegistration]:
    return [im_message_created_registration(enqueue_inbound)]
