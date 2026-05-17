#!/usr/bin/env python3
"""Workspace projection entrypoints used by runtime tools and tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from env_store import ROOT
from runtime_store.projections import (
    build_artifact_view as _build_artifact_view,
    build_task_view as _build_task_view,
    build_track_views as _build_track_views,
    build_workspace_projection,
)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def build_artifact_view(artifact: dict[str, Any]) -> dict[str, Any]:
    return _build_artifact_view(artifact, {})


def build_task_view(task: dict[str, Any], artifact_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    del artifact_map
    return _build_task_view(task)


def build_track_views(
    tracks: list[dict[str, Any]],
    task_map: dict[str, dict[str, Any]],
    artifact_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    del task_map
    return _build_track_views(tracks, artifact_map, {})


def build_workspace_data() -> dict[str, Any]:
    return build_workspace_projection()
