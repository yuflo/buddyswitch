#!/usr/bin/env python3
"""Task repository helpers backed by runtime object files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import runtime_files

VALID_TASK_STATUS = ("active", "blocked", "done", "archived")
_LEGACY_TASK_RUN_IDS = "run" + "_ids"
_LEGACY_TASK_LATEST_RUN = "latest" + "_run_id"
_LEGACY_TASK_FIELDS = {"artifact_ids", "artifact" + "_slots"}


def _require_non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _task_file(task_id: str) -> Path:
    return runtime_files.TASKS_DIR / f"{runtime_files.require_id(task_id, 'task id')}.json"


def _validate_task(task: dict[str, Any]) -> dict[str, Any]:
    if _LEGACY_TASK_RUN_IDS in task or _LEGACY_TASK_LATEST_RUN in task:
        raise ValueError("legacy task run lineage fields are retired")
    forbidden = sorted(field for field in task if field in _LEGACY_TASK_FIELDS)
    if forbidden:
        raise ValueError(f"legacy task fields are retired: {', '.join(forbidden)}")

    task_id = runtime_files.require_id(task.get("id", ""), "task.id")
    buddy = _require_non_empty_text(task.get("buddy"), "task.buddy")
    title = _require_non_empty_text(task.get("title"), "task.title")
    status = task.get("status")
    if status not in VALID_TASK_STATUS:
        raise ValueError(f"task.status must be one of {', '.join(VALID_TASK_STATUS)}")

    track_id = task.get("track_id")
    if track_id is not None:
        runtime_files.require_id(track_id, "task.track_id")

    summary = task.get("summary", "")
    if not isinstance(summary, str):
        raise ValueError("task.summary must be a string")
    created_at = _require_non_empty_text(task.get("created_at"), "task.created_at")
    updated_at = _require_non_empty_text(task.get("updated_at"), "task.updated_at")

    return {
        "id": task_id,
        "buddy": buddy,
        "title": title,
        "status": status,
        "track_id": track_id,
        "summary": summary,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def valid_task_statuses() -> tuple[str, ...]:
    return VALID_TASK_STATUS


def slugify(value: str) -> str:
    return runtime_files.slugify(value)


def list_tasks() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if runtime_files.TASKS_DIR.exists():
        for path in runtime_files.TASKS_DIR.glob("*.json"):
            rows.append(_validate_task(runtime_files.read_json_object(path)))
    rows.sort(key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
    return rows


def get_task(task_id: str) -> dict[str, Any] | None:
    path = _task_file(task_id)
    if not path.exists():
        return None
    return _validate_task(runtime_files.read_json_object(path))


def save_task(task: dict[str, Any]) -> dict[str, Any]:
    normalized = _validate_task(task)
    runtime_files.require_runtime_workspace_write_root()
    runtime_files.TASKS_DIR.mkdir(parents=True, exist_ok=True)
    runtime_files.write_json_object(_task_file(normalized["id"]), normalized)
    return normalized


def create_task(
    *,
    task_id: str,
    title: str,
    buddy: str,
    track_id: str | None,
    status: str,
    summary: str,
) -> dict[str, Any]:
    runtime_files.require_id(task_id, "task id")
    if get_task(task_id):
        raise ValueError(f"task already exists: {task_id}")
    timestamp = runtime_files.now_iso()
    task = {
        "id": task_id,
        "buddy": buddy,
        "title": title,
        "status": status,
        "track_id": track_id,
        "summary": summary,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    return save_task(task)


def update_task(task_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise ValueError(f"task not found: {task_id}")
    allowed = {"title", "status", "track_id", "summary"}
    for key, value in patch.items():
        if key not in allowed:
            raise ValueError(f"unsupported task field: {key}")
        task[key] = value
    task["updated_at"] = runtime_files.now_iso()
    return save_task(task)
