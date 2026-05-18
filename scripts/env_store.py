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

VALID_TRACK_STATE = ("active", "blocked", "review", "done")
VALID_TRACK_HEALTH = ("ok", "risk", "blocked", "stale")
VALID_UPDATE_KIND = ("progress", "decision", "blocker", "proof")
VALID_TASK_STATUS = ("active", "blocked", "done", "archived")
VALID_ARTIFACT_STATUS = ("draft", "published", "archived")
VALID_ARTIFACT_TEMPLATES = ("brief", "proposal", "design", "decision", "proof", "note")

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_LEGACY_TASK_RUN_IDS = "run" + "_ids"
_LEGACY_TASK_LATEST_RUN = "latest" + "_run_id"
_LEGACY_SOURCE_RUN = "source" + "_run_id"
_LEGACY_TRACK_BUDDY_FIELDS = ("current" + "_buddy", "next" + "_buddy")
_LEGACY_TRACK_FIELDS = {
    "status",
    "summary",
    "task_ids",
    "artifact_ids",
    "tasks",
    "missing_task_ids",
}
_LEGACY_TASK_FIELDS = {"artifact_ids", "artifact" + "_slots"}
_LEGACY_ARTIFACT_FIELDS = {"task_id", "kind", "content", "publication_role", "asset", "media", "material", "blocks", "figma_file"}
_KNOWN_BUDDY_IDS = {"pm", "design", "dev", "market", "test"}


def _template_from_legacy_kind(kind: str) -> str:
    normalized = kind.strip().lower()
    if normalized in {"design-handoff", "design"}:
        return "design"
    if normalized in {"solution-spec", "technical-proposal", "proposal"}:
        return "proposal"
    if normalized in {"pm-decision", "decision"}:
        return "decision"
    if normalized in {"verification-proof", "smoke-test", "test-report", "proof"}:
        return "proof"
    if normalized in {"prd", "brief"}:
        return "brief"
    return "note"


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


