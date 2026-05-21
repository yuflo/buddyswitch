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

from env.repos import artifacts as artifact_repo
from env.repos import comments as comment_repo
from env.repos import requests as request_repo
from env.repos import runtime_files
from env.repos import tasks as task_repo
from env.repos import tracks as track_repo
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
    for base in (runtime_files.ROOT.absolute(), PROJECT_ROOT.absolute()):
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

    workspace_root = runtime_files.ROOT
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


def request_object_path(request_id: str) -> str:
    return f"buddyswitch/objects/requests/{request_id}.json"


def build_comment_ids_by_target(comments: list[dict[str, Any]]) -> dict[tuple[str, str], list[str]]:
    grouped: dict[tuple[str, str], list[str]] = {}
    for comment in comments:
        target_type = comment.get("target_type")
        target_id = comment.get("target_id")
        comment_id = comment.get("id")
        if target_type == "artifact_section":
            target_type = "artifact"
        if not isinstance(target_type, str) or target_type not in {"track", "artifact"}:
            continue
        if not isinstance(target_id, str) or not target_id:
            continue
        if not isinstance(comment_id, str) or not comment_id:
            continue
        grouped.setdefault((target_type, target_id), []).append(comment_id)
    return grouped


def build_comment_status_counts_by_target(comments: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, int]]:
    grouped: dict[tuple[str, str], dict[str, int]] = {}
    for comment in comments:
        target_type = comment.get("target_type")
        target_id = comment.get("target_id")
        if target_type == "artifact_section":
            target_type = "artifact"
        if not isinstance(target_type, str) or target_type not in {"track", "artifact"}:
            continue
        if not isinstance(target_id, str) or not target_id:
            continue
        key = (target_type, target_id)
        bucket = grouped.setdefault(key, {"open_comment_count": 0, "resolved_comment_count": 0})
        if comment.get("status") == "resolved":
            bucket["resolved_comment_count"] += 1
        else:
            bucket["open_comment_count"] += 1
    return grouped


def build_artifact_view(
    artifact: dict[str, Any],
    comment_ids_by_target: dict[tuple[str, str], list[str]],
    comment_status_by_target: dict[tuple[str, str], dict[str, int]],
) -> dict[str, Any]:
    counts = comment_status_by_target.get(("artifact", artifact["id"]), {"open_comment_count": 0, "resolved_comment_count": 0})
    return {
        **artifact,
        "object_path": artifact_object_path(artifact["id"]),
        "file_name": Path(artifact_object_path(artifact["id"])).name,
        "comment_ids": list(comment_ids_by_target.get(("artifact", artifact["id"]), [])),
        "open_comment_count": counts.get("open_comment_count", 0),
        "resolved_comment_count": counts.get("resolved_comment_count", 0),
        "missing": False,
    }


def build_task_view(task: dict[str, Any]) -> dict[str, Any]:
    return {
        **task,
        "object_path": task_object_path(task["id"]),
        "file_name": Path(task_object_path(task["id"])).name,
        "missing": False,
    }


def build_request_view(request: dict[str, Any]) -> dict[str, Any]:
    return {
        **request,
        "object_path": request_object_path(request["id"]),
        "file_name": Path(request_object_path(request["id"])).name,
        "missing": False,
    }


