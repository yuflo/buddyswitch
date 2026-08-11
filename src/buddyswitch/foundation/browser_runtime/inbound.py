"""Browser-owned daemon inbound registration."""

from __future__ import annotations

from pathlib import Path
import sys



from buddyswitch.foundation.browser_runtime import page_handlers  # noqa: E402
from buddyswitch.foundation.browser_runtime import release_handler  # noqa: E402
from buddyswitch.foundation.daemon import inbound  # noqa: E402


BROWSER_PAGE_EXPIRED_EVENT_TYPE = "browser.page.expired"
BROWSER_PAGE_EXPIRED_PAYLOAD_CONTRACT = {
    "required_fields": ("tab_target_id", "idle_seconds"),
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


def browser_page_expired_registration() -> inbound.InboundSourceRegistration:
    return inbound.InboundSourceRegistration(
        event_type=BROWSER_PAGE_EXPIRED_EVENT_TYPE,
        payload_contract=BROWSER_PAGE_EXPIRED_PAYLOAD_CONTRACT,
        handler_factory=page_handlers.BrowserPageExpiredHandler,
        owner_module=OWNER_MODULE,
    )


def browser_cockpit_release_registration() -> inbound.InboundSourceRegistration:
    return inbound.InboundSourceRegistration(
        event_type=BROWSER_COCKPIT_RELEASE_EVENT_TYPE,
        payload_contract=BROWSER_COCKPIT_RELEASE_PAYLOAD_CONTRACT,
        handler_factory=release_handler.BrowserReleaseHandler,
        owner_module=OWNER_MODULE,
    )


def browser_failed_open_page_cleanup_registration() -> inbound.InboundSourceRegistration:
    return inbound.InboundSourceRegistration(
        event_type=BROWSER_FAILED_OPEN_PAGE_CLEANUP_EVENT_TYPE,
        payload_contract=BROWSER_FAILED_OPEN_PAGE_CLEANUP_PAYLOAD_CONTRACT,
        handler_factory=page_handlers.BrowserFailedOpenPageCleanupHandler,
        owner_module=OWNER_MODULE,
    )


def inbound_registrations() -> list[inbound.InboundSourceRegistration]:
    return [
        browser_page_expired_registration(),
        browser_cockpit_release_registration(),
        browser_failed_open_page_cleanup_registration(),
    ]


if __name__ == "__main__":
    raise SystemExit("browser inbound registrations are not a standalone command")
