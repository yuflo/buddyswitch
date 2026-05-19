#!/usr/bin/env python3
"""Task repository adapters for runtime task persistence access."""

from __future__ import annotations

from typing import Any

import env_legacy_store as env_store

_VALID_TASK_STATUSES = tuple(env_store.VALID_TASK_STATUS)


def valid_task_statuses() -> tuple[str, ...]:
    return _VALID_TASK_STATUSES


def slugify(value: str) -> str:
    return env_store.slugify(value)


def list_tasks() -> list[dict[str, Any]]:
    return env_store.list_tasks()


def get_task(task_id: str) -> dict[str, Any] | None:
    return env_store.get_task(task_id)


def create_task(
    *,
    task_id: str,
    title: str,
    buddy: str,
    track_id: str | None,
    status: str,
    summary: str,
) -> dict[str, Any]:
    return env_store.create_task(
        task_id,
        title,
        buddy=buddy,
        track_id=track_id,
        status=status,
        summary=summary,
        initial_run_id=None,
    )


def update_task(task_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    return env_store.update_task(task_id, patch)


def track_exists(track_id: str) -> bool:
    try:
        return env_store.get_track(track_id) is not None
    except ValueError:
        return False
