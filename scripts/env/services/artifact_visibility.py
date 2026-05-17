#!/usr/bin/env python3
"""Shared artifact visibility and track readability helpers."""

from __future__ import annotations

from typing import Any

import env_store


def artifacts_for_task(task_id: str) -> list[dict[str, Any]]:
    task = env_store.get_task(task_id)
    if not isinstance(task, dict):
        return []
    rows: list[dict[str, Any]] = []
    for artifact_id in task.get("artifact_ids", []):
        if not isinstance(artifact_id, str) or not artifact_id:
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
    return {
        "task_id": task_id,
        "task": task,
        "track_id": track_id,
        "track": track if isinstance(track, dict) else None,
    }


def _has_active_task_relation(track: dict[str, Any], active_buddy: str) -> bool:
    for task_id in track.get("task_ids", []):
        if not isinstance(task_id, str) or not task_id:
            continue
        task = env_store.get_task(task_id)
        if not isinstance(task, dict):
            continue
        if task.get("buddy") != active_buddy:
            continue
        if task.get("status") == "active":
            return True
    return False


def artifact_read_decision(artifact: dict[str, Any], active_buddy: str) -> dict[str, Any]:
    artifact_id = artifact.get("id") if isinstance(artifact.get("id"), str) else None
    association = artifact_track_association(artifact)
    owner = artifact.get("buddy")

    if not isinstance(association, dict):
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": None,
            "source_task_id": None,
            "relation": "none",
            "permission_boundary": "artifact.task_association",
            "why": "artifact is missing a readable task association",
        }

    track_id = association.get("track_id")
    source_task_id = association.get("task_id")
    track = association.get("track")

    if isinstance(track, dict) and track.get("status") == "archived":
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": track_id,
            "source_task_id": source_task_id,
            "relation": "none",
            "permission_boundary": "track.lifecycle_status",
            "why": "archived tracks are explicit read boundaries for related artifacts",
        }

    if isinstance(owner, str) and owner == active_buddy:
        return {
            "allowed": True,
            "artifact_id": artifact_id,
            "track_id": track_id,
            "source_task_id": source_task_id,
            "relation": "owner",
            "permission_boundary": "none",
            "why": "active buddy owns source artifact",
        }

    if not isinstance(track, dict):
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": track_id,
            "source_task_id": source_task_id,
            "relation": "none",
            "permission_boundary": "artifact.track_association",
            "why": "foreign artifact task is not attached to a readable track",
        }

    if not bool(artifact.get("is_current")):
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": track_id,
            "source_task_id": source_task_id,
            "relation": "none",
            "permission_boundary": "artifact.currentness",
            "why": "only current foreign artifacts are readable through track collaboration",
        }

    if _has_active_task_relation(track, active_buddy):
        return {
            "allowed": True,
            "artifact_id": artifact_id,
            "track_id": track_id,
            "source_task_id": source_task_id,
            "relation": "track_task",
            "permission_boundary": "none",
            "why": "active buddy has an active task relation on the same track",
        }

    return {
        "allowed": False,
        "artifact_id": artifact_id,
        "track_id": track_id,
        "source_task_id": source_task_id,
        "relation": "none",
        "permission_boundary": "artifact.track_relation",
        "why": "active buddy has no active task relation on source track",
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

    relation = decision.get("relation")
    if relation not in {"owner", "track_task"}:
        relation = "none"

    is_current = bool(artifact.get("is_current"))
    return {
        "id": artifact.get("id"),
        "artifact_id": artifact.get("id"),
        "track_id": source_track.get("id") if isinstance(source_track, dict) else decision.get("track_id"),
        "relation": relation,
        "kind": artifact.get("kind"),
        "title": artifact.get("title"),
        "summary": artifact.get("summary", ""),
        "source_buddy": artifact.get("buddy"),
        "source_task_id": source_task.get("id") if isinstance(source_task, dict) else artifact.get("task_id"),
        "created_by": artifact.get("created_by"),
        "source_refs": artifact.get("source_refs"),
        "revision": artifact.get("revision"),
        "currentness": "current" if is_current else "superseded",
        "readable_by_active_buddy": bool(decision.get("allowed")),
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


def assert_track_readable(track_id: str, *, active_buddy: str, action: str) -> dict[str, Any]:
    track = env_store.get_track(track_id)
    if not isinstance(track, dict):
        return {
            "ok": False,
            "code": "E_TRACK_PAYLOAD",
            "message": f"track not found: {track_id}",
            "permission_boundary": "request-payload",
        }
    if track.get("status") == "archived":
        return {
            "ok": False,
            "code": "E_TRACK_ARCHIVED",
            "message": f"track '{track_id}' is archived and cannot be read via {action}",
            "permission_boundary": "track.lifecycle_status",
        }
    return {
        "ok": True,
        "track": track,
        "active_buddy": active_buddy,
    }
