#!/usr/bin/env python3
"""Runless buddybox services."""

from __future__ import annotations

import base64
import mimetypes
import os
import tempfile
from datetime import datetime
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


BUDDYBOX_PRIVACY_MESSAGE = (
    "This is the active buddy's private local working directory. "
    "Other buddies cannot list, read, write, or delete these files. "
    "Use artifact when content must become product-readable."
)

_DESC_FIELDS: set[str] = set()
_LIST_FIELDS = {"path", "recursive", "limit"}
_READ_FIELDS = {"path", "encoding"}
_WRITE_FIELDS = {"path", "content", "content_base64", "content_type"}
_DELETE_FIELDS = {"path"}


def buddybox_root_for_buddy(buddy: str) -> Path:
    return env_store.BUDDYBOX_LOCAL_DIR / buddy


def normalize_active_buddybox_path(path: Any, *, active_buddy: str) -> str:
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
    if pieces[0] != active_buddy:
        raise ValueError(f"path must stay under active buddy private local root '{active_buddy}/'")
    return normalized


def normalize_buddybox_prefix(path: Any, *, active_buddy: str) -> str:
    if path is None:
        return active_buddy
    if not isinstance(path, str) or not path.strip():
        return active_buddy
    normalized = normalize_active_buddybox_path(path, active_buddy=active_buddy)
    return normalized


def _resolve_path(path: str) -> Path:
    return env_store.BUDDYBOX_LOCAL_DIR / path


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _resolved_active_root(active_buddy: str) -> Path:
    return buddybox_root_for_buddy(active_buddy).resolve(strict=False)


def _resolved_path_stays_in_active_root(path: Path, *, active_buddy: str) -> bool:
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        return False
    return _path_is_within(resolved, _resolved_active_root(active_buddy))


def _write_parent_stays_in_active_root(path: Path, *, active_buddy: str) -> bool:
    parent = path.parent.resolve(strict=False)
    return _path_is_within(parent, _resolved_active_root(active_buddy))


def _updated_at_from_stat(path: Path) -> str:
    stat = path.stat()
    return datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds")


def _file_summary(path: Path, *, active_buddy: str) -> dict[str, Any]:
    stat = path.stat()
    content_type, _ = mimetypes.guess_type(path.name)
    rel_path = path.relative_to(env_store.BUDDYBOX_LOCAL_DIR).as_posix()
    return {
        "buddy": active_buddy,
        "path": rel_path,
        "size_bytes": stat.st_size,
        "updated_at": _updated_at_from_stat(path),
        "content_type": content_type or "application/octet-stream",
        "private_to_buddy": active_buddy,
    }


def _buddybox_state_summary(root: Path, *, active_buddy: str) -> dict[str, Any]:
    file_count = 0
    total_bytes = 0
    latest_mtime: float | None = None
    if root.exists():
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if not _resolved_path_stays_in_active_root(path, active_buddy=active_buddy):
                continue
            stat = path.stat()
            file_count += 1
            total_bytes += stat.st_size
            if latest_mtime is None or stat.st_mtime > latest_mtime:
                latest_mtime = stat.st_mtime
    latest_update_at = (
        datetime.fromtimestamp(latest_mtime).astimezone().isoformat(timespec="seconds")
        if latest_mtime is not None
        else None
    )
    return {
        "file_count": file_count,
        "total_bytes": total_bytes,
        "latest_update_at": latest_update_at,
    }


def build_buddybox_desc(active_buddy: str) -> dict[str, Any]:
    root = buddybox_root_for_buddy(active_buddy)
    env_store.ensure_runtime_dirs()
    root.mkdir(parents=True, exist_ok=True)
    return {
        "active_buddy": active_buddy,
        "logical_root": f"buddyswitch/local/buddybox/{active_buddy}",
        "privacy_boundary": "active-buddy-private-local-workspace",
        "message": BUDDYBOX_PRIVACY_MESSAGE,
        "available_operations": [
            "buddybox.desc",
            "buddybox.list",
            "buddybox.read",
            "buddybox.write",
            "buddybox.delete",
        ],
        "state_summary": _buddybox_state_summary(root, active_buddy=active_buddy),
        "allowed_next_actions": [
            "Use buddybox.list to inspect active buddy private file summaries.",
            "Use buddybox.write for private local drafts or generated files.",
            (
                "When the host decides another buddy must read this content, create an artifact revision "
                "or another explicit readable reference that carries the content."
            ),
        ],
    }


