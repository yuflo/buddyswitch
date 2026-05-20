#!/usr/bin/env python3
"""message env.tool contract."""

from __future__ import annotations

from typing import Any

from env.tools.model import MUTATES_NONE, MUTATES_RUNTIME_OBJECTS

TOOL_ID = "message"

TOOL_SPEC: dict[str, Any] = {
    "tool": TOOL_ID,
    "cli_resource": "message",
    "command": "python3 scripts/env/client.py message <operation>",
    "scope": "direct buddy-to-buddy inbox messaging",
    "actions": [
        {
            "name": "send",
            "payload_fields": ["to_buddy", "content", "reply_to"],
            "kind": "write",
            "mutates": MUTATES_RUNTIME_OBJECTS,
            "required_permission": "message.send",
            "authority": "message.direct_buddy_channel",
            "preconditions": ["to_buddy is a declared manifest buddy", "to_buddy != active_buddy"],
            "returns": ["message_id", "message"],
        },
        {
            "name": "list",
            "payload_fields": ["buddy"],
            "kind": "read",
            "mutates": MUTATES_NONE,
            "required_permission": "message.list",
            "authority": "message.active_buddy_inbox",
            "preconditions": ["active buddy owns message.list permission"],
            "returns": ["messages"],
        },
    ],
}
