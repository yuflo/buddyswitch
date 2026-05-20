#!/usr/bin/env python3
"""comment env.tool handlers."""

from __future__ import annotations

HandlerSpec = tuple[str, str]

HANDLER_SPECS: dict[str, HandlerSpec] = {
    "add": ("env.tools.comment.service", "add_comment"),
    "list": ("env.tools.comment.service", "list_comments"),
}
