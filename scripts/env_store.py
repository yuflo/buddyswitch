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
MESSAGES_DIR = OBJECTS_ROOT / "messages"
COMMENTS_DIR = OBJECTS_ROOT / "comments"
CONTENT_ROOT = STATE_ROOT / "buddyswitch" / "content"
LOCAL_ROOT = STATE_ROOT / "buddyswitch" / "local"
BUDDYBOX_LOCAL_DIR = LOCAL_ROOT / "buddybox"

RUNTIME_WORKSPACE_AGENTS_HEADER = "# BuddySwitch Runtime Workspace"

VALID_TRACK_STATUS = ("active", "blocked", "done", "archived")
VALID_TASK_STATUS = ("active", "blocked", "done", "archived")

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_LEGACY_TASK_RUN_IDS = "run" + "_ids"
_LEGACY_TASK_LATEST_RUN = "latest" + "_run_id"
_LEGACY_SOURCE_RUN = "source" + "_run_id"
_LEGACY_TRACK_BUDDY_FIELDS = ("current" + "_buddy", "next" + "_buddy")
_KNOWN_BUDDY_IDS = {"pm", "design", "dev", "market", "test"}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def runtime_workspace_root(instance_payload: dict[str, Any] | None = None) -> Path:
    if isinstance(instance_payload, dict):
        candidate = instance_payload.get("workspace_dir")
        if isinstance(candidate, str) and candidate.strip():
            return Path(candidate.strip()).expanduser().resolve(strict=False)
    for env_key in ("BUDDYSWITCH_WORKSPACE_DIR", "BUDDYSWITCH_RUNTIME_WORKSPACE_ROOT"):
        raw = os.environ.get(env_key)
        if isinstance(raw, str) and raw.strip():
            return Path(raw.strip()).expanduser().resolve(strict=False)
    return ROOT


def buddybox_local_dir(instance_payload: dict[str, Any] | None = None) -> Path:
    return runtime_workspace_root(instance_payload) / "buddyswitch" / "local" / "buddybox"


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
    MESSAGES_DIR.mkdir(parents=True, exist_ok=True)
    COMMENTS_DIR.mkdir(parents=True, exist_ok=True)


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


def message_file(message_id: str) -> Path:
    return MESSAGES_DIR / f"{require_id(message_id, 'message id')}.json"


def comment_file(comment_id: str) -> Path:
    return COMMENTS_DIR / f"{require_id(comment_id, 'comment id')}.json"


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


def _validate_buddybox_ref_logical_name(logical_name: Any, *, active_buddy: str | None = None) -> str:
    if not isinstance(logical_name, str) or not logical_name.strip():
        raise ValueError("source_refs.buddybox.logical_name must be a non-empty string")
    normalized = logical_name.replace("\\", "/").strip()
    if normalized.startswith("/"):
        raise ValueError("source_refs.buddybox.logical_name must be relative")
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    if not parts:
        raise ValueError("source_refs.buddybox.logical_name must be non-empty")
    if any(part == ".." for part in parts):
        raise ValueError("source_refs.buddybox.logical_name must not include '..' traversal")
    blocked_prefixes = set(_KNOWN_BUDDY_IDS)
    if isinstance(active_buddy, str) and active_buddy:
        blocked_prefixes.add(active_buddy)
    if parts[0] in blocked_prefixes:
        raise ValueError("source_refs.buddybox.logical_name must not include a buddy prefix")
    return "/".join(parts)


