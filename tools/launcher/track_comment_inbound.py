"""Track-comment-owned daemon inbound registration."""

from __future__ import annotations

from pathlib import Path
import sys


HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import notification_center  # noqa: E402
import track_comment_added_handler  # noqa: E402


TRACK_COMMENT_ADDED_EVENT_TYPE = "track.comment.added"
TRACK_COMMENT_ADDED_PAYLOAD_CONTRACT = {"required_fields": ("track_id", "comment_id", "thread_id")}
OWNER_MODULE = "track_comment_inbound"


def track_comment_added_registration() -> notification_center.InboundSourceRegistration:
    return notification_center.InboundSourceRegistration(
        event_type=TRACK_COMMENT_ADDED_EVENT_TYPE,
        payload_contract=TRACK_COMMENT_ADDED_PAYLOAD_CONTRACT,
        handler_factory=track_comment_added_handler.TrackCommentAddedHandler,
        owner_module=OWNER_MODULE,
    )


def inbound_registrations() -> list[notification_center.InboundSourceRegistration]:
    return [track_comment_added_registration()]


if __name__ == "__main__":
    raise SystemExit("track_comment_inbound is not a standalone command")
