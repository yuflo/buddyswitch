#!/usr/bin/env python3
"""Current runtime context service for broker-routed env.tool operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

import env_store
from env.services import bindings

_IDENTITY_FIELDS = {"active_buddy", "buddy", "instance_id"}
_GET_FIELDS = {"context"} | _IDENTITY_FIELDS


class ContextServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


def _error_payload(
    *,
    action: str,
    active_buddy: str,
    code: str,
    message: str,
    permission_boundary: str,
    allowed_next_actions: list[str],
) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": "context",
        "action": action,
        "error": {
            "code": code,
            "message": message,
        },
        "permission_boundary": permission_boundary,
        "active_buddy": active_buddy,
        "allowed_next_actions": allowed_next_actions,
    }


def _payload_error(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_CONTEXT_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        allowed_next_actions=[
            'Fix the env.tool envelope fields (`tool`, `action`, `args`) and retry.',
            "Use context.list_sources to inspect available context sections.",
        ],
    )


def _context_boundary_error(
    *,
    action: str,
    active_buddy: str,
    code: str = "E_CONTEXT_SCOPE",
    message: str,
    permission_boundary: str,
) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code=code,
        message=message,
        permission_boundary=permission_boundary,
        allowed_next_actions=[
            "Rerun prepare in the active launcher-managed instance.",
            "Use the refreshed context returned by prepare for the next action.",
        ],
    )


def _ensure_allowed_fields(
    *,
    action: str,
    active_buddy: str,
    args: dict[str, Any],
    allowed_fields: set[str],
) -> dict[str, Any] | None:
    unknown = sorted(key for key in args.keys() if key not in allowed_fields)
    if not unknown:
        return None
    return _payload_error(
        action=action,
        active_buddy=active_buddy,
        message=f"unsupported payload fields: {', '.join(unknown)}",
    )


def _derive_context_sequence(task: dict[str, Any]) -> int:
    run_ids = task.get("run_ids")
    if isinstance(run_ids, list):
        return len(run_ids) + 1
    return 1


def _derive_context_revision(task: dict[str, Any], sequence: int) -> str:
    task_id = task.get("id")
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("task.id is required to derive context revision")
    return f"ctx-{task_id}-turn-{sequence}"


def _summarize_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": artifact.get("id"),
        "kind": artifact.get("kind"),
        "title": artifact.get("title"),
        "summary": artifact.get("summary", ""),
        "buddy": artifact.get("buddy"),
        "task_id": artifact.get("task_id"),
        "source_run_id": artifact.get("source_run_id"),
        "updated_at": artifact.get("updated_at"),
    }


def context_sources_desc() -> dict[str, str]:
    return {
        "request_text": "Original user request for this turn.",
        "task_context.task": "Current task metadata and summary.",
        "task_context.artifacts": "Full prior artifact content for the current task when available.",
        "track_context.track": "Current track title, status, buddies, and summary when bound.",
        "track_context.recent_handoffs": "Recent handoff reason and context.",
        "current_context_summary": "Compact scan-friendly summary; use full task_context artifacts when content detail is needed.",
    }


def build_task_context(task: dict[str, Any] | None) -> dict[str, Any]:
    if not task:
        return {
            "task": None,
            "artifacts": [],
            "recent_runs": [],
        }

    artifact_map = {artifact["id"]: artifact for artifact in env_store.list_artifacts()}
    artifacts = [artifact_map[item] for item in task.get("artifact_ids", []) if item in artifact_map]
    artifacts.sort(key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
    return {
        "task": {
            "id": task["id"],
            "buddy": task["buddy"],
            "status": task["status"],
            "summary": task.get("summary", ""),
            "track_id": task.get("track_id"),
            "latest_run_id": task.get("latest_run_id"),
            "artifact_slots": task.get("artifact_slots", {}),
        },
        "artifacts": artifacts[:5],
        "recent_runs": scan_task_recent_runs(task["id"], limit=3),
    }


def build_track_context(track_id: str | None) -> dict[str, Any] | None:
    if not track_id:
        return None
    track = env_store.get_track(track_id)
    if track is None:
        return None

    rows: list[dict[str, Any]] = []
    for task_id in track.get("task_ids", []):
        task = env_store.get_task(task_id)
        if task is None:
            continue
        current_artifacts: dict[str, dict[str, Any]] = {}
        artifact_slots = task.get("artifact_slots", {})
        if isinstance(artifact_slots, dict):
            for kind, row in artifact_slots.items():
                if not isinstance(row, dict):
                    continue
                artifact_id = row.get("current_artifact_id")
                if not isinstance(artifact_id, str) or not artifact_id:
                    continue
                artifact = env_store.get_artifact(artifact_id)
                if artifact is not None:
                    current_artifacts[kind] = artifact
        rows.append(
            {
                "task_id": task["id"],
                "buddy": task["buddy"],
                "status": task["status"],
                "summary": task.get("summary", ""),
                "current_artifacts": current_artifacts,
            }
        )

    return {
        "track": {
            "id": track["id"],
            "title": track["title"],
            "status": track["status"],
            "current_buddy": track["current_buddy"],
            "next_buddy": track.get("next_buddy"),
            "summary": track.get("summary", ""),
        },
        "tasks": rows,
        "recent_handoffs": scan_track_recent_handoffs(track["id"], limit=5),
    }


def scan_track_recent_handoffs(track_id: str, *, limit: int = 5) -> list[dict[str, Any]]:
    run_root = env_store.RUN_CONTENT_DIR
    if not run_root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in run_root.glob("*.json"):
        if path.name == ".gitkeep":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict):
            continue
        payload_track_id = payload.get("track_id")
        if not isinstance(payload_track_id, str) or payload_track_id != track_id:
            continue
        handoff = payload.get("handoff")
        if not isinstance(handoff, dict):
            continue
        next_buddy = handoff.get("next_buddy")
        reason = handoff.get("reason")
        context = handoff.get("context")
        if not isinstance(next_buddy, str) or not next_buddy.strip():
            continue
        if not isinstance(reason, str) or not reason.strip():
            continue
        if not isinstance(context, str) or not context.strip():
            continue
        rows.append(
            {
                "run_id": payload.get("run_id", path.stem),
                "task_id": payload.get("task_id"),
                "buddy_id": payload.get("buddy_id"),
                "next_buddy": next_buddy.strip(),
                "reason": reason.strip(),
                "context": context.strip(),
                "timestamp": payload.get("timestamp"),
            }
        )
    rows.sort(key=lambda row: (row.get("timestamp") or "", row.get("run_id") or ""), reverse=True)
    return rows[:limit]


def scan_task_recent_runs(task_id: str, *, limit: int = 3) -> list[dict[str, Any]]:
    run_root = env_store.RUN_CONTENT_DIR
    if not run_root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in run_root.glob("*.json"):
        if path.name == ".gitkeep":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("task_id") != task_id:
            continue
        run_id = payload.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            run_id = path.stem
        rows.append(
            {
                "run_id": run_id,
                "buddy_id": payload.get("buddy_id"),
                "execution_summary": payload.get("execution_summary"),
                "timestamp": payload.get("timestamp"),
            }
        )
    rows.sort(key=lambda row: (row.get("timestamp") or "", row.get("run_id") or ""), reverse=True)
    return rows[:limit]


def summarize_current_context(
    *,
    task_context: dict[str, Any],
    track_context: dict[str, Any] | None,
) -> dict[str, Any]:
    task_payload = task_context.get("task")
    if isinstance(task_payload, dict):
        summarized_task: dict[str, Any] | None = {
            "id": task_payload.get("id"),
            "buddy": task_payload.get("buddy"),
            "status": task_payload.get("status"),
            "summary": task_payload.get("summary", ""),
            "track_id": task_payload.get("track_id"),
            "latest_run_id": task_payload.get("latest_run_id"),
        }
    else:
        summarized_task = None

    track_payload = track_context.get("track") if isinstance(track_context, dict) else None
    if isinstance(track_payload, dict):
        summarized_track: dict[str, Any] | None = {
            "id": track_payload.get("id"),
            "title": track_payload.get("title"),
            "status": track_payload.get("status"),
            "current_buddy": track_payload.get("current_buddy"),
            "next_buddy": track_payload.get("next_buddy"),
            "summary": track_payload.get("summary", ""),
        }
    else:
        summarized_track = None

    summarized_artifacts: list[dict[str, Any]] = []
    task_artifacts = task_context.get("artifacts")
    if isinstance(task_artifacts, list):
        for artifact in task_artifacts:
            if isinstance(artifact, dict):
                summarized_artifacts.append(_summarize_artifact(artifact))

    summarized_handoffs: list[dict[str, Any]] = []
    handoff_rows = track_context.get("recent_handoffs") if isinstance(track_context, dict) else None
    if isinstance(handoff_rows, list):
        for row in handoff_rows:
            if not isinstance(row, dict):
                continue
            summarized_handoffs.append(
                {
                    "run_id": row.get("run_id"),
                    "task_id": row.get("task_id"),
                    "buddy_id": row.get("buddy_id"),
                    "next_buddy": row.get("next_buddy"),
                    "reason": row.get("reason"),
                    "context": row.get("context"),
                    "timestamp": row.get("timestamp"),
                }
            )

    return {
        "task": summarized_task,
        "track": summarized_track,
        "artifacts": summarized_artifacts,
        "recent_handoffs": summarized_handoffs,
    }


def current_context_sections(context: ContextServiceContext) -> dict[str, Any]:
    binding = bindings.current_binding(
        {
            "active_buddy": context["active_buddy"],
            "instance_id": context["instance_id"],
            "instance_json": context["instance_json"],
            "instance_payload": context["instance_payload"],
            "manifest": context["manifest"],
        }
    )
    task_id = binding.get("current_task_id")
    task = env_store.get_task(task_id.strip()) if isinstance(task_id, str) and task_id.strip() else None
    task_context = build_task_context(task)
    track_id = binding.get("current_track_id")
    if not isinstance(track_id, str) or not track_id.strip():
        track_id = task.get("track_id") if isinstance(task, dict) else None
    track_context = build_track_context(track_id if isinstance(track_id, str) else None)
    return {
        "current_binding": binding,
        "task_context": task_context,
        "track_context": track_context,
        "context_sources_desc": context_sources_desc(),
        "current_context_summary": summarize_current_context(
            task_context=task_context,
            track_context=track_context,
        ),
    }


def _validate_context_payload(
    *,
    action: str,
    args_context: dict[str, Any],
    context: ContextServiceContext,
) -> dict[str, Any] | None:
    if args_context.get("ok") is not True:
        return _context_boundary_error(
            action=action,
            active_buddy=context["active_buddy"],
            code="E_CONTEXT_SCOPE",
            message="context must be a successful prepare payload",
            permission_boundary="prepare.context_revision",
        )
    if args_context.get("instance_id") != context["instance_id"]:
        return _context_boundary_error(
            action=action,
            active_buddy=context["active_buddy"],
            message="context instance_id does not match active instance",
            permission_boundary="active-instance",
        )
    if args_context.get("active_buddy") != context["active_buddy"]:
        return _context_boundary_error(
            action=action,
            active_buddy=context["active_buddy"],
            message="context active_buddy does not match active buddy",
            permission_boundary="active-buddy",
        )

    payload_task_id = args_context.get("current_task_id")
    if not isinstance(payload_task_id, str) or not payload_task_id.strip():
        return _context_boundary_error(
            action=action,
            active_buddy=context["active_buddy"],
            message="context current_task_id is required",
            permission_boundary="prepare.context_revision",
        )
    task_id = payload_task_id.strip()
    try:
        env_store.require_id(task_id, "task id")
    except ValueError as exc:
        return _payload_error(action=action, active_buddy=context["active_buddy"], message=str(exc))

    bound_task_id = context["instance_payload"].get("current_task_id")
    if isinstance(bound_task_id, str) and bound_task_id.strip() and bound_task_id.strip() != task_id:
        return _context_boundary_error(
            action=action,
            active_buddy=context["active_buddy"],
            message="context current_task_id does not match active instance binding",
            permission_boundary="active-instance",
        )

    payload_track_id = args_context.get("current_track_id")
    bound_track_id = context["instance_payload"].get("current_track_id")
    if isinstance(bound_track_id, str) and bound_track_id.strip():
        if payload_track_id != bound_track_id.strip():
            return _context_boundary_error(
                action=action,
                active_buddy=context["active_buddy"],
                message="context current_track_id does not match active instance binding",
                permission_boundary="active-instance",
            )

    task = env_store.get_task(task_id)
    if task is None:
        return _context_boundary_error(
            action=action,
            active_buddy=context["active_buddy"],
            code="E_CONTEXT_TASK_NOT_FOUND",
            message=f"context task not found: {task_id}",
            permission_boundary="prepare.context_revision",
        )

    expected_sequence = _derive_context_sequence(task)
    expected_revision = _derive_context_revision(task, expected_sequence)
    context_revision = args_context.get("context_revision")
    if context_revision != expected_revision:
        return _context_boundary_error(
            action=action,
            active_buddy=context["active_buddy"],
            code="E_CONTEXT_REVISION",
            message=f"context_revision mismatch: expected '{expected_revision}', received '{context_revision}'",
            permission_boundary="prepare.context_revision",
        )
    run_envelope = args_context.get("run_envelope")
    sequence = run_envelope.get("sequence") if isinstance(run_envelope, dict) else None
    if isinstance(sequence, int) and sequence != expected_sequence:
        return _context_boundary_error(
            action=action,
            active_buddy=context["active_buddy"],
            code="E_CONTEXT_REVISION",
            message=f"context sequence mismatch: expected {expected_sequence}, received {sequence}",
            permission_boundary="prepare.context_revision",
        )
    turn_identity = run_envelope.get("turn_identity") if isinstance(run_envelope, dict) else None
    if isinstance(turn_identity, dict):
        if turn_identity.get("instance_id") != context["instance_id"]:
            return _context_boundary_error(
                action=action,
                active_buddy=context["active_buddy"],
                message="context turn_identity instance_id does not match active instance",
                permission_boundary="active-instance",
            )
        if turn_identity.get("active_buddy") != context["active_buddy"]:
            return _context_boundary_error(
                action=action,
                active_buddy=context["active_buddy"],
                message="context turn_identity active_buddy does not match active buddy",
                permission_boundary="active-buddy",
            )
        if turn_identity.get("task_id") != task_id:
            return _context_boundary_error(
                action=action,
                active_buddy=context["active_buddy"],
                message="context turn_identity task_id does not match current task",
                permission_boundary="prepare.context_revision",
            )
    return None


def get_context(*, args: dict[str, Any], context: ContextServiceContext) -> dict[str, Any]:
    action = "context.get"
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_GET_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    supplied_context = args.get("context")
    if supplied_context is not None:
        if not isinstance(supplied_context, dict):
            return _payload_error(
                action=action,
                active_buddy=context["active_buddy"],
                message="context must be an object when provided",
            )
        validation_error = _validate_context_payload(
            action=action,
            args_context=supplied_context,
            context=context,
        )
        if validation_error is not None:
            return validation_error

    sections = current_context_sections(context)
    return {
        "ok": True,
        "tool": "context",
        "action": action,
        "active_buddy": context["active_buddy"],
        **sections,
        "allowed_next_actions": [
            "Use context.summarize for compact scan-friendly context.",
            "Use task, track, or artifact tools for permitted state operations.",
        ],
    }


def summarize_context(*, args: dict[str, Any], context: ContextServiceContext) -> dict[str, Any]:
    action = "context.summarize"
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_IDENTITY_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    sections = current_context_sections(context)
    return {
        "ok": True,
        "tool": "context",
        "action": action,
        "active_buddy": context["active_buddy"],
        "current_binding": sections["current_binding"],
        "current_context_summary": sections["current_context_summary"],
        "allowed_next_actions": [
            "Use context.get when full task artifacts or track rows are needed.",
            "Use context.list_sources to inspect available section names.",
        ],
    }


def list_sources(*, args: dict[str, Any], context: ContextServiceContext) -> dict[str, Any]:
    action = "context.list_sources"
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_IDENTITY_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    return {
        "ok": True,
        "tool": "context",
        "action": action,
        "active_buddy": context["active_buddy"],
        "sources": context_sources_desc(),
        "allowed_next_actions": [
            "Use context.get to read full current context.",
            "Use context.summarize for compact context.",
        ],
    }
