#!/usr/bin/env python3
"""track env.tool semantics."""

from __future__ import annotations

from typing import Any

CAPABILITY: dict[str, Any] = {
    "title": "Track Pages",
    "plain_description": "Operate shared progress pages and shared material/proof publication.",
    "use_when": ["You need to operate shared collaboration on a non-archived track."],
    "do_not_use_when": ["You need full artifact body content by id; use artifact.get."],
    "capability_boundary": "Only PM can create/archive tracks; shared mutation requires readable track scope.",
}


def _semantic(*, action: str, description: str, mutates: str, inputs: dict[str, str], failures: list[str]) -> dict[str, Any]:
    return {
        "title": f"track.{action}",
        "plain_description": description,
        "use_when": [f"Use when track.{action} is the exact shared-track operation needed."],
        "do_not_use_when": ["Do not use when the goal is private draft authoring in artifact.create_revision."],
        "inputs_explained": inputs,
        "side_effects": {
            "mutates": mutates,
            "writes": ["buddyswitch/objects/tracks/*.json"] if mutates != "none" else [],
            "does_not_write": ["artifacts body content"] if mutates != "none" else ["tracks", "artifacts"],
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
        "success_means": f"track.{action} completed with track publication and lifecycle constraints honored.",
        "common_failures": failures,
    }


ACTION_SEMANTICS: dict[str, dict[str, Any]] = {
    "create": _semantic(
        action="create",
        description="Create one PM-owned shared track page.",
        mutates="runtime_objects",
        inputs={"track_id": "Track id.", "title": "Track title.", "outcome": "Target outcome.", "now": "Current next step."},
        failures=["active buddy is not pm", "track_id already exists", "payload validation failed"],
    ),
    "list": _semantic(
        action="list",
        description="List non-archived track page summaries.",
        mutates="none",
        inputs={"state": "Optional state filter.", "limit": "Optional max rows."},
        failures=["payload validation failed"],
    ),
    "open": _semantic(
        action="open",
        description="Open one non-archived shared track page.",
        mutates="none",
        inputs={"track_id": "Track id to read."},
        failures=["track not found", "track archived"],
    ),
    "update_now": _semantic(
        action="update_now",
        description="Update now/state/health on a shared track page.",
        mutates="runtime_objects",
        inputs={"track_id": "Track id to update.", "now": "Updated next step payload."},
        failures=["track not found", "track archived", "payload validation failed"],
    ),
    "add_material": _semantic(
        action="add_material",
        description="Publish one draft artifact as current shared material.",
        mutates="runtime_objects",
        inputs={"track_id": "Track id.", "artifact_id": "Draft artifact id.", "label": "Slot label.", "summary": "Publication summary."},
        failures=["track archived", "artifact scope denied", "duplicate publication"],
    ),
    "add_update": _semantic(
        action="add_update",
        description="Append one track timeline update row.",
        mutates="runtime_objects",
        inputs={"track_id": "Track id.", "summary": "Update summary.", "kind": "Update kind."},
        failures=["track archived", "invalid refs payload", "payload validation failed"],
    ),
    "add_proof": _semantic(
        action="add_proof",
        description="Publish one draft artifact as current close proof.",
        mutates="runtime_objects",
        inputs={"track_id": "Track id.", "artifact_id": "Draft artifact id.", "label": "Proof label.", "summary": "Proof summary."},
        failures=["track archived", "artifact scope denied", "duplicate proof publication"],
    ),
    "archive": _semantic(
        action="archive",
        description="Archive one PM-owned shared track page.",
        mutates="runtime_objects",
        inputs={"track_id": "Track id to archive."},
        failures=["active buddy is not pm", "track not found"],
    ),
}
