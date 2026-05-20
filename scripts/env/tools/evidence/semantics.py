#!/usr/bin/env python3
"""evidence env.tool semantics."""

from __future__ import annotations

from typing import Any

CAPABILITY: dict[str, Any] = {
    "title": "Market Evidence",
    "plain_description": "Issue target-scoped transient evidence token metadata for artifact quality gates.",
    "use_when": ["You need artifact-scoped evidence token metadata."],
    "do_not_use_when": ["You need durable runtime object mutation."],
    "capability_boundary": "Evidence actions are target-scoped and return transient token metadata.",
}


def _semantic(*, action: str, description: str, inputs: dict[str, str]) -> dict[str, Any]:
    return {
        "title": f"evidence.{action}",
        "plain_description": description,
        "use_when": [f"Use when evidence.{action} token metadata is required."],
        "do_not_use_when": ["Do not use for durable product state writes."],
        "inputs_explained": inputs,
        "side_effects": {
            "mutates": "broker_token",
            "writes": ["transient broker token metadata"],
            "does_not_write": ["tracks", "tasks", "artifacts"],
            "durability": "transient token",
            "idempotency": "non-idempotent issue",
        },
        "risk_hints": {
            "read_only": False,
            "destructive": False,
            "idempotent": False,
            "open_world": False,
            "requires_human_approval": False,
            "external_effect": False,
        },
        "success_means": f"evidence.{action} issued scoped token metadata.",
        "common_failures": ["target_type invalid", "target_id unreadable", "payload validation failed"],
    }


ACTION_SEMANTICS: dict[str, dict[str, Any]] = {
    "issue_browser": _semantic(
        action="issue_browser",
        description="Issue one browser evidence token metadata row.",
        inputs={"target_type": "Target type.", "target_id": "Target id.", "mode": "Optional evidence mode."},
    ),
    "approve_downgrade": _semantic(
        action="approve_downgrade",
        description="Issue one downgrade approval token metadata row.",
        inputs={"target_type": "Target type.", "target_id": "Target id.", "reason": "Downgrade reason."},
    ),
}
