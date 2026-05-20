#!/usr/bin/env python3
"""artifact env.tool contract."""

from __future__ import annotations

from typing import Any

from env.tools.model import MUTATES_NONE, MUTATES_RUNTIME_OBJECTS

TOOL_ID = "artifact"

TOOL_SPEC: dict[str, Any] = {
    "tool": TOOL_ID,
    "cli_resource": "artifact",
    "command": "python3 scripts/env/client.py artifact <operation>",
    "scope": "private drafts and published track material/proof artifacts",
    "actions": [
        {
            "name": "get",
            "payload_fields": ["artifact_id"],
            "kind": "read",
            "mutates": MUTATES_NONE,
            "required_permission": "artifact.read",
            "authority": "artifact.owner_or_publication_boundary",
            "preconditions": ["artifact_id references a readable artifact"],
            "returns": ["artifact"],
        },
        {
            "name": "create_revision",
            "payload_fields": [
                "artifact_id",
                "title",
                "summary",
                "template",
                "body",
                "supersedes_artifact_id",
                "source_refs",
                "read_claim",
            ],
            "kind": "write",
            "mutates": MUTATES_RUNTIME_OBJECTS,
            "required_permission": "artifact.create",
            "authority": "artifact.buddy_scope",
            "preconditions": [
                "active buddy owns artifact.create permission",
                "status and published_to_track are not accepted create_revision inputs",
            ],
            "returns": ["artifact"],
        },
        {
            "name": "update_metadata",
            "payload_fields": ["artifact_id", "title", "summary", "template", "body", "source_refs", "read_claim"],
            "kind": "write",
            "mutates": MUTATES_RUNTIME_OBJECTS,
            "required_permission": "artifact.update",
            "authority": "artifact.buddy_scope",
            "preconditions": ["artifact_id references an active-buddy-owned artifact"],
            "returns": ["artifact"],
        },
    ],
}
