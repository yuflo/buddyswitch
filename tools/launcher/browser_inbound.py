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
import browser_release_handler  # noqa: E402
import notification_center  # noqa: E402


BROWSER_PAGE_EXPIRED_EVENT_TYPE = "browser.page.expired"
BROWSER_PAGE_EXPIRED_PAYLOAD_CONTRACT = {
    "required_fields": ("page_id",),
}
BROWSER_COCKPIT_RELEASE_EVENT_TYPE = "browser.cockpit.release"
BROWSER_COCKPIT_RELEASE_PAYLOAD_CONTRACT = {
    "required_fields": ("reason",),
}
BROWSER_FAILED_OPEN_PAGE_CLEANUP_EVENT_TYPE = "browser.failed_open_page.cleanup"
BROWSER_FAILED_OPEN_PAGE_CLEANUP_PAYLOAD_CONTRACT = {
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


def browser_cockpit_release_registration() -> notification_center.InboundSourceRegistration:
    return notification_center.InboundSourceRegistration(
        event_type=BROWSER_COCKPIT_RELEASE_EVENT_TYPE,
        payload_contract=BROWSER_COCKPIT_RELEASE_PAYLOAD_CONTRACT,
        handler_factory=browser_release_handler.BrowserReleaseHandler,
        owner_module=OWNER_MODULE,
    )


def browser_failed_open_page_cleanup_registration() -> notification_center.InboundSourceRegistration:
    return notification_center.InboundSourceRegistration(
        event_type=BROWSER_FAILED_OPEN_PAGE_CLEANUP_EVENT_TYPE,
        payload_contract=BROWSER_FAILED_OPEN_PAGE_CLEANUP_PAYLOAD_CONTRACT,
        handler_factory=browser_page_expired_handler.BrowserFailedOpenPageCleanupHandler,
        owner_module=OWNER_MODULE,
    )


def inbound_registrations() -> list[notification_center.InboundSourceRegistration]:
    return [
        browser_page_expired_registration(),
        browser_cockpit_release_registration(),
        browser_failed_open_page_cleanup_registration(),
    ]


if __name__ == "__main__":
    raise SystemExit("browser_inbound is not a standalone command")
