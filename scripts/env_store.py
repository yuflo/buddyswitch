#!/usr/bin/env python3
"""BuddySwitch runless env object store for durable collaboration objects."""

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
_RAW_STATE_ROOT = os.environ.get("BUDDYSWITCH_STATE_ROOT")
if isinstance(_RAW_STATE_ROOT, str) and _RAW_STATE_ROOT.strip():
    STATE_ROOT = Path(_RAW_STATE_ROOT.strip()).expanduser().resolve(strict=False)
else:
    STATE_ROOT = ROOT

OBJECTS_ROOT = STATE_ROOT / "buddyswitch" / "objects"
TRACKS_DIR = OBJECTS_ROOT / "tracks"
TASKS_DIR = OBJECTS_ROOT / "tasks"
ARTIFACT_OBJECTS_DIR = OBJECTS_ROOT / "artifacts"
HANDOFF_OBJECTS_DIR = OBJECTS_ROOT / "handoffs"
CONTENT_ROOT = STATE_ROOT / "buddyswitch" / "content"
BUDDYBOX_CONTENT_DIR = CONTENT_ROOT / "buddybox"

RUNTIME_WORKSPACE_AGENTS_HEADER = "# BuddySwitch Runtime Workspace"

VALID_TRACK_STATUS = ("active", "blocked", "done", "archived")
VALID_TASK_STATUS = ("active", "blocked", "done", "archived")
VALID_HANDOFF_STATUS = ("active", "superseded", "archived")

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_LEGACY_TASK_RUN_IDS = "run" + "_ids"
_LEGACY_TASK_LATEST_RUN = "latest" + "_run_id"
_LEGACY_SOURCE_RUN = "source" + "_run_id"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    for candidate_root in (ROOT, STATE_ROOT):
        try:
            return path.relative_to(candidate_root).as_posix()
        except ValueError:
            continue
    return path.as_posix()


def runtime_workspace_agents_file(root: Path | None = None) -> Path:
    return (ROOT if root is None else root) / "AGENTS.md"


def is_runtime_workspace(root: Path | None = None) -> bool:
    agents_path = runtime_workspace_agents_file(root)
    try:
        first_line = agents_path.read_text(encoding="utf-8").splitlines()[0].strip()
    except (IndexError, OSError):
        return False
    return first_line == RUNTIME_WORKSPACE_AGENTS_HEADER


def require_runtime_workspace_write_root(root: Path | None = None) -> None:
    candidate = ROOT if root is None else root
    if is_runtime_workspace(candidate):
        return
    raise ValueError(
        "BuddySwitch runtime writes are blocked in the source checkout. "
        "Start the launcher workspace with ./buddyswitch-codex instance start --buddy <buddy> and rerun there."
    )


def ensure_runtime_dirs() -> None:
    require_runtime_workspace_write_root()
    TRACKS_DIR.mkdir(parents=True, exist_ok=True)
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_OBJECTS_DIR.mkdir(parents=True, exist_ok=True)
    HANDOFF_OBJECTS_DIR.mkdir(parents=True, exist_ok=True)
    BUDDYBOX_CONTENT_DIR.mkdir(parents=True, exist_ok=True)


def require_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not ID_PATTERN.match(value):
        raise ValueError(f"{label} must match /^[a-z0-9][a-z0-9-]*$/")
    return value


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned or "artifact"


def track_file(track_id: str) -> Path:
    return TRACKS_DIR / f"{require_id(track_id, 'track id')}.json"


def task_file(task_id: str) -> Path:
    return TASKS_DIR / f"{require_id(task_id, 'task id')}.json"


def artifact_file(artifact_id: str) -> Path:
    return ARTIFACT_OBJECTS_DIR / f"{require_id(artifact_id, 'artifact id')}.json"


def handoff_file(handoff_id: str) -> Path:
    return HANDOFF_OBJECTS_DIR / f"{require_id(handoff_id, 'handoff id')}.json"


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


def _validate_buddybox_ref_path(path: Any) -> str:
    if not isinstance(path, str) or not path.strip():
        raise ValueError("source_refs.buddybox path must be a non-empty string")
    normalized = path.replace("\\", "/").strip()
    if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
        raise ValueError("source_refs.buddybox path must be relative and stay inside buddybox")
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    if not parts:
        raise ValueError("source_refs.buddybox path must be non-empty")
    return "/".join(parts)


