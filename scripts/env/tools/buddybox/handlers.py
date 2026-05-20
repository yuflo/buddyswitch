#!/usr/bin/env python3
"""buddybox env.tool handlers."""

from __future__ import annotations

HandlerSpec = tuple[str, str]

HANDLER_SPECS: dict[str, HandlerSpec] = {
    "desc": ("env.tools.buddybox.service", "describe_buddybox_for_active_buddy"),
    "list": ("env.tools.buddybox.service", "list_buddybox_for_active_buddy"),
    "read": ("env.tools.buddybox.service", "read_buddybox_for_active_buddy"),
    "write": ("env.tools.buddybox.service", "write_buddybox_for_active_buddy"),
    "delete": ("env.tools.buddybox.service", "delete_buddybox_for_active_buddy"),
}
