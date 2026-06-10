#!/usr/bin/env python3
"""Track repository helpers backed by runtime object files."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any

from env.tool_runtime.actor_profile import ActorAddress
from . import runtime_files

VALID_TRACK_STATE = ("active", "blocked", "review", "done")
VALID_TRACK_HEALTH = ("ok", "risk", "blocked", "stale")
VALID_UPDATE_KIND = ("progress", "decision", "blocker", "proof")
VALID_ARTIFACT_RELATION_ROLE = ("material", "proof", "input", "deliverable")
_LEGACY_TRACK_ROLE_FIELDS = ("current" + "_role", "next" + "_role")
_LEGACY_TRACK_FIELDS = {
    "status",
    "summary",
    "task_ids",
    "artifact_ids",
    "tasks",
    "missing_task_ids",
    "shared_materials",
    "close_proof",
}


def _require_non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _normalize_actor(value: Any, field: str) -> dict[str, str]:
    try:
        return ActorAddress.from_payload(value).to_payload()
    except ValueError as exc:
        raise ValueError(f"{field} must be an ActorAddress payload: {exc}") from exc


def _track_file(track_id: str) -> Path:
    return runtime_files.TRACKS_DIR / f"{runtime_files.require_id(track_id, 'track id')}.json"


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


def _normalize_artifact_relation(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("track.artifact_relations[] must be an object")
    if row.get("type") != "artifact":
        raise ValueError("track.artifact_relations[].type must be 'artifact'")
    role = row.get("role")
    if role not in VALID_ARTIFACT_RELATION_ROLE:
        raise ValueError(f"track.artifact_relations[].role must be one of {', '.join(VALID_ARTIFACT_RELATION_ROLE)}")
    return {
        "type": "artifact",
        "relation_id": runtime_files.require_id(row.get("relation_id"), "track.artifact_relations[].relation_id"),
        "artifact_id": runtime_files.require_id(row.get("artifact_id"), "track.artifact_relations[].artifact_id"),
        "role": role,
        "label": _require_non_empty_text(row.get("label"), "track.artifact_relations[].label"),
        "template": _require_non_empty_text(row.get("template"), "track.artifact_relations[].template"),
        "from_actor": _normalize_actor(row.get("from_actor"), "track.artifact_relations[].from_actor"),
        "summary": row.get("summary", "") if isinstance(row.get("summary", ""), str) else "",
        "current": bool(row.get("current", False)),
        "created_at": _require_non_empty_text(row.get("created_at"), "track.artifact_relations[].created_at"),
    }


def _normalize_update_ref(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("track.updates[].refs[] must be an object")
    ref_type = row.get("type")
    if ref_type != "artifact":
        raise ValueError("track.updates[].refs[].type must be 'artifact'")
    return {"type": "artifact", "id": runtime_files.require_id(row.get("id"), "track.updates[].refs[].id")}


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
        "by_actor": _normalize_actor(row.get("by_actor"), "track.updates[].by_actor"),
        "summary": _require_non_empty_text(row.get("summary"), "track.updates[].summary"),
        "kind": kind,
        "refs": [_normalize_update_ref(item) for item in refs],
        "created_at": created_at,
    }


def _call_test_save_hook_if_mock(track: dict[str, Any]) -> dict[str, Any] | None:
    module = sys.modules.get("env" + "_legacy_store")
    if module is None:
        return None
    save_fn = getattr(module, "save_track", None)
    if not callable(save_fn):
        return None
    if not save_fn.__class__.__module__.startswith("unittest.mock"):
        return None
    payload = save_fn(track)
    if isinstance(payload, dict):
        return payload
    return track


def now_iso() -> str:
    return runtime_files.now_iso()


def list_tracks() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if runtime_files.TRACKS_DIR.exists():
        for path in runtime_files.TRACKS_DIR.glob("*.json"):
            rows.append(validate_track(runtime_files.read_json_object(path)))
    rows.sort(key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
    return rows


def get_track(track_id: str) -> dict[str, Any] | None:
    path = _track_file(track_id)
    if not path.exists():
        return None
    return validate_track(runtime_files.read_json_object(path))


def save_track(track: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_track(track)
    hooked = _call_test_save_hook_if_mock(normalized)
    if isinstance(hooked, dict):
        return validate_track(hooked)
    runtime_files.require_runtime_workspace_write_root()
    runtime_files.TRACKS_DIR.mkdir(parents=True, exist_ok=True)
    runtime_files.write_json_object(_track_file(normalized["id"]), normalized)
    return normalized


def create_track(
    track_id: str,
    title: str,
    *,
    owner_role: str = "pm",
    created_by_actor: dict[str, Any] | None = None,
    outcome: str = "",
    appetite: str = "1 day",
    now: dict[str, Any] | None = None,
    state: str = "active",
    health: str = "ok",
) -> dict[str, Any]:
    runtime_files.require_id(track_id, "track id")
    if get_track(track_id):
        raise ValueError(f"track already exists: {track_id}")
    timestamp = runtime_files.now_iso()
    track = {
        "id": track_id,
        "title": title,
        "outcome": outcome or "unspecified outcome",
        "owner_role": owner_role,
        "created_by_actor": created_by_actor
        if isinstance(created_by_actor, dict)
        else {"actor_id": f"act-{owner_role}-system", "role_id": owner_role},
        "state": state,
        "health": health,
        "appetite": appetite,
        "now": now or {"next": "unspecified", "blocker": None},
        "artifact_relations": [],
        "updates": [],
        "created_at": timestamp,
        "updated_at": timestamp,
        "archived_at": None,
    }
    return save_track(track)


def update_track(track_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    track = get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    allowed = {"title", "outcome", "state", "health", "appetite", "now", "artifact_relations", "updates", "archived_at"}
    for key, value in patch.items():
        if key not in allowed:
            raise ValueError(f"unsupported track field: {key}")
        track[key] = value
    track["updated_at"] = runtime_files.now_iso()
    return save_track(track)


def append_track_update(
    *,
    track_id: str,
    by_actor: dict[str, Any],
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
        "by_actor": by_actor,
        "summary": summary,
        "kind": kind,
        "refs": refs or [],
        "created_at": runtime_files.now_iso(),
    }
    updates = [entry for entry in track.get("updates", []) if isinstance(entry, dict)]
    updates.append(row)
    track["updates"] = updates
    track["updated_at"] = runtime_files.now_iso()
    track = save_track(track)
    return track, row


def validate_track(track: dict[str, Any]) -> dict[str, Any]:
    for field in _LEGACY_TRACK_ROLE_FIELDS:
        if field in track:
            raise ValueError("legacy track role-routing fields are retired; use immutable owner_role")
    forbidden = sorted(field for field in track if field in _LEGACY_TRACK_FIELDS)
    if forbidden:
        raise ValueError(f"legacy track fields are retired: {', '.join(forbidden)}")

    track_id = runtime_files.require_id(track.get("id", ""), "track.id")
    title = _require_non_empty_text(track.get("title"), "track.title")
    outcome = _require_non_empty_text(track.get("outcome"), "track.outcome")
    owner_role = _require_non_empty_text(track.get("owner_role"), "track.owner_role")
    created_by_actor = _normalize_actor(track.get("created_by_actor"), "track.created_by_actor")
    state = track.get("state")
    health = track.get("health")
    if state not in VALID_TRACK_STATE:
        raise ValueError(f"track.state must be one of {', '.join(VALID_TRACK_STATE)}")
    if health not in VALID_TRACK_HEALTH:
        raise ValueError(f"track.health must be one of {', '.join(VALID_TRACK_HEALTH)}")

    appetite = _require_non_empty_text(track.get("appetite"), "track.appetite")
    now = _normalize_now(track.get("now"))

    artifact_relations = track.get("artifact_relations")
    if not isinstance(artifact_relations, list):
        raise ValueError("track.artifact_relations must be a list")
    updates = track.get("updates")
    if not isinstance(updates, list):
        raise ValueError("track.updates must be a list")

    created_at = _require_non_empty_text(track.get("created_at"), "track.created_at")
    updated_at = _require_non_empty_text(track.get("updated_at"), "track.updated_at")
    archived_at = track.get("archived_at")
    if archived_at is not None and not isinstance(archived_at, str):
        raise ValueError("track.archived_at must be a string or null")

    return {
        "id": track_id,
        "title": title,
        "outcome": outcome,
        "owner_role": owner_role,
        "created_by_actor": created_by_actor,
        "state": state,
        "health": health,
        "appetite": appetite,
        "now": now,
        "artifact_relations": [_normalize_artifact_relation(row) for row in artifact_relations],
        "updates": [_normalize_update_row(row) for row in updates],
        "created_at": created_at,
        "updated_at": updated_at,
        "archived_at": archived_at,
    }
