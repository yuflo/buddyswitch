"""Concrete runtime file helpers for env repositories."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping


RUNTIME_WORKSPACE_AGENTS_HEADER = "# BuddySwitch Runtime Workspace"
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

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
    global WORKSPACE_ROOT
    global STATE_ROOT
    global OBJECTS_ROOT
    global TRACKS_DIR
    global ARTIFACT_OBJECTS_DIR
    global ARTIFACT_ATTACHMENTS_DIR
    global MESSAGES_DIR
    global TRACK_COMMENTS_DIR
    global CONTENT_ROOT
    global LOCAL_ROOT
    global ACTOR_PRIVATE_DIR

    ROOT = _default_repo_root()
    STATE_ROOT = _runtime_root_from_env(ROOT)
    WORKSPACE_ROOT = ROOT

    OBJECTS_ROOT = STATE_ROOT / "buddyswitch" / "objects"
    TRACKS_DIR = OBJECTS_ROOT / "tracks"
    ARTIFACT_OBJECTS_DIR = OBJECTS_ROOT / "artifacts"
    ARTIFACT_ATTACHMENTS_DIR = OBJECTS_ROOT / "artifact-attachments"
    MESSAGES_DIR = OBJECTS_ROOT / "messages"
    TRACK_COMMENTS_DIR = OBJECTS_ROOT / "track-comments"
    CONTENT_ROOT = STATE_ROOT / "buddyswitch" / "content"
    LOCAL_ROOT = STATE_ROOT / "buddyswitch" / "local"
    ACTOR_PRIVATE_DIR = runtime_workspace_root(None) / "private"
    for listener in _RUNTIME_ROOT_LISTENERS:
        listener()


def refresh_runtime_roots_from_env() -> None:
    _recompute_runtime_roots()


def register_runtime_root_listener(listener: Callable[[], None], *, call_immediately: bool = False) -> None:
    if listener not in _RUNTIME_ROOT_LISTENERS:
        _RUNTIME_ROOT_LISTENERS.append(listener)
    if call_immediately:
        listener()


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


def actor_private_dir(instance_payload: dict[str, Any] | None = None) -> Path:
    return runtime_workspace_root(instance_payload) / "private"


def instance_tmp_dir(instance_payload: dict[str, Any] | None = None) -> Path:
    if isinstance(instance_payload, Mapping):
        return instance_root_from_context(
            instance_json=None,
            instance_payload=instance_payload,
        ) / "tmp"
    raw_root = os.environ.get("BUDDYSWITCH_INSTANCE_ROOT")
    if isinstance(raw_root, str) and raw_root.strip():
        return Path(raw_root.strip()).expanduser().resolve(strict=False) / "tmp"
    raise ValueError("instance context is required for instance tmp access")


def instance_root_from_context(
    *,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> Path:
    if instance_payload is not None:
        raw_root = instance_payload.get("instance_root")
        if isinstance(raw_root, str) and raw_root.strip():
            return Path(raw_root.strip()).expanduser().resolve(strict=False)
    if instance_json is not None:
        return Path(instance_json).expanduser().resolve(strict=False).parent
    raise ValueError("instance context is required for instance-root access")


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
    actor_id_raw = os.environ.get("BUDDYSWITCH_ACTOR_ID")

    if is_runtime_workspace(candidate):
        return
    if isinstance(actor_id_raw, str) and actor_id_raw.strip():
        if shared_state_root_is_bound():
            return
    raise ValueError(
        "BuddySwitch runtime writes are blocked in the source checkout. "
        "Start the launcher workspace with ./buddyswitch-codex instance start --role <role> and rerun there."
    )


def require_central_im_write_root(root: Path | None = None) -> None:
    candidate = ROOT if root is None else root
    if is_runtime_workspace(candidate):
        return
    if shared_state_root_is_bound():
        return
    raise ValueError(
        "BuddySwitch Central IM writes are blocked until BUDDYSWITCH_STATE_ROOT is bound to "
        "BUDDYSWITCH_SHARED_ROOT/state."
    )


def shared_state_root_is_bound() -> bool:
    shared_root_raw = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
    state_root_raw = os.environ.get("BUDDYSWITCH_STATE_ROOT")
    if not isinstance(shared_root_raw, str) or not shared_root_raw.strip():
        return False
    shared_root = Path(shared_root_raw.strip()).expanduser().resolve(strict=False)
    session_state_root = (
        Path(state_root_raw.strip()).expanduser().resolve(strict=False)
        if isinstance(state_root_raw, str) and state_root_raw.strip()
        else STATE_ROOT.resolve(strict=False)
    )
    return session_state_root == (shared_root / "state").resolve(strict=False)


def ensure_runtime_dirs() -> None:
    require_runtime_workspace_write_root()
    TRACKS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_OBJECTS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    MESSAGES_DIR.mkdir(parents=True, exist_ok=True)
    TRACK_COMMENTS_DIR.mkdir(parents=True, exist_ok=True)


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
