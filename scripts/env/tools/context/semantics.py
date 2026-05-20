#!/usr/bin/env python3
"""context env.tool semantics."""

from __future__ import annotations

from typing import Any

CAPABILITY: dict[str, Any] = {
    "title": "Context Discovery",
    "plain_description": "Read runtime orientation, compact affordances, full tool catalog, and operation semantics.",
    "use_when": ["You need runtime discovery and orientation before choosing write operations."],
    "do_not_use_when": ["You need to mutate product or private file state."],
    "capability_boundary": "Context actions are read-only and never grant write authority.",
}


def _semantic(*, action: str, description: str, inputs: dict[str, str]) -> dict[str, Any]:
    return {
        "title": f"context.{action}",
        "plain_description": description,
        "use_when": [f"Use when context.{action} is needed for runtime discovery."],
        "do_not_use_when": ["Do not use for state mutation."],
        "inputs_explained": inputs,
        "side_effects": {
            "mutates": "none",
            "writes": [],
            "does_not_write": ["tracks", "tasks", "artifacts", "buddybox files"],
            "durability": "none",
            "idempotency": "idempotent read",
        },
        "risk_hints": {
            "read_only": True,
            "destructive": False,
            "idempotent": True,
            "open_world": False,
            "requires_human_approval": False,
            "external_effect": False,
        },
        "success_means": f"context.{action} returned read-only runtime discovery payload.",
        "common_failures": ["payload validation failed"],
    }


ACTION_SEMANTICS: dict[str, dict[str, Any]] = {
    "get": _semantic(
        action="get",
        description="Return full runtime context sections with full tool catalog and operation semantics.",
        inputs={"track_id": "Optional track filter.", "task_id": "Optional task filter.", "limit": "Optional max rows."},
    ),
    "summarize": _semantic(
        action="summarize",
        description="Return compact runtime context orientation and first-pass affordances.",
        inputs={"track_id": "Optional track filter.", "task_id": "Optional task filter.", "limit": "Optional max rows."},
    ),
    "list_sources": _semantic(
        action="list_sources",
        description="Return context source descriptors only.",
        inputs={},
    ),
}
