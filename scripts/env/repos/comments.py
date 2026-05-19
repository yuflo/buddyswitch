#!/usr/bin/env python3
"""Comment repository adapters for runtime comment persistence access."""

from __future__ import annotations

from typing import Any

import env_legacy_store as env_store


def list_comments() -> list[dict[str, Any]]:
    return env_store.list_comments()


def get_comment(comment_id: str) -> dict[str, Any] | None:
    return env_store.get_comment(comment_id)


def create_comment(
    *,
    target_type: str,
    target_id: str,
    by_buddy: str,
    content: str,
    reply_to: str | None = None,
    mentions: list[str] | None = None,
    thread_id: str | None = None,
    status: str = "open",
    anchor: str | None = None,
    artifact_revision_id: str | None = None,
) -> dict[str, Any]:
    return env_store.create_comment(
        target_type=target_type,
        target_id=target_id,
        by_buddy=by_buddy,
        content=content,
        reply_to=reply_to,
        mentions=mentions,
        thread_id=thread_id,
        status=status,
        anchor=anchor,
        artifact_revision_id=artifact_revision_id,
    )


def comments_for_target(target_type: str, target_id: str) -> list[dict[str, Any]]:
    return env_store.comments_for_target(target_type, target_id)


def artifact_revision_chain(artifact_id: str) -> list[dict[str, Any]]:
    return env_store.artifact_revision_chain(artifact_id)
