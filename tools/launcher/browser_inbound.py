#!/usr/bin/env python3
"""Browser-owned daemon inbound registration."""

from __future__ import annotations

from pathlib import Path
import sys


HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import browser_page_expired_handler  # noqa: E402
import notification_center  # noqa: E402


BROWSER_PAGE_EXPIRED_EVENT_TYPE = "browser.page.expired"
BROWSER_PAGE_EXPIRED_PAYLOAD_CONTRACT = {
    "required_fields": ("target_id",),
}
OWNER_MODULE = "browser_inbound"


def browser_page_expired_registration() -> notification_center.InboundSourceRegistration:
    return notification_center.InboundSourceRegistration(
        event_type=BROWSER_PAGE_EXPIRED_EVENT_TYPE,
        payload_contract=BROWSER_PAGE_EXPIRED_PAYLOAD_CONTRACT,
        handler_factory=browser_page_expired_handler.BrowserPageExpiredHandler,
        owner_module=OWNER_MODULE,
    )


def inbound_registrations() -> list[notification_center.InboundSourceRegistration]:
    return [browser_page_expired_registration()]


if __name__ == "__main__":
    raise SystemExit("browser_inbound is not a standalone command")
