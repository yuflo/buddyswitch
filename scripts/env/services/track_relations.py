#!/usr/bin/env python3
"""Deterministic relation helpers for track/task/artifact read surfaces."""

from __future__ import annotations

import shlex
from typing import Any, TypedDict

import env_store


class TrackRelation(TypedDict):
    track_id: str | None
    active_buddy: str
    relation: str
    relations: dict[str, bool]


class ArtifactReadDecision(TypedDict):
    allowed: bool
    artifact_id: str | None
    track_id: str | None
    source_task_id: str | None
    relation: str
    permission_boundary: str
    why: str
    missing_preconditions: list[str]


def command_hint(tool: str, action: str, args: dict[str, Any] | None = None) -> str:
    op = action.replace("_", "-")
    parts = ["python3", "scripts/env/client.py", tool, op]
    if isinstance(args, dict):
        for key in sorted(args.keys()):
            value = args[key]
            if value is None:
                continue
            flag = f"--{key.replace('_', '-')}"
            if isinstance(value, bool):
                if value:
                    parts.append(flag)
                continue
            parts.append(flag)
            parts.append(shlex.quote(str(value)))
    return " ".join(parts)


def _latest_handoff_target(track_id: str) -> str | None:
    rows: list[tuple[str, str, str]] = []
    list_handoffs = getattr(env_store, "list_handoffs", None)
    if callable(list_handoffs):
        for row in list_handoffs():
            if not isinstance(row, dict):
                continue
            if row.get("track_id") != track_id:
                continue
            if row.get("status") != "active":
                continue
            target = row.get("target_buddy")
            if not isinstance(target, str) or not target.strip():
                continue
            timestamp = str(row.get("updated_at") or row.get("created_at") or "")
            rows.append((timestamp, str(row.get("id") or ""), target.strip()))

    if not rows:
        return None
    rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return rows[0][2]


def _active_buddy_participates(track: dict[str, Any], active_buddy: str) -> bool:
    for task_id in track.get("task_ids", []):
        if not isinstance(task_id, str) or not task_id:
            continue
        task = env_store.get_task(task_id)
        if not isinstance(task, dict):
            continue
        if task.get("buddy") != active_buddy:
            continue
        if task.get("status") == "archived":
            continue
        return True
    return False


def track_relation_for_buddy(track: dict[str, Any], active_buddy: str) -> TrackRelation:
    track_id = track.get("id") if isinstance(track.get("id"), str) else None
    relations = {
        "pm_lifecycle_owner": active_buddy == "pm",
        "participant": _active_buddy_participates(track, active_buddy),
        "current_buddy": track.get("current_buddy") == active_buddy,
        "next_buddy": track.get("next_buddy") == active_buddy,
        "handoff_recipient": isinstance(track_id, str) and _latest_handoff_target(track_id) == active_buddy,
    }
    relation = "none"
    for name in ("pm_lifecycle_owner", "participant", "current_buddy", "next_buddy", "handoff_recipient"):
        if relations[name]:
            relation = name
            break
    return {
        "track_id": track_id,
        "active_buddy": active_buddy,
        "relation": relation,
        "relations": relations,
    }


def artifact_track_association(artifact: dict[str, Any]) -> dict[str, Any] | None:
    task_id = artifact.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        return None
    task = env_store.get_task(task_id)
    if not isinstance(task, dict):
        return None
    track_id = task.get("track_id")
    if not isinstance(track_id, str) or not track_id:
        return None
    track = env_store.get_track(track_id)
    if not isinstance(track, dict):
        return None
    if task_id not in track.get("task_ids", []):
        return None
    return {
        "task_id": task_id,
        "task": task,
        "track_id": track_id,
        "track": track,
    }


def artifact_read_decision(artifact: dict[str, Any], active_buddy: str) -> ArtifactReadDecision:
    artifact_id = artifact.get("id") if isinstance(artifact.get("id"), str) else None
    association = artifact_track_association(artifact)
    source_task_id: str | None = None
    track_id: str | None = None
    if isinstance(association, dict):
        source_task_id = association["task_id"]
        track_id = association["track_id"]
    owner_buddy = artifact.get("buddy")
    if isinstance(owner_buddy, str) and owner_buddy == active_buddy:
        return {
            "allowed": True,
            "artifact_id": artifact_id,
            "track_id": track_id,
            "source_task_id": source_task_id,
            "relation": "owner",
            "permission_boundary": "none",
            "why": "active buddy owns source task artifact",
            "missing_preconditions": [],
        }
    if association is None:
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": track_id,
            "source_task_id": source_task_id,
            "relation": "none",
            "permission_boundary": "artifact.track_association",
            "why": "artifact is missing task-track association",
            "missing_preconditions": ["source artifact must reference a task linked to an existing track"],
        }

    track = association["track"]
    relation = track_relation_for_buddy(track, active_buddy)
    detected_relation = relation["relation"]
    if track.get("status") == "archived":
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": association["track_id"],
            "source_task_id": association["task_id"],
            "relation": detected_relation,
            "permission_boundary": "track.lifecycle_status",
            "why": "archived tracks do not grant cross-buddy artifact reads",
            "missing_preconditions": ["track must not be archived for relation-based artifact reads"],
        }
    if not bool(artifact.get("is_current")):
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": association["track_id"],
            "source_task_id": association["task_id"],
            "relation": detected_relation,
            "permission_boundary": "artifact.currentness",
            "why": "foreign historical artifact read is outside relation scope",
            "missing_preconditions": ["artifact must be current unless active buddy owns the artifact"],
        }
    if detected_relation == "none":
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": association["track_id"],
            "source_task_id": association["task_id"],
            "relation": "none",
            "permission_boundary": "artifact.track_relation",
            "why": "active buddy has no readable relation on source artifact track",
            "missing_preconditions": [
                "active buddy must be pm, participant, current_buddy, next_buddy, or latest handoff recipient",
            ],
        }
    return {
        "allowed": True,
        "artifact_id": artifact_id,
        "track_id": association["track_id"],
        "source_task_id": association["task_id"],
        "relation": detected_relation,
        "permission_boundary": "none",
        "why": "active buddy relation allows reading current source artifact",
        "missing_preconditions": [],
    }