def _normalize_source_refs(
    raw_refs: Any,
    *,
    active_buddy: str | None = None,
    allow_buddybox: bool = True,
) -> list[dict[str, Any]] | None:
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

        if ref_type in {"artifact", "track", "task"}:
            row["id"] = require_id(raw.get("id"), f"source_ref.{ref_type}.id")
        elif ref_type == "buddybox":
            if not allow_buddybox:
                raise ValueError("source_ref.buddybox is private provenance and cannot be used in this payload")
            if "path" in raw:
                raise ValueError("source_refs.buddybox.logical_name is required; path is retired")
            normalized_name = _validate_buddybox_ref_logical_name(raw.get("logical_name"), active_buddy=active_buddy)
            row["logical_name"] = normalized_name
            if isinstance(active_buddy, str) and active_buddy:
                row["private_to_buddy"] = active_buddy
            row["read_grant"] = False
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
    if any(field in track for field in _LEGACY_TRACK_BUDDY_FIELDS):
        raise ValueError("legacy track buddy-routing fields are retired; use immutable owner_buddy")

    track_id = require_id(track.get("id", ""), "track.id")
    title = track.get("title")
    status = track.get("status")
    owner_buddy = track.get("owner_buddy")
    task_ids = track.get("task_ids")
    comment_ids = track.get("comment_ids", [])
    summary = track.get("summary")
    updated_at = track.get("updated_at")

    if not isinstance(title, str) or not title.strip():
        raise ValueError("track.title must be a non-empty string")
    if status not in VALID_TRACK_STATUS:
        raise ValueError(f"track.status must be one of {', '.join(VALID_TRACK_STATUS)}")
    if not isinstance(owner_buddy, str) or not owner_buddy.strip():
        raise ValueError("track.owner_buddy must be a non-empty string")
    if not isinstance(task_ids, list) or any(not isinstance(item, str) or not item for item in task_ids):
        raise ValueError("track.task_ids must be a list of non-empty strings")
    for task_id in task_ids:
        require_id(task_id, "track.task_ids[]")
    if not isinstance(comment_ids, list):
        raise ValueError("track.comment_ids must be a list (missing normalizes to [])")
    for comment_id in comment_ids:
        if not isinstance(comment_id, str) or not comment_id:
            raise ValueError("track.comment_ids must contain only non-empty strings")
        require_id(comment_id, "track.comment_ids[]")
    if summary is not None and not isinstance(summary, str):
        raise ValueError("track.summary must be a string or null")
    if not isinstance(updated_at, str) or not updated_at:
        raise ValueError("track.updated_at must be a non-empty string")

    return {
        "id": track_id,
        "title": title.strip(),
        "status": status,
        "owner_buddy": owner_buddy.strip(),
        "task_ids": list(dict.fromkeys(task_ids)),
        "comment_ids": list(dict.fromkeys(comment_ids)),
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
    source_refs = _normalize_source_refs(
        artifact.get("source_refs"),
        active_buddy=buddy if isinstance(buddy, str) else None,
        allow_buddybox=True,
    )
    comment_ids = artifact.get("comment_ids", [])
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
    if not isinstance(comment_ids, list):
        raise ValueError("artifact.comment_ids must be a list (missing normalizes to [])")
    for comment_id in comment_ids:
        if not isinstance(comment_id, str) or not comment_id:
            raise ValueError("artifact.comment_ids must contain only non-empty strings")
        require_id(comment_id, "artifact.comment_ids[]")
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
        "comment_ids": list(dict.fromkeys(comment_ids)),
        "summary": summary or "",
        "content": content,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def validate_message(message: dict[str, Any]) -> dict[str, Any]:
    _FORBIDDEN_MSG_FIELDS = {"status", "read_at", "track_id", "task_id", "artifact_id", "recipients", "broadcast"}
    forbidden = sorted(key for key in message if key in _FORBIDDEN_MSG_FIELDS)
    if forbidden:
        raise ValueError(f"unsupported message fields: {', '.join(forbidden)}")

    msg_id = require_id(message.get("id", ""), "message.id")
    from_buddy = message.get("from_buddy")
    to_buddy = message.get("to_buddy")
    content = message.get("content")
    reply_to = message.get("reply_to")
    created_at = message.get("created_at")

    if not isinstance(from_buddy, str) or not from_buddy.strip():
        raise ValueError("message.from_buddy must be a non-empty string")
    if not isinstance(to_buddy, str) or not to_buddy.strip():
        raise ValueError("message.to_buddy must be a non-empty string")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("message.content must be a non-empty string")
    if reply_to is not None:
        require_id(reply_to, "message.reply_to")
    if not isinstance(created_at, str) or not created_at:
        raise ValueError("message.created_at must be a non-empty string")

    return {
        "id": msg_id,
        "from_buddy": from_buddy.strip(),
        "to_buddy": to_buddy.strip(),
        "content": content.strip(),
        "reply_to": reply_to,
        "created_at": created_at,
    }


def validate_comment(comment: dict[str, Any]) -> dict[str, Any]:
    _FORBIDDEN_CMT_FIELDS = {"status", "resolved", "resolved_at", "task_id", "edit_history", "attachment"}
    forbidden = sorted(key for key in comment if key in _FORBIDDEN_CMT_FIELDS)
    if forbidden:
        raise ValueError(f"unsupported comment fields: {', '.join(forbidden)}")

    cmt_id = require_id(comment.get("id", ""), "comment.id")
    target_type = comment.get("target_type")
    target_id = comment.get("target_id")
    author_buddy = comment.get("author_buddy")
    content = comment.get("content")
    reply_to = comment.get("reply_to")
    created_at = comment.get("created_at")

    if target_type not in {"track", "artifact"}:
        raise ValueError("comment.target_type must be 'track' or 'artifact'")
    require_id(target_id, "comment.target_id")
    if not isinstance(author_buddy, str) or not author_buddy.strip():
        raise ValueError("comment.author_buddy must be a non-empty string")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("comment.content must be a non-empty string")
    if reply_to is not None:
        require_id(reply_to, "comment.reply_to")
    if not isinstance(created_at, str) or not created_at:
        raise ValueError("comment.created_at must be a non-empty string")

    return {
        "id": cmt_id,
        "target_type": target_type,
        "target_id": target_id,
        "author_buddy": author_buddy.strip(),
        "content": content.strip(),
        "reply_to": reply_to,
        "created_at": created_at,
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


def create_track(
    track_id: str,
    title: str,
    *,
    status: str = "active",
    owner_buddy: str = "pm",
    summary: str = "",
) -> dict[str, Any]:
    require_id(track_id, "track id")
    if get_track(track_id):
        raise ValueError(f"track already exists: {track_id}")
    track = {
        "id": track_id,
        "title": title,
        "status": status,
        "owner_buddy": owner_buddy,
        "task_ids": [],
        "comment_ids": [],
        "summary": summary,
        "updated_at": now_iso(),
    }
    return save_track(track)


def update_track(track_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    track = get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    allowed = {"title", "status", "summary", "task_ids"}
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
        "comment_ids": [],
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


# ---------------------------------------------------------------------------
# Message object helpers
# ---------------------------------------------------------------------------


def list_messages() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if MESSAGES_DIR.is_dir():
        for path in MESSAGES_DIR.glob("*.json"):
            rows.append(validate_message(_read_json(path)))
    rows.sort(key=lambda row: (row.get("created_at", ""), row["id"]))
    return rows


def get_message(message_id: str) -> dict[str, Any] | None:
    path = message_file(message_id)
    if not path.exists():
        return None
    return validate_message(_read_json(path))


def save_message(message: dict[str, Any]) -> dict[str, Any]:
    normalize_message = validate_message(message)
    ensure_runtime_dirs()
    _write_json(message_file(normalize_message["id"]), normalize_message)
    return normalize_message


def create_message(
    *,
    from_buddy: str,
    to_buddy: str,
    content: str,
    reply_to: str | None = None,
) -> dict[str, Any]:
    if not isinstance(from_buddy, str) or not from_buddy.strip():
        raise ValueError("from_buddy must be a non-empty string")
    if not isinstance(to_buddy, str) or not to_buddy.strip():
        raise ValueError("to_buddy must be a non-empty string")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("content must be a non-empty string")
    if reply_to is not None:
        require_id(reply_to, "reply_to")
    message_id = f"msg-{uuid.uuid4().hex[:12]}"
    require_id(message_id, "message id")
    message = {
        "id": message_id,
        "from_buddy": from_buddy.strip(),
        "to_buddy": to_buddy.strip(),
        "content": content.strip(),
        "reply_to": reply_to,
        "created_at": now_iso(),
    }
    return save_message(message)


# ---------------------------------------------------------------------------
# Comment object helpers
# ---------------------------------------------------------------------------


def list_comments() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if COMMENTS_DIR.is_dir():
        for path in COMMENTS_DIR.glob("*.json"):
            rows.append(validate_comment(_read_json(path)))
    rows.sort(key=lambda row: (row.get("created_at", ""), row["id"]))
    return rows


def get_comment(comment_id: str) -> dict[str, Any] | None:
    path = comment_file(comment_id)
    if not path.exists():
        return None
    return validate_comment(_read_json(path))


def save_comment(comment: dict[str, Any]) -> dict[str, Any]:
    normalize_comment = validate_comment(comment)
    ensure_runtime_dirs()
    _write_json(comment_file(normalize_comment["id"]), normalize_comment)
    return normalize_comment


def create_comment(
    *,
    target_type: str,
    target_id: str,
    author_buddy: str,
    content: str,
    reply_to: str | None = None,
) -> dict[str, Any]:
    if target_type not in {"track", "artifact"}:
        raise ValueError("target_type must be 'track' or 'artifact'")
    require_id(target_id, "target_id")
    if not isinstance(author_buddy, str) or not author_buddy.strip():
        raise ValueError("author_buddy must be a non-empty string")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("content must be a non-empty string")
    if reply_to is not None:
        require_id(reply_to, "reply_to")
    comment_id = f"comment-{uuid.uuid4().hex[:12]}"
    require_id(comment_id, "comment id")
    comment = {
        "id": comment_id,
        "target_type": target_type,
        "target_id": target_id,
        "author_buddy": author_buddy.strip(),
        "content": content.strip(),
        "reply_to": reply_to,
        "created_at": now_iso(),
    }
    return save_comment(comment)


# ---------------------------------------------------------------------------
# Private target comment_ids helpers (used by comment service and cleanup)
# ---------------------------------------------------------------------------


def add_comment_id_to_track(track_id: str, comment_id: str) -> dict[str, Any]:
    track = get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    require_id(comment_id, "comment id")
    if comment_id not in track["comment_ids"]:
        track["comment_ids"].append(comment_id)
        track["updated_at"] = now_iso()
    return save_track(track)


def add_comment_id_to_artifact(artifact_id: str, comment_id: str) -> dict[str, Any]:
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")
    require_id(comment_id, "comment id")
    if comment_id not in artifact["comment_ids"]:
        artifact["comment_ids"].append(comment_id)
        artifact["updated_at"] = now_iso()
    return save_artifact(artifact)


def remove_comment_id_from_target(
    target_type: str, target_id: str, comment_id: str
) -> dict[str, Any] | None:
    if target_type not in {"track", "artifact"}:
        return None
    require_id(target_id, "target_id")
    require_id(comment_id, "comment id")
    if target_type == "track":
        target = get_track(target_id)
    else:
        target = get_artifact(target_id)
    if target is None:
        return None
    if comment_id not in target.get("comment_ids", []):
        return None
    target["comment_ids"] = [item for item in target["comment_ids"] if item != comment_id]
    target["updated_at"] = now_iso()
    if target_type == "track":
        return save_track(target)
    return save_artifact(target)
