#!/usr/bin/env python3
"""message env.tool semantics."""

from __future__ import annotations

from typing import Any

CAPABILITY: dict[str, Any] = {
    "title": "Buddy Messages",
    "plain_description": "Send and list direct buddy-to-buddy inbox messages.",
    "use_when": ["You need direct inbox messaging between manifest-declared buddies."],
    "do_not_use_when": ["You need object-level discussion; use comment tool actions."],
    "capability_boundary": "Messages are direct buddy-to-buddy scope only.",
}


def _semantic(*, action: str, description: str, mutates: str, inputs: dict[str, str]) -> dict[str, Any]:
    return {
        "title": f"message.{action}",
        "plain_description": description,
        "use_when": [f"Use when message.{action} is the intended direct messaging action."],
        "do_not_use_when": ["Do not use for track/artifact thread discussion."],
        "inputs_explained": inputs,
        "side_effects": {
            "mutates": mutates,
            "writes": ["buddyswitch/objects/messages/*.json"] if mutates != "none" else [],
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
        "success_means": f"message.{action} completed with buddy messaging boundary checks.",
        "common_failures": ["payload validation failed", "manifest buddy scope denied"],
    }


ACTION_SEMANTICS: dict[str, dict[str, Any]] = {
    "send": _semantic(
        action="send",
        description="Send one direct message to another manifest buddy.",
        mutates="runtime_objects",
        inputs={"to_buddy": "Destination buddy id.", "content": "Message content.", "reply_to": "Optional reply target."},
    ),
    "list": _semantic(
        action="list",
        description="List active-buddy inbox messages.",
        mutates="none",
        inputs={"buddy": "Optional sender buddy filter."},
    ),
}
