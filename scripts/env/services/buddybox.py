#!/usr/bin/env python3
"""Runless buddybox services."""

from __future__ import annotations

import base64
import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Any, TypedDict

import env_store
from env.tools import responses as tool_responses


class BuddyboxServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


_LIST_FIELDS = {"path", "recursive", "limit"}
_READ_FIELDS = {"path", "encoding"}
_WRITE_FIELDS = {"path", "content", "content_base64", "content_type"}
_DELETE_FIELDS = {"path"}


def buddybox_root_for_buddy(buddy: str) -> Path:
    return env_store.BUDDYBOX_CONTENT_DIR / buddy


def normalize_buddybox_path(path: Any, *, active_buddy: str, for_write: bool) -> str:
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path must be a non-empty string")
    normalized = path.replace("\\", "/").strip()
    if normalized.startswith("/"):
        raise ValueError("absolute paths are not allowed")
    if normalized.startswith("../") or "/../" in normalized:
        raise ValueError("path traversal is not allowed")
    pieces = [piece for piece in normalized.split("/") if piece not in {"", "."}]
    if not pieces:
        raise ValueError("path must not be empty")
    normalized = "/".join(pieces)
    if for_write and pieces[0] != active_buddy:
        raise ValueError(f"path must stay under active buddy root '{active_buddy}/'")
    return normalized


def _resolve_path(path: str) -> Path:
    return env_store.BUDDYBOX_CONTENT_DIR / path


def _file_summary(path: Path, *, root: Path | None = None) -> dict[str, Any]:
    stat = path.stat()
    content_type, _ = mimetypes.guess_type(path.name)
    normalized_root = root or env_store.BUDDYBOX_CONTENT_DIR
    rel_path = path.relative_to(normalized_root).as_posix()
    buddy = rel_path.split("/", 1)[0] if "/" in rel_path else rel_path
    return {
        "buddy": buddy,
        "path": rel_path,
        "size_bytes": stat.st_size,
        "updated_at": env_store.now_iso(),
        "content_type": content_type or "application/octet-stream",
        "source_ref": {"type": "buddybox", "path": rel_path},
    }


def _reject_payload(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        code="E_BUDDYBOX_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Buddybox payload is invalid.",
        why_blocked=message,
        impact="No buddybox file state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix buddybox payload and retry.",
        allowed_next_actions=[
            "Use buddybox.list to inspect readable paths.",
            "Retry with valid relative path and payload encoding.",
        ],
    )


def _reject_scope(*, action: str, active_buddy: str, boundary: str, message: str, code: str = "E_BUDDYBOX_SCOPE") -> dict[str, Any]:
    return tool_responses.rejection(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        code=code,
        message=message,
        permission_boundary=boundary,
        human_summary="Buddybox scope check failed.",
        why_blocked=message,
        impact="No buddybox file state changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Use active-buddy-owned paths under buddybox root.",
        allowed_next_actions=[
            "Use buddybox.list to confirm path scope.",
            "Use active buddy root prefix for write/delete operations.",
        ],
    )


def _require_allowed_fields(action: str, args: dict[str, Any], active_buddy: str) -> dict[str, Any] | None:
    allowed = _LIST_FIELDS if action == "buddybox.list" else _READ_FIELDS if action == "buddybox.read" else _WRITE_FIELDS if action == "buddybox.write" else _DELETE_FIELDS
    unknown = sorted(key for key in args if key not in allowed)
    if unknown:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"unsupported payload fields: {', '.join(unknown)}")
    return None


def list_buddybox_for_active_buddy(*, args: dict[str, Any], context: BuddyboxServiceContext) -> dict[str, Any]:
    action = "buddybox.list"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    root = buddybox_root_for_buddy(active_buddy)
    env_store.ensure_runtime_dirs()
    root.mkdir(parents=True, exist_ok=True)

    path_filter = args.get("path")
    prefix = f"{active_buddy}"
    if isinstance(path_filter, str) and path_filter.strip():
        try:
            normalized = normalize_buddybox_path(path_filter, active_buddy=active_buddy, for_write=False)
        except ValueError as exc:
            return _reject_scope(action=action, active_buddy=active_buddy, boundary="buddybox.path", message=str(exc))
        prefix = normalized

    recursive = bool(args.get("recursive", False))
    limit = args.get("limit")
    limit_value = limit if isinstance(limit, int) and limit > 0 else 200

    files: list[dict[str, Any]] = []
    walker = root.rglob("*") if recursive else root.glob("*")
    for path in walker:
        if not path.is_file():
            continue
        rel_path = path.relative_to(env_store.BUDDYBOX_CONTENT_DIR).as_posix()
        if not rel_path.startswith(prefix):
            continue
        files.append(_file_summary(path))

    files.sort(key=lambda row: (str(row.get("updated_at") or ""), str(row.get("path") or "")), reverse=True)
    files = files[:limit_value]

    return tool_responses.success(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Listed {len(files)} buddybox file summary row(s).",
        state_changed=False,
        durability="none",
        read_scope="active-buddy buddybox file summaries",
        allowed_next_actions=[
            "Use buddybox.read for file content.",
            "Use buddybox.write to add or replace durable files.",
        ],
        extra={"files": files},
    )


