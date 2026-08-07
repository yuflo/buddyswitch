"""Track-owned repository helpers backed by runtime object files."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from buddyswitch.foundation.identity.model import IdentityRef
import buddyswitch.foundation.state.runtime as state_runtime

VALID_TRACK_STATE = ("active", "blocked", "done")
VALID_UPDATE_KIND = ("progress", "decision", "blocker")
VALID_ARTIFACT_RELATION_ROLE = ("material", "proof", "input", "deliverable")
_LEGACY_TRACK_ROLE_FIELDS = ("current" + "_role", "next" + "_role")
_RETIRED_TRACK_FIELDS = {
    "owner_role",
    "created_by_" + "actor",
    "health",
    "appetite",
}
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


def _identity_id(value: Any, field: str) -> str:
    if isinstance(value, str) and value.strip():
        return state_runtime.require_id(value.strip(), field)
    if isinstance(value, dict):
        if isinstance(value.get("identity"), dict):
            return IdentityRef.from_payload(value["identity"]).id
        if isinstance(value.get("id"), str) and isinstance(value.get("type"), str):
            return IdentityRef.from_payload(value).id
    raise ValueError(f"{field} must be an identity id or identity payload")


def _normalize_text_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    rows: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field}[{index}] must be a non-empty string")
        rows.append(item.strip())
    return rows


def _track_file(track_id: str) -> Path:
    return tracks_dir() / f"{state_runtime.require_id(track_id, 'track id')}.json"


def tracks_dir() -> Path:
    return state_runtime.OBJECTS_ROOT / "tracks"


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
    retired_source_field = "from_" + "actor"
    if retired_source_field in row:
        raise ValueError("track.artifact_relations[].from_identity_id is required")
    if row.get("type") != "artifact":
        raise ValueError("track.artifact_relations[].type must be 'artifact'")
    role = row.get("role")
    if role not in VALID_ARTIFACT_RELATION_ROLE:
        raise ValueError(f"track.artifact_relations[].role must be one of {', '.join(VALID_ARTIFACT_RELATION_ROLE)}")
    return {
        "type": "artifact",
        "relation_id": state_runtime.require_id(row.get("relation_id"), "track.artifact_relations[].relation_id"),
        "artifact_id": state_runtime.require_id(row.get("artifact_id"), "track.artifact_relations[].artifact_id"),
        "role": role,
        "label": _require_non_empty_text(row.get("label"), "track.artifact_relations[].label"),
        "template": _require_non_empty_text(row.get("template"), "track.artifact_relations[].template"),
        "from_identity_id": _identity_id(
            row.get("from_identity_id"),
            "track.artifact_relations[].from_identity_id",
        ),
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
    return {"type": "artifact", "id": state_runtime.require_id(row.get("id"), "track.updates[].refs[].id")}


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
        "by_identity_id": _identity_id(row.get("by_identity_id"), "track.updates[].by_identity_id"),
        "summary": _require_non_empty_text(row.get("summary"), "track.updates[].summary"),
        "kind": kind,
        "refs": [_normalize_update_ref(item) for item in refs],
        "created_at": created_at,
    }


def _has_current_proof_relation(relations: list[dict[str, Any]]) -> bool:
    return any(row.get("role") == "proof" and bool(row.get("current")) for row in relations)


def _enforce_state_invariants(*, state: str, now: dict[str, Any], artifact_relations: list[dict[str, Any]]) -> None:
    blocker = now.get("blocker")
    if state == "active":
        if blocker is not None:
            raise ValueError("active tracks require track.now.blocker = null")
        return
    if state == "blocked":
        if not isinstance(blocker, str) or not blocker.strip():
            raise ValueError("blocked tracks require a non-empty track.now.blocker")
        return
    if state == "done":
        if blocker is not None:
            raise ValueError("done tracks require track.now.blocker = null")
        if not _has_current_proof_relation(artifact_relations):
            raise ValueError("done tracks require at least one current proof relation")
        return
    raise ValueError(f"track.state must be one of {', '.join(VALID_TRACK_STATE)}")


def now_iso() -> str:
    return state_runtime.now_iso()


def list_tracks() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if tracks_dir().exists():
        for path in tracks_dir().glob("*.json"):
            rows.append(validate_track(state_runtime.read_json_object(path)))
    rows.sort(key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
    return rows


def get_track(track_id: str) -> dict[str, Any] | None:
    path = _track_file(track_id)
    if not path.exists():
        return None
    return validate_track(state_runtime.read_json_object(path))


def save_track(track: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_track(track)
    state_runtime.require_runtime_workspace_write_root()
    tracks_dir().mkdir(parents=True, exist_ok=True)
    state_runtime.write_json_object(_track_file(normalized["id"]), normalized)
    return normalized


def create_track(
    track_id: str,
    title: str,
    *,
    owner_identity: dict[str, Any] | str,
    outcome: str,
    now: dict[str, Any],
    acceptance_criteria: list[str] | None = None,
    non_goals: list[str] | None = None,
) -> dict[str, Any]:
    state_runtime.require_id(track_id, "track id")
    if get_track(track_id):
        raise ValueError(f"track already exists: {track_id}")
    timestamp = state_runtime.now_iso()
    track = {
        "id": track_id,
        "title": title,
        "outcome": outcome,
        "owner_identity_id": _identity_id(owner_identity, "owner_identity"),
        "state": "active",
        "now": now,
        "acceptance_criteria": acceptance_criteria or [],
        "non_goals": non_goals or [],
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
    allowed = {
        "title",
        "outcome",
        "state",
        "now",
        "acceptance_criteria",
        "non_goals",
        "artifact_relations",
        "updates",
        "archived_at",
    }
    for key, value in patch.items():
        if key not in allowed:
            raise ValueError(f"unsupported track field: {key}")
        track[key] = value
    track["updated_at"] = state_runtime.now_iso()
    return save_track(track)


def append_track_update(
    *,
    track_id: str,
    by_identity: dict[str, Any] | str,
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
        "by_identity_id": _identity_id(by_identity, "by_identity"),
        "summary": summary,
        "kind": kind,
        "refs": refs or [],
        "created_at": state_runtime.now_iso(),
    }
    updates = [entry for entry in track.get("updates", []) if isinstance(entry, dict)]
    updates.append(row)
    track["updates"] = updates
    track["updated_at"] = state_runtime.now_iso()
    track = save_track(track)
    return track, row


def validate_track(track: dict[str, Any]) -> dict[str, Any]:
    for field in _LEGACY_TRACK_ROLE_FIELDS:
        if field in track:
            raise ValueError("legacy track role-routing fields are retired; use owner_identity_id")
    forbidden = sorted(field for field in track if field in _LEGACY_TRACK_FIELDS or field in _RETIRED_TRACK_FIELDS)
    if forbidden:
        raise ValueError(f"legacy track fields are retired: {', '.join(forbidden)}")

    track_id = state_runtime.require_id(track.get("id", ""), "track.id")
    title = _require_non_empty_text(track.get("title"), "track.title")
    outcome = _require_non_empty_text(track.get("outcome"), "track.outcome")
    owner_identity_id = _identity_id(track.get("owner_identity_id"), "track.owner_identity_id")
    state = track.get("state")
    if state not in VALID_TRACK_STATE:
        raise ValueError(f"track.state must be one of {', '.join(VALID_TRACK_STATE)}")
    now = _normalize_now(track.get("now"))

    artifact_relations = track.get("artifact_relations")
    if not isinstance(artifact_relations, list):
        raise ValueError("track.artifact_relations must be a list")
    normalized_relations = [_normalize_artifact_relation(row) for row in artifact_relations]

    updates = track.get("updates")
    if not isinstance(updates, list):
        raise ValueError("track.updates must be a list")
    normalized_updates = [_normalize_update_row(row) for row in updates]

    _enforce_state_invariants(state=state, now=now, artifact_relations=normalized_relations)

    created_at = _require_non_empty_text(track.get("created_at"), "track.created_at")
    updated_at = _require_non_empty_text(track.get("updated_at"), "track.updated_at")
    archived_at = track.get("archived_at")
    if archived_at is not None and not isinstance(archived_at, str):
        raise ValueError("track.archived_at must be a string or null")

    return {
        "id": track_id,
        "title": title,
        "outcome": outcome,
        "owner_identity_id": owner_identity_id,
        "state": state,
        "now": now,
        "acceptance_criteria": _normalize_text_list(track.get("acceptance_criteria", []), "track.acceptance_criteria"),
        "non_goals": _normalize_text_list(track.get("non_goals", []), "track.non_goals"),
        "artifact_relations": normalized_relations,
        "updates": normalized_updates,
        "created_at": created_at,
        "updated_at": updated_at,
        "archived_at": archived_at,
    }