def build_track_views(
    tracks: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    requests: list[dict[str, Any]],
    comment_ids_by_target: dict[tuple[str, str], list[str]],
    comment_status_by_target: dict[tuple[str, str], dict[str, int]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    artifact_by_id: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        artifact_id = artifact.get("id")
        if isinstance(artifact_id, str) and artifact_id:
            artifact_by_id[artifact_id] = artifact

    artifact_rows_by_track: dict[str, list[dict[str, Any]]] = {}
    for artifact in artifacts:
        status = artifact.get("status")
        is_current = bool(artifact.get("is_current"))
        track_id = artifact.get("published_to_track")
        if status != "published" or not is_current or not isinstance(track_id, str) or not track_id:
            continue
        artifact_rows_by_track.setdefault(track_id, []).append(artifact)
    for track_id in artifact_rows_by_track:
        artifact_rows_by_track[track_id].sort(
            key=lambda row: (str(row.get("updated_at", "")), str(row.get("id", ""))),
            reverse=True,
        )

    request_rows_by_track: dict[str, list[dict[str, Any]]] = {}
    for request in requests:
        track_id = request.get("track_id")
        if not isinstance(track_id, str) or not track_id:
            continue
        request_rows_by_track.setdefault(track_id, []).append(request)
    for track_id in request_rows_by_track:
        request_rows_by_track[track_id].sort(
            key=lambda row: (str(row.get("updated_at", "")), str(row.get("id", ""))),
            reverse=True,
        )

    for track in tracks:
        track_id = str(track["id"])
        shared_materials: list[dict[str, Any]] = []
        for artifact in artifact_rows_by_track.get(track_id, []):
            artifact_id = str(artifact.get("id", ""))
            counts = comment_status_by_target.get(("artifact", artifact_id), {"open_comment_count": 0, "resolved_comment_count": 0})
            shared_materials.append(
                {
                    "artifact_id": artifact_id,
                    "title": artifact.get("title"),
                    "summary": artifact.get("summary", ""),
                    "template": artifact.get("template"),
                    "status": artifact.get("status"),
                    "published_to_track": artifact.get("published_to_track"),
                    "revision": artifact.get("revision"),
                    "is_current": artifact.get("is_current"),
                    "supersedes_artifact_id": artifact.get("supersedes_artifact_id"),
                    "updated_at": artifact.get("updated_at"),
                    "open_comment_count": counts.get("open_comment_count", 0),
                    "resolved_comment_count": counts.get("resolved_comment_count", 0),
                }
            )
        close_proof: list[dict[str, Any]] = []
        for ref in track.get("close_proof", []):
            if not isinstance(ref, dict):
                continue
            if ref.get("type") != "artifact":
                continue
            artifact_id = ref.get("artifact_id")
            if not isinstance(artifact_id, str) or not artifact_id:
                continue
            artifact = artifact_by_id.get(artifact_id)
            counts = comment_status_by_target.get(("artifact", artifact_id), {"open_comment_count": 0, "resolved_comment_count": 0})
            close_proof.append(
                {
                    "artifact_id": artifact_id,
                    "title": artifact.get("title") if isinstance(artifact, dict) else None,
                    "summary": ref.get("summary", ""),
                    "template": artifact.get("template") if isinstance(artifact, dict) else None,
                    "status": artifact.get("status") if isinstance(artifact, dict) else None,
                    "published_to_track": artifact.get("published_to_track") if isinstance(artifact, dict) else track_id,
                    "revision": artifact.get("revision") if isinstance(artifact, dict) else None,
                    "is_current": artifact.get("is_current") if isinstance(artifact, dict) else None,
                    "supersedes_artifact_id": artifact.get("supersedes_artifact_id") if isinstance(artifact, dict) else None,
                    "label": ref.get("label"),
                    "kind": ref.get("kind"),
                    "from_buddy": ref.get("from_buddy"),
                    "published_at": ref.get("published_at"),
                    "updated_at": artifact.get("updated_at") if isinstance(artifact, dict) else None,
                    "open_comment_count": counts.get("open_comment_count", 0),
                    "resolved_comment_count": counts.get("resolved_comment_count", 0),
                }
            )
        close_proof.sort(
            key=lambda row: (str(row.get("published_at") or ""), str(row.get("artifact_id") or "")),
            reverse=True,
        )
        comment_counts = comment_status_by_target.get(("track", track_id), {"open_comment_count": 0, "resolved_comment_count": 0})
        track_request_rows = request_rows_by_track.get(track_id, [])
        request_ids = [str(row.get("id")) for row in track_request_rows if isinstance(row.get("id"), str)]
        open_request_count = 0
        blocked_request_count = 0
        done_request_count = 0
        for request in track_request_rows:
            status = request.get("status")
            if status == "open" or status == "accepted":
                open_request_count += 1
            elif status == "blocked":
                blocked_request_count += 1
            elif status == "done":
                done_request_count += 1
        rows.append(
            {
                "id": track_id,
                "title": track["title"],
                "outcome": track.get("outcome", ""),
                "state": track.get("state"),
                "health": track.get("health"),
                "owner_buddy": track["owner_buddy"],
                "appetite": track.get("appetite", ""),
                "now": track.get("now"),
                "shared_materials": shared_materials,
                "updates": [row for row in track.get("updates", []) if isinstance(row, dict)],
                "close_proof": close_proof,
                "comment_ids": list(comment_ids_by_target.get(("track", track_id), [])),
                "request_ids": request_ids,
                "updated_at": track["updated_at"],
                "archived_at": track.get("archived_at"),
                "open_comment_count": comment_counts.get("open_comment_count", 0),
                "resolved_comment_count": comment_counts.get("resolved_comment_count", 0),
                "open_request_count": open_request_count,
                "blocked_request_count": blocked_request_count,
                "done_request_count": done_request_count,
            }
        )
    rows.sort(key=lambda item: (item.get("updated_at", ""), item["id"]), reverse=True)
    return rows


def build_workspace_projection() -> dict[str, Any]:
    manifest = load_manifest(DEFAULT_MANIFEST)
    comments = comment_repo.list_comments()
    comment_ids_by_target = build_comment_ids_by_target(comments)
    comment_status_by_target = build_comment_status_counts_by_target(comments)
    artifacts = [
        build_artifact_view(artifact, comment_ids_by_target, comment_status_by_target)
        for artifact in artifact_repo.list_artifacts()
    ]
    requests = [build_request_view(request) for request in request_repo.list_requests()]
    tasks = [build_task_view(task) for task in task_repo.list_tasks()]
    tracks = build_track_views(track_repo.list_tracks(), artifacts, requests, comment_ids_by_target, comment_status_by_target)
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
        "requests": requests,
    }


def build_workspace_projection_snapshot() -> dict[str, Any]:
    with runtime_snapshot_lock():
        return build_workspace_projection()
