#!/usr/bin/env python3
"""Repository helpers for active-buddy private buddybox files."""

from __future__ import annotations

import mimetypes
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from . import runtime_files


class BuddyboxLogicalNameError(ValueError):
    """Raised when logical_name is invalid for active buddy scope."""


class BuddyboxBoundaryError(ValueError):
    """Raised when a request would escape active buddy private file boundary."""


def normalize_logical_name(value: Any, *, active_buddy: str, buddy_ids: set[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BuddyboxLogicalNameError("logical_name must be a non-empty string")
    normalized = value.replace("\\", "/").strip()
    if normalized.startswith("/"):
        raise BuddyboxLogicalNameError("logical_name must be relative")
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    if not parts:
        raise BuddyboxLogicalNameError("logical_name must be non-empty")
    if any(part == ".." for part in parts):
        raise BuddyboxLogicalNameError("logical_name must not include '..' traversal")
    if parts[0] in (set(buddy_ids) | {active_buddy}):
        raise BuddyboxLogicalNameError(
            "logical_name must be relative to the active buddy private file capability and must not include a buddy prefix"
        )
    return "/".join(parts)


def normalize_logical_prefix(value: Any, *, active_buddy: str, buddy_ids: set[str]) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise BuddyboxLogicalNameError("logical_name must be a string when provided")
    if not value.strip():
        return None
    return normalize_logical_name(value, active_buddy=active_buddy, buddy_ids=buddy_ids)


def active_buddy_root(*, active_buddy: str, instance_payload: dict[str, Any] | None = None) -> Path:
    return runtime_files.buddybox_local_dir(instance_payload) / active_buddy


def ensure_active_buddy_root(*, active_buddy: str, instance_payload: dict[str, Any] | None = None) -> Path:
    root = active_buddy_root(active_buddy=active_buddy, instance_payload=instance_payload)
    if root.exists() and root.is_symlink():
        raise BuddyboxBoundaryError("active buddy private file root cannot be a symlink")
    try:
        root.mkdir(parents=True, exist_ok=True)
    except FileExistsError as exc:
        raise BuddyboxBoundaryError("active buddy private file root must be a directory") from exc
    if root.is_symlink() or not root.is_dir():
        raise BuddyboxBoundaryError("active buddy private file root must be a directory")
    return root


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _resolved_path_within_any_root(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(_path_is_within(path, root.resolve(strict=False)) for root in roots)


def _resolved_existing_path_stays_in_root(path: Path, *, root: Path) -> bool:
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        return False
    return _path_is_within(resolved, root.resolve(strict=False))


def _resolved_write_parent_stays_in_root(path: Path, *, root: Path) -> bool:
    parent = path.parent.resolve(strict=False)
    return _path_is_within(parent, root.resolve(strict=False))


def _updated_at_from_stat(path: Path) -> str:
    stat = path.stat()
    return datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds")


def file_summary(path: Path, *, logical_name: str, active_buddy: str) -> dict[str, Any]:
    stat = path.stat()
    content_type, _ = mimetypes.guess_type(path.name)
    return {
        "logical_name": logical_name,
        "size_bytes": stat.st_size,
        "updated_at": _updated_at_from_stat(path),
        "content_type": content_type or "application/octet-stream",
        "visibility": "active_buddy_private",
        "private_to_buddy": active_buddy,
    }


def state_summary(*, root: Path) -> dict[str, Any]:
    file_count = 0
    total_bytes = 0
    latest_mtime: float | None = None
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if not _resolved_existing_path_stays_in_root(path, root=root):
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


def list_private_file_summaries(
    *,
    root: Path,
    active_buddy: str,
    recursive: bool,
    limit: int,
    logical_prefix: str | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    walker = root.rglob("*") if recursive else root.glob("*")
    for path in walker:
        if not path.is_file():
            continue
        if not _resolved_existing_path_stays_in_root(path, root=root):
            continue
        logical_name = path.relative_to(root).as_posix()
        if isinstance(logical_prefix, str) and not logical_name.startswith(logical_prefix):
            continue
        rows.append(file_summary(path, logical_name=logical_name, active_buddy=active_buddy))
    rows.sort(key=lambda row: (str(row.get("updated_at") or ""), str(row.get("logical_name") or "")), reverse=True)
    return rows[:limit]


def read_private_file(*, root: Path, logical_name: str) -> tuple[bytes, str]:
    path = root / logical_name
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(logical_name)
    if not _resolved_existing_path_stays_in_root(path, root=root):
        raise BuddyboxBoundaryError("logical_name resolves outside the active buddy private file root")
    raw = path.read_bytes()
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return raw, content_type


def write_private_file(*, root: Path, logical_name: str, content: bytes) -> tuple[bool, str]:
    path = root / logical_name
    if not _resolved_write_parent_stays_in_root(path, root=root):
        raise BuddyboxBoundaryError("logical_name parent resolves outside the active buddy private file root")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.is_dir():
        raise IsADirectoryError(logical_name)
    if path.exists() and not _resolved_existing_path_stays_in_root(path, root=root):
        raise BuddyboxBoundaryError("logical_name resolves outside the active buddy private file root")

    existed = path.exists() and path.is_file()
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=path.parent) as handle:
        handle.write(content)
        temp_name = handle.name
    os.replace(temp_name, path)
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return existed, content_type


def import_private_file(
    *,
    root: Path,
    logical_name: str,
    source_path: Path,
    allowed_roots: tuple[Path, ...],
    blocked_roots: tuple[Path, ...],
) -> tuple[bool, str, int]:
    try:
        resolved_source = source_path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError(str(source_path)) from exc

    if resolved_source.is_dir():
        raise IsADirectoryError(str(source_path))
    if not resolved_source.is_file():
        raise ValueError("source_path must resolve to an existing regular file")

    if not _resolved_path_within_any_root(resolved_source, allowed_roots):
        raise ValueError("source_path must stay inside one allowed local import root")
    if _resolved_path_within_any_root(resolved_source, blocked_roots):
        raise ValueError("source_path must not resolve inside runtime objects or runtime local storage")

    raw = resolved_source.read_bytes()
    existed, content_type = write_private_file(root=root, logical_name=logical_name, content=raw)
    return existed, content_type, len(raw)


def delete_private_file(*, root: Path, logical_name: str) -> bool:
    path = root / logical_name
    if path.exists() and path.is_dir():
        raise IsADirectoryError(logical_name)
    if path.exists() and not _resolved_existing_path_stays_in_root(path, root=root):
        raise BuddyboxBoundaryError("logical_name resolves outside the active buddy private file root")
    if path.exists() and path.is_file():
        path.unlink()
        return True
    return False
