#!/usr/bin/env python3
"""Compatibility facade for workspace projection builders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from env_store import ROOT


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def build_artifact_view(
    artifact: dict[str, Any],
    comment_ids_by_target: dict[tuple[str, str], list[str]] | None = None,
    comment_status_by_target: dict[tuple[str, str], dict[str, int]] | None = None,
) -> dict[str, Any]:
    from runtime_store.projections import build_artifact_view as _build_artifact_view

    return _build_artifact_view(
        artifact,
        comment_ids_by_target or {},
        comment_status_by_target or {},
    )


def build_task_view(task: dict[str, Any]) -> dict[str, Any]:
    from runtime_store.projections import build_task_view as _build_task_view

    return _build_task_view(task)


def build_track_views(
    tracks: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    comment_ids_by_target: dict[tuple[str, str], list[str]] | None = None,
    comment_status_by_target: dict[tuple[str, str], dict[str, int]] | None = None,
) -> list[dict[str, Any]]:
    from runtime_store.projections import build_track_views as _build_track_views

    return _build_track_views(
        tracks,
        artifacts,
        comment_ids_by_target or {},
        comment_status_by_target or {},
    )


def build_workspace_data() -> dict[str, Any]:
    from runtime_store.projections import build_workspace_projection

    return build_workspace_projection()
