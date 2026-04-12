#!/usr/bin/env python3
"""BuddySwitch env object store for tracks and artifacts."""

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
ARTIFACT_OBJECTS_DIR = OBJECTS_ROOT / "artifacts"
CONTENT_ROOT = ROOT / "buddyswitch" / "content"
RUN_CONTENT_DIR = CONTENT_ROOT / "runs"
VALID_TRACK_STATUS = ("active", "blocked", "done", "archived")
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def ensure_dirs() -> None:
    TRACKS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_OBJECTS_DIR.mkdir(parents=True, exist_ok=True)
    RUN_CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    for marker in (
        TRACKS_DIR / ".gitkeep",
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
    track_id = require_id(track.get("id", ""), "track.id")
    title = track.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("track.title must be a non-empty string")
    status = track.get("status")
    if status not in VALID_TRACK_STATUS:
        raise ValueError(f"track.status must be one of {', '.join(VALID_TRACK_STATUS)}")
    current_buddy = track.get("current_buddy")
    if not isinstance(current_buddy, str) or not current_buddy:
        raise ValueError("track.current_buddy must be a non-empty string")
    next_buddy = track.get("next_buddy")
    if next_buddy is not None and (not isinstance(next_buddy, str) or not next_buddy):
        raise ValueError("track.next_buddy must be a non-empty string or null")
    artifact_ids = track.get("artifact_ids")
    if not isinstance(artifact_ids, list) or any(not isinstance(item, str) or not item for item in artifact_ids):
        raise ValueError("track.artifact_ids must be a list of non-empty strings")
    summary = track.get("summary")
    if summary is not None and not isinstance(summary, str):
        raise ValueError("track.summary must be a string or null")
    updated_at = track.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at:
        raise ValueError("track.updated_at must be a non-empty string")
    return {
        "id": track_id,
        "title": title.strip(),
        "status": status,
        "current_buddy": current_buddy,
        "next_buddy": next_buddy,
        "artifact_ids": list(dict.fromkeys(artifact_ids)),
        "summary": summary or "",
        "updated_at": updated_at,
    }


def validate_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    artifact_id = require_id(artifact.get("id", ""), "artifact.id")
    title = artifact.get("title")
    buddy = artifact.get("buddy")
    skill_id = artifact.get("skill_id")
    created_at = artifact.get("created_at")
    updated_at = artifact.get("updated_at")
    track_id = artifact.get("track_id")
    summary = artifact.get("summary")
    content = artifact.get("content", {})

    if not isinstance(title, str) or not title.strip():
        raise ValueError("artifact.title must be a non-empty string")
    if not isinstance(buddy, str) or not buddy.strip():
        raise ValueError("artifact.buddy must be a non-empty string")
    if not isinstance(skill_id, str) or not skill_id.strip():
        raise ValueError("artifact.skill_id must be a non-empty string")
    if not isinstance(created_at, str) or not created_at:
        raise ValueError("artifact.created_at must be a non-empty string")
    if not isinstance(updated_at, str) or not updated_at:
        raise ValueError("artifact.updated_at must be a non-empty string")
    if track_id is not None:
        require_id(track_id, "artifact.track_id")
    if summary is not None and not isinstance(summary, str):
        raise ValueError("artifact.summary must be a string or null")
    if not isinstance(content, dict):
        raise ValueError("artifact.content must be an object")

    return {
        "id": artifact_id,
        "title": title.strip(),
        "track_id": track_id,
        "buddy": buddy.strip(),
        "skill_id": skill_id.strip(),
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
        "artifact_ids": [],
        "summary": summary,
        "updated_at": now_iso(),
    }
    return save_track(track)


def update_track(track_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    track = get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    allowed = {"title", "status", "current_buddy", "next_buddy", "summary", "artifact_ids"}
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


def _attach_id_to_track(track_id: str, artifact_id: str) -> dict[str, Any]:
    track = get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    if artifact_id not in track["artifact_ids"]:
        track["artifact_ids"].append(artifact_id)
        track["updated_at"] = now_iso()
        track = save_track(track)
    return track


def _detach_id_from_track(track_id: str, artifact_id: str) -> dict[str, Any]:
    track = get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    next_ids = [item for item in track["artifact_ids"] if item != artifact_id]
    if len(next_ids) != len(track["artifact_ids"]):
        track["artifact_ids"] = next_ids
        track["updated_at"] = now_iso()
        track = save_track(track)
    return track


def attach_artifact(track_id: str, artifact_id: str) -> dict[str, Any]:
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")
    _attach_id_to_track(track_id, artifact_id)
    if artifact.get("track_id") != track_id:
        artifact["track_id"] = track_id
        artifact["updated_at"] = now_iso()
        save_artifact(artifact)
        artifact = get_artifact(artifact_id) or artifact
    return artifact


def detach_artifact(track_id: str, artifact_id: str) -> dict[str, Any]:
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")
    _detach_id_from_track(track_id, artifact_id)
    if artifact.get("track_id") == track_id:
        artifact["track_id"] = None
        artifact["updated_at"] = now_iso()
        save_artifact(artifact)
        artifact = get_artifact(artifact_id) or artifact
    return artifact


def create_artifact(
    *,
    artifact_id: str | None,
    title: str,
    buddy: str,
    skill_id: str,
    track_id: str | None = None,
    summary: str = "",
    content: dict[str, Any] | None = None,
    auto_register: bool = True,
) -> dict[str, Any]:
    ensure_dirs()
    resolved_id = artifact_id or f"art-{uuid.uuid4().hex[:10]}"
    require_id(resolved_id, "artifact id")
    if get_artifact(resolved_id):
        raise ValueError(f"artifact already exists: {resolved_id}")
    if track_id is not None and get_track(track_id) is None:
        raise ValueError(f"track not found: {track_id}")
    timestamp = now_iso()
    artifact = {
        "id": resolved_id,
        "title": title,
        "track_id": track_id,
        "buddy": buddy,
        "skill_id": skill_id,
        "summary": summary,
        "content": content or {},
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    artifact = save_artifact(artifact)
    if auto_register and track_id:
        _attach_id_to_track(track_id, resolved_id)
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
    old_track = artifact.get("track_id")
    allowed = {
        "title",
        "track_id",
        "buddy",
        "skill_id",
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
    new_track = artifact.get("track_id")
    if new_track is not None and get_track(new_track) is None:
        raise ValueError(f"track not found: {new_track}")
    artifact["updated_at"] = now_iso()
    artifact = save_artifact(artifact)
    if auto_register:
        if old_track and old_track != new_track:
            _detach_id_from_track(old_track, artifact_id)
        if new_track:
            _attach_id_to_track(new_track, artifact_id)
    return artifact


def delete_artifact(artifact_id: str, *, delete_file: bool = False) -> dict[str, Any]:
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")
    track_id = artifact.get("track_id")
    if track_id:
        _detach_id_from_track(track_id, artifact_id)
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
