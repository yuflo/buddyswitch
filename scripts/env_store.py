#!/usr/bin/env python3
"""BuddySwitch env object store for tracks, tasks, and artifacts."""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OBJECTS_ROOT = ROOT / "buddyswitch" / "objects"
TRACKS_DIR = OBJECTS_ROOT / "tracks"
TASKS_DIR = OBJECTS_ROOT / "tasks"
ARTIFACT_OBJECTS_DIR = OBJECTS_ROOT / "artifacts"
CONTENT_ROOT = ROOT / "buddyswitch" / "content"
RUN_CONTENT_DIR = CONTENT_ROOT / "runs"
VALID_TRACK_STATUS = ("active", "blocked", "done", "archived")
VALID_TASK_STATUS = ("active", "blocked", "done", "archived")
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def ensure_dirs() -> None:
    TRACKS_DIR.mkdir(parents=True, exist_ok=True)
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_OBJECTS_DIR.mkdir(parents=True, exist_ok=True)
    RUN_CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    for marker in (
        TRACKS_DIR / ".gitkeep",
        TASKS_DIR / ".gitkeep",
        ARTIFACT_OBJECTS_DIR / ".gitkeep",
        RUN_CONTENT_DIR / ".gitkeep",
    ):
        if not marker.exists():
            marker.write_text("", encoding="utf-8")


def require_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not ID_PATTERN.match(value):
        raise ValueError(f"{label} must match /^[a-z0-9][a-z0-9-]*$/")
    return value


def normalize_repo_path(raw_path: str) -> str:
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"path must be repo-relative and must not contain '..': {raw_path}")
    return path.as_posix()


def normalize_run_content_path(raw_path: str) -> str:
    normalized = normalize_repo_path(raw_path)
    path = Path(normalized)
    if path.parts[:3] != ("buddyswitch", "content", "runs"):
        raise ValueError("run content path must start with buddyswitch/content/runs/")
    if path.suffix.lower() != ".json":
        raise ValueError("run content path must be a JSON file (*.json)")
    return normalized


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned or "artifact"


def run_content_path(run_id: str) -> str:
    return f"buddyswitch/content/runs/{require_id(run_id, 'run id')}.json"


def track_file(track_id: str) -> Path:
    return TRACKS_DIR / f"{require_id(track_id, 'track id')}.json"


def task_file(task_id: str) -> Path:
    return TASKS_DIR / f"{require_id(task_id, 'task id')}.json"


def artifact_file(artifact_id: str) -> Path:
    return ARTIFACT_OBJECTS_DIR / f"{require_id(artifact_id, 'artifact id')}.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {rel(path)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{rel(path)} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=True, indent=2) + os.linesep
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as handle:
        handle.write(serialized)
        temp_name = handle.name
    os.replace(temp_name, path)


def validate_track(track: dict[str, Any]) -> dict[str, Any]:
    if "artifact_ids" in track:
        raise ValueError("track.artifact_ids is retired; use track.task_ids")

    track_id = require_id(track.get("id", ""), "track.id")
    title = track.get("title")
    status = track.get("status")
    current_buddy = track.get("current_buddy")
    next_buddy = track.get("next_buddy")
    task_ids = track.get("task_ids")
    summary = track.get("summary")
    updated_at = track.get("updated_at")

    if not isinstance(title, str) or not title.strip():
        raise ValueError("track.title must be a non-empty string")
    if status not in VALID_TRACK_STATUS:
        raise ValueError(f"track.status must be one of {', '.join(VALID_TRACK_STATUS)}")
    if not isinstance(current_buddy, str) or not current_buddy:
        raise ValueError("track.current_buddy must be a non-empty string")
    if next_buddy is not None and (not isinstance(next_buddy, str) or not next_buddy):
        raise ValueError("track.next_buddy must be a non-empty string or null")
    if not isinstance(task_ids, list) or any(not isinstance(item, str) or not item for item in task_ids):
        raise ValueError("track.task_ids must be a list of non-empty strings")
    if summary is not None and not isinstance(summary, str):
        raise ValueError("track.summary must be a string or null")
    if not isinstance(updated_at, str) or not updated_at:
        raise ValueError("track.updated_at must be a non-empty string")

    return {
        "id": track_id,
        "title": title.strip(),
        "status": status,
        "current_buddy": current_buddy,
        "next_buddy": next_buddy,
        "task_ids": list(dict.fromkeys(task_ids)),
        "summary": summary or "",
        "updated_at": updated_at,
    }


