#!/usr/bin/env python3
"""message env.tool handlers."""

from __future__ import annotations

HandlerSpec = tuple[str, str]

HANDLER_SPECS: dict[str, HandlerSpec] = {
    "send": ("env.tools.message.service", "send_message"),
    "list": ("env.tools.message.service", "list_messages"),
}
