#!/usr/bin/env python3
"""search env.tool semantics."""

from __future__ import annotations

from typing import Any

CAPABILITY: dict[str, Any] = {
    "title": "Search Boundary",
    "plain_description": "Expose search backend metadata, URL planning, and browser open actions.",
    "use_when": ["You need runtime search boundary metadata or explicit browser search actions."],
    "do_not_use_when": ["You need durable product object mutation."],
    "capability_boundary": "Search actions remain inside configured profile backend and launcher browser boundaries.",
}


def _semantic(*, action: str, description: str, mutates: str, inputs: dict[str, str]) -> dict[str, Any]:
    return {
        "title": f"search.{action}",
        "plain_description": description,
        "use_when": [f"Use when search.{action} is required for explicit search boundary operations."],
        "do_not_use_when": ["Do not use for implicit automation outside profile boundaries."],
        "inputs_explained": inputs,
        "side_effects": {
            "mutates": mutates,
            "writes": ["browser session"] if mutates == "browser_session" else [],
            "does_not_write": ["tracks", "tasks", "artifacts"],
            "durability": "none" if mutates == "none" else "session",
            "idempotency": "idempotent read" if mutates == "none" else "non-idempotent open",
        },
        "risk_hints": {
            "read_only": mutates == "none",
            "destructive": False,
            "idempotent": mutates == "none",
            "open_world": True,
            "requires_human_approval": False,
            "external_effect": mutates == "browser_session",
        },
        "success_means": f"search.{action} completed within profile search capability boundaries.",
        "common_failures": ["query invalid", "engine invalid", "backend unavailable", "browser not ready"],
    }


ACTION_SEMANTICS: dict[str, dict[str, Any]] = {
    "status": _semantic(
        action="status",
        description="Read search capability and backend/browser readiness metadata.",
        mutates="none",
        inputs={},
    ),
    "request": _semantic(
        action="request",
        description="Resolve one explicit search target URL intent.",
        mutates="none",
        inputs={"query": "Non-empty query.", "backend": "Explicit backend.", "engine": "Optional engine."},
    ),
    "open_browser": _semantic(
        action="open_browser",
        description="Open one search URL through launcher-managed browser endpoint.",
        mutates="browser_session",
        inputs={"query": "Non-empty query.", "engine": "Optional engine."},
    ),
}
