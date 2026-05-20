#!/usr/bin/env python3
"""artifact env.tool handlers."""

from __future__ import annotations

HandlerSpec = tuple[str, str]

HANDLER_SPECS: dict[str, HandlerSpec] = {
    "get": ("env.tools.artifact.service", "get_artifact_for_active_buddy"),
    "create_revision": ("env.tools.artifact.service", "create_artifact_revision"),
    "update_metadata": ("env.tools.artifact.service", "update_artifact_metadata"),
}