def _normalize_source_refs(raw_refs: Any) -> list[dict[str, Any]] | None:
    if raw_refs is None:
        return None
    if not isinstance(raw_refs, list):
        raise ValueError("source_refs must be a list when provided")

    normalized: list[dict[str, Any]] = []
    for raw in raw_refs:
        if not isinstance(raw, dict):
            raise ValueError("each source_ref must be an object")
        ref_type = raw.get("type")
        if not isinstance(ref_type, str) or not ref_type.strip():
            raise ValueError("source_ref.type must be a non-empty string")
        ref_type = ref_type.strip()
        row: dict[str, Any] = {"type": ref_type}

        if ref_type in {"artifact", "track", "task", "handoff"}:
            row["id"] = require_id(raw.get("id"), f"source_ref.{ref_type}.id")
        elif ref_type == "buddybox":
            row["path"] = _validate_buddybox_ref_path(raw.get("path"))
        elif ref_type == "external":
            label = raw.get("label")
            if not isinstance(label, str) or not label.strip():
                raise ValueError("source_ref.external.label must be a non-empty string")
            row["label"] = label.strip()
            url = raw.get("url")
            if url is not None:
                if not isinstance(url, str) or not url.strip():
                    raise ValueError("source_ref.external.url must be a non-empty string when provided")
                row["url"] = url.strip()
        elif ref_type == "note":
            label = raw.get("label")
            if not isinstance(label, str) or not label.strip():
                raise ValueError("source_ref.note.label must be a non-empty string")
            row["label"] = label.strip()
        else:
            raise ValueError(f"unsupported source_ref type: {ref_type}")

        normalized.append(row)
    return normalized


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
    for task_id in task_ids:
        require_id(task_id, "track.task_ids[]")
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
    if _LEGACY_TASK_RUN_IDS in task or _LEGACY_TASK_LATEST_RUN in task:
        raise ValueError("legacy task run lineage fields are retired; use artifact_ids and artifact_slots")

    task_id = require_id(task.get("id", ""), "task.id")
    buddy = task.get("buddy")
    title = task.get("title")
    status = task.get("status")
    track_id = task.get("track_id")
    artifact_ids = task.get("artifact_ids")
    artifact_slots = task.get("artifact_slots", {})
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
    for artifact_id in artifact_ids:
        require_id(artifact_id, "task.artifact_ids[]")
    if not isinstance(artifact_slots, dict):
        raise ValueError("task.artifact_slots must be an object")

    normalized_slots: dict[str, dict[str, Any]] = {}
    for slot, row in artifact_slots.items():
        if not isinstance(slot, str) or not slot.strip():
            raise ValueError("task.artifact_slots keys must be non-empty strings")
        if not isinstance(row, dict):
            raise ValueError("task.artifact_slots values must be objects")
        current_artifact_id = row.get("current_artifact_id")
        revision_count = row.get("revision_count")
        require_id(current_artifact_id, f"task.artifact_slots[{slot}].current_artifact_id")
        if not isinstance(revision_count, int) or revision_count <= 0:
            raise ValueError("task.artifact_slots revision_count must be a positive integer")
        normalized_slots[slot] = {
            "current_artifact_id": current_artifact_id,
            "revision_count": revision_count,
        }

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
        "artifact_slots": normalized_slots,
        "summary": summary or "",
        "created_at": created_at,
        "updated_at": updated_at,
    }


