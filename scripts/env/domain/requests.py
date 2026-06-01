#!/usr/bin/env python3
"""Request-domain validation, visibility, and transition helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from env.repos import requests as request_repo
from env.repos import runtime_files
from env.tool_runtime.actor_profile import ActorAddress


class RequestPayloadError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        correctable_fields: list[str] | None = None,
        field_errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.correctable_fields = correctable_fields
        self.field_errors = field_errors


class RequestScopeError(ValueError):
    def __init__(
        self,
        *,
        message: str,
        permission_boundary: str,
        human_summary: str,
        why_blocked: str,
        retryable: bool = False,
        correctable_fields: list[str] | None = None,
        code: str = "E_REQUEST_SCOPE",
    ) -> None:
        super().__init__(message)
        self.permission_boundary = permission_boundary
        self.human_summary = human_summary
        self.why_blocked = why_blocked
        self.retryable = retryable
        self.correctable_fields = correctable_fields
        self.code = code


class RequestStateError(ValueError):
    def __init__(self, message: str, *, correctable_fields: list[str] | None = None) -> None:
        super().__init__(message)
        self.correctable_fields = correctable_fields


def _require_non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RequestPayloadError(f"{field} must be a non-empty string", correctable_fields=[field])
    return value.strip()


def _actor_payload(value: ActorAddress | dict[str, Any], field: str) -> dict[str, str]:
    try:
        if isinstance(value, ActorAddress):
            return value.to_payload()
        return ActorAddress.from_payload(value).to_payload()
    except ValueError as exc:
        raise RequestPayloadError(f"{field} must be a valid ActorAddress: {exc}", correctable_fields=[field]) from exc


def _request_actor(value: Any, field: str) -> ActorAddress:
    try:
        return ActorAddress.from_payload(value)
    except ValueError as exc:
        raise RequestScopeError(
            message=f"{field} must be a valid ActorAddress: {exc}",
            permission_boundary="request.actor_identity",
            human_summary="Request actor identity is malformed.",
            why_blocked="Request lifecycle decisions require concrete actor identity.",
            retryable=False,
            correctable_fields=["request_id"],
        ) from exc


def manifest_role_ids(manifest: dict[str, Any] | None) -> set[str]:
    if not isinstance(manifest, dict):
        return set()
    roles = manifest.get("roles")
    if not isinstance(roles, list):
        return set()
    rows: set[str] = set()
    for row in roles:
        if not isinstance(row, dict):
            continue
        role_id = row.get("id")
        if isinstance(role_id, str) and role_id.strip():
            rows.add(role_id.strip())
    return rows


def ensure_manifest_role(role_id: str, manifest_role_ids: set[str], field: str) -> None:
    if role_id in manifest_role_ids:
        return
    raise RequestPayloadError(
        f"{field} must be one of manifest roles",
        correctable_fields=[field],
        field_errors=[
            {
                "path": field,
                "message": f"unknown role id: {role_id}",
                "allowed_values": sorted(manifest_role_ids),
                "example": sorted(manifest_role_ids)[:1],
            }
        ],
    )


def normalize_ref_items(value: Any, field: str) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise RequestPayloadError(f"{field} must be a list", correctable_fields=[field])
    rows: list[dict[str, str]] = []
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            raise RequestPayloadError(f"{field}[{index}] must be an object", correctable_fields=[field])
        unknown = sorted(key for key in row if key not in {"type", "id"})
        if unknown:
            raise RequestPayloadError(
                f"{field}[{index}] has unsupported fields: {', '.join(unknown)}",
                correctable_fields=[field],
            )
        ref_type = _require_non_empty_text(row.get("type"), f"{field}[{index}].type")
        if ref_type not in {"track", "artifact", "comment"}:
            raise RequestPayloadError(
                f"{field}[{index}].type must be one of track|artifact|comment",
                correctable_fields=[field],
            )
        ref_id = runtime_files.require_id(
            _require_non_empty_text(row.get("id"), f"{field}[{index}].id"),
            f"{field}[{index}].id",
        )
        rows.append({"type": ref_type, "id": ref_id})
    return rows


def normalize_create_args(
    *,
    args: Mapping[str, Any],
    active_role: str,
    active_actor_address: ActorAddress | dict[str, Any],
    manifest: dict[str, Any],
    track: dict[str, Any],
    readable_ref_checker: Callable[[dict[str, str], str], None],
    allowed_fields: set[str],
) -> dict[str, Any]:
    unknown = sorted(key for key in args if key not in allowed_fields)
    if unknown:
        raise RequestPayloadError(
            f"unsupported payload fields: {', '.join(unknown)}",
            correctable_fields=unknown,
        )

    manifest_ids = manifest_role_ids(manifest)
    ensure_manifest_role(active_role, manifest_ids, "active_role")

    track_id = runtime_files.require_id(
        _require_non_empty_text(args.get("track_id"), "track_id"),
        "track_id",
    )
    current_track_id = str(track.get("id") or "")
    if track_id != current_track_id:
        raise RequestPayloadError("track_id does not match loaded track context", correctable_fields=["track_id"])

    to_role = _require_non_empty_text(args.get("to_role"), "to_role")
    ensure_manifest_role(to_role, manifest_ids, "to_role")
    if to_role == active_role:
        raise RequestScopeError(
            message="request sender and recipient must differ",
            permission_boundary="request.self_request",
            human_summary="Self-directed requests are not allowed.",
            why_blocked="request.create requires from_actor and to_role to be different manifest roles.",
            retryable=True,
            correctable_fields=["to_role"],
        )

    title = _require_non_empty_text(args.get("title"), "title")
    summary = _require_non_empty_text(args.get("summary"), "summary")
    target_refs = normalize_ref_items(args.get("target_refs"), "target_refs")
    for ref in target_refs:
        if ref["type"] == "track" and ref["id"] != track_id:
            raise RequestPayloadError(
                "track target_refs must match track_id",
                correctable_fields=["target_refs", "track_id"],
            )
        readable_ref_checker(ref, track_id)

    return {
        "track_id": track_id,
        "from_actor": _actor_payload(active_actor_address, "active_actor"),
        "to_role": to_role,
        "title": title,
        "summary": summary,
        "target_refs": target_refs,
    }


def normalize_list_args(
    *,
    args: Mapping[str, Any],
    manifest: dict[str, Any],
    allowed_fields: set[str],
) -> dict[str, Any]:
    unknown = sorted(key for key in args if key not in allowed_fields)
    if unknown:
        raise RequestPayloadError(
            f"unsupported payload fields: {', '.join(unknown)}",
            correctable_fields=unknown,
        )

    box_value = args.get("box", "all")
    if not isinstance(box_value, str) or box_value.strip() not in {"all", "inbox", "outbox"}:
        raise RequestPayloadError("box must be one of all|inbox|outbox", correctable_fields=["box"])
    box = box_value.strip()

    status_raw = args.get("status")
    status: str | None = None
    if status_raw is not None:
        if not isinstance(status_raw, str) or status_raw.strip() not in request_repo.VALID_REQUEST_STATUS:
            raise RequestPayloadError(
                f"status must be one of {', '.join(request_repo.VALID_REQUEST_STATUS)}",
                correctable_fields=["status"],
            )
        status = status_raw.strip()

    track_raw = args.get("track_id")
    track_id: str | None = None
    if track_raw is not None:
        track_id = runtime_files.require_id(_require_non_empty_text(track_raw, "track_id"), "track_id")

    role_raw = args.get("role")
    role: str | None = None
    if role_raw is not None:
        role = _require_non_empty_text(role_raw, "role")
        ensure_manifest_role(role, manifest_role_ids(manifest), "role")

    return {
        "box": box,
        "status": status,
        "track_id": track_id,
        "role": role,
    }


def require_request_id(args: Mapping[str, Any]) -> str:
    request_id = _require_non_empty_text(args.get("request_id"), "request_id")
    return runtime_files.require_id(request_id, "request_id")


def ensure_visible(
    request: Mapping[str, Any],
    active_role: str,
    active_actor_address: ActorAddress | dict[str, Any],
) -> None:
    active_actor = ActorAddress.from_payload(_actor_payload(active_actor_address, "active_actor"))
    requester = _request_actor(request.get("from_actor"), "request.from_actor")
    if (
        requester.actor_id == active_actor.actor_id
        or request.get("to_role") == active_role
        or active_role == "pm"
    ):
        return
    raise RequestScopeError(
        message=f"request '{request.get('id')}' is not visible to active role '{active_role}'",
        permission_boundary="request.visibility",
        human_summary="Request is outside active-role visibility scope.",
        why_blocked="Only requester, recipient, or PM can read this request.",
        retryable=False,
        correctable_fields=["request_id"],
    )


def ensure_recipient(request: Mapping[str, Any], active_role: str) -> None:
    if request.get("to_role") == active_role:
        return
    raise RequestScopeError(
        message=f"request '{request.get('id')}' can only be changed by recipient '{request.get('to_role')}'",
        permission_boundary="request.recipient_scope",
        human_summary="Only the request recipient can run this action.",
        why_blocked="request.accept/block/complete are recipient-only mutations.",
        retryable=False,
        correctable_fields=["request_id"],
    )


def ensure_requester(
    request: Mapping[str, Any],
    active_actor_address: ActorAddress | dict[str, Any],
) -> None:
    active_actor = ActorAddress.from_payload(_actor_payload(active_actor_address, "active_actor"))
    requester = _request_actor(request.get("from_actor"), "request.from_actor")
    if requester.actor_id == active_actor.actor_id:
        return
    raise RequestScopeError(
        message=f"request '{request.get('id')}' can only be canceled by requester '{requester.actor_id}'",
        permission_boundary="request.requester_scope",
        human_summary="Only the request sender can cancel this request.",
        why_blocked="request.cancel is requester-only in this runtime scope.",
        retryable=False,
        correctable_fields=["request_id"],
    )


def accept_patch(
    request: Mapping[str, Any],
    active_role: str,
    active_actor_address: ActorAddress | dict[str, Any],
    now: str,
) -> dict[str, Any]:
    ensure_recipient(request, active_role)
    status = request.get("status")
    if status not in {"open", "blocked"}:
        raise RequestStateError(
            f"request.accept requires status open|blocked, got {status!r}",
            correctable_fields=["request_id"],
        )
    return {
        "status": "accepted",
        "updated_at": now,
        "accepted_at": now,
        "blocked_at": None,
        "completed_at": None,
        "canceled_at": None,
        "accepted_by_actor": _actor_payload(active_actor_address, "active_actor"),
        "blocked_by_actor": None,
        "completed_by_actor": None,
        "canceled_by_actor": None,
        "blocker": None,
    }


def block_patch(
    request: Mapping[str, Any],
    active_role: str,
    active_actor_address: ActorAddress | dict[str, Any],
    blocker: str,
    now: str,
) -> dict[str, Any]:
    ensure_recipient(request, active_role)
    status = request.get("status")
    if status != "accepted":
        raise RequestStateError(
            f"request.block requires status accepted, got {status!r}",
            correctable_fields=["request_id"],
        )
    blocker_text = _require_non_empty_text(blocker, "blocker")
    return {
        "status": "blocked",
        "updated_at": now,
        "blocker": blocker_text,
        "blocked_at": now,
        "completed_at": None,
        "canceled_at": None,
        "blocked_by_actor": _actor_payload(active_actor_address, "active_actor"),
        "completed_by_actor": None,
        "canceled_by_actor": None,
    }


def complete_patch(
    request: Mapping[str, Any],
    active_role: str,
    active_actor_address: ActorAddress | dict[str, Any],
    result_refs: list[dict[str, str]],
    now: str,
) -> dict[str, Any]:
    ensure_recipient(request, active_role)
    status = request.get("status")
    if status not in {"accepted", "blocked"}:
        raise RequestStateError(
            f"request.complete requires status accepted|blocked, got {status!r}",
            correctable_fields=["request_id"],
        )
    if not result_refs:
        raise RequestPayloadError("result_refs must be a non-empty list", correctable_fields=["result_refs"])
    return {
        "status": "done",
        "updated_at": now,
        "result_refs": result_refs,
        "blocker": None,
        "completed_at": now,
        "canceled_at": None,
        "completed_by_actor": _actor_payload(active_actor_address, "active_actor"),
        "canceled_by_actor": None,
    }


def cancel_patch(request: Mapping[str, Any], active_actor_address: ActorAddress | dict[str, Any], now: str) -> dict[str, Any]:
    ensure_requester(request, active_actor_address)
    status = request.get("status")
    if status not in {"open", "accepted", "blocked"}:
        raise RequestStateError(
            f"request.cancel requires status open|accepted|blocked, got {status!r}",
            correctable_fields=["request_id"],
        )
    return {
        "status": "canceled",
        "updated_at": now,
        "canceled_at": now,
        "completed_at": None,
        "canceled_by_actor": _actor_payload(active_actor_address, "active_actor"),
    }