def _require_non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _normalize_now(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("track.now must be an object")
    if set(value) - {"next", "blocker"}:
        extras = ", ".join(sorted(set(value) - {"next", "blocker"}))
        raise ValueError(f"track.now has unsupported fields: {extras}")
    next_value = _require_non_empty_text(value.get("next"), "track.now.next")
    blocker = value.get("blocker")
    if blocker is not None and not isinstance(blocker, str):
        raise ValueError("track.now.blocker must be a string or null")
    blocker_text = blocker.strip() if isinstance(blocker, str) and blocker.strip() else None
    return {"next": next_value, "blocker": blocker_text}


def _normalize_material_ref(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("track.shared_materials[] must be an object")
    if row.get("type") != "artifact":
        raise ValueError("track.shared_materials[].type must be 'artifact'")
    published_at = _require_non_empty_text(row.get("published_at"), "track.shared_materials[].published_at")
    normalized = {
        "type": "artifact",
        "artifact_id": require_id(row.get("artifact_id"), "track.shared_materials[].artifact_id"),
        "label": _require_non_empty_text(row.get("label"), "track.shared_materials[].label"),
        "kind": _require_non_empty_text(row.get("kind"), "track.shared_materials[].kind"),
        "from_buddy": _require_non_empty_text(row.get("from_buddy"), "track.shared_materials[].from_buddy"),
        "summary": row.get("summary", "") if isinstance(row.get("summary", ""), str) else "",
        "current": bool(row.get("current", False)),
        "published_at": published_at,
    }
    return normalized


def _normalize_proof_ref(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("track.close_proof[] must be an object")
    if row.get("type") != "artifact":
        raise ValueError("track.close_proof[].type must be 'artifact'")
    published_at = _require_non_empty_text(row.get("published_at"), "track.close_proof[].published_at")
    return {
        "type": "artifact",
        "artifact_id": require_id(row.get("artifact_id"), "track.close_proof[].artifact_id"),
        "label": _require_non_empty_text(row.get("label"), "track.close_proof[].label"),
        "kind": _require_non_empty_text(row.get("kind"), "track.close_proof[].kind"),
        "from_buddy": _require_non_empty_text(row.get("from_buddy"), "track.close_proof[].from_buddy"),
        "summary": row.get("summary", "") if isinstance(row.get("summary", ""), str) else "",
        "published_at": published_at,
    }


def _normalize_update_ref(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("track.updates[].refs[] must be an object")
    ref_type = row.get("type")
    if ref_type != "artifact":
        raise ValueError("track.updates[].refs[].type must be 'artifact'")
    return {"type": "artifact", "id": require_id(row.get("id"), "track.updates[].refs[].id")}


def _normalize_update_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("track.updates[] must be an object")
    kind = row.get("kind")
    if kind not in VALID_UPDATE_KIND:
        raise ValueError(f"track.updates[].kind must be one of {', '.join(VALID_UPDATE_KIND)}")
    refs = row.get("refs", [])
    if not isinstance(refs, list):
        raise ValueError("track.updates[].refs must be a list")
    created_at = _require_non_empty_text(row.get("created_at"), "track.updates[].created_at")
    return {
        "id": _require_non_empty_text(row.get("id"), "track.updates[].id"),
        "by_buddy": _require_non_empty_text(row.get("by_buddy"), "track.updates[].by_buddy"),
        "summary": _require_non_empty_text(row.get("summary"), "track.updates[].summary"),
        "kind": kind,
        "refs": [_normalize_update_ref(item) for item in refs],
        "created_at": created_at,
    }


def validate_track(track: dict[str, Any]) -> dict[str, Any]:
    for field in _LEGACY_TRACK_BUDDY_FIELDS:
        if field in track:
            raise ValueError("legacy track buddy-routing fields are retired; use immutable owner_buddy")
    forbidden = sorted(field for field in track if field in _LEGACY_TRACK_FIELDS)
    if forbidden:
        raise ValueError(f"legacy track fields are retired: {', '.join(forbidden)}")

    track_id = require_id(track.get("id", ""), "track.id")
    title = _require_non_empty_text(track.get("title"), "track.title")
    outcome = _require_non_empty_text(track.get("outcome"), "track.outcome")
    owner_buddy = _require_non_empty_text(track.get("owner_buddy"), "track.owner_buddy")
    state = track.get("state")
    health = track.get("health")
    if state not in VALID_TRACK_STATE:
        raise ValueError(f"track.state must be one of {', '.join(VALID_TRACK_STATE)}")
    if health not in VALID_TRACK_HEALTH:
        raise ValueError(f"track.health must be one of {', '.join(VALID_TRACK_HEALTH)}")

    appetite = _require_non_empty_text(track.get("appetite"), "track.appetite")
    now = _normalize_now(track.get("now"))

    shared_materials = track.get("shared_materials")
    if not isinstance(shared_materials, list):
        raise ValueError("track.shared_materials must be a list")
    updates = track.get("updates")
    if not isinstance(updates, list):
        raise ValueError("track.updates must be a list")
    close_proof = track.get("close_proof")
    if not isinstance(close_proof, list):
        raise ValueError("track.close_proof must be a list")

    created_at = _require_non_empty_text(track.get("created_at"), "track.created_at")
    updated_at = _require_non_empty_text(track.get("updated_at"), "track.updated_at")
    archived_at = track.get("archived_at")
    if archived_at is not None and not isinstance(archived_at, str):
        raise ValueError("track.archived_at must be a string or null")

    return {
        "id": track_id,
        "title": title,
        "outcome": outcome,
        "owner_buddy": owner_buddy,
        "state": state,
        "health": health,
        "appetite": appetite,
        "now": now,
        "shared_materials": [_normalize_material_ref(row) for row in shared_materials],
        "updates": [_normalize_update_row(row) for row in updates],
        "close_proof": [_normalize_proof_ref(row) for row in close_proof],
        "created_at": created_at,
        "updated_at": updated_at,
        "archived_at": archived_at,
    }


def validate_task(task: dict[str, Any]) -> dict[str, Any]:
    if _LEGACY_TASK_RUN_IDS in task or _LEGACY_TASK_LATEST_RUN in task:
        raise ValueError("legacy task run lineage fields are retired")
    forbidden = sorted(field for field in task if field in _LEGACY_TASK_FIELDS)
    if forbidden:
        raise ValueError(f"legacy task fields are retired: {', '.join(forbidden)}")

    task_id = require_id(task.get("id", ""), "task.id")
    buddy = _require_non_empty_text(task.get("buddy"), "task.buddy")
    title = _require_non_empty_text(task.get("title"), "task.title")
    status = task.get("status")
    if status not in VALID_TASK_STATUS:
        raise ValueError(f"task.status must be one of {', '.join(VALID_TASK_STATUS)}")

    track_id = task.get("track_id")
    if track_id is not None:
        require_id(track_id, "task.track_id")

    summary = task.get("summary", "")
    if not isinstance(summary, str):
        raise ValueError("task.summary must be a string")
    created_at = _require_non_empty_text(task.get("created_at"), "task.created_at")
    updated_at = _require_non_empty_text(task.get("updated_at"), "task.updated_at")

    return {
        "id": task_id,
        "buddy": buddy,
        "title": title,
        "status": status,
        "track_id": track_id,
        "summary": summary,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def validate_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    if _LEGACY_SOURCE_RUN in artifact:
        raise ValueError("legacy artifact run lineage field is retired; use source_refs")
    forbidden = sorted(field for field in artifact if field in _LEGACY_ARTIFACT_FIELDS)
    allow_legacy = (
        "task_id" in artifact
        or "kind" in artifact
        or "content" in artifact
        or "buddy" in artifact
    )
    if forbidden and not allow_legacy:
        raise ValueError(f"legacy artifact fields are retired: {', '.join(forbidden)}")

    artifact_id = require_id(artifact.get("id", ""), "artifact.id")
    title = _require_non_empty_text(artifact.get("title"), "artifact.title")

    created_by_raw = artifact.get("created_by")
    if not isinstance(created_by_raw, str) or not created_by_raw.strip():
        created_by_raw = artifact.get("buddy") if allow_legacy else created_by_raw
    created_by = _require_non_empty_text(created_by_raw, "artifact.created_by")
    if created_by not in _KNOWN_BUDDY_IDS:
        raise ValueError("artifact.created_by must be one of known buddy ids")

    body = artifact.get("body")
    if not isinstance(body, str) or not body.strip():
        if allow_legacy:
            content = artifact.get("content")
            if isinstance(content, dict):
                legacy_body = content.get("body")
                if isinstance(legacy_body, str) and legacy_body.strip():
                    body = legacy_body
        if not isinstance(body, str) or not body.strip():
            raise ValueError("artifact.body must be a non-empty string")

    template = artifact.get("template")
    if not isinstance(template, str) or not template.strip():
        if allow_legacy:
            kind = artifact.get("kind")
            if isinstance(kind, str) and kind.strip():
                template = _template_from_legacy_kind(kind)
    if not isinstance(template, str) or template not in VALID_ARTIFACT_TEMPLATES:
        raise ValueError(f"artifact.template must be one of {', '.join(VALID_ARTIFACT_TEMPLATES)}")

    published_to_track = artifact.get("published_to_track")
    if published_to_track is not None:
        require_id(published_to_track, "artifact.published_to_track")

    status = artifact.get("status")
    if not isinstance(status, str):
        if allow_legacy:
            status = "draft" if published_to_track is None else "published"
    if status not in VALID_ARTIFACT_STATUS:
        raise ValueError(f"artifact.status must be one of {', '.join(VALID_ARTIFACT_STATUS)}")
    if status == "draft" and published_to_track is not None:
        raise ValueError("artifact.published_to_track must be null for draft artifacts")
    if status in {"published", "archived"} and published_to_track is None:
        raise ValueError("artifact.published_to_track is required for published/archived artifacts")

    summary = artifact.get("summary", "")
    if not isinstance(summary, str):
        raise ValueError("artifact.summary must be a string")

    source_refs = _normalize_source_refs(artifact.get("source_refs"), active_buddy=created_by, allow_buddybox=True)

    revision = artifact.get("revision")
    if not isinstance(revision, int) or revision <= 0:
        raise ValueError("artifact.revision must be a positive integer")

    supersedes_artifact_id = artifact.get("supersedes_artifact_id")
    if supersedes_artifact_id is not None:
        require_id(supersedes_artifact_id, "artifact.supersedes_artifact_id")

    is_current = artifact.get("is_current")
    if not isinstance(is_current, bool):
        raise ValueError("artifact.is_current must be a boolean")

    authors_raw = artifact.get("authors")
    authors: list[str] = []
    if isinstance(authors_raw, list):
        for row in authors_raw:
            if isinstance(row, str) and row in _KNOWN_BUDDY_IDS and row not in authors:
                authors.append(row)
    if created_by not in authors:
        authors.insert(0, created_by)

    created_at = _require_non_empty_text(artifact.get("created_at"), "artifact.created_at")
    updated_at = _require_non_empty_text(artifact.get("updated_at"), "artifact.updated_at")

    if published_to_track is not None and get_track(published_to_track) is None:
        raise ValueError(f"track not found: {published_to_track}")

    return {
        "id": artifact_id,
        "title": title,
        "summary": summary,
        "body": body,
        "template": template,
        "status": status,
        "published_to_track": published_to_track,
        "revision": revision,
        "is_current": is_current,
        "supersedes_artifact_id": supersedes_artifact_id,
        "created_by": created_by,
        "authors": authors,
        "source_refs": source_refs,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def validate_message(message: dict[str, Any]) -> dict[str, Any]:
    forbidden_fields = {"status", "read_at", "track_id", "task_id", "artifact_id", "recipients", "broadcast"}
    forbidden = sorted(key for key in message if key in forbidden_fields)
    if forbidden:
        raise ValueError(f"unsupported message fields: {', '.join(forbidden)}")

    msg_id = require_id(message.get("id", ""), "message.id")
    from_buddy = _require_non_empty_text(message.get("from_buddy"), "message.from_buddy")
    to_buddy = _require_non_empty_text(message.get("to_buddy"), "message.to_buddy")
    content = _require_non_empty_text(message.get("content"), "message.content")
    reply_to = message.get("reply_to")
    if reply_to is not None:
        require_id(reply_to, "message.reply_to")
    created_at = _require_non_empty_text(message.get("created_at"), "message.created_at")

    return {
        "id": msg_id,
        "from_buddy": from_buddy,
        "to_buddy": to_buddy,
        "content": content,
        "reply_to": reply_to,
        "created_at": created_at,
    }


def validate_comment(comment: dict[str, Any]) -> dict[str, Any]:
    forbidden_fields = {"status", "resolved", "resolved_at", "task_id", "edit_history", "attachment"}
    forbidden = sorted(key for key in comment if key in forbidden_fields)
    if forbidden:
        raise ValueError(f"unsupported comment fields: {', '.join(forbidden)}")

    comment_id = require_id(comment.get("id", ""), "comment.id")
    target_type = comment.get("target_type")
    if target_type not in {"track", "artifact"}:
        raise ValueError("comment.target_type must be 'track' or 'artifact'")
    target_id = require_id(comment.get("target_id"), "comment.target_id")
    author_buddy = _require_non_empty_text(comment.get("author_buddy"), "comment.author_buddy")
    content = _require_non_empty_text(comment.get("content"), "comment.content")
    reply_to = comment.get("reply_to")
    if reply_to is not None:
        require_id(reply_to, "comment.reply_to")
    created_at = _require_non_empty_text(comment.get("created_at"), "comment.created_at")

    return {
        "id": comment_id,
        "target_type": target_type,
        "target_id": target_id,
        "author_buddy": author_buddy,
        "content": content,
        "reply_to": reply_to,
        "created_at": created_at,
    }


def list_tracks() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if TRACKS_DIR.exists():
        for path in TRACKS_DIR.glob("*.json"):
            rows.append(validate_track(_read_json(path)))
    rows.sort(key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
    return rows


def list_tasks() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if TASKS_DIR.exists():
        for path in TASKS_DIR.glob("*.json"):
            rows.append(validate_task(_read_json(path)))
    rows.sort(key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
    return rows


def list_artifacts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if ARTIFACT_OBJECTS_DIR.exists():
        for path in ARTIFACT_OBJECTS_DIR.glob("*.json"):
            rows.append(validate_artifact(_read_json(path)))
    rows.sort(key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
    return rows


def build_track_artifact_index(track_id: str | None) -> dict[str, Any] | None:
    if not track_id:
        return None
    track = get_track(track_id)
    if track is None:
        return None
    return {
        "track_id": track["id"],
        "track_title": track["title"],
        "outcome": track["outcome"],
        "shared_materials": [row for row in track.get("shared_materials", []) if isinstance(row, dict)],
        "close_proof": [row for row in track.get("close_proof", []) if isinstance(row, dict)],
        "updated_at": track.get("updated_at", ""),
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
    normalized = validate_task(task)
    ensure_runtime_dirs()
    _write_json(task_file(normalized["id"]), normalized)
    return normalized


def save_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_artifact(artifact)
    ensure_runtime_dirs()
    _write_json(artifact_file(normalized["id"]), normalized)
    return normalized


def create_track(
    track_id: str,
    title: str,
    *,
    owner_buddy: str = "pm",
    outcome: str = "",
    appetite: str = "1 day",
    now: dict[str, Any] | None = None,
    state: str = "active",
    health: str = "ok",
) -> dict[str, Any]:
    require_id(track_id, "track id")
    if get_track(track_id):
        raise ValueError(f"track already exists: {track_id}")
    timestamp = now_iso()
    track = {
        "id": track_id,
        "title": title,
        "outcome": outcome or "unspecified outcome",
        "owner_buddy": owner_buddy,
        "state": state,
        "health": health,
        "appetite": appetite,
        "now": now or {"next": "unspecified", "blocker": None},
        "shared_materials": [],
        "updates": [],
        "close_proof": [],
        "created_at": timestamp,
        "updated_at": timestamp,
        "archived_at": None,
    }
    return save_track(track)


def update_track(track_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    track = get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    allowed = {"title", "outcome", "state", "health", "appetite", "now", "shared_materials", "updates", "close_proof", "archived_at"}
    for key, value in patch.items():
        if key not in allowed:
            raise ValueError(f"unsupported track field: {key}")
        track[key] = value
    track["updated_at"] = now_iso()
    return save_track(track)


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
        "summary": summary,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    return save_task(task)


def update_task(task_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise ValueError(f"task not found: {task_id}")
    allowed = {"title", "status", "track_id", "summary"}
    for key, value in patch.items():
        if key not in allowed:
            raise ValueError(f"unsupported task field: {key}")
        task[key] = value
    track_id = task.get("track_id")
    if track_id is not None and get_track(track_id) is None:
        raise ValueError(f"track not found: {track_id}")
    task["updated_at"] = now_iso()
    return save_task(task)


def create_artifact_revision(
    *,
    artifact_id: str | None,
    title: str,
    created_by: str,
    body: str,
    template: str,
    summary: str = "",
    source_refs: list[dict[str, Any]] | None = None,
    status: str | None = None,
    published_to_track: str | None = None,
    supersedes_artifact_id: str | None = None,
    authors: list[str] | None = None,
    legacy_source_run: str | None = None,
) -> dict[str, Any]:
    if legacy_source_run is not None:
        raise ValueError("legacy artifact run lineage field is retired; use source_refs")

    resolved_id = artifact_id or f"art-{uuid.uuid4().hex[:10]}"
    require_id(resolved_id, "artifact id")
    if get_artifact(resolved_id):
        raise ValueError(f"artifact already exists: {resolved_id}")

    if created_by not in _KNOWN_BUDDY_IDS:
        raise ValueError("created_by must be one of known buddy ids")
    if not isinstance(body, str) or not body.strip():
        raise ValueError("body must be a non-empty string")
    if template not in VALID_ARTIFACT_TEMPLATES:
        raise ValueError(f"template must be one of {', '.join(VALID_ARTIFACT_TEMPLATES)}")
    if not isinstance(summary, str):
        raise ValueError("summary must be a string")
    normalized_refs = _normalize_source_refs(source_refs, active_buddy=created_by, allow_buddybox=True)

    inherited_track = published_to_track
    revision = 1
    supersedes_id: str | None = None
    if supersedes_artifact_id is not None:
        require_id(supersedes_artifact_id, "artifact.supersedes_artifact_id")
        previous = get_artifact(supersedes_artifact_id)
        if previous is None:
            raise ValueError(f"artifact not found: {supersedes_artifact_id}")
        if not bool(previous.get("is_current")):
            raise ValueError(f"artifact '{supersedes_artifact_id}' is not current and cannot be superseded")
        supersedes_id = supersedes_artifact_id
        revision = int(previous.get("revision", 1)) + 1
        previous_track = previous.get("published_to_track")
        if inherited_track is None:
            inherited_track = previous_track
        elif previous_track is not None and inherited_track != previous_track:
            raise ValueError("published_to_track must match superseded artifact publication target")
        previous["is_current"] = False
        previous["updated_at"] = now_iso()
        save_artifact(previous)

    resolved_status = status if isinstance(status, str) else ("published" if inherited_track else "draft")
    if resolved_status not in VALID_ARTIFACT_STATUS:
        raise ValueError(f"status must be one of {', '.join(VALID_ARTIFACT_STATUS)}")
    if inherited_track is not None:
        require_id(inherited_track, "artifact.published_to_track")
        if get_track(inherited_track) is None:
            raise ValueError(f"track not found: {inherited_track}")
    if resolved_status == "draft" and inherited_track is not None:
        raise ValueError("published_to_track must be omitted when status is draft")
    if resolved_status in {"published", "archived"} and inherited_track is None:
        raise ValueError("published_to_track is required when status is published or archived")

    author_rows = [created_by]
    if isinstance(authors, list):
        for row in authors:
            if isinstance(row, str) and row in _KNOWN_BUDDY_IDS and row not in author_rows:
                author_rows.append(row)

    timestamp = now_iso()
    artifact = {
        "id": resolved_id,
        "title": _require_non_empty_text(title, "artifact.title"),
        "summary": summary,
        "body": body,
        "template": template,
        "status": resolved_status,
        "published_to_track": inherited_track,
        "revision": revision,
        "is_current": True,
        "supersedes_artifact_id": supersedes_id,
        "created_by": created_by,
        "authors": author_rows,
        "source_refs": normalized_refs,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    return save_artifact(artifact)


def create_artifact(
    *,
    artifact_id: str | None,
    title: str,
    kind: str,
    created_by: str,
    summary: str = "",
    content: dict[str, Any] | None = None,
    source_refs: list[dict[str, Any]] | None = None,
    published_to_track: str | None = None,
    publication_role: str | None = None,
    supersedes_artifact_id: str | None = None,
    revision: int | None = None,
    is_current: bool = True,
    legacy_source_run: str | None = None,
) -> dict[str, Any]:
    del revision, is_current
    if publication_role is not None:
        raise ValueError("artifact.publication_role is retired")
    normalized_kind = _require_non_empty_text(kind, "artifact.kind")
    if not isinstance(content, dict):
        raise ValueError("artifact.content must be an object")
    body = content.get("body")
    if not isinstance(body, str) or not body.strip():
        body = json.dumps(content, ensure_ascii=True, sort_keys=True)
    return create_artifact_revision(
        artifact_id=artifact_id,
        title=title,
        created_by=created_by,
        body=body,
        template=_template_from_legacy_kind(normalized_kind),
        summary=summary,
        source_refs=source_refs,
        status="published" if published_to_track else "draft",
        published_to_track=published_to_track,
        supersedes_artifact_id=supersedes_artifact_id,
        authors=[created_by],
        legacy_source_run=legacy_source_run,
    )


def update_artifact(artifact_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")
    if _LEGACY_SOURCE_RUN in patch:
        raise ValueError("legacy artifact run lineage field is retired; use source_refs")

    retired = sorted(key for key in patch if key in {"kind", "content", "publication_role", "task_id"})
    if retired:
        raise ValueError(f"retired artifact fields are unsupported: {', '.join(retired)}")

    allowed = {
        "title",
        "summary",
        "body",
        "template",
        "status",
        "source_refs",
        "published_to_track",
        "supersedes_artifact_id",
        "is_current",
        "revision",
        "authors",
    }
    for key, value in patch.items():
        if key not in allowed:
            raise ValueError(f"unsupported artifact field: {key}")
        artifact[key] = value
    artifact["updated_at"] = now_iso()
    return save_artifact(artifact)


def publish_track_material(
    *,
    track_id: str,
    artifact_id: str,
    label: str,
    from_buddy: str,
    summary: str,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    track = get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")

    kind = str(artifact.get("template") or "")
    if not kind:
        raise ValueError("artifact.template is required for track publication")

    published_to_track = artifact.get("published_to_track")
    if published_to_track is not None and published_to_track != track_id:
        raise ValueError(
            f"artifact '{artifact_id}' is already published to track '{published_to_track}' and cannot be republished to '{track_id}'"
        )
    if published_to_track == track_id:
        already_current = any(
            isinstance(row, dict)
            and row.get("type") == "artifact"
            and row.get("artifact_id") == artifact_id
            and bool(row.get("current"))
            for row in track.get("shared_materials", [])
        )
        if not already_current:
            raise ValueError(
                f"artifact '{artifact_id}' is already bound to track '{track_id}' but not as current material; create a new revision instead"
            )
        return track, artifact, False

    supersedes: str | None = None
    next_refs: list[dict[str, Any]] = []
    for row in track.get("shared_materials", []):
        if not isinstance(row, dict):
            continue
        same_slot = row.get("kind") == kind and row.get("label") == label and row.get("from_buddy") == from_buddy
        if same_slot and bool(row.get("current")):
            supersedes = str(row.get("artifact_id") or "") or supersedes
            old_artifact_id = row.get("artifact_id")
            if isinstance(old_artifact_id, str):
                old_artifact = get_artifact(old_artifact_id)
                if isinstance(old_artifact, dict):
                    old_artifact["is_current"] = False
                    old_artifact["updated_at"] = now_iso()
                    save_artifact(old_artifact)
        next_row = dict(row)
        if same_slot:
            next_row["current"] = False
        next_refs.append(next_row)

    artifact_revision = int(artifact.get("revision", 1))
    if supersedes:
        previous = get_artifact(supersedes)
        if previous is not None:
            artifact_revision = max(int(previous.get("revision", 1)) + 1, artifact_revision)
    artifact.update(
        {
            "published_to_track": track_id,
            "status": "published",
            "supersedes_artifact_id": supersedes,
            "is_current": True,
            "revision": artifact_revision,
            "updated_at": now_iso(),
        }
    )
    artifact = save_artifact(artifact)

    ref = {
        "type": "artifact",
        "artifact_id": artifact_id,
        "label": label,
        "kind": kind,
        "from_buddy": from_buddy,
        "summary": summary,
        "current": True,
        "published_at": now_iso(),
    }
    next_refs.append(ref)

    track["shared_materials"] = next_refs
    track["updated_at"] = now_iso()
    track = save_track(track)
    return track, artifact, True


def publish_track_proof(
    *,
    track_id: str,
    artifact_id: str,
    label: str,
    from_buddy: str,
    summary: str,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    track = get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")

    kind = str(artifact.get("template") or "")
    if not kind:
        raise ValueError("artifact.template is required for track proof publication")

    published_to_track = artifact.get("published_to_track")
    if published_to_track is not None and published_to_track != track_id:
        raise ValueError(
            f"artifact '{artifact_id}' is already published to track '{published_to_track}' and cannot be republished to '{track_id}'"
        )
    if published_to_track == track_id:
        already_listed = any(
            isinstance(row, dict)
            and row.get("type") == "artifact"
            and row.get("artifact_id") == artifact_id
            for row in track.get("close_proof", [])
        )
        if not already_listed:
            raise ValueError(
                f"artifact '{artifact_id}' is already bound to track '{track_id}' but missing close_proof ref; create a new proof artifact instead"
            )
        return track, artifact, False

    artifact.update(
        {
            "published_to_track": track_id,
            "status": "published",
            "is_current": True,
            "updated_at": now_iso(),
        }
    )
    artifact = save_artifact(artifact)

    proof_ref = {
        "type": "artifact",
        "artifact_id": artifact_id,
        "label": label,
        "kind": kind,
        "from_buddy": from_buddy,
        "summary": summary,
        "published_at": now_iso(),
    }
    close_proof = [row for row in track.get("close_proof", []) if isinstance(row, dict)]
    close_proof.append(proof_ref)
    track["close_proof"] = close_proof
    track["updated_at"] = now_iso()
    track = save_track(track)
    return track, artifact, True


def append_track_update(
    *,
    track_id: str,
    by_buddy: str,
    kind: str,
    summary: str,
    refs: list[dict[str, Any]] | None = None,
    update_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    track = get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    if kind not in VALID_UPDATE_KIND:
        raise ValueError(f"kind must be one of {', '.join(VALID_UPDATE_KIND)}")

    row = {
        "id": update_id or f"upd-{uuid.uuid4().hex[:8]}",
        "by_buddy": by_buddy,
        "summary": summary,
        "kind": kind,
        "refs": refs or [],
        "created_at": now_iso(),
    }
    updates = [entry for entry in track.get("updates", []) if isinstance(entry, dict)]
    updates.append(row)
    track["updates"] = updates
    track["updated_at"] = now_iso()
    track = save_track(track)
    return track, row


def delete_artifact(artifact_id: str) -> dict[str, Any]:
    require_runtime_workspace_write_root()
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")
    path = artifact_file(artifact_id)
    if path.exists():
        path.unlink()
    return artifact


def delete_artifacts_by_buddy(
    buddy_id: str,
    *,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    targets = [artifact for artifact in list_artifacts() if artifact.get("created_by") == buddy_id]
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
    normalized_message = validate_message(message)
    ensure_runtime_dirs()
    _write_json(message_file(normalized_message["id"]), normalized_message)
    return normalized_message


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
    normalized_comment = validate_comment(comment)
    ensure_runtime_dirs()
    _write_json(comment_file(normalized_comment["id"]), normalized_comment)
    return normalized_comment


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