def _reject_payload(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        code="E_BUDDYBOX_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Buddybox payload is invalid for the active buddy private local workspace.",
        why_blocked=message,
        impact="No private local buddybox file changed and no product/collaboration object changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix the payload fields and retry with an active-buddy private local path.",
        allowed_next_actions=[
            "Use buddybox.desc to review private local workspace semantics.",
            "Use buddybox.list with an active buddy local prefix.",
        ],
        allowed_next_action_options=_rejection_options(action),
    )


def _reject_scope(
    *,
    action: str,
    active_buddy: str,
    boundary: str,
    message: str,
    code: str = "E_BUDDYBOX_SCOPE",
) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        code=code,
        message=message,
        permission_boundary=boundary,
        human_summary="Buddybox request crossed the active-buddy private local boundary.",
        why_blocked=message,
        impact="No private local buddybox file changed and no product/collaboration object changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Stay under the active buddy local root and retry.",
        allowed_next_actions=[
            "Use buddybox.desc to confirm the private local boundary.",
            "Retry with a path under the active buddy local root.",
        ],
        allowed_next_action_options=_rejection_options(action),
    )


def _require_allowed_fields(action: str, args: dict[str, Any], active_buddy: str) -> dict[str, Any] | None:
    if action == "buddybox.desc":
        allowed = _DESC_FIELDS
    elif action == "buddybox.list":
        allowed = _LIST_FIELDS
    elif action == "buddybox.read":
        allowed = _READ_FIELDS
    elif action == "buddybox.write":
        allowed = _WRITE_FIELDS
    else:
        allowed = _DELETE_FIELDS
    unknown = sorted(key for key in args if key not in allowed)
    if unknown:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"unsupported payload fields: {', '.join(unknown)}")
    return None


def _normalize_action_name(action: str) -> str:
    if action.startswith("buddybox."):
        return action.split(".", 1)[1]
    return action


def _operation_semantic_ref(action: str) -> str:
    return f"context.get.operation_semantics['buddybox.{action}']"


def _tool_catalog_ref(tool: str) -> str:
    return f"context.get.tool_catalog['{tool}']"