def validate_task(task: dict[str, Any]) -> dict[str, Any]:
    task_id = require_id(task.get("id", ""), "task.id")
    buddy = task.get("buddy")
    title = task.get("title")
    status = task.get("status")
    track_id = task.get("track_id")
    artifact_ids = task.get("artifact_ids")
    run_ids = task.get("run_ids")
    latest_run_id = task.get("latest_run_id")
    latest_artifact_id = task.get("latest_artifact_id")
    summary = task.get("summary")
    created_at = task.get("created_at")
    updated_at = task.get("updated_at")

    if not isinstance(buddy, str) or not buddy:
        raise ValueError("task.buddy must be a non-empty string")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("task.title must be a non-empty string")
    if status not in VALID_TASK_STATUS:
        raise ValueError(f"task.status must be one of {', '.join(VALID_TASK_STATUS)}")
    if track_id is not None:
        require_id(track_id, "task.track_id")
    if not isinstance(artifact_ids, list) or any(not isinstance(item, str) or not item for item in artifact_ids):
        raise ValueError("task.artifact_ids must be a list of non-empty strings")
    if not isinstance(run_ids, list) or any(not isinstance(item, str) or not item for item in run_ids):
        raise ValueError("task.run_ids must be a list of non-empty strings")
    if not run_ids:
        raise ValueError("task.run_ids must include at least one run id")
    if not isinstance(latest_run_id, str) or not latest_run_id:
        raise ValueError("task.latest_run_id must be a non-empty string")
    if latest_run_id not in run_ids:
        raise ValueError("task.latest_run_id must be included in task.run_ids")
    if latest_artifact_id is not None:
        if not isinstance(latest_artifact_id, str) or not latest_artifact_id:
            raise ValueError("task.latest_artifact_id must be a non-empty string or null")
        if latest_artifact_id not in artifact_ids:
            raise ValueError("task.latest_artifact_id must be included in task.artifact_ids")
    if summary is not None and not isinstance(summary, str):
        raise ValueError("task.summary must be a string or null")
    if not isinstance(created_at, str) or not created_at:
        raise ValueError("task.created_at must be a non-empty string")
    if not isinstance(updated_at, str) or not updated_at:
        raise ValueError("task.updated_at must be a non-empty string")

    return {
        "id": task_id,
        "buddy": buddy.strip(),
        "title": title.strip(),
        "status": status,
        "track_id": track_id,
        "artifact_ids": list(dict.fromkeys(artifact_ids)),
        "run_ids": list(dict.fromkeys(run_ids)),
        "latest_run_id": latest_run_id,
        "latest_artifact_id": latest_artifact_id,
        "summary": summary or "",
        "created_at": created_at,
        "updated_at": updated_at,
    }


