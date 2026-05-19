#!/usr/bin/env python3
"""Concrete runtime file helpers for env repositories."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


RUNTIME_WORKSPACE_AGENTS_HEADER = "# BuddySwitch Runtime Workspace"
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

_RUNTIME_ROOT_OVERRIDE: Path | None = None
_RUNTIME_ROOT_LISTENERS: list[Callable[[], None]] = []


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _runtime_root_from_env(default_root: Path) -> Path:
    raw = os.environ.get("BUDDYSWITCH_STATE_ROOT")
    if isinstance(raw, str) and raw.strip():
        return Path(raw.strip()).expanduser().resolve(strict=False)
    return default_root


def _recompute_runtime_roots() -> None:
    global ROOT
    global STATE_ROOT
    global OBJECTS_ROOT
    global TRACKS_DIR
    global TASKS_DIR
    global ARTIFACT_OBJECTS_DIR
    global MESSAGES_DIR
    global COMMENTS_DIR
    global CONTENT_ROOT
    global LOCAL_ROOT
    global BUDDYBOX_LOCAL_DIR

    if _RUNTIME_ROOT_OVERRIDE is None:
        ROOT = _default_repo_root()
        STATE_ROOT = _runtime_root_from_env(ROOT)
    else:
        ROOT = _RUNTIME_ROOT_OVERRIDE
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
    for listener in _RUNTIME_ROOT_LISTENERS:
        listener()


def register_runtime_root_listener(listener: Callable[[], None], *, call_immediately: bool = False) -> None:
    if listener not in _RUNTIME_ROOT_LISTENERS:
        _RUNTIME_ROOT_LISTENERS.append(listener)
    if call_immediately:
        listener()


def set_runtime_root_override(root: Path) -> Path:
    """Force runtime roots to a specific workspace path (test-only override)."""
    global _RUNTIME_ROOT_OVERRIDE
    _RUNTIME_ROOT_OVERRIDE = Path(root).expanduser().resolve(strict=False)
    _recompute_runtime_roots()
    return ROOT


def reset_runtime_root_override() -> None:
    global _RUNTIME_ROOT_OVERRIDE
    _RUNTIME_ROOT_OVERRIDE = None
    _recompute_runtime_roots()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def runtime_workspace_root(instance_payload: dict[str, Any] | None = None) -> Path:
    if isinstance(instance_payload, dict):
        candidate = instance_payload.get("workspace_dir")
        if isinstance(candidate, str) and candidate.strip():
            return Path(candidate.strip()).expanduser().resolve(strict=False)
    if _RUNTIME_ROOT_OVERRIDE is not None:
        return ROOT
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


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {rel(path)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{rel(path)} must contain a JSON object")
    return payload


def write_json_object(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=True, indent=2) + os.linesep
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as handle:
        handle.write(serialized)
        temp_name = handle.name
    os.replace(temp_name, path)


_recompute_runtime_roots()
