#!/usr/bin/env python3
"""context env.tool handlers."""

from __future__ import annotations

HandlerSpec = tuple[str, str]

HANDLER_SPECS: dict[str, HandlerSpec] = {
    "get": ("env.tools.context.service", "get_context"),
    "summarize": ("env.tools.context.service", "summarize_context"),
    "list_sources": ("env.tools.context.service", "list_sources"),
}
