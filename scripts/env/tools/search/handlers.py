#!/usr/bin/env python3
"""search env.tool handlers."""

from __future__ import annotations

HandlerSpec = tuple[str, str]

HANDLER_SPECS: dict[str, HandlerSpec] = {
    "status": ("env.tools.search.service", "status_for_active_instance"),
    "request": ("env.tools.search.service", "request_for_active_instance"),
    "open_browser": ("env.tools.search.service", "open_browser_for_active_instance"),
}
