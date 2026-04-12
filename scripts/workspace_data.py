#!/usr/bin/env python3
"""Build BuddySwitch Context Panel data from canonical BuddySwitch objects."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import json

from env_manifest import DEFAULT_MANIFEST, load_manifest
from env_store import ROOT, list_artifacts, list_tracks


def iso_time(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def artifact_object_path(artifact_id: str) -> str:
    return f"buddyswitch/objects/artifacts/{artifact_id}.json"


def build_artifact_view(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        **artifact,
        "object_path": artifact_object_path(artifact["id"]),
        "file_name": Path(artifact_object_path(artifact["id"])).name,
        "missing": False,
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


def scan_run_audits() -> list[dict[str, Any]]:
    run_root = ROOT / "buddyswitch" / "content" / "runs"
    if not run_root.exists():
        return []

    rows = []
    for path in sorted(run_root.glob("*.json")):
        if path.name == ".gitkeep":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            rows.append(
                {
                    "run_id": path.stem,
                    "path": rel(path),
                    "status": "invalid",
                    "updated_at": iso_time(path),
                }
            )
            continue

        if not isinstance(payload, dict):
            rows.append(
                {
                    "run_id": path.stem,
                    "path": rel(path),
                    "status": "invalid",
                    "updated_at": iso_time(path),
                }
            )
            continue

        switch = payload.get("switch")
        switch_payload = switch if isinstance(switch, dict) else {}
        rows.append(
            {
                "run_id": payload.get("run_id", path.stem),
                "path": rel(path),
                "buddy": switch_payload.get("buddy"),
                "task": switch_payload.get("task"),
                "skill_id": payload.get("skill_id"),
                "artifact_id": payload.get("artifact_id"),
                "track_id": payload.get("track_id"),
                "track_action": payload.get("track_action"),
                "execution_summary": payload.get("execution_summary"),
                "suggested_next_switch": payload.get("suggested_next_switch"),
                "updated_at": payload.get("timestamp") or iso_time(path),
                "status": "ok",
            }
        )
    rows.sort(key=lambda item: (item.get("updated_at", ""), item.get("run_id", "")), reverse=True)
    return rows


def build_workspace_data() -> dict[str, Any]:
    manifest = load_manifest(DEFAULT_MANIFEST)
    artifacts = [build_artifact_view(artifact) for artifact in list_artifacts()]
    artifact_map = {artifact["id"]: artifact for artifact in artifacts}
    tracks = build_track_views(list_tracks(), artifact_map)

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
        "run_audits": scan_run_audits(),
    }
