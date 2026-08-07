"""Canonical runtime paths, guards, and atomic JSON storage."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


RUNTIME_WORKSPACE_AGENTS_HEADER = "# BuddySwitch Runtime Workspace"
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _default_shared_root() -> Path:
    configured = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
    if isinstance(configured, str) and configured.strip():
        return Path(configured.strip()).expanduser().resolve(strict=False)
    source_home = os.environ.get("BUDDYSWITCH_SOURCE_HOME") or os.environ.get("HOME")
    if isinstance(source_home, str) and source_home.strip():
        return (
            Path(source_home.strip()).expanduser() / ".codex-buddyswitch"
        ).resolve(strict=False)
    return (Path.home() / ".codex-buddyswitch").resolve(strict=False)


def _runtime_root_from_env(default_root: Path) -> Path:
    raw = os.environ.get("BUDDYSWITCH_STATE_ROOT")
    if isinstance(raw, str) and raw.strip():
        return Path(raw.strip()).expanduser().resolve(strict=False)
    return default_root / "state"


def _recompute_runtime_roots() -> None:
    global ROOT
    global STATE_ROOT
    global OBJECTS_ROOT
    global LOCAL_ROOT

    ROOT = _default_shared_root()
    STATE_ROOT = _runtime_root_from_env(ROOT)
    OBJECTS_ROOT = STATE_ROOT / "buddyswitch" / "objects"
    LOCAL_ROOT = STATE_ROOT / "buddyswitch" / "local"


def refresh_runtime_roots_from_env() -> None:
    _recompute_runtime_roots()


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


def _display_path(path: Path) -> str:
    for candidate_root in (ROOT, STATE_ROOT):
        try:
            return path.relative_to(candidate_root).as_posix()
        except ValueError:
            continue
    return path.as_posix()


def _runtime_workspace_agents_file(root: Path | None = None) -> Path:
    return (ROOT if root is None else root) / "AGENTS.md"


def is_runtime_workspace(root: Path | None = None) -> bool:
    agents_path = _runtime_workspace_agents_file(root)
    try:
        first_line = agents_path.read_text(encoding="utf-8").splitlines()[0].strip()
    except (IndexError, OSError):
        return False
    return first_line == RUNTIME_WORKSPACE_AGENTS_HEADER


def _shared_state_root_is_bound() -> bool:
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


def require_runtime_workspace_write_root(root: Path | None = None) -> None:
    candidate = ROOT if root is None else root
    actor_id_raw = os.environ.get("BUDDYSWITCH_ACTOR_ID")

    if is_runtime_workspace(candidate):
        return
    if isinstance(actor_id_raw, str) and actor_id_raw.strip():
        if _shared_state_root_is_bound():
            return
    raise ValueError(
        "BuddySwitch runtime writes are blocked in the source checkout. "
        "Start the launcher workspace with ./buddyswitch-codex instance start --role <role> and rerun there."
    )


def require_central_im_write_root(root: Path | None = None) -> None:
    candidate = ROOT if root is None else root
    if is_runtime_workspace(candidate):
        return
    if _shared_state_root_is_bound():
        return
    raise ValueError(
        "BuddySwitch Central IM writes are blocked until BUDDYSWITCH_STATE_ROOT is bound to "
        "BUDDYSWITCH_SHARED_ROOT/state."
    )


def require_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not ID_PATTERN.match(value):
        raise ValueError(f"{label} must match /^[a-z0-9][a-z0-9-]*$/")
    return value


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {_display_path(path)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{_display_path(path)} must contain a JSON object")
    return payload


def write_json_object(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=True, indent=2) + os.linesep
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False, dir=path.parent
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(serialized)
        assert temp_path is not None
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


_recompute_runtime_roots()