def read_buddybox_for_active_buddy(*, args: dict[str, Any], context: BuddyboxServiceContext) -> dict[str, Any]:
    action = "buddybox.read"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    path = args.get("path")
    try:
        normalized = normalize_buddybox_path(path, active_buddy=active_buddy, for_write=False)
    except ValueError as exc:
        return _reject_scope(action=action, active_buddy=active_buddy, boundary="buddybox.path", message=str(exc))

    if normalized.split("/", 1)[0] != active_buddy and active_buddy != "pm":
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            boundary="buddybox.read_scope",
            code="E_BUDDYBOX_READ_SCOPE",
            message=f"path '{normalized}' is outside readable scope for buddy '{active_buddy}'",
        )

    resolved = _resolve_path(normalized)
    if not resolved.exists() or not resolved.is_file():
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"buddybox file not found: {normalized}")

    raw = resolved.read_bytes()
    preferred = args.get("encoding")
    encoding = "auto"
    if isinstance(preferred, str) and preferred.strip():
        encoding = preferred.strip().lower()
        if encoding not in {"auto", "utf-8", "base64"}:
            return _reject_payload(action=action, active_buddy=active_buddy, message="encoding must be auto, utf-8, or base64")

    payload: dict[str, Any] = {
        "buddy": normalized.split("/", 1)[0],
        "path": normalized,
        "size_bytes": len(raw),
        "content_type": mimetypes.guess_type(resolved.name)[0] or "application/octet-stream",
        "source_ref": {"type": "buddybox", "path": normalized},
    }

    if encoding == "base64":
        payload["encoding"] = "base64"
        payload["content_base64"] = base64.b64encode(raw).decode("ascii")
    else:
        try:
            text = raw.decode("utf-8")
            payload["encoding"] = "utf-8"
            payload["content"] = text
        except UnicodeDecodeError:
            payload["encoding"] = "base64"
            payload["content_base64"] = base64.b64encode(raw).decode("ascii")

    return tool_responses.success(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Read buddybox file '{normalized}'.",
        state_changed=False,
        durability="none",
        read_scope="active scope buddybox file content",
        allowed_next_actions=[
            "Use buddybox.write to replace content.",
            "Reference this path in artifact or handoff source_refs.",
        ],
        extra=payload,
    )


def write_buddybox_for_active_buddy(*, args: dict[str, Any], context: BuddyboxServiceContext) -> dict[str, Any]:
    action = "buddybox.write"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    path = args.get("path")
    try:
        normalized = normalize_buddybox_path(path, active_buddy=active_buddy, for_write=True)
    except ValueError as exc:
        return _reject_scope(action=action, active_buddy=active_buddy, boundary="buddybox.owner_scope", message=str(exc))

    content = args.get("content")
    content_base64 = args.get("content_base64")
    if (content is None and content_base64 is None) or (content is not None and content_base64 is not None):
        return _reject_payload(action=action, active_buddy=active_buddy, message="provide exactly one of content or content_base64")

    if content is not None:
        if not isinstance(content, str):
            return _reject_payload(action=action, active_buddy=active_buddy, message="content must be a string")
        raw = content.encode("utf-8")
    else:
        if not isinstance(content_base64, str) or not content_base64.strip():
            return _reject_payload(action=action, active_buddy=active_buddy, message="content_base64 must be a non-empty string")
        try:
            raw = base64.b64decode(content_base64.encode("ascii"), validate=True)
        except Exception:
            return _reject_payload(action=action, active_buddy=active_buddy, message="content_base64 must be valid base64")

    resolved = _resolve_path(normalized)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    existed = resolved.exists()

    with tempfile.NamedTemporaryFile("wb", delete=False, dir=resolved.parent) as handle:
        handle.write(raw)
        temp_name = handle.name
    os.replace(temp_name, resolved)

    content_type = args.get("content_type")
    if not isinstance(content_type, str) or not content_type.strip():
        content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"

    payload = {
        "buddy": normalized.split("/", 1)[0],
        "path": normalized,
        "size_bytes": len(raw),
        "content_type": content_type,
        "source_ref": {"type": "buddybox", "path": normalized},
        "overwrote": existed,
    }

    return tool_responses.success(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Wrote buddybox file '{normalized}'.",
        state_changed=True,
        durability="durable",
        created_ids=[normalized] if not existed else None,
        updated_ids=[normalized] if existed else None,
        allowed_next_actions=[
            "Use buddybox.read to verify content.",
            "Attach this path via source_refs in artifact/handoff writes.",
        ],
        extra=payload,
    )


def delete_buddybox_for_active_buddy(*, args: dict[str, Any], context: BuddyboxServiceContext) -> dict[str, Any]:
    action = "buddybox.delete"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    path = args.get("path")
    try:
        normalized = normalize_buddybox_path(path, active_buddy=active_buddy, for_write=True)
    except ValueError as exc:
        return _reject_scope(action=action, active_buddy=active_buddy, boundary="buddybox.owner_scope", message=str(exc))

    resolved = _resolve_path(normalized)
    if resolved.exists() and resolved.is_dir():
        return _reject_payload(action=action, active_buddy=active_buddy, message="path points to a directory, not a file")

    deleted = False
    if resolved.exists() and resolved.is_file():
        resolved.unlink()
        deleted = True

    return tool_responses.success(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Deleted buddybox file '{normalized}'." if deleted else f"Buddybox file '{normalized}' did not exist.",
        state_changed=deleted,
        durability="durable" if deleted else "none",
        updated_ids=[normalized] if deleted else None,
        allowed_next_actions=["Use buddybox.list to inspect remaining files."],
        extra={"path": normalized, "deleted": deleted},
    )
