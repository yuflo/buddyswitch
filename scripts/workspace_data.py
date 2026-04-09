#!/usr/bin/env python3
"""Build BuddySwitch Context Panel data from env objects."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from env_manifest import DEFAULT_MANIFEST, load_manifest
from env_store import ROOT, list_artifacts, list_tracks


ARTIFACTS_ROOT = ROOT / "artifacts"
SUMMARIES_ROOT = ROOT / "runs" / "summaries"


def iso_time(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def title_from_markdown(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except UnicodeDecodeError:
        return path.stem
    return path.stem


def build_artifact_view(artifact: dict[str, Any]) -> dict[str, Any]:
    resolved = ROOT / artifact["path"]
    exists = resolved.exists()
    return {
        **artifact,
        "file_name": Path(artifact["path"]).name,
        "missing": not exists,
        "file_updated_at": iso_time(resolved) if exists else None,
    }


def build_track_views(
    tracks: list[dict[str, Any]], artifact_map: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for track in tracks:
        artifacts: list[dict[str, Any]] = []
        missing_artifact_ids: list[str] = []
        latest = track["updated_at"]

        for artifact_id in track.get("artifact_ids", []):
            artifact = artifact_map.get(artifact_id)
            if artifact is None:
                missing_artifact_ids.append(artifact_id)
                continue
            artifacts.append(artifact)
            if artifact.get("updated_at", "") > latest:
                latest = artifact["updated_at"]

        artifacts.sort(key=lambda item: (item.get("updated_at", ""), item["id"]), reverse=True)
        rows.append(
            {
                "id": track["id"],
                "title": track["title"],
                "status": track["status"],
                "current_buddy": track["current_buddy"],
                "next_buddy": track["next_buddy"],
                "artifact_ids": track["artifact_ids"],
                "summary": track.get("summary", ""),
                "updated_at": latest,
                "artifacts": artifacts,
                "missing_artifact_ids": missing_artifact_ids,
            }
        )
    rows.sort(key=lambda item: (item.get("updated_at", ""), item["id"]), reverse=True)
    return rows


def scan_untracked_artifacts(registered_paths: set[str]) -> list[dict[str, Any]]:
    if not ARTIFACTS_ROOT.exists():
        return []

    rows = []
    for path in sorted(ARTIFACTS_ROOT.glob("*.md")):
        if path.name == ".gitkeep":
            continue
        relative_path = rel(path)
        if relative_path in registered_paths:
            continue
        rows.append(
            {
                "title": title_from_markdown(path),
                "path": relative_path,
                "updated_at": iso_time(path),
            }
        )
    rows.sort(key=lambda item: (item["updated_at"], item["path"]), reverse=True)
    return rows


def scan_summaries() -> list[dict[str, Any]]:
    if not SUMMARIES_ROOT.exists():
        return []

    rows = []
    for path in sorted(SUMMARIES_ROOT.glob("**/*.md")):
        if path.name == ".gitkeep":
            continue
        rows.append(
            {
                "path": rel(path),
                "file_name": path.name,
                "title": title_from_markdown(path),
                "updated_at": iso_time(path),
            }
        )
    rows.sort(key=lambda item: item["updated_at"], reverse=True)
    return rows


def build_workspace_data() -> dict[str, Any]:
    manifest = load_manifest(DEFAULT_MANIFEST)
    artifacts = [build_artifact_view(artifact) for artifact in list_artifacts()]
    artifact_map = {artifact["id"]: artifact for artifact in artifacts}
    tracks = build_track_views(list_tracks(), artifact_map)
    registered_paths = {artifact["path"] for artifact in artifacts}

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "manifest_path": rel(DEFAULT_MANIFEST),
        "objects_root": "buddyswitch/objects",
        "buddies": [
            {"id": buddy["id"], "label": buddy["label"], "scope": buddy["scope"]}
            for buddy in manifest.get("buddies", [])
        ],
        "tracks": tracks,
        "artifacts": artifacts,
        "untracked_artifacts": scan_untracked_artifacts(registered_paths),
        "summaries": scan_summaries(),
    }