def _next_option(
    *,
    tool: str,
    action: str,
    option_id: str,
    reason: str,
    preconditions: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = [_tool_catalog_ref(tool), f"context.get.operation_semantics['{tool}.{action}']"]
    return tool_responses.next_action_option(
        tool=tool,
        action=action,
        option_id=option_id,
        reason=reason,
        preconditions=preconditions,
        source_refs=source_refs,
    )


def _buddybox_retry_option(action: str) -> dict[str, Any]:
    action_name = _normalize_action_name(action)
    return _next_option(
        tool="buddybox",
        action=action_name,
        option_id="retry_active_buddy_private_path",
        reason="Retry the same buddybox action with a path under the active buddy private local root.",
        preconditions=[f"path stays under <active_buddy>/... for buddybox.{action_name}"],
    )


def _rejection_options(action: str) -> list[dict[str, Any]]:
    return [
        _next_option(
            tool="buddybox",
            action="desc",
            option_id="review_buddybox_private_boundary",
            reason="Review the active buddy private-local boundary before retrying.",
        ),
        _buddybox_retry_option(action),
    ]


def _desc_options() -> list[dict[str, Any]]:
    return [
        _next_option(
            tool="buddybox",
            action="list",
            option_id="inspect_private_buddybox_summaries",
            reason="Inspect private local file summary rows in the active buddy workspace.",
        ),
        _next_option(
            tool="buddybox",
            action="write",
            option_id="write_private_buddybox_file",
            reason="Create or replace one active buddy private local file.",
        ),
    ]


def _list_options() -> list[dict[str, Any]]:
    return [
        _next_option(
            tool="buddybox",
            action="read",
            option_id="read_private_buddybox_file",
            reason="Read one private local file chosen from list summaries.",
        ),
        _next_option(
            tool="buddybox",
            action="write",
            option_id="write_private_buddybox_file",
            reason="Create or replace one active buddy private local file.",
        ),
    ]


def _read_options() -> list[dict[str, Any]]:
    return [
        _next_option(
            tool="buddybox",
            action="write",
            option_id="replace_private_buddybox_file",
            reason="Replace the current private local file with an updated version.",
        ),
        _next_option(
            tool="artifact",
            action="create_revision",
            option_id="promote_readable_content_when_needed",
            reason="Use artifact.create_revision when the host decides content should become product-readable.",
        ),
    ]


def _write_options() -> list[dict[str, Any]]:
    return [
        _next_option(
            tool="buddybox",
            action="read",
            option_id="confirm_private_buddybox_file",
            reason="Confirm the private local file that was just written.",
        ),
        _next_option(
            tool="buddybox",
            action="list",
            option_id="inspect_private_buddybox_summaries",
            reason="Inspect private local summaries after the write.",
        ),
        _next_option(
            tool="artifact",
            action="create_revision",
            option_id="promote_readable_content_when_needed",
            reason="Use artifact.create_revision when the host decides content should become product-readable.",
        ),
    ]


def _delete_options() -> list[dict[str, Any]]:
    return [
        _next_option(
            tool="buddybox",
            action="list",
            option_id="inspect_private_buddybox_summaries",
            reason="Inspect remaining private local summaries after delete.",
        ),
        _next_option(
            tool="buddybox",
            action="write",
            option_id="write_private_buddybox_file",
            reason="Create a replacement private local file if needed.",
        ),
    ]


def describe_buddybox_for_active_buddy(*, args: dict[str, Any], context: BuddyboxServiceContext) -> dict[str, Any]:
    action = "buddybox.desc"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    desc = build_buddybox_desc(active_buddy)
    desc_payload = dict(desc)
    allowed_next_actions = list(desc_payload.pop("allowed_next_actions", []))
    desc_payload.pop("active_buddy", None)
    return tool_responses.success(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        effect_summary=(
            "Returned active buddy private local workspace semantics and compact state summary only. "
            "No file content and no product/collaboration object state were changed."
        ),
        state_changed=False,
        durability="none",
        read_scope="active-buddy private local workspace description",
        allowed_next_actions=allowed_next_actions,
        allowed_next_action_options=_desc_options(),
        extra=desc_payload,
    )


def list_buddybox_for_active_buddy(*, args: dict[str, Any], context: BuddyboxServiceContext) -> dict[str, Any]:
    action = "buddybox.list"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    root = buddybox_root_for_buddy(active_buddy)
    env_store.ensure_runtime_dirs()
    root.mkdir(parents=True, exist_ok=True)

    try:
        prefix = normalize_buddybox_prefix(args.get("path"), active_buddy=active_buddy)
    except ValueError as exc:
        return _reject_scope(action=action, active_buddy=active_buddy, boundary="buddybox.path", message=str(exc))

    recursive = bool(args.get("recursive", False))
    limit = args.get("limit")
    limit_value = limit if isinstance(limit, int) and limit > 0 else 200

    files: list[dict[str, Any]] = []
    walker = root.rglob("*") if recursive else root.glob("*")
    for path in walker:
        if not path.is_file():
            continue
        if not _resolved_path_stays_in_active_root(path, active_buddy=active_buddy):
            continue
        rel_path = path.relative_to(env_store.BUDDYBOX_LOCAL_DIR).as_posix()
        if not rel_path.startswith(prefix):
            continue
        files.append(_file_summary(path, active_buddy=active_buddy))

    files.sort(key=lambda row: (str(row.get("updated_at") or ""), str(row.get("path") or "")), reverse=True)
    files = files[:limit_value]

    return tool_responses.success(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        effect_summary=(
            f"Listed {len(files)} active-buddy private local file summary row(s). "
            "No file content was returned and no product/collaboration object changed."
        ),
        state_changed=False,
        durability="none",
        read_scope="active-buddy private local file summaries",
        allowed_next_actions=[
            "Use buddybox.read for one active buddy private local file.",
            "Use buddybox.write to create or replace one active buddy private local file.",
        ],
        allowed_next_action_options=_list_options(),
        extra={"files": files},
    )


def read_buddybox_for_active_buddy(*, args: dict[str, Any], context: BuddyboxServiceContext) -> dict[str, Any]:
    action = "buddybox.read"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    try:
        normalized = normalize_active_buddybox_path(args.get("path"), active_buddy=active_buddy)
    except ValueError as exc:
        return _reject_scope(action=action, active_buddy=active_buddy, boundary="buddybox.path", message=str(exc))

    resolved = _resolve_path(normalized)
    if not _resolved_path_stays_in_active_root(resolved, active_buddy=active_buddy):
        if resolved.exists():
            return _reject_scope(
                action=action,
                active_buddy=active_buddy,
                boundary="buddybox.path",
                message="path resolves outside the active buddy private local root",
            )
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"buddybox file not found: {normalized}")
    if not resolved.exists() or not resolved.is_file():
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"buddybox file not found: {normalized}")

    preferred = args.get("encoding")
    encoding = "auto"
    if isinstance(preferred, str) and preferred.strip():
        encoding = preferred.strip().lower()
        if encoding not in {"auto", "utf-8", "base64"}:
            return _reject_payload(action=action, active_buddy=active_buddy, message="encoding must be auto, utf-8, or base64")

    raw = resolved.read_bytes()
    payload: dict[str, Any] = {
        "buddy": active_buddy,
        "path": normalized,
        "size_bytes": len(raw),
        "content_type": mimetypes.guess_type(resolved.name)[0] or "application/octet-stream",
        "private_to_buddy": active_buddy,
    }

    if encoding == "base64":
        payload["encoding"] = "base64"
        payload["content_base64"] = base64.b64encode(raw).decode("ascii")
    else:
        try:
            payload["content"] = raw.decode("utf-8")
            payload["encoding"] = "utf-8"
        except UnicodeDecodeError:
            payload["encoding"] = "base64"
            payload["content_base64"] = base64.b64encode(raw).decode("ascii")

    return tool_responses.success(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        effect_summary=(
            f"Read one active-buddy private local file '{normalized}'. "
            "No artifact/handoff/task/track/context/evidence state changed."
        ),
        state_changed=False,
        durability="none",
        read_scope="one active-buddy private local file content",
        allowed_next_actions=[
            "Use buddybox.write to replace this private local file.",
            "When cross-buddy readability is needed, create an artifact with readable content.",
        ],
        allowed_next_action_options=_read_options(),
        extra=payload,
    )


