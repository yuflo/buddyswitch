#!/usr/bin/env python3
"""artifact env.tool semantics."""

from __future__ import annotations

from typing import Any

CAPABILITY: dict[str, Any] = {
    "title": "Artifact Bodies",
    "plain_description": "Read full artifact bodies and manage active-buddy private drafts/metadata.",
    "use_when": ["You need full body reads or private draft artifact mutation."],
    "do_not_use_when": ["You need shared publication mutation; use track.add_material or track.add_proof."],
    "capability_boundary": "Private drafts are owner-scoped until published on a non-archived track.",
}


def _semantic(*, action: str, description: str, mutates: str, inputs: dict[str, str], failures: list[str]) -> dict[str, Any]:
    return {
        "title": f"artifact.{action}",
        "plain_description": description,
        "use_when": [f"Use when artifact.{action} matches the intended artifact workflow step."],
        "do_not_use_when": ["Do not use when the goal is direct track page publication flow selection."],
        "inputs_explained": inputs,
        "side_effects": {
            "mutates": mutates,
            "writes": ["buddyswitch/objects/artifacts/*.json"] if mutates != "none" else [],
            "does_not_write": ["tracks"] if mutates != "none" else ["artifacts", "tracks"],
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
        "success_means": f"artifact.{action} completed with draft/publication-scope constraints preserved.",
        "common_failures": failures,
    }


ACTION_SEMANTICS: dict[str, dict[str, Any]] = {
    "get": _semantic(
        action="get",
        description="Get one readable artifact including full markdown body.",
        mutates="none",
        inputs={"artifact_id": "Artifact id to read."},
        failures=["artifact not found", "artifact read scope denied"],
    ),
    "create_revision": _semantic(
        action="create_revision",
        description="Create one active-buddy private draft artifact revision.",
        mutates="runtime_objects",
        inputs={
            "title": "Artifact title.",
            "template": "Artifact template kind.",
            "body": "Non-empty markdown body.",
            "supersedes_artifact_id": "Optional superseded artifact id.",
        },
        failures=["payload validation failed", "source_refs invalid", "supersedes scope invalid"],
    ),
    "update_metadata": _semantic(
        action="update_metadata",
        description="Update metadata on one active-buddy-owned artifact.",
        mutates="runtime_objects",
        inputs={"artifact_id": "Artifact id to update.", "source_refs": "Optional provenance metadata refs."},
        failures=["artifact not found", "artifact scope denied", "payload validation failed"],
    ),
}
