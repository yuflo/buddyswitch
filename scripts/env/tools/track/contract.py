#!/usr/bin/env python3
"""track env.tool contract."""

from __future__ import annotations

from typing import Any

from env.tools.model import MUTATES_NONE, MUTATES_RUNTIME_OBJECTS

TOOL_ID = "track"

TOOL_SPEC: dict[str, Any] = {
    "tool": TOOL_ID,
    "cli_resource": "track",
    "command": "python3 scripts/env/client.py track <operation>",
    "scope": "shared track progress pages and publication timeline",
    "actions": [
        {
            "name": "create",
            "payload_fields": ["track_id", "title", "outcome", "appetite", "now", "state", "health"],
            "kind": "write",
            "mutates": MUTATES_RUNTIME_OBJECTS,
            "required_permission": "track.create",
            "authority": "pm.lifecycle_authority",
            "preconditions": ["active buddy is pm"],
            "returns": ["track"],
        },
        {
            "name": "list",
            "payload_fields": ["state", "limit"],
            "kind": "read",
            "mutates": MUTATES_NONE,
            "required_permission": "track.read",
            "authority": "track.lookup",
            "preconditions": ["active buddy owns track.read permission"],
            "returns": ["tracks"],
        },
        {
            "name": "open",
            "payload_fields": ["track_id"],
            "kind": "read",
            "mutates": MUTATES_NONE,
            "required_permission": "track.read",
            "authority": "track.lookup",
            "preconditions": ["track_id references an existing non-archived track"],
            "returns": ["track"],
        },
        {
            "name": "update_now",
            "payload_fields": ["track_id", "now", "state", "health"],
            "kind": "write",
            "mutates": MUTATES_RUNTIME_OBJECTS,
            "required_permission": "track.update_now",
            "authority": "track.shared_mutation",
            "preconditions": ["track_id references an existing non-archived track"],
            "returns": ["track"],
        },
        {
            "name": "add_material",
            "payload_fields": ["track_id", "artifact_id", "label", "summary"],
            "kind": "write",
            "mutates": MUTATES_RUNTIME_OBJECTS,
            "required_permission": "track.add_material",
            "authority": "track.shared_mutation",
            "preconditions": [
                "track_id references an existing non-archived track",
                "artifact_id references an active-buddy-owned draft artifact",
                "artifact is not already published to another track",
            ],
            "returns": ["artifact_id", "track", "state_changes"],
        },
        {
            "name": "add_update",
            "payload_fields": ["track_id", "summary", "kind", "refs"],
            "kind": "write",
            "mutates": MUTATES_RUNTIME_OBJECTS,
            "required_permission": "track.add_update",
            "authority": "track.shared_mutation",
            "preconditions": ["track_id references an existing non-archived track"],
            "returns": ["track", "update"],
        },
        {
            "name": "add_proof",
            "payload_fields": ["track_id", "artifact_id", "label", "summary"],
            "kind": "write",
            "mutates": MUTATES_RUNTIME_OBJECTS,
            "required_permission": "track.add_proof",
            "authority": "track.shared_mutation",
            "preconditions": [
                "track_id references an existing non-archived track",
                "artifact_id references an active-buddy-owned draft artifact",
                "artifact is not already published to another track",
            ],
            "returns": ["artifact_id", "track", "state_changes"],
        },
        {
            "name": "archive",
            "payload_fields": ["track_id"],
            "kind": "write",
            "mutates": MUTATES_RUNTIME_OBJECTS,
            "required_permission": "track.archive",
            "authority": "pm.lifecycle_authority",
            "preconditions": ["active buddy is pm", "track_id references an existing track"],
            "returns": ["track"],
        },
    ],
}