def write_buddybox_for_active_buddy(*, args: dict[str, Any], context: BuddyboxServiceContext) -> dict[str, Any]:
    action = "buddybox.write"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    try:
        normalized = normalize_active_buddybox_path(args.get("path"), active_buddy=active_buddy)
    except ValueError as exc:
        return _reject_scope(action=action, active_buddy=active_buddy, boundary="buddybox.path", message=str(exc))

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
    env_store.ensure_runtime_dirs()
    if not _write_parent_stays_in_active_root(resolved, active_buddy=active_buddy):
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            boundary="buddybox.path",
            message="path parent resolves outside the active buddy private local root",
        )
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
        "buddy": active_buddy,
        "path": normalized,
        "size_bytes": len(raw),
        "content_type": content_type,
        "private_to_buddy": active_buddy,
        "overwrote": existed,
    }
    change_word = "overwrote" if existed else "created"
    return tool_responses.success(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        effect_summary=(
            f"{change_word.capitalize()} one active-buddy private local file '{normalized}'. "
            "No artifact/handoff/task/track/context/evidence state changed."
        ),
        state_changed=True,
        durability="durable",
        created_ids=[normalized] if not existed else None,
        updated_ids=[normalized] if existed else None,
        allowed_next_actions=[
            "Use buddybox.read to confirm this private local file.",
            "Keep iterating locally, or create an artifact when host decides readable promotion is needed.",
        ],
        allowed_next_action_options=_write_options(),
        extra=payload,
    )


def delete_buddybox_for_active_buddy(*, args: dict[str, Any], context: BuddyboxServiceContext) -> dict[str, Any]:
    action = "buddybox.delete"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    try:
        normalized = normalize_active_buddybox_path(args.get("path"), active_buddy=active_buddy)
    except ValueError as exc:
        return _reject_scope(action=action, active_buddy=active_buddy, boundary="buddybox.path", message=str(exc))

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
        effect_summary=(
            f"Deleted active-buddy private local file '{normalized}'."
            if deleted
            else f"Active-buddy private local file '{normalized}' was already absent."
        )
        + " No artifact/handoff/task/track/context/evidence state changed.",
        state_changed=deleted,
        durability="durable" if deleted else "none",
        updated_ids=[normalized] if deleted else None,
        allowed_next_actions=[
            "Use buddybox.list to inspect remaining private local summaries.",
            "Use buddybox.write to create a replacement private local file if needed.",
        ],
        allowed_next_action_options=_delete_options(),
        extra={"path": normalized, "deleted": deleted, "private_to_buddy": active_buddy},
    )
