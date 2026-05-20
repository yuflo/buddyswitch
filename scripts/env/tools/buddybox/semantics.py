#!/usr/bin/env python3
"""buddybox env.tool semantics."""

from __future__ import annotations

from typing import Any

CAPABILITY: dict[str, Any] = {
    "title": "Buddybox Files",
    "plain_description": "Operate active-buddy private files through logical_name values.",
    "use_when": ["You need active-buddy private file read/write/list/delete operations."],
    "do_not_use_when": ["You need product-readable shared output; use artifact and track publication."],
    "capability_boundary": "Only files under the active-buddy private file capability are allowed.",
}


def _semantic(*, action: str, description: str, mutates: str, inputs: dict[str, str], failures: list[str]) -> dict[str, Any]:
    return {
        "title": f"buddybox.{action}",
        "plain_description": description,
        "use_when": [f"Use when buddybox.{action} is needed for private workspace data."],
        "do_not_use_when": ["Do not use when shared product object mutation is required."],
        "inputs_explained": inputs,
        "side_effects": {
            "mutates": mutates,
            "writes": ["buddyswitch/local/buddybox/<buddy>/**"] if mutates != "none" else [],
            "does_not_write": ["tracks", "tasks", "artifacts"],
            "durability": "durable" if mutates != "none" else "none",
            "idempotency": "idempotent read" if mutates == "none" else "state mutation",
        },
        "risk_hints": {
            "read_only": mutates == "none",
            "destructive": action == "delete",
            "idempotent": mutates == "none",
            "open_world": False,
            "requires_human_approval": False,
            "external_effect": False,
        },
        "success_means": f"buddybox.{action} completed within active-buddy private file scope.",
        "common_failures": failures,
    }


ACTION_SEMANTICS: dict[str, dict[str, Any]] = {
    "desc": _semantic(
        action="desc",
        description="Describe active-buddy private file capability.",
        mutates="none",
        inputs={},
        failures=["active instance binding unavailable"],
    ),
    "list": _semantic(
        action="list",
        description="List active-buddy private file summaries.",
        mutates="none",
        inputs={"logical_name": "Optional prefix.", "recursive": "Recursive listing.", "limit": "Optional max rows."},
        failures=["logical_name validation failed", "private boundary denied"],
    ),
    "read": _semantic(
        action="read",
        description="Read one active-buddy private file.",
        mutates="none",
        inputs={"logical_name": "Private file logical name.", "encoding": "Optional response encoding."},
        failures=["logical_name validation failed", "file not found", "private boundary denied"],
    ),
    "write": _semantic(
        action="write",
        description="Write one active-buddy private file.",
        mutates="runtime_files",
        inputs={"logical_name": "Private file logical name.", "content": "Text content.", "content_base64": "Binary content."},
        failures=["payload validation failed", "private boundary denied", "content encoding invalid"],
    ),
    "delete": _semantic(
        action="delete",
        description="Delete one active-buddy private file.",
        mutates="runtime_files",
        inputs={"logical_name": "Private file logical name."},
        failures=["logical_name validation failed", "file not found", "private boundary denied"],
    ),
}
