#!/usr/bin/env python3
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

import message_available_handler  # noqa: E402
import notification_center  # noqa: E402


MESSAGE_AVAILABLE_EVENT_TYPE = "message.available"
MESSAGE_AVAILABLE_PAYLOAD_CONTRACT = {"required_fields": ("message_id",)}
OWNER_MODULE = "message_inbound"


def message_available_registration() -> notification_center.InboundSourceRegistration:
    return notification_center.InboundSourceRegistration(
        event_type=MESSAGE_AVAILABLE_EVENT_TYPE,
        payload_contract=MESSAGE_AVAILABLE_PAYLOAD_CONTRACT,
        handler_factory=message_available_handler.MessageAvailableHandler,
        owner_module=OWNER_MODULE,
    )


def inbound_registrations() -> list[notification_center.InboundSourceRegistration]:
    return [message_available_registration()]


if __name__ == "__main__":
    raise SystemExit("message_inbound is not a standalone command")
