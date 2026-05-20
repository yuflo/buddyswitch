#!/usr/bin/env python3
"""task env.tool contract."""

from __future__ import annotations

from typing import Any

from env.tools.model import MUTATES_NONE, MUTATES_RUNTIME_OBJECTS

TOOL_ID = "task"

TOOL_SPEC: dict[str, Any] = {
    "tool": TOOL_ID,
    "cli_resource": "task",
    "command": "python3 scripts/env/client.py task <operation>",
    "scope": "active-buddy private task work items",
    "actions": [
        {
            "name": "create",
            "payload_fields": ["task_id", "title", "summary", "status", "track_id"],
            "kind": "write",
            "mutates": MUTATES_RUNTIME_OBJECTS,
            "required_permission": "task.create",
            "authority": "task.buddy_scope",
            "preconditions": ["active buddy owns task.create permission"],
            "returns": ["task_id", "task"],
        },
        {
            "name": "list",
            "payload_fields": ["status", "track_id", "limit"],
            "kind": "read",
            "mutates": MUTATES_NONE,
            "required_permission": "task.read",
            "authority": "task.buddy_scope",
            "preconditions": ["active buddy owns task.read permission"],
            "returns": ["tasks"],
        },
        {
            "name": "get",
            "payload_fields": ["task_id"],
            "kind": "read",
            "mutates": MUTATES_NONE,
            "required_permission": "task.read",
            "authority": "task.buddy_scope",
            "preconditions": ["task_id references an active-buddy task"],
            "returns": ["task"],
        },
        {
            "name": "update",
            "payload_fields": ["task_id", "title", "summary", "status", "track_id"],
            "kind": "write",
            "mutates": MUTATES_RUNTIME_OBJECTS,
            "required_permission": "task.update",
            "authority": "task.buddy_scope",
            "preconditions": ["task_id references an active-buddy task"],
            "returns": ["task"],
        },
        {
            "name": "archive",
            "payload_fields": ["task_id"],
            "kind": "write",
            "mutates": MUTATES_RUNTIME_OBJECTS,
            "required_permission": "task.archive",
            "authority": "task.buddy_scope",
            "preconditions": ["task_id references an active-buddy task"],
            "returns": ["task"],
        },
    ],
}
