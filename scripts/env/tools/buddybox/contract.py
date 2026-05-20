#!/usr/bin/env python3
"""buddybox env.tool contract."""

from __future__ import annotations

from typing import Any

from env.tools.model import MUTATES_NONE, MUTATES_RUNTIME_FILES

TOOL_ID = "buddybox"

TOOL_SPEC: dict[str, Any] = {
    "tool": TOOL_ID,
    "cli_resource": "buddybox",
    "command": "python3 scripts/env/client.py buddybox <operation>",
    "scope": "active-buddy private local workspace files",
    "actions": [
        {
            "name": "desc",
            "payload_fields": [],
            "kind": "read",
            "mutates": MUTATES_NONE,
            "required_permission": "buddybox.read",
            "authority": "buddybox.private_local_scope",
            "preconditions": ["active buddy is bound to an instance"],
            "returns": ["buddybox_desc"],
        },
        {
            "name": "list",
            "payload_fields": ["logical_name", "recursive", "limit"],
            "kind": "read",
            "mutates": MUTATES_NONE,
            "required_permission": "buddybox.read",
            "authority": "buddybox.private_local_scope",
            "preconditions": ["logical_name stays within active buddy private file capability when provided"],
            "returns": ["files"],
        },
        {
            "name": "read",
            "payload_fields": ["logical_name", "encoding"],
            "kind": "read",
            "mutates": MUTATES_NONE,
            "required_permission": "buddybox.read",
            "authority": "buddybox.private_local_scope",
            "preconditions": ["logical_name references one active buddy private file"],
            "returns": ["private_file"],
        },
        {
            "name": "write",
            "payload_fields": ["logical_name", "content", "content_base64", "content_type"],
            "kind": "write",
            "mutates": MUTATES_RUNTIME_FILES,
            "required_permission": "buddybox.write",
            "authority": "buddybox.private_local_scope",
            "preconditions": [
                "logical_name stays inside active buddy private file capability",
                "payload provides exactly one of content or content_base64",
            ],
            "returns": ["private_file"],
        },
        {
            "name": "delete",
            "payload_fields": ["logical_name"],
            "kind": "write",
            "mutates": MUTATES_RUNTIME_FILES,
            "required_permission": "buddybox.delete",
            "authority": "buddybox.private_local_scope",
            "preconditions": ["logical_name resolves inside active buddy private file capability"],
            "returns": ["deleted", "logical_name"],
        },
    ],
}
