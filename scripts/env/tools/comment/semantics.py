#!/usr/bin/env python3
"""comment env.tool semantics."""

from __future__ import annotations

from typing import Any

CAPABILITY: dict[str, Any] = {
    "title": "Object Comments",
    "plain_description": "Add and list comments on readable track and artifact targets.",
    "use_when": ["You need target-scoped discussion on tracks or artifacts."],
    "do_not_use_when": ["You need direct buddy inbox messages; use message tool."],
    "capability_boundary": "Comment scope requires active-buddy readability on the target object.",
}


def _semantic(*, action: str, description: str, mutates: str, inputs: dict[str, str], failures: list[str]) -> dict[str, Any]:
    return {
        "title": f"comment.{action}",
        "plain_description": description,
        "use_when": [f"Use when comment.{action} matches the needed thread operation."],
        "do_not_use_when": ["Do not use for non-target-scoped discussion."],
        "inputs_explained": inputs,
        "side_effects": {
            "mutates": mutates,
            "writes": ["buddyswitch/objects/comments/*.json"] if mutates != "none" else [],
            "does_not_write": ["tracks", "tasks", "artifacts"],
            "durability": "durable" if mutates != "none" else "none",
            "idempotency": "idempotent read" if mutates == "none" else "state mutation",
        },
        "risk_hints": {
            "read_only": mutates == "none",
            "destructive": False,
            "idempotent": mutates == "none",
            "open_world": False,
            "requires_human_approval": False,
            "external_effect": False,
        },
        "success_means": f"comment.{action} completed with target readability boundary checks.",
        "common_failures": failures,
    }


ACTION_SEMANTICS: dict[str, dict[str, Any]] = {
    "add": _semantic(
        action="add",
        description="Add one comment row to a readable target thread.",
        mutates="runtime_objects",
        inputs={
            "target_type": "Target type.",
            "target_id": "Target id.",
            "content": "Plain-text comment content.",
            "reply_to": "Optional parent comment id.",
        },
        failures=["target unreadable", "reply_to scope invalid", "payload validation failed"],
    ),
    "list": _semantic(
        action="list",
        description="List comment rows for a readable target thread.",
        mutates="none",
        inputs={"target_type": "Target type.", "target_id": "Target id.", "status": "Optional status filter."},
        failures=["target unreadable", "status filter invalid"],
    ),
}