def validate_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    if "track_id" in artifact:
        raise ValueError("artifact.track_id is retired; use artifact.task_id")
    if _LEGACY_SOURCE_RUN in artifact:
        raise ValueError("legacy artifact run lineage field is retired; use created_by and source_refs")

    artifact_id = require_id(artifact.get("id", ""), "artifact.id")
    title = artifact.get("title")
    task_id = artifact.get("task_id")
    buddy = artifact.get("buddy")
    kind = artifact.get("kind")
    revision = artifact.get("revision")
    supersedes_sentinel = object()
    supersedes_artifact_id = artifact.get("supersedes_artifact_id", supersedes_sentinel)
    is_current = artifact.get("is_current")
    created_by = artifact.get("created_by")
    source_refs = _normalize_source_refs(artifact.get("source_refs"))
    summary = artifact.get("summary")
    content = artifact.get("content", {})
    created_at = artifact.get("created_at")
    updated_at = artifact.get("updated_at")

    if not isinstance(title, str) or not title.strip():
        raise ValueError("artifact.title must be a non-empty string")
    require_id(task_id, "artifact.task_id")
    if not isinstance(buddy, str) or not buddy.strip():
        raise ValueError("artifact.buddy must be a non-empty string")
    if not isinstance(kind, str) or not kind.strip():
        raise ValueError("artifact.kind must be a non-empty string")
    require_id(kind.strip(), "artifact.kind")
    if not isinstance(revision, int) or revision <= 0:
        raise ValueError("artifact.revision must be a positive integer")
    if supersedes_artifact_id is supersedes_sentinel:
        raise ValueError("artifact.supersedes_artifact_id must be present")
    if supersedes_artifact_id is not None:
        require_id(supersedes_artifact_id, "artifact.supersedes_artifact_id")
    if not isinstance(is_current, bool):
        raise ValueError("artifact.is_current must be a boolean")
    if not isinstance(created_by, str) or not created_by.strip():
        raise ValueError("artifact.created_by must be a non-empty string")
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
        "kind": kind.strip(),
        "revision": revision,
        "supersedes_artifact_id": supersedes_artifact_id,
        "is_current": is_current,
        "created_by": created_by.strip(),
        "source_refs": source_refs,
        "summary": summary or "",
        "content": content,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def validate_handoff_record(record: dict[str, Any]) -> dict[str, Any]:
    if _LEGACY_SOURCE_RUN in record:
        raise ValueError("legacy handoff run lineage field is retired; use product object refs")
    if "historical_artifact_ids" in record:
        raise ValueError("handoff.historical_artifact_ids is retired; use source_refs")

    handoff_id = require_id(record.get("id", ""), "handoff.id")
    track_id = require_id(record.get("track_id", ""), "handoff.track_id")
    source_buddy = record.get("source_buddy")
    target_buddy = record.get("target_buddy")
    source_task_id = record.get("source_task_id")
    artifact_ids = record.get("artifact_ids", [])
    buddybox_paths = record.get("buddybox_paths", [])
    source_refs = _normalize_source_refs(record.get("source_refs"))
    reason = record.get("reason")
    context = record.get("context")
    status = record.get("status")
    created_at = record.get("created_at")
    updated_at = record.get("updated_at")

    if not isinstance(source_buddy, str) or not source_buddy.strip():
        raise ValueError("handoff.source_buddy must be a non-empty string")
    if not isinstance(target_buddy, str) or not target_buddy.strip():
        raise ValueError("handoff.target_buddy must be a non-empty string")
    if source_task_id is not None:
        require_id(source_task_id, "handoff.source_task_id")
    if status not in VALID_HANDOFF_STATUS:
        raise ValueError(f"handoff.status must be one of {', '.join(VALID_HANDOFF_STATUS)}")

    if not isinstance(artifact_ids, list) or any(not isinstance(item, str) or not item.strip() for item in artifact_ids):
        raise ValueError("handoff.artifact_ids must be a list of non-empty strings")
    for artifact_id in artifact_ids:
        require_id(artifact_id, "handoff.artifact_ids[]")

    if not isinstance(buddybox_paths, list) or any(not isinstance(item, str) or not item.strip() for item in buddybox_paths):
        raise ValueError("handoff.buddybox_paths must be a list of non-empty strings")
    normalized_buddybox_paths = [_validate_buddybox_ref_path(path) for path in buddybox_paths]

    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("handoff.reason must be a non-empty string")
    if not isinstance(context, str) or not context.strip():
        raise ValueError("handoff.context must be a non-empty string")
    if not isinstance(created_at, str) or not created_at:
        raise ValueError("handoff.created_at must be a non-empty string")
    if not isinstance(updated_at, str) or not updated_at:
        raise ValueError("handoff.updated_at must be a non-empty string")

    return {
        "id": handoff_id,
        "track_id": track_id,
        "source_buddy": source_buddy.strip(),
        "target_buddy": target_buddy.strip(),
        "source_task_id": source_task_id,
        "artifact_ids": list(dict.fromkeys(artifact_ids)),
        "buddybox_paths": list(dict.fromkeys(normalized_buddybox_paths)),
        "source_refs": source_refs,
        "reason": reason.strip(),
        "context": context.strip(),
        "status": status,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _artifact_kind_name(task: dict[str, Any], artifact: dict[str, Any] | None = None) -> str:
    if artifact is not None:
        kind = artifact.get("kind")
        if isinstance(kind, str) and kind.strip():
            return kind.strip()
    task_title = task.get("title")
    if isinstance(task_title, str) and task_title.strip():
        return slugify(task_title)
    return "artifact"


def _task_kind_state(task: dict[str, Any], kind: str) -> dict[str, Any] | None:
    artifact_slots = task.get("artifact_slots", {})
    if not isinstance(artifact_slots, dict):
        return None
    row = artifact_slots.get(kind)
    return row if isinstance(row, dict) else None


def list_tracks() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in TRACKS_DIR.glob("*.json"):
        rows.append(validate_track(_read_json(path)))
    rows.sort(key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
    return rows


def list_tasks() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in TASKS_DIR.glob("*.json"):
        rows.append(validate_task(_read_json(path)))
    rows.sort(key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
    return rows


def list_artifacts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in ARTIFACT_OBJECTS_DIR.glob("*.json"):
        rows.append(validate_artifact(_read_json(path)))
    rows.sort(key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
    return rows


def list_handoffs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in HANDOFF_OBJECTS_DIR.glob("*.json"):
        rows.append(validate_handoff_record(_read_json(path)))
    rows.sort(key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
    return rows


def _task_artifacts_from_map(task: dict[str, Any], artifact_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [artifact_map[item] for item in task.get("artifact_ids", []) if item in artifact_map]
    rows.sort(key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
    return rows


def build_track_artifact_index(track_id: str | None) -> dict[str, Any] | None:
    if not track_id:
        return None
    track = get_track(track_id)
    if track is None:
        return None

    artifact_map = {artifact["id"]: artifact for artifact in list_artifacts()}
    track_updated_at = track.get("updated_at", "")
    task_rows: list[dict[str, Any]] = []
    for task_id in track.get("task_ids", []):
        task = get_task(task_id)
        if task is None:
            continue
        task_updated_at = task.get("updated_at", "")
        if task_updated_at > track_updated_at:
            track_updated_at = task_updated_at
        artifacts = _task_artifacts_from_map(task, artifact_map)
        artifact_rows: list[dict[str, Any]] = []
        for artifact in artifacts:
            artifact_updated_at = artifact.get("updated_at", "")
            if artifact_updated_at > track_updated_at:
                track_updated_at = artifact_updated_at
            artifact_rows.append(
                {
                    "artifact_id": artifact["id"],
                    "title": artifact["title"],
                    "kind": artifact.get("kind"),
                    "revision": artifact.get("revision"),
                    "supersedes_artifact_id": artifact.get("supersedes_artifact_id"),
                    "summary": artifact.get("summary", ""),
                    "created_by": artifact.get("created_by"),
                    "source_refs": artifact.get("source_refs"),
                    "source_buddy": artifact.get("buddy"),
                    "updated_at": artifact_updated_at,
                    "is_current": bool(artifact.get("is_current")),
                }
            )

        task_rows.append(
            {
                "task_id": task["id"],
                "buddy": task["buddy"],
                "task_title": task["title"],
                "task_summary": task.get("summary", ""),
                "artifact_slots": task.get("artifact_slots", {}),
                "artifacts": artifact_rows,
            }
        )

    return {
        "track_id": track["id"],
        "track_title": track["title"],
        "track_summary": track.get("summary", ""),
        "updated_at": track_updated_at,
        "tasks": task_rows,
    }


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


def get_handoff(handoff_id: str) -> dict[str, Any] | None:
    path = handoff_file(handoff_id)
    if not path.exists():
        return None
    return validate_handoff_record(_read_json(path))


def save_track(track: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_track(track)
    ensure_runtime_dirs()
    _write_json(track_file(normalized["id"]), normalized)
    return normalized


def save_task(task: dict[str, Any]) -> dict[str, Any]:
    ensure_runtime_dirs()
    normalized = validate_task(task)
    _write_json(task_file(normalized["id"]), normalized)
    return normalized


def save_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    ensure_runtime_dirs()
    normalized = validate_artifact(artifact)
    _write_json(artifact_file(normalized["id"]), normalized)
    return normalized


def save_handoff(record: dict[str, Any]) -> dict[str, Any]:
    ensure_runtime_dirs()
    normalized = validate_handoff_record(record)
    _write_json(handoff_file(normalized["id"]), normalized)
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
    initial_run_id: str | None = None,
) -> dict[str, Any]:
    require_id(task_id, "task id")
    if initial_run_id is not None:
        raise ValueError("task.initial_run_id is retired in runless runtime")
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
        "artifact_slots": {},
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
        "artifact_slots",
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


def add_artifact_to_task(task_id: str, artifact_id: str, *, summary: str | None = None) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise ValueError(f"task not found: {task_id}")
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")
    kind = _artifact_kind_name(task, artifact)
    revision = artifact.get("revision")
    if not isinstance(revision, int) or revision <= 0:
        raise ValueError("artifact.revision must be a positive integer")
    if artifact_id not in task["artifact_ids"]:
        task["artifact_ids"].append(artifact_id)
    artifact_slots = task.setdefault("artifact_slots", {})
    current_kind = artifact_slots.get(kind)
    if not isinstance(current_kind, dict):
        current_kind = None
    current_artifact_id = current_kind.get("current_artifact_id") if current_kind else None
    current_revision_count = current_kind.get("revision_count") if current_kind else None
    if current_kind is None or not isinstance(current_artifact_id, str) or not current_artifact_id:
        if not artifact.get("is_current"):
            artifact["is_current"] = True
            artifact["updated_at"] = now_iso()
            save_artifact(artifact)
        artifact_slots[kind] = {
            "current_artifact_id": artifact_id,
            "revision_count": revision,
        }
    elif artifact.get("is_current"):
        if current_artifact_id != artifact_id:
            current_artifact = get_artifact(current_artifact_id)
            if current_artifact is not None:
                current_artifact["is_current"] = False
                current_artifact["updated_at"] = now_iso()
                save_artifact(current_artifact)
        artifact_slots[kind] = {
            "current_artifact_id": artifact_id,
            "revision_count": max(current_revision_count if isinstance(current_revision_count, int) else 0, revision),
        }
    else:
        artifact_slots[kind] = {
            "current_artifact_id": current_artifact_id,
            "revision_count": max(current_revision_count if isinstance(current_revision_count, int) else 0, revision),
        }
    if summary is not None:
        task["summary"] = summary
    task["updated_at"] = now_iso()
    return save_task(task)


def remove_artifact_from_task(task_id: str, artifact_id: str) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise ValueError(f"task not found: {task_id}")
    artifact = get_artifact(artifact_id)
    kind = _artifact_kind_name(task, artifact) if artifact else None
    kind_state = _task_kind_state(task, kind) if kind else None
    task["artifact_ids"] = [item for item in task["artifact_ids"] if item != artifact_id]
    if kind and kind_state is not None and isinstance(task.get("artifact_slots"), dict):
        deleting_current = kind_state.get("current_artifact_id") == artifact_id
        if deleting_current:
            candidates = []
            artifact_map = {item["id"]: item for item in list_artifacts()}
            for candidate_id in task["artifact_ids"]:
                candidate = artifact_map.get(candidate_id)
                if candidate is None:
                    continue
                if _artifact_kind_name(task, candidate) == kind:
                    candidates.append(candidate)
            if candidates:
                candidates.sort(key=lambda row: (row.get("revision", 0), row.get("updated_at", ""), row["id"]), reverse=True)
                promoted = candidates[0]
                revision_count = kind_state.get("revision_count", promoted["revision"])
                if not isinstance(revision_count, int) or revision_count < promoted["revision"]:
                    revision_count = promoted["revision"]
                timestamp = now_iso()
                for candidate in candidates:
                    candidate["is_current"] = candidate["id"] == promoted["id"]
                    candidate["updated_at"] = timestamp
                    save_artifact(candidate)
                task["artifact_slots"][kind] = {
                    "current_artifact_id": promoted["id"],
                    "revision_count": revision_count,
                }
            else:
                task["artifact_slots"].pop(kind, None)
    task["updated_at"] = now_iso()
    return save_task(task)


def create_artifact(
    *,
    artifact_id: str | None,
    title: str,
    buddy: str,
    kind: str,
    task_id: str,
    summary: str = "",
    content: dict[str, Any] | None = None,
    created_by: str,
    source_refs: list[dict[str, Any]] | None = None,
    legacy_source_run: str | None = None,
) -> dict[str, Any]:
    if legacy_source_run is not None:
        raise ValueError("legacy artifact run lineage field is retired; use source_refs")

    task = get_task(task_id)
    if task is None:
        raise ValueError(f"task not found: {task_id}")
    resolved_id = artifact_id or f"art-{uuid.uuid4().hex[:10]}"
    require_id(resolved_id, "artifact id")
    if get_artifact(resolved_id):
        raise ValueError(f"artifact already exists: {resolved_id}")
    if task["buddy"] != buddy:
        raise ValueError(f"artifact.buddy '{buddy}' must match task buddy '{task['buddy']}'")
    normalized_kind = kind.strip() if isinstance(kind, str) else ""
    require_id(normalized_kind, "artifact.kind")
    current_kind = _task_kind_state(task, normalized_kind)
    previous = get_artifact(current_kind["current_artifact_id"]) if current_kind else None
    revision = 1 if current_kind is None else int(current_kind["revision_count"]) + 1
    if previous is not None:
        previous["is_current"] = False
        previous["updated_at"] = now_iso()
        save_artifact(previous)

    timestamp = now_iso()
    artifact = {
        "id": resolved_id,
        "title": title,
        "task_id": task_id,
        "buddy": buddy,
        "kind": normalized_kind,
        "revision": revision,
        "supersedes_artifact_id": previous["id"] if previous else None,
        "is_current": True,
        "created_by": created_by,
        "source_refs": source_refs,
        "summary": summary,
        "content": content or {},
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    artifact = save_artifact(artifact)
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
    if _LEGACY_SOURCE_RUN in patch:
        raise ValueError("legacy artifact run lineage field is retired; use source_refs")

    allowed = {
        "title",
        "task_id",
        "buddy",
        "kind",
        "summary",
        "content",
        "created_by",
        "source_refs",
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
    require_id(artifact.get("kind"), "artifact.kind")

    artifact["updated_at"] = now_iso()
    artifact = save_artifact(artifact)

    if auto_register and old_task_id and old_task_id != new_task_id:
        remove_artifact_from_task(old_task_id, artifact_id)
        add_artifact_to_task(new_task_id, artifact_id, summary=artifact.get("summary") or None)
    return artifact


def create_handoff(
    *,
    handoff_id: str,
    track_id: str,
    source_buddy: str,
    target_buddy: str,
    source_task_id: str | None,
    artifact_ids: list[str],
    buddybox_paths: list[str],
    source_refs: list[dict[str, Any]] | None,
    reason: str,
    context: str,
    status: str = "active",
) -> dict[str, Any]:
    require_id(handoff_id, "handoff id")
    if get_handoff(handoff_id) is not None:
        raise ValueError(f"handoff already exists: {handoff_id}")
    payload = {
        "id": handoff_id,
        "track_id": require_id(track_id, "handoff.track_id"),
        "source_buddy": source_buddy,
        "target_buddy": target_buddy,
        "source_task_id": source_task_id,
        "artifact_ids": artifact_ids,
        "buddybox_paths": buddybox_paths,
        "source_refs": source_refs,
        "reason": reason,
        "context": context,
        "status": status,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    return save_handoff(payload)


def delete_artifact(artifact_id: str) -> dict[str, Any]:
    require_runtime_workspace_write_root()
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
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    targets = [artifact for artifact in list_artifacts() if artifact.get("buddy") == buddy_id]
    if dry_run:
        return targets
    for artifact in targets:
        delete_artifact(artifact["id"])
    return targets


def delete_all_artifacts(*, dry_run: bool = False) -> list[dict[str, Any]]:
    targets = list_artifacts()
    if dry_run:
        return targets
    for artifact in targets:
        delete_artifact(artifact["id"])
    return targets
