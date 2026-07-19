"""Launcher-side ingress helpers for Task Sys."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any, Mapping


HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _ensure_state_root_env() -> None:
    if os.environ.get("BUDDYSWITCH_STATE_ROOT"):
        return
    shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
    if isinstance(shared_root, str) and shared_root.strip():
        os.environ["BUDDYSWITCH_STATE_ROOT"] = str(Path(shared_root.strip()).expanduser().resolve(strict=False) / "state")


_ensure_state_root_env()

from env.domain import task_sys  # noqa: E402


def _require_text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _actor_target(*, actor_id: str, role_id: str) -> dict[str, str]:
    return {
        "actor_id": _require_text(actor_id, "actor_id"),
        "role_id": _require_text(role_id, "role_id"),
    }


def _result_payload(result: Mapping[str, Any], *, actor_id: str, role_id: str) -> dict[str, Any]:
    instruction = result.get("instruction")
    instruction_type = instruction.get("type") if isinstance(instruction, Mapping) else None
    payload: dict[str, Any] = {
        "ok": bool(result.get("ok")),
        "actor_id": actor_id,
        "role_id": role_id,
        "action": "task_created",
        "task_id": result.get("task_id"),
        "instruction_type": instruction_type,
        "instruction": dict(instruction) if isinstance(instruction, Mapping) else None,
    }
    return payload


def ingest_track_comment(
    *,
    actor_id: str,
    role_id: str,
    track_id: str,
    comment_id: str,
    thread_id: str,
    source_identity_id: str,
    source_role_id: str,
) -> dict[str, Any]:
    source_ref = {
        "track_id": _require_text(track_id, "track_id"),
        "comment_id": _require_text(comment_id, "comment_id"),
        "thread_id": _require_text(thread_id, "thread_id"),
    }
    envelope = {
        "source": {
            "type": "track.comment.added",
            "ref": source_ref,
        },
        "actor_target": _actor_target(actor_id=actor_id, role_id=role_id),
        "context": {
            **source_ref,
            "source_identity_id": _require_text(source_identity_id, "source_identity_id"),
            "source_role_id": _require_text(source_role_id, "source_role_id"),
        },
    }
    return _result_payload(
        task_sys.ingest(envelope),
        actor_id=actor_id,
        role_id=role_id,
    )
