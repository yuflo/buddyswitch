#!/usr/bin/env python3
"""search env.tool contract."""

from __future__ import annotations

from typing import Any

from env.tools.model import MUTATES_BROWSER_SESSION, MUTATES_NONE

TOOL_ID = "search"

TOOL_SPEC: dict[str, Any] = {
    "tool": TOOL_ID,
    "cli_resource": "search",
    "command": "python3 scripts/env/client.py search <operation>",
    "scope": "runtime-visible search capability boundary",
    "backend_model": {
        "allowed_backends": ["browser", "search_api"],
        "allowed_engines": ["google", "web", "reddit", "x"],
        "native_codex_web_search": "disabled",
        "search_api_provider": "not-configured",
    },
    "actions": [
        {
            "name": "status",
            "payload_fields": [],
            "kind": "read",
            "mutates": MUTATES_NONE,
            "required_permission": "none",
            "authority": "profile.search_boundary",
            "preconditions": ["active instance is available"],
            "returns": ["backend_status"],
        },
        {
            "name": "request",
            "payload_fields": ["query", "backend", "engine"],
            "kind": "request",
            "mutates": MUTATES_NONE,
            "required_permission": "none",
            "authority": "profile.search_boundary",
            "preconditions": ["query is non-empty"],
            "returns": ["target_url", "backend", "engine"],
        },
        {
            "name": "open_browser",
            "payload_fields": ["query", "engine"],
            "kind": "open",
            "mutates": MUTATES_BROWSER_SESSION,
            "required_permission": "none",
            "authority": "profile.search_boundary",
            "preconditions": ["query is non-empty"],
            "returns": ["target_url", "backend", "engine"],
        },
    ],
}
