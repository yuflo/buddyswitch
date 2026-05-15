#!/usr/bin/env python3
"""Compatibility facade for workspace projection builders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from env_store import ROOT


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def build_artifact_view(artifact: dict[str, Any]) -> dict[str, Any]:
    from runtime_store.projections import build_artifact_view as _build_artifact_view

    return _build_artifact_view(artifact)


def build_task_view(task: dict[str, Any], artifact_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    from runtime_store.projections import build_task_view as _build_task_view

    return _build_task_view(task, artifact_map)


def build_track_views(
    tracks: list[dict[str, Any]],
    task_map: dict[str, dict[str, Any]],
    artifact_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    from runtime_store.projections import build_track_views as _build_track_views

    return _build_track_views(tracks, task_map, artifact_map)


def build_handoff_view(handoff: dict[str, Any]) -> dict[str, Any]:
    from runtime_store.projections import build_handoff_view as _build_handoff_view

    return _build_handoff_view(handoff)


def build_workspace_data() -> dict[str, Any]:
    from runtime_store.projections import build_workspace_projection

    return build_workspace_projection()
