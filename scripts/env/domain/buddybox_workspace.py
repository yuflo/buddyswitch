#!/usr/bin/env python3
"""Shared buddybox workspace descriptor helpers."""

from __future__ import annotations

from typing import Any

from env.repos import buddybox_files as buddybox_repo

BUDDYBOX_PRIVACY_MESSAGE = (
    "This is the active buddy's private file capability. "
    "Other buddies cannot list, read, write, or delete these files. "
    "Use artifact when content must become product-readable."
)


def _logical_name_policy() -> dict[str, Any]:
    return {
        "scope": "active_buddy_private_relative_path",
        "valid_shape": "non-empty relative logical_name without absolute prefix, buddy prefix, or '..' traversal",
        "invalid_patterns": [
            {"pattern": "absolute path", "reason": "logical_name must be relative"},
            {"pattern": ".. traversal", "reason": "logical_name must stay inside active buddy private root"},
            {
                "pattern": "manifest buddy prefix",
                "reason": "logical_name is already relative to the active buddy private capability",
            },
        ],
        "examples": ["notes/todo.md", "scratch/analysis.md"],
    }


def build_buddybox_desc(active_buddy: str, *, instance_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    root = buddybox_repo.ensure_active_buddy_root(active_buddy=active_buddy, instance_payload=instance_payload)
    return {
        "capability": "private_file_workspace",
        "owner_scope": "active_buddy",
        "lifetime_scope": "active_instance_workspace",
        "visibility": "active_buddy_private",
        "product_readable": False,
        "cross_buddy_readable": False,
        "mutates_product_state": False,
        "message": BUDDYBOX_PRIVACY_MESSAGE,
        "supports": [
            "describe_capability",
            "list_private_file_summaries",
            "read_private_file",
            "write_private_text",
            "write_private_binary",
            "delete_private_file",
        ],
        "workspace_relative_root": "buddybox",
        "logical_name_policy": _logical_name_policy(),
        "state_summary": buddybox_repo.state_summary(root=root),
    }
