"""Message-owned daemon inbound registration."""

from __future__ import annotations

from pathlib import Path
import sys


HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import im_wake_handler  # noqa: E402
import notification_center  # noqa: E402


IM_MESSAGE_CREATED_EVENT_TYPE = "im.message.created"
IM_MESSAGE_CREATED_PAYLOAD_CONTRACT = {"required_fields": ("message_id", "conversation_id", "event_id")}
OWNER_MODULE = "message_inbound"


def im_message_created_registration() -> notification_center.InboundSourceRegistration:
    return notification_center.InboundSourceRegistration(
        event_type=IM_MESSAGE_CREATED_EVENT_TYPE,
        payload_contract=IM_MESSAGE_CREATED_PAYLOAD_CONTRACT,
        handler_factory=im_wake_handler.ImMessageCreatedHandler,
        owner_module=OWNER_MODULE,
    )


def inbound_registrations() -> list[notification_center.InboundSourceRegistration]:
    return [im_message_created_registration()]


if __name__ == "__main__":
    raise SystemExit("message_inbound is not a standalone command")
