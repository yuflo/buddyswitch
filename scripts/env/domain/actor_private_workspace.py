#!/usr/bin/env python3
"""Shared actor actor_private descriptor helpers."""

from __future__ import annotations

from typing import Any

from env.repos import actor_private_files as actor_private_repo

ACTOR_PRIVATE_PRIVACY_MESSAGE = (
    "This is the current identity's private file capability. "
    "Other actors cannot list, read, write, or delete these files. "
    "Use artifact when content must become product-readable."
)


def build_actor_private_desc(
    active_role: str,
    *,
    current_identity: dict[str, Any],
    instance_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = actor_private_repo.ensure_current_identity_private_root(active_role=active_role, instance_payload=instance_payload)
    return {
        "capability": "private_file_workspace",
        "owner_scope": "current_identity",
        "owner_identity": dict(current_identity),
        "lifetime_scope": "active_instance_workspace",
        "visibility": "current_identity_private",
        "product_readable": False,
        "cross_actor_readable": False,
        "mutates_product_state": False,
        "message": ACTOR_PRIVATE_PRIVACY_MESSAGE,
        "workspace_relative_root": "private",
        "host_surface": {
            "env": "BUDDYSWITCH_ACTOR_PRIVATE_DIR",
            "workspace_relative_root": "private",
            "durability": "active_instance_persistent",
        },
        "state_summary": actor_private_repo.state_summary(root=root),
    }
