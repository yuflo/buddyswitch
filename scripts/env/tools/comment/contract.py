#!/usr/bin/env python3
"""comment env.tool contract."""

from __future__ import annotations

from typing import Any

from env.tools.model import MUTATES_NONE, MUTATES_RUNTIME_OBJECTS

TOOL_ID = "comment"

TOOL_SPEC: dict[str, Any] = {
    "tool": TOOL_ID,
    "cli_resource": "comment",
    "command": "python3 scripts/env/client.py comment <operation>",
    "scope": "target-scoped plain-text comments on readable tracks and artifacts",
    "actions": [
        {
            "name": "add",
            "payload_fields": ["target_type", "target_id", "content", "reply_to", "artifact_revision_id", "anchor", "mentions"],
            "kind": "write",
            "mutates": MUTATES_RUNTIME_OBJECTS,
            "required_permission": "comment.add",
            "authority": "target.read_boundary",
            "preconditions": ["target_type is track or artifact", "active buddy has read access to target"],
            "returns": ["comment_id", "comment"],
        },
        {
            "name": "list",
            "payload_fields": ["target_type", "target_id", "status"],
            "kind": "read",
            "mutates": MUTATES_NONE,
            "required_permission": "comment.list",
            "authority": "target.read_boundary",
            "preconditions": ["target_type is track or artifact", "active buddy has read access to target"],
            "returns": ["comments"],
        },
    ],
}
