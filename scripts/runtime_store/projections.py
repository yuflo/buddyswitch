#!/usr/bin/env python3
"""Read-only workspace projection builders for runless durable output objects."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
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


def build_comment_ids_by_target(
    comments: list[dict[str, Any]],
) -> dict[tuple[str, str], list[str]]:
    grouped: dict[tuple[str, str], list[str]] = {}
    for comment in comments:
        target_type = comment.get("target_type")
        target_id = comment.get("target_id")
        comment_id = comment.get("id")
        if not isinstance(target_type, str) or target_type not in {"track", "artifact"}:
            continue
        if not isinstance(target_id, str) or not target_id:
            continue
        if not isinstance(comment_id, str) or not comment_id:
            continue
        grouped.setdefault((target_type, target_id), []).append(comment_id)
    return grouped


def build_artifact_view(
    artifact: dict[str, Any],
    comment_ids_by_target: dict[tuple[str, str], list[str]],
) -> dict[str, Any]:
    return {
        **artifact,
        "object_path": artifact_object_path(artifact["id"]),
        "file_name": Path(artifact_object_path(artifact["id"])).name,
        "comment_ids": list(comment_ids_by_target.get(("artifact", artifact["id"]), [])),
        "missing": False,
    }


def build_task_view(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task.get("id"),
        "buddy": task.get("buddy"),
        "title": task.get("title"),
        "status": task.get("status"),
        "track_id": task.get("track_id"),
        "summary": task.get("summary", ""),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "object_path": task_object_path(task["id"]),
        "file_name": Path(task_object_path(task["id"])).name,
        "missing": False,
    }


def _track_ref_artifact_ids(track: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for key in ("shared_materials", "close_proof"):
        for row in track.get(key, []):
            if not isinstance(row, dict):
                continue
            artifact_id = row.get("artifact_id")
            if not isinstance(artifact_id, str) or not artifact_id:
                continue
            ids.append(artifact_id)
    return ids


def build_track_views(
    tracks: list[dict[str, Any]],
    artifact_map: dict[str, dict[str, Any]],
    comment_ids_by_target: dict[tuple[str, str], list[str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for track in tracks:
        track_id = track.get("id")
        if not isinstance(track_id, str) or not track_id:
            continue
        missing_artifact_ids: list[str] = []
        latest = str(track.get("updated_at", ""))
        for artifact_id in _track_ref_artifact_ids(track):
            artifact = artifact_map.get(artifact_id)
            if artifact is None:
                missing_artifact_ids.append(artifact_id)
                continue
            artifact_updated = artifact.get("updated_at")
            if isinstance(artifact_updated, str) and artifact_updated > latest:
                latest = artifact_updated
        rows.append(
            {
                "id": track_id,
                "title": track.get("title"),
                "outcome": track.get("outcome", ""),
                "owner_buddy": track.get("owner_buddy"),
                "state": track.get("state"),
                "health": track.get("health"),
                "appetite": track.get("appetite"),
                "now": track.get("now"),
                "shared_materials": [row for row in track.get("shared_materials", []) if isinstance(row, dict)],
                "updates": [row for row in track.get("updates", []) if isinstance(row, dict)],
                "close_proof": [row for row in track.get("close_proof", []) if isinstance(row, dict)],
                "created_at": track.get("created_at"),
                "updated_at": latest,
                "archived_at": track.get("archived_at"),
                "comment_ids": list(comment_ids_by_target.get(("track", track_id), [])),
                "missing_artifact_ids": missing_artifact_ids,
            }
        )
    rows.sort(key=lambda item: (item.get("updated_at", ""), item["id"]), reverse=True)
    return rows


def build_workspace_projection() -> dict[str, Any]:
    manifest = load_manifest(DEFAULT_MANIFEST)
    comments = env_store.list_comments()
    comment_ids_by_target = build_comment_ids_by_target(comments)
    artifacts = [
        build_artifact_view(artifact, comment_ids_by_target)
        for artifact in env_store.list_artifacts()
    ]
    artifact_map = {artifact["id"]: artifact for artifact in artifacts}

    tasks = [build_task_view(task) for task in env_store.list_tasks()]
    tracks = build_track_views(env_store.list_tracks(), artifact_map, comment_ids_by_target)
    standalone_tasks = [task for task in tasks if not task.get("track_id")]
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
    }


def build_workspace_projection_snapshot() -> dict[str, Any]:
    with runtime_snapshot_lock():
        return build_workspace_projection()
