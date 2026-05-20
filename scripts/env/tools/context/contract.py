#!/usr/bin/env python3
"""context env.tool contract."""

from __future__ import annotations

from typing import Any

from env.tools.model import MUTATES_NONE

TOOL_ID = "context"

TOOL_SPEC: dict[str, Any] = {
    "tool": TOOL_ID,
    "cli_resource": "context",
    "command": "python3 scripts/env/client.py context <operation>",
    "scope": "runless read-only orientation payload",
    "actions": [
        {
            "name": "get",
            "payload_fields": ["track_id", "task_id", "limit"],
            "kind": "read",
            "mutates": MUTATES_NONE,
            "required_permission": "none",
            "authority": "read-only context discovery",
            "preconditions": ["filters are valid"],
            "returns": ["sections", "tool_catalog", "decision_surface"],
        },
        {
            "name": "summarize",
            "payload_fields": ["track_id", "task_id", "limit"],
            "kind": "read",
            "mutates": MUTATES_NONE,
            "required_permission": "none",
            "authority": "read-only context discovery",
            "preconditions": ["filters are valid"],
            "returns": ["summary", "candidate_tracks", "buddybox_desc"],
        },
        {
            "name": "list_sources",
            "payload_fields": [],
            "kind": "read",
            "mutates": MUTATES_NONE,
            "required_permission": "none",
            "authority": "read-only context discovery",
            "preconditions": ["none"],
            "returns": ["sources"],
        },
    ],
}
