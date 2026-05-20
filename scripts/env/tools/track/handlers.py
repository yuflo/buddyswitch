#!/usr/bin/env python3
"""track env.tool handlers."""

from __future__ import annotations

HandlerSpec = tuple[str, str]

HANDLER_SPECS: dict[str, HandlerSpec] = {
    "create": ("env.tools.track.service", "create_track_for_pm"),
    "list": ("env.tools.track.service", "list_tracks_for_active_buddy"),
    "open": ("env.tools.track.service", "open_track_for_active_buddy"),
    "update_now": ("env.tools.track.service", "update_now_for_active_buddy"),
    "add_material": ("env.tools.track.service", "add_material_to_track"),
    "add_update": ("env.tools.track.service", "add_update_to_track"),
    "add_proof": ("env.tools.track.service", "add_proof_to_track"),
    "archive": ("env.tools.track.service", "archive_track_for_pm"),
}
