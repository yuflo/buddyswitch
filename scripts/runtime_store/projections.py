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


def _shared_root_from_workspace_root(workspace_root: Path) -> Path | None:
    parts = workspace_root.resolve(strict=False).parts
    if ".codex-buddyswitch" not in parts:
        return None
    index = len(parts) - 1 - list(reversed(parts)).index(".codex-buddyswitch")
    suffix = parts[index + 1 :]
    if len(suffix) >= 3 and suffix[0] == "instances" and suffix[1] and suffix[2] == "workspace":
        return Path(*parts[: index + 1])
    if len(suffix) >= 1 and suffix[0] == "workspace":
        return Path(*parts[: index + 1])
    return None


def _workspace_uses_projected_state(workspace_root: Path) -> bool:
    projected_paths = (
        workspace_root / "buddyswitch" / "objects" / "tracks",
        workspace_root / "buddyswitch" / "objects" / "tasks",
        workspace_root / "buddyswitch" / "objects" / "artifacts",
        workspace_root / "buddyswitch" / "content" / "runs",
    )
    return any(path.is_symlink() for path in projected_paths)


def _runtime_lock_path() -> Path | None:
    raw_shared_root = os.environ.get(SHARED_ROOT_ENV, "").strip()
    if raw_shared_root:
        shared_root = raw_shared_root.rstrip("/")
        if not shared_root:
            return None
        return Path(shared_root) / "run" / "locks" / "runtime.lock"

    workspace_root = env_store.ROOT
    derived_shared_root = _shared_root_from_workspace_root(workspace_root)
    if derived_shared_root is not None:
        return derived_shared_root / "run" / "locks" / "runtime.lock"
    if _workspace_uses_projected_state(workspace_root):
        raise RuntimeSnapshotLockError(
            f"runtime snapshot lock shared root could not be derived from workspace root: {workspace_root}"
        )
    return None


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
        for kind, row in artifact_slots.items():
            if not isinstance(row, dict):
                continue
            artifact_id = row.get("current_artifact_id")
            if not isinstance(artifact_id, str) or not artifact_id:
                continue
            artifact = artifact_map.get(artifact_id)
            if artifact is not None:
                current_artifacts[kind] = artifact
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

        def _clean(value: Any) -> str | None:
            if not isinstance(value, str):
                return None
            text = value.strip()
            return text or None

        def _known_buddy(value: Any) -> str | None:
            buddy = _clean(value)
            if buddy is None or buddy not in valid_buddy_ids:
                return None
            return buddy

        buddy = _known_buddy(payload.get("buddy_id")) or _known_buddy(payload.get("active_buddy"))
        task_id = (
            _clean(payload.get("task_id"))
            or _clean(payload.get("current_task_id"))
            or _clean(payload.get("resolved_task_id"))
        )
        track_id = (
            _clean(payload.get("track_id"))
            or _clean(payload.get("current_track_id"))
            or _clean(payload.get("effective_track_id"))
        )
        demand = _clean(payload.get("request_text"))
        next_state = payload.get("next_state")
        if not isinstance(next_state, dict):
            mode = "archive" if payload.get("track_action") == "archive" else "continue_current_task"
            next_state = {
                "task_id": task_id,
                "track_id": track_id,
                "current_buddy": buddy,
                "next_buddy": None,
                "mode": mode,
            }
        receipt_paths = payload.get("receipt_paths")
        if not isinstance(receipt_paths, dict):
            # Legacy runs used "paths" before receipt_paths was introduced.
            receipt_paths = payload.get("paths") if isinstance(payload.get("paths"), dict) else {}

        rows.append(
            {
                "run_id": payload.get("run_id", path.stem),
                "path": rel(path),
                "buddy": buddy,
                "task_id": task_id,
                "task_title": payload.get("task_title"),
                "demand": demand,
                "artifact_ids": payload.get("artifact_ids") or [],
                "track_id": track_id,
                "track_title": payload.get("track_title"),
                "track_action": payload.get("track_action"),
                "execution_summary": payload.get("execution_summary"),
                "handoff": payload.get("handoff") if isinstance(payload.get("handoff"), dict) else {},
                "contributors": payload.get("contributors") if isinstance(payload.get("contributors"), dict) else {},
                "state_effects": payload.get("state_effects") if isinstance(payload.get("state_effects"), dict) else {},
                "next_state": next_state,
                "receipt_paths": receipt_paths,
                "related_run_ids": payload.get("related_run_ids")
                if isinstance(payload.get("related_run_ids"), list)
                else [],
                "updated_at": payload.get("timestamp") or iso_time(path),
                "status": "ok",
            }
        )
    rows.sort(key=lambda item: (item.get("updated_at", ""), item.get("run_id", "")), reverse=True)
    return rows


def build_workspace_projection() -> dict[str, Any]:
    manifest = load_manifest(DEFAULT_MANIFEST)
    artifacts = [build_artifact_view(artifact) for artifact in env_store.list_artifacts()]
    artifact_map = {artifact["id"]: artifact for artifact in artifacts}
    tasks = [build_task_view(task, artifact_map) for task in env_store.list_tasks()]
    task_map = {task["id"]: task for task in tasks}
    tracks = build_track_views(env_store.list_tracks(), task_map, artifact_map)
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
