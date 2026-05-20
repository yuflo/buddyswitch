#!/usr/bin/env python3
"""evidence env.tool handlers."""

from __future__ import annotations

HandlerSpec = tuple[str, str]

HANDLER_SPECS: dict[str, HandlerSpec] = {
    "issue_browser": ("env.tools.evidence.service", "issue_browser_for_active_instance"),
    "approve_downgrade": ("env.tools.evidence.service", "approve_downgrade_for_active_instance"),
}
