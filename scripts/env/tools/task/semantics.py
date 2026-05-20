#!/usr/bin/env python3
"""task env.tool semantics."""

from __future__ import annotations

from typing import Any

CAPABILITY: dict[str, Any] = {
    "title": "Task Management",
    "plain_description": "Manage active-buddy private tasks as optional work aids.",
    "use_when": ["You need to create, list, read, update, or archive tasks owned by the active buddy."],
    "do_not_use_when": ["You need shared artifact publication; use track and artifact tools."],
    "capability_boundary": "Only active-buddy-owned tasks are readable and writable.",
}


def _semantic(*, action: str, description: str, mutates: str, inputs: dict[str, str]) -> dict[str, Any]:
    return {
        "title": f"task.{action}",
        "plain_description": description,
        "use_when": [f"Use when task.{action} is the needed task action."],
        "do_not_use_when": ["Do not use when a shared track/artifact workflow is required."],
        "inputs_explained": inputs,
        "side_effects": {
            "mutates": mutates,
            "writes": ["buddyswitch/objects/tasks/*.json"] if mutates != "none" else [],
            "does_not_write": ["tracks", "artifacts"] if mutates == "none" else ["tracks", "artifacts"],
            "durability": "durable" if mutates != "none" else "none",
            "idempotency": "idempotent read" if mutates == "none" else "state mutation",
        },
        "risk_hints": {
            "read_only": mutates == "none",
            "destructive": action == "archive",
            "idempotent": mutates == "none",
            "open_world": False,
            "requires_human_approval": False,
            "external_effect": False,
        },
        "success_means": f"task.{action} completed with task-domain constraints satisfied.",
        "common_failures": ["payload validation failed", "task ownership scope denied", "task id not found"],
    }


ACTION_SEMANTICS: dict[str, dict[str, Any]] = {
    "create": _semantic(
        action="create",
        description="Create one active-buddy private task.",
        mutates="runtime_objects",
        inputs={"title": "Task title.", "summary": "Task summary.", "track_id": "Optional track context."},
    ),
    "list": _semantic(
        action="list",
        description="List active-buddy private tasks.",
        mutates="none",
        inputs={"status": "Optional status filter.", "track_id": "Optional track filter.", "limit": "Optional max rows."},
    ),
    "get": _semantic(
        action="get",
        description="Get one active-buddy private task.",
        mutates="none",
        inputs={"task_id": "Task id to read."},
    ),
    "update": _semantic(
        action="update",
        description="Update one active-buddy private task.",
        mutates="runtime_objects",
        inputs={"task_id": "Task id to update.", "status": "Optional task status."},
    ),
    "archive": _semantic(
        action="archive",
        description="Archive one active-buddy private task.",
        mutates="runtime_objects",
        inputs={"task_id": "Task id to archive."},
    ),
}
