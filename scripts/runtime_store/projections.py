#!/usr/bin/env python3
"""Read-only workspace projection builders."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import json

import env_store
from env_manifest import DEFAULT_MANIFEST, load_manifest

from .repositories import list_artifacts, list_tasks, list_tracks


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def iso_time(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    candidate = path.resolve()
    for base in (env_store.ROOT, PROJECT_ROOT):
        try:
            return candidate.relative_to(base.resolve()).as_posix()
        except ValueError:
            continue
    return candidate.as_posix()


def artifact_object_path(artifact_id: str) -> str:
    return f"buddyswitch/objects/artifacts/{artifact_id}.json"


def task_object_path(task_id: str) -> str:
    return f"buddyswitch/objects/tasks/{task_id}.json"


def build_artifact_view(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        **artifact,
        "object_path": artifact_object_path(artifact["id"]),
        "file_name": Path(artifact_object_path(artifact["id"])).name,
        "missing": False,
    }


def build_task_view(task: dict[str, Any], artifact_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    current_artifacts: dict[str, dict[str, Any]] = {}
    artifact_slots = task.get("artifact_slots", {})
    if isinstance(artifact_slots, dict):
        for slot, row in artifact_slots.items():
            if not isinstance(row, dict):
                continue
            artifact_id = row.get("current_artifact_id")
            if not isinstance(artifact_id, str) or not artifact_id:
                continue
            artifact = artifact_map.get(artifact_id)
            if artifact is not None:
                current_artifacts[slot] = artifact
    return {
        **task,
        "object_path": task_object_path(task["id"]),
        "file_name": Path(task_object_path(task["id"])).name,
        "current_artifacts": current_artifacts,
        "missing": False,
    }


def build_track_views(
    tracks: list[dict[str, Any]],
    task_map: dict[str, dict[str, Any]],
    artifact_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for track in tracks:
        tasks: list[dict[str, Any]] = []
        missing_task_ids: list[str] = []
        latest = track["updated_at"]

        for task_id in track.get("task_ids", []):
            task = task_map.get(task_id)
            if task is None:
                missing_task_ids.append(task_id)
                continue
            tasks.append(task)
            if task.get("updated_at", "") > latest:
                latest = task["updated_at"]
            current_artifacts = task.get("current_artifacts")
            if isinstance(current_artifacts, dict):
                for artifact in current_artifacts.values():
                    if isinstance(artifact, dict) and artifact.get("updated_at", "") > latest:
                        latest = artifact["updated_at"]

        tasks.sort(key=lambda item: (item.get("updated_at", ""), item["id"]), reverse=True)
        rows.append(
            {
                "id": track["id"],
                "title": track["title"],
                "status": track["status"],
                "current_buddy": track["current_buddy"],
                "next_buddy": track["next_buddy"],
                "task_ids": track.get("task_ids", []),
                "summary": track.get("summary", ""),
                "updated_at": latest,
                "tasks": tasks,
                "missing_task_ids": missing_task_ids,
            }
        )
    rows.sort(key=lambda item: (item.get("updated_at", ""), item["id"]), reverse=True)
    return rows


def scan_run_audits() -> list[dict[str, Any]]:
    run_root = env_store.ROOT / "buddyswitch" / "content" / "runs"
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
                "task_id": payload.get("resolved_task_id") or switch_payload.get("task_id"),
                "task_title": payload.get("task_title"),
                "demand": switch_payload.get("demand"),
                "skill_id": payload.get("skill_id"),
                "artifact_ids": payload.get("artifact_ids") or [],
                "track_id": payload.get("effective_track_id") or switch_payload.get("track_id"),
                "track_title": payload.get("track_title"),
                "track_action": payload.get("track_action"),
                "execution_summary": payload.get("execution_summary"),
                "reference_switches": payload.get("reference_switches")
                if isinstance(payload.get("reference_switches"), dict)
                else {},
                "related_run_ids": payload.get("related_run_ids")
                if isinstance(payload.get("related_run_ids"), list)
                else [],
                "recommended_switch": payload.get("recommended_switch"),
                "updated_at": payload.get("timestamp") or iso_time(path),
                "status": "ok",
            }
        )
    rows.sort(key=lambda item: (item.get("updated_at", ""), item.get("run_id", "")), reverse=True)
    return rows


def build_workspace_projection() -> dict[str, Any]:
    manifest = load_manifest(DEFAULT_MANIFEST)
    artifacts = [build_artifact_view(artifact) for artifact in list_artifacts()]
    artifact_map = {artifact["id"]: artifact for artifact in artifacts}
    tasks = [build_task_view(task, artifact_map) for task in list_tasks()]
    task_map = {task["id"]: task for task in tasks}
    tracks = build_track_views(list_tracks(), task_map, artifact_map)
    tracked_task_ids = {
        task_id
        for track in tracks
        for task_id in track.get("task_ids", [])
        if isinstance(task_id, str) and task_id
    }
    standalone_tasks = [
        task
        for task in tasks
        if not task.get("track_id") and task["id"] not in tracked_task_ids
    ]
    standalone_tasks.sort(key=lambda item: (item.get("updated_at", ""), item["id"]), reverse=True)

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "manifest_path": rel(DEFAULT_MANIFEST),
        "objects_root": "buddyswitch/objects",
        "buddies": [
            {"id": buddy["id"], "label": buddy["label"], "scope": buddy["scope"]}
            for buddy in manifest.get("buddies", [])
        ],
        "tracks": tracks,
        "standalone_tasks": standalone_tasks,
        "tasks": tasks,
        "artifacts": artifacts,
        "run_audits": scan_run_audits(),
    }
