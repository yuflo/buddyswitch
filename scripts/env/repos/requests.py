#!/usr/bin/env python3
"""Request repository helpers backed by runtime object files."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from env.tool_runtime.actor_profile import ActorAddress
from . import runtime_files

VALID_REQUEST_STATUS = ("open", "accepted", "blocked", "done", "canceled")
_REF_TYPES = {"track", "artifact", "comment"}
_REQUEST_FIELDS = {
    "id",
    "track_id",
    "from_actor",
    "to_role",
    "title",
    "summary",
    "target_refs",
    "status",
    "blocker",
    "result_refs",
    "created_at",
    "updated_at",
    "accepted_at",
    "blocked_at",
    "completed_at",
    "canceled_at",
    "accepted_by_actor",
    "blocked_by_actor",
    "completed_by_actor",
    "canceled_by_actor",
}


def _require_non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_non_empty_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string or null")
    return value.strip()


def _normalize_ref_row(row: Any, *, field: str) -> dict[str, str]:
    if not isinstance(row, dict):
        raise ValueError(f"{field} entries must be objects")
    extras = sorted(key for key in row if key not in {"type", "id"})
    if extras:
        raise ValueError(f"{field} entries contain unsupported fields: {', '.join(extras)}")
    ref_type = _require_non_empty_text(row.get("type"), f"{field}.type")
    if ref_type not in _REF_TYPES:
        raise ValueError(f"{field}.type must be one of track|artifact|comment")
    ref_id = runtime_files.require_id(
        _require_non_empty_text(row.get("id"), f"{field}.id"),
        f"{field}.id",
    )
    return {
        "type": ref_type,
        "id": ref_id,
    }


def _normalize_refs(value: Any, *, field: str) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return [_normalize_ref_row(row, field=f"{field}[{idx}]") for idx, row in enumerate(value)]


def _normalize_actor(value: Any, field: str) -> dict[str, str]:
    try:
        return ActorAddress.from_payload(value).to_payload()
    except ValueError as exc:
        raise ValueError(f"{field} must be an ActorAddress payload: {exc}") from exc


def _optional_actor(value: Any, field: str) -> dict[str, str] | None:
    if value is None:
        return None
    return _normalize_actor(value, field)


def request_file(request_id: str) -> Path:
    return runtime_files.REQUESTS_DIR / f"{runtime_files.require_id(request_id, 'request id')}.json"


def _validate_request(request: dict[str, Any]) -> dict[str, Any]:
    extras = sorted(key for key in request if key not in _REQUEST_FIELDS)
    if extras:
        raise ValueError(f"unsupported request fields: {', '.join(extras)}")

    request_id = runtime_files.require_id(request.get("id", ""), "request.id")
    track_id = runtime_files.require_id(request.get("track_id", ""), "request.track_id")
    from_actor = _normalize_actor(request.get("from_actor"), "request.from_actor")
    to_role = _require_non_empty_text(request.get("to_role"), "request.to_role")
    title = _require_non_empty_text(request.get("title"), "request.title")
    summary = _require_non_empty_text(request.get("summary"), "request.summary")
    target_refs = _normalize_refs(request.get("target_refs"), field="request.target_refs")
    status = _require_non_empty_text(request.get("status"), "request.status")
    if status not in VALID_REQUEST_STATUS:
        raise ValueError(f"request.status must be one of {', '.join(VALID_REQUEST_STATUS)}")
    blocker = _optional_non_empty_text(request.get("blocker"), "request.blocker")
    result_refs = _normalize_refs(request.get("result_refs"), field="request.result_refs")
    created_at = _require_non_empty_text(request.get("created_at"), "request.created_at")
    updated_at = _require_non_empty_text(request.get("updated_at"), "request.updated_at")
    accepted_at = _optional_non_empty_text(request.get("accepted_at"), "request.accepted_at")
    blocked_at = _optional_non_empty_text(request.get("blocked_at"), "request.blocked_at")
    completed_at = _optional_non_empty_text(request.get("completed_at"), "request.completed_at")
    canceled_at = _optional_non_empty_text(request.get("canceled_at"), "request.canceled_at")
    accepted_by_actor = _optional_actor(request.get("accepted_by_actor"), "request.accepted_by_actor")
    blocked_by_actor = _optional_actor(request.get("blocked_by_actor"), "request.blocked_by_actor")
    completed_by_actor = _optional_actor(request.get("completed_by_actor"), "request.completed_by_actor")
    canceled_by_actor = _optional_actor(request.get("canceled_by_actor"), "request.canceled_by_actor")

    return {
        "id": request_id,
        "track_id": track_id,
        "from_actor": from_actor,
        "to_role": to_role,
        "title": title,
        "summary": summary,
        "target_refs": target_refs,
        "status": status,
        "blocker": blocker,
        "result_refs": result_refs,
        "created_at": created_at,
        "updated_at": updated_at,
        "accepted_at": accepted_at,
        "blocked_at": blocked_at,
        "completed_at": completed_at,
        "canceled_at": canceled_at,
        "accepted_by_actor": accepted_by_actor,
        "blocked_by_actor": blocked_by_actor,
        "completed_by_actor": completed_by_actor,
        "canceled_by_actor": canceled_by_actor,
    }


def list_requests() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if runtime_files.REQUESTS_DIR.is_dir():
        for path in runtime_files.REQUESTS_DIR.glob("*.json"):
            rows.append(_validate_request(runtime_files.read_json_object(path)))
    rows.sort(
        key=lambda row: (
            str(row.get("updated_at") or ""),
            str(row.get("id") or ""),
        ),
        reverse=True,
    )
    return rows


def get_request(request_id: str) -> dict[str, Any] | None:
    path = request_file(request_id)
    if not path.exists():
        return None
    return _validate_request(runtime_files.read_json_object(path))


def save_request(request: dict[str, Any]) -> dict[str, Any]:
    normalized = _validate_request(request)
    runtime_files.require_runtime_workspace_write_root()
    runtime_files.REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    runtime_files.write_json_object(request_file(normalized["id"]), normalized)
    return normalized


def create_request(
    *,
    track_id: str,
    from_actor: dict[str, Any],
    to_role: str,
    title: str,
    summary: str,
    target_refs: list[dict[str, Any]] | None = None,
    status: str = "open",
    blocker: str | None = None,
    result_refs: list[dict[str, Any]] | None = None,
    request_id: str | None = None,
    accepted_at: str | None = None,
    blocked_at: str | None = None,
    completed_at: str | None = None,
    canceled_at: str | None = None,
    accepted_by_actor: dict[str, Any] | None = None,
    blocked_by_actor: dict[str, Any] | None = None,
    completed_by_actor: dict[str, Any] | None = None,
    canceled_by_actor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_value = request_id.strip() if isinstance(request_id, str) and request_id.strip() else f"req-{uuid.uuid4().hex[:12]}"
    runtime_files.require_id(request_value, "request id")
    now = runtime_files.now_iso()
    return save_request(
        {
            "id": request_value,
            "track_id": track_id,
            "from_actor": from_actor,
            "to_role": to_role,
            "title": title,
            "summary": summary,
            "target_refs": target_refs if target_refs is not None else [],
            "status": status,
            "blocker": blocker,
            "result_refs": result_refs if result_refs is not None else [],
            "created_at": now,
            "updated_at": now,
            "accepted_at": accepted_at,
            "blocked_at": blocked_at,
            "completed_at": completed_at,
            "canceled_at": canceled_at,
            "accepted_by_actor": accepted_by_actor,
            "blocked_by_actor": blocked_by_actor,
            "completed_by_actor": completed_by_actor,
            "canceled_by_actor": canceled_by_actor,
        }
    )


def update_request(request_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    request = get_request(request_id)
    if request is None:
        raise ValueError(f"request not found: {request_id}")
    if not isinstance(patch, dict):
        raise ValueError("patch must be an object")
    if "id" in patch:
        raise ValueError("request.id is immutable")
    if not patch:
        raise ValueError("request patch must contain at least one field")
    allowed_patch_fields = _REQUEST_FIELDS - {"id", "created_at"}
    unknown = sorted(key for key in patch if key not in allowed_patch_fields)
    if unknown:
        raise ValueError(f"unsupported request patch fields: {', '.join(unknown)}")

    merged = dict(request)
    merged.update(patch)
    return save_request(merged)