def validate_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    if "track_id" in artifact:
        raise ValueError("artifact.track_id is retired; use artifact.task_id")

    artifact_id = require_id(artifact.get("id", ""), "artifact.id")
    title = artifact.get("title")
    task_id = artifact.get("task_id")
    buddy = artifact.get("buddy")
    skill_id = artifact.get("skill_id")
    source_run_id = artifact.get("source_run_id")
    summary = artifact.get("summary")
    content = artifact.get("content", {})
    created_at = artifact.get("created_at")
    updated_at = artifact.get("updated_at")

    if not isinstance(title, str) or not title.strip():
        raise ValueError("artifact.title must be a non-empty string")
    require_id(task_id, "artifact.task_id")
    if not isinstance(buddy, str) or not buddy.strip():
        raise ValueError("artifact.buddy must be a non-empty string")
    if not isinstance(skill_id, str) or not skill_id.strip():
        raise ValueError("artifact.skill_id must be a non-empty string")
    require_id(source_run_id, "artifact.source_run_id")
    if summary is not None and not isinstance(summary, str):
        raise ValueError("artifact.summary must be a string or null")
    if not isinstance(content, dict):
        raise ValueError("artifact.content must be an object")
    if not isinstance(created_at, str) or not created_at:
        raise ValueError("artifact.created_at must be a non-empty string")
    if not isinstance(updated_at, str) or not updated_at:
        raise ValueError("artifact.updated_at must be a non-empty string")

    return {
        "id": artifact_id,
        "title": title.strip(),
        "task_id": task_id,
        "buddy": buddy.strip(),
        "skill_id": skill_id.strip(),
        "source_run_id": source_run_id,
        "summary": summary or "",
        "content": content,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def list_tracks() -> list[dict[str, Any]]:
    ensure_dirs()
    rows: list[dict[str, Any]] = []
    for path in TRACKS_DIR.glob("*.json"):
        rows.append(validate_track(_read_json(path)))
    rows.sort(key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
    return rows


def list_tasks() -> list[dict[str, Any]]:
    ensure_dirs()
    rows: list[dict[str, Any]] = []
    for path in TASKS_DIR.glob("*.json"):
        rows.append(validate_task(_read_json(path)))
    rows.sort(key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
    return rows


def list_artifacts() -> list[dict[str, Any]]:
    ensure_dirs()
    rows: list[dict[str, Any]] = []
    for path in ARTIFACT_OBJECTS_DIR.glob("*.json"):
        rows.append(validate_artifact(_read_json(path)))
    rows.sort(key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
    return rows


def get_track(track_id: str) -> dict[str, Any] | None:
    path = track_file(track_id)
    if not path.exists():
        return None
    return validate_track(_read_json(path))


def get_task(task_id: str) -> dict[str, Any] | None:
    path = task_file(task_id)
    if not path.exists():
        return None
    return validate_task(_read_json(path))


def get_artifact(artifact_id: str) -> dict[str, Any] | None:
    path = artifact_file(artifact_id)
    if not path.exists():
        return None
    return validate_artifact(_read_json(path))


def save_track(track: dict[str, Any]) -> dict[str, Any]:
    ensure_dirs()
    normalized = validate_track(track)
    _write_json(track_file(normalized["id"]), normalized)
    return normalized


def save_task(task: dict[str, Any]) -> dict[str, Any]:
    ensure_dirs()
    normalized = validate_task(task)
    _write_json(task_file(normalized["id"]), normalized)
    return normalized


def save_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    ensure_dirs()
    normalized = validate_artifact(artifact)
    _write_json(artifact_file(normalized["id"]), normalized)
    return normalized


def create_track(
    track_id: str,
    title: str,
    *,
    status: str = "active",
    current_buddy: str = "pm",
    next_buddy: str | None = None,
    summary: str = "",
) -> dict[str, Any]:
    require_id(track_id, "track id")
    if get_track(track_id):
        raise ValueError(f"track already exists: {track_id}")
    track = {
        "id": track_id,
        "title": title,
        "status": status,
        "current_buddy": current_buddy,
        "next_buddy": next_buddy,
        "task_ids": [],
        "summary": summary,
        "updated_at": now_iso(),
    }
    return save_track(track)


def update_track(track_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    track = get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    allowed = {"title", "status", "current_buddy", "next_buddy", "summary", "task_ids"}
    for key, value in patch.items():
        if key not in allowed:
            raise ValueError(f"unsupported track field: {key}")
        track[key] = value
    track["updated_at"] = now_iso()
    return save_track(track)


def advance_track(
    track_id: str,
    *,
    current_buddy: str | None = None,
    next_buddy: str | None = None,
    status: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if current_buddy is not None:
        patch["current_buddy"] = current_buddy
    if next_buddy is not None:
        patch["next_buddy"] = next_buddy
    if status is not None:
        patch["status"] = status
    if summary is not None:
        patch["summary"] = summary
    if not patch:
        raise ValueError("advance requires at least one field")
    return update_track(track_id, patch)


def _register_task_id(track_id: str, task_id: str) -> dict[str, Any]:
    track = get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    if task_id not in track["task_ids"]:
        track["task_ids"].append(task_id)
        track["updated_at"] = now_iso()
        track = save_track(track)
    return track


def _unregister_task_id(track_id: str, task_id: str) -> dict[str, Any]:
    track = get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    next_ids = [item for item in track["task_ids"] if item != task_id]
    if len(next_ids) != len(track["task_ids"]):
        track["task_ids"] = next_ids
        track["updated_at"] = now_iso()
        track = save_track(track)
    return track


def create_task(
    task_id: str,
    title: str,
    *,
    buddy: str,
    track_id: str | None = None,
    status: str = "active",
    summary: str = "",
    initial_run_id: str,
) -> dict[str, Any]:
    require_id(task_id, "task id")
    require_id(initial_run_id, "task.initial_run_id")
    if get_task(task_id):
        raise ValueError(f"task already exists: {task_id}")
    if track_id is not None and get_track(track_id) is None:
        raise ValueError(f"track not found: {track_id}")
    timestamp = now_iso()
    task = {
        "id": task_id,
        "buddy": buddy,
        "title": title,
        "status": status,
        "track_id": track_id,
        "artifact_ids": [],
        "run_ids": [initial_run_id],
        "latest_run_id": initial_run_id,
        "latest_artifact_id": None,
        "summary": summary,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    task = save_task(task)
    if track_id:
        _register_task_id(track_id, task_id)
    return task


def update_task(task_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise ValueError(f"task not found: {task_id}")
    old_track = task.get("track_id")
    allowed = {
        "title",
        "status",
        "track_id",
        "summary",
        "artifact_ids",
        "run_ids",
        "latest_run_id",
        "latest_artifact_id",
    }
    for key, value in patch.items():
        if key not in allowed:
            raise ValueError(f"unsupported task field: {key}")
        task[key] = value
    new_track = task.get("track_id")
    if new_track is not None and get_track(new_track) is None:
        raise ValueError(f"track not found: {new_track}")
    task["updated_at"] = now_iso()
    task = save_task(task)
    if old_track and old_track != new_track:
        _unregister_task_id(old_track, task_id)
    if new_track:
        _register_task_id(new_track, task_id)
    return task


def register_task_to_track(track_id: str, task_id: str) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise ValueError(f"task not found: {task_id}")
    if task.get("track_id") not in {None, track_id}:
        raise ValueError(f"task '{task_id}' is already bound to track '{task['track_id']}'")
    if task.get("track_id") != track_id:
        task = update_task(task_id, {"track_id": track_id})
    _register_task_id(track_id, task_id)
    return task


def add_run_to_task(task_id: str, run_id: str, *, summary: str | None = None) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise ValueError(f"task not found: {task_id}")
    if run_id not in task["run_ids"]:
        task["run_ids"].append(run_id)
    task["latest_run_id"] = run_id
    if summary is not None:
        task["summary"] = summary
    task["updated_at"] = now_iso()
    return save_task(task)


def add_artifact_to_task(task_id: str, artifact_id: str, *, summary: str | None = None) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise ValueError(f"task not found: {task_id}")
    if artifact_id not in task["artifact_ids"]:
        task["artifact_ids"].append(artifact_id)
    task["latest_artifact_id"] = artifact_id
    if summary is not None:
        task["summary"] = summary
    task["updated_at"] = now_iso()
    return save_task(task)


def remove_artifact_from_task(task_id: str, artifact_id: str) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise ValueError(f"task not found: {task_id}")
    task["artifact_ids"] = [item for item in task["artifact_ids"] if item != artifact_id]
    if task.get("latest_artifact_id") == artifact_id:
        task["latest_artifact_id"] = task["artifact_ids"][-1] if task["artifact_ids"] else None
    task["updated_at"] = now_iso()
    return save_task(task)


def create_artifact(
    *,
    artifact_id: str | None,
    title: str,
    buddy: str,
    skill_id: str,
    task_id: str,
    source_run_id: str,
    summary: str = "",
    content: dict[str, Any] | None = None,
    auto_register: bool = True,
) -> dict[str, Any]:
    ensure_dirs()
    task = get_task(task_id)
    if task is None:
        raise ValueError(f"task not found: {task_id}")
    resolved_id = artifact_id or f"art-{uuid.uuid4().hex[:10]}"
    require_id(resolved_id, "artifact id")
    if get_artifact(resolved_id):
        raise ValueError(f"artifact already exists: {resolved_id}")
    if task["buddy"] != buddy:
        raise ValueError(f"artifact.buddy '{buddy}' must match task buddy '{task['buddy']}'")
    timestamp = now_iso()
    artifact = {
        "id": resolved_id,
        "title": title,
        "task_id": task_id,
        "buddy": buddy,
        "skill_id": skill_id,
        "source_run_id": require_id(source_run_id, "artifact.source_run_id"),
        "summary": summary,
        "content": content or {},
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    artifact = save_artifact(artifact)
    if auto_register:
        add_artifact_to_task(task_id, resolved_id, summary=summary or None)
    return artifact


def update_artifact(
    artifact_id: str,
    patch: dict[str, Any],
    *,
    auto_register: bool = True,
) -> dict[str, Any]:
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")
    old_task_id = artifact.get("task_id")
    allowed = {
        "title",
        "task_id",
        "buddy",
        "skill_id",
        "source_run_id",
        "summary",
        "content",
    }
    for key, value in patch.items():
        if key not in allowed:
            raise ValueError(f"unsupported artifact field: {key}")
        if key == "content":
            if not isinstance(value, dict):
                raise ValueError("artifact.content must be an object")
            artifact[key] = value
        elif key == "summary":
            if value is not None and not isinstance(value, str):
                raise ValueError("artifact.summary must be a string or null")
            artifact[key] = value or ""
        else:
            artifact[key] = value

    new_task_id = artifact.get("task_id")
    task = get_task(new_task_id)
    if task is None:
        raise ValueError(f"task not found: {new_task_id}")
    if artifact.get("buddy") != task["buddy"]:
        raise ValueError("artifact.buddy must match artifact.task_id owner")
    require_id(artifact.get("source_run_id"), "artifact.source_run_id")

    artifact["updated_at"] = now_iso()
    artifact = save_artifact(artifact)

    if auto_register:
        if old_task_id and old_task_id != new_task_id:
            remove_artifact_from_task(old_task_id, artifact_id)
        add_artifact_to_task(new_task_id, artifact_id, summary=artifact.get("summary") or None)
    return artifact


def delete_artifact(artifact_id: str, *, delete_file: bool = False) -> dict[str, Any]:
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")
    task_id = artifact.get("task_id")
    if isinstance(task_id, str) and task_id:
        remove_artifact_from_task(task_id, artifact_id)
    object_path = artifact_file(artifact_id)
    if object_path.exists():
        object_path.unlink()
    return artifact


def delete_artifacts_by_buddy(
    buddy_id: str,
    *,
    delete_files: bool = False,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    targets = [artifact for artifact in list_artifacts() if artifact.get("buddy") == buddy_id]
    if dry_run:
        return targets
    for artifact in targets:
        delete_artifact(artifact["id"], delete_file=delete_files)
    return targets


def delete_all_artifacts(*, delete_files: bool = False, dry_run: bool = False) -> list[dict[str, Any]]:
    targets = list_artifacts()
    if dry_run:
        return targets
    for artifact in targets:
        delete_artifact(artifact["id"], delete_file=delete_files)
    return targets


def save_run_content(run_id: str, payload: dict[str, Any]) -> str:
    ensure_dirs()
    path = ROOT / run_content_path(run_id)
    _write_json(path, payload)
    return rel(path)
