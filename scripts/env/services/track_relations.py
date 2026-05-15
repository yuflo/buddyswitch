#!/usr/bin/env python3
"""Relation helpers for runless track/task/artifact read surfaces."""

from __future__ import annotations

from typing import Any

import env_store


def artifacts_for_task(task_id: str) -> list[dict[str, Any]]:
    task = env_store.get_task(task_id)
    if not isinstance(task, dict):
        return []
    rows: list[dict[str, Any]] = []
    for artifact_id in task.get("artifact_ids", []):
        if not isinstance(artifact_id, str):
            continue
        artifact = env_store.get_artifact(artifact_id)
        if isinstance(artifact, dict):
            rows.append(artifact)
    rows.sort(key=lambda row: (str(row.get("updated_at") or ""), str(row.get("id") or "")), reverse=True)
    return rows


def artifact_track_association(artifact: dict[str, Any]) -> dict[str, Any] | None:
    task_id = artifact.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        return None
    task = env_store.get_task(task_id)
    if not isinstance(task, dict):
        return None
    track_id = task.get("track_id")
    if not isinstance(track_id, str) or not track_id:
        return {
            "task_id": task_id,
            "task": task,
            "track_id": None,
            "track": None,
        }
    track = env_store.get_track(track_id)
    if not isinstance(track, dict):
        return {
            "task_id": task_id,
            "task": task,
            "track_id": track_id,
            "track": None,
        }
    return {
        "task_id": task_id,
        "task": task,
        "track_id": track_id,
        "track": track,
    }


def _active_buddy_participates(track: dict[str, Any], active_buddy: str) -> bool:
    for task_id in track.get("task_ids", []):
        if not isinstance(task_id, str):
            continue
        task = env_store.get_task(task_id)
        if isinstance(task, dict) and task.get("buddy") == active_buddy and task.get("status") != "archived":
            return True
    return False


def artifact_read_decision(artifact: dict[str, Any], active_buddy: str) -> dict[str, Any]:
    artifact_id = artifact.get("id") if isinstance(artifact.get("id"), str) else None
    association = artifact_track_association(artifact)
    track_id = association.get("track_id") if isinstance(association, dict) else None
    source_task_id = association.get("task_id") if isinstance(association, dict) else None

    owner = artifact.get("buddy")
    if isinstance(owner, str) and owner == active_buddy:
        return {
            "allowed": True,
            "artifact_id": artifact_id,
            "track_id": track_id,
            "source_task_id": source_task_id,
            "relation": "owner",
            "permission_boundary": "none",
            "why": "active buddy owns source artifact",
            "missing_preconditions": [],
        }

    if not isinstance(association, dict):
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": None,
            "source_task_id": None,
            "relation": "none",
            "permission_boundary": "artifact.task_association",
            "why": "artifact is missing a readable task association",
            "missing_preconditions": ["artifact must reference a task"],
        }

    track = association.get("track")
    if not isinstance(track, dict):
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": track_id,
            "source_task_id": source_task_id,
            "relation": "none",
            "permission_boundary": "artifact.track_association",
            "why": "artifact task is not attached to a readable track",
            "missing_preconditions": ["artifact task must reference an existing track"],
        }

    if track.get("status") == "archived":
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": track_id,
            "source_task_id": source_task_id,
            "relation": "observer",
            "permission_boundary": "track.lifecycle_status",
            "why": "archived tracks do not grant cross-buddy reads",
            "missing_preconditions": ["track must not be archived"],
        }

    if not artifact.get("is_current"):
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": track_id,
            "source_task_id": source_task_id,
            "relation": "observer",
            "permission_boundary": "artifact.currentness",
            "why": "only current foreign artifacts are readable by relation",
            "missing_preconditions": ["artifact must be current"],
        }

    relation = "observer"
    if track.get("current_buddy") == active_buddy:
        relation = "current_buddy"
    elif track.get("next_buddy") == active_buddy:
        relation = "next_buddy"
    elif _active_buddy_participates(track, active_buddy):
        relation = "participant"

    if relation == "observer":
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": track_id,
            "source_task_id": source_task_id,
            "relation": relation,
            "permission_boundary": "artifact.track_relation",
            "why": "active buddy has no readable relation on source track",
            "missing_preconditions": ["active buddy must be participant/current/next on track"],
        }

    return {
        "allowed": True,
        "artifact_id": artifact_id,
        "track_id": track_id,
        "source_task_id": source_task_id,
        "relation": relation,
        "permission_boundary": "none",
        "why": "active buddy relation allows reading current source artifact",
        "missing_preconditions": [],
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

    is_current = bool(artifact.get("is_current"))
    return {
        "id": artifact.get("id"),
        "artifact_id": artifact.get("id"),
        "track_id": source_track.get("id") if isinstance(source_track, dict) else decision.get("track_id"),
        "relation": decision.get("relation"),
        "kind": artifact.get("kind"),
        "title": artifact.get("title"),
        "summary": artifact.get("summary", ""),
        "source_buddy": artifact.get("buddy"),
        "source_task_id": source_task.get("id") if isinstance(source_task, dict) else artifact.get("task_id"),
        "created_by": artifact.get("created_by"),
        "source_refs": artifact.get("source_refs"),
        "revision": artifact.get("revision"),
        "currentness": "current" if is_current else "superseded",
        "readable_by_current_buddy": bool(decision.get("allowed")),
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
        for slot in task.get("artifact_slots", {}).values():
            if not isinstance(slot, dict):
                continue
            artifact_id = slot.get("current_artifact_id")
            if not isinstance(artifact_id, str) or not artifact_id or artifact_id in seen:
                continue
            seen.add(artifact_id)
            artifact = env_store.get_artifact(artifact_id)
            if isinstance(artifact, dict):
                rows.append(artifact_summary_row(artifact, active_buddy, track=track, task=task))

    rows.sort(
        key=lambda row: (
            str(row.get("source_buddy") or ""),
            str(row.get("kind") or ""),
            str(row.get("artifact_id") or ""),
        )
    )
    return rows