def _summary_next_action(*, decision: ArtifactReadDecision) -> dict[str, Any]:
    artifact_id = decision.get("artifact_id")
    track_id = decision.get("track_id")
    if decision["allowed"] and isinstance(artifact_id, str):
        return {
            "tool": "artifact",
            "action": "get",
            "args": {"artifact_id": artifact_id},
            "command_hint": command_hint("artifact", "get", {"artifact_id": artifact_id}),
        }
    if isinstance(track_id, str):
        return {
            "tool": "track",
            "action": "join",
            "args": {"track_id": track_id},
            "command_hint": command_hint("track", "join", {"track_id": track_id}),
        }
    source_task_id = decision.get("source_task_id")
    return {
        "tool": "task",
        "action": "get",
        "args": {"task_id": source_task_id},
        "command_hint": command_hint("task", "get", {"task_id": source_task_id}),
    }


def artifact_summary_row(
    artifact: dict[str, Any],
    active_buddy: str,
    *,
    track: dict[str, Any] | None = None,
    task: dict[str, Any] | None = None,
) -> dict[str, Any]:
    decision = artifact_read_decision(artifact, active_buddy)
    source_task = task
    if not isinstance(source_task, dict):
        task_id = artifact.get("task_id")
        source_task = env_store.get_task(task_id) if isinstance(task_id, str) else None
    source_track = track
    if not isinstance(source_track, dict) and isinstance(source_task, dict):
        track_id = source_task.get("track_id")
        source_track = env_store.get_track(track_id) if isinstance(track_id, str) else None
    source_task_id = source_task.get("id") if isinstance(source_task, dict) else artifact.get("task_id")
    source_track_id = source_track.get("id") if isinstance(source_track, dict) else decision.get("track_id")
    is_current = bool(artifact.get("is_current"))
    next_action = _summary_next_action(decision=decision)
    return {
        "id": artifact.get("id"),
        "artifact_id": artifact.get("id"),
        "track_id": source_track_id,
        "relation": decision.get("relation"),
        "kind": artifact.get("kind"),
        "title": artifact.get("title"),
        "summary": artifact.get("summary", ""),
        "source_buddy": artifact.get("buddy"),
        "source_task_id": source_task_id,
        "source_run_id": artifact.get("source_run_id"),
        "source_run": artifact.get("source_run_id"),
        "revision": artifact.get("revision"),
        "currentness": "current" if is_current else "superseded",
        "readable_by_current_buddy": bool(decision.get("allowed")),
        "next_action": next_action,
        "command_hint": str(next_action.get("command_hint") or ""),
    }


def current_artifact_rows_for_track(track_id: str, active_buddy: str) -> list[dict[str, Any]]:
    track = env_store.get_track(track_id)
    if not isinstance(track, dict):
        return []
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for task_id in track.get("task_ids", []):
        if not isinstance(task_id, str) or not task_id:
            continue
        task = env_store.get_task(task_id)
        if not isinstance(task, dict):
            continue
        artifact_slots = task.get("artifact_slots")
        if not isinstance(artifact_slots, dict):
            continue
        for slot in artifact_slots.values():
            if not isinstance(slot, dict):
                continue
            artifact_id = slot.get("current_artifact_id")
            if not isinstance(artifact_id, str) or not artifact_id:
                continue
            if artifact_id in seen:
                continue
            seen.add(artifact_id)
            artifact = env_store.get_artifact(artifact_id)
            if not isinstance(artifact, dict):
                continue
            rows.append(artifact_summary_row(artifact, active_buddy, track=track, task=task))
    rows.sort(
        key=lambda row: (
            str(row.get("source_buddy") or ""),
            str(row.get("kind") or ""),
            str(row.get("artifact_id") or ""),
        )
    )
    return rows
