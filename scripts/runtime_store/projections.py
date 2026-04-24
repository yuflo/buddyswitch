#!/usr/bin/env python3
"""Read-only workspace projection builders."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
import json
import math
import os
import time

try:
    import fcntl
except ModuleNotFoundError:  # pragma: no cover - Windows fallback
    fcntl = None  # type: ignore[assignment]

import env_store
from env_manifest import DEFAULT_MANIFEST, load_manifest

from .repositories import list_artifacts, list_tasks, list_tracks


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCK_WAIT_POLL_SECONDS = 0.05
DEFAULT_RUNTIME_LOCK_TIMEOUT_SECONDS = 1.0
RUNTIME_LOCK_TIMEOUT_ENV = "BUDDYSWITCH_RUNTIME_LOCK_TIMEOUT_SECONDS"
SHARED_ROOT_ENV = "BUDDYSWITCH_SHARED_ROOT"


class RuntimeSnapshotLockError(RuntimeError):
    """Raised when a configured runtime snapshot lock cannot protect a read."""


def iso_time(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    candidate = path.absolute()
    for base in (env_store.ROOT.absolute(), PROJECT_ROOT.absolute()):
        try:
            return candidate.relative_to(base).as_posix()
        except ValueError:
            continue
    return candidate.as_posix()


def _runtime_lock_timeout_seconds() -> float:
    raw_timeout = os.environ.get(RUNTIME_LOCK_TIMEOUT_ENV, "")
    if not raw_timeout.strip():
        return DEFAULT_RUNTIME_LOCK_TIMEOUT_SECONDS
    try:
        timeout = float(raw_timeout)
    except ValueError:
        return DEFAULT_RUNTIME_LOCK_TIMEOUT_SECONDS
    if not math.isfinite(timeout):
        return DEFAULT_RUNTIME_LOCK_TIMEOUT_SECONDS
    if timeout < 0:
        return 0.0
    return timeout


def _runtime_lock_path() -> Path | None:
    raw_shared_root = os.environ.get(SHARED_ROOT_ENV, "").strip()
    if not raw_shared_root:
        return None
    shared_root = raw_shared_root.rstrip("/")
    if not shared_root:
        return None
    return Path(f"{shared_root}.lock")


@contextmanager
def runtime_snapshot_lock() -> Any:
    lock_path = _runtime_lock_path()
    if lock_path is None:
        yield
        return
    if fcntl is None:
        raise RuntimeSnapshotLockError("runtime snapshot lock requires fcntl support")

    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as exc:
        raise RuntimeSnapshotLockError(f"could not open runtime snapshot lock: {lock_path}") from exc

    locked = False
    timeout_seconds = _runtime_lock_timeout_seconds()
    deadline = time.monotonic() + timeout_seconds
    try:
        while True:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
                locked = True
                break
            except BlockingIOError as exc:
                if time.monotonic() >= deadline:
                    raise RuntimeSnapshotLockError(f"could not acquire runtime snapshot lock: {lock_path}") from exc
                time.sleep(LOCK_WAIT_POLL_SECONDS)
            except OSError as exc:
                raise RuntimeSnapshotLockError(f"could not acquire runtime snapshot lock: {lock_path}") from exc
        yield
    finally:
        if locked:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
        os.close(lock_fd)


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

    manifest = load_manifest(DEFAULT_MANIFEST)
    valid_buddy_ids = {
        buddy_id
        for buddy in manifest.get("buddies", [])
        if isinstance(buddy, dict)
        for buddy_id in [buddy.get("id")]
        if isinstance(buddy_id, str) and buddy_id
    }

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
        raw_buddy_id = switch_payload.get("buddy_id")
        buddy_id = raw_buddy_id.strip() if isinstance(raw_buddy_id, str) else None
        if not buddy_id or buddy_id not in valid_buddy_ids:
            buddy_id = None
        raw_legacy_buddy = switch_payload.get("buddy")
        legacy_buddy = raw_legacy_buddy.strip() if isinstance(raw_legacy_buddy, str) else None
        if not legacy_buddy or legacy_buddy not in valid_buddy_ids:
            legacy_buddy = None
        rows.append(
            {
                "run_id": payload.get("run_id", path.stem),
                "path": rel(path),
                "buddy": buddy_id or legacy_buddy,
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


def build_workspace_projection_snapshot() -> dict[str, Any]:
    with runtime_snapshot_lock():
        return build_workspace_projection()
