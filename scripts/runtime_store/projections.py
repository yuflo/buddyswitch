#!/usr/bin/env python3
"""Projection entrypoints delegating to workspace_data legacy implementations."""

from __future__ import annotations

from typing import Any


def build_artifact_view(artifact: dict[str, Any]) -> dict[str, Any]:
    import workspace_data

    return workspace_data._legacy_build_artifact_view(artifact)


def build_task_view(task: dict[str, Any], artifact_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    import workspace_data

    return workspace_data._legacy_build_task_view(task, artifact_map)


def build_track_views(
    tracks: list[dict[str, Any]],
    task_map: dict[str, dict[str, Any]],
    artifact_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    import workspace_data

    return workspace_data._legacy_build_track_views(tracks, task_map, artifact_map)


def scan_run_audits() -> list[dict[str, Any]]:
    import workspace_data

    return workspace_data._legacy_scan_run_audits()


def build_workspace_projection() -> dict[str, Any]:
    import workspace_data

    return workspace_data._legacy_build_workspace_data()
