#!/usr/bin/env python3
"""Task TUI launcher input wrapper."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.domain import task_management, task_tui  # noqa: E402


class TaskTuiInputWrapperError(RuntimeError):
    """Raised when Task TUI launcher input cannot be composed."""


def _load_instance_payload(instance_json: Path) -> dict[str, Any]:
    if not instance_json.exists():
        raise TaskTuiInputWrapperError(f"instance JSON does not exist: {instance_json}")
    try:
        payload = json.loads(instance_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TaskTuiInputWrapperError(f"invalid instance JSON: {instance_json}") from exc
    if not isinstance(payload, dict):
        raise TaskTuiInputWrapperError(f"instance JSON must contain an object: {instance_json}")
    return payload


def compose(*, raw_text: str, instance_json: Path) -> str:
    payload = _load_instance_payload(instance_json)
    role = payload.get("role")
    actor_id = payload.get("actor_id")
    if not isinstance(role, str) or not role.strip():
        raise TaskTuiInputWrapperError("instance JSON is missing role")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise TaskTuiInputWrapperError("instance JSON is missing actor_id")
    view = task_management.current_view(
        active_actor={"actor_id": actor_id.strip(), "role_id": role.strip()},
        active_role=role.strip(),
        instance_json=instance_json,
        instance_payload=payload,
    )
    tui = task_tui.render_task_tui(view)
    return f"{tui}\n\n[USER INPUT]\n{raw_text}"
