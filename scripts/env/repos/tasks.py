#!/usr/bin/env python3
"""Task repository helpers backed by instance-local taskbox files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from . import runtime_files

VALID_TASK_STATUS = ("active", "blocked", "done", "archived")
VALID_TASK_PRIORITY = ("high", "normal", "low")
PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}
_LEGACY_TASK_RUN_IDS = "run" + "_ids"
_LEGACY_TASK_LATEST_RUN = "latest" + "_run_id"
_LEGACY_TASK_FIELDS = {"artifact_ids", "artifact" + "_slots"}


def _require_non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _normalize_refs(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("task.refs must be a list")
    rows: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict):
            raise ValueError("task.refs entries must be objects")
        rows.append(dict(raw))
    return rows


def _tasks_dir(
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> Path:
    return runtime_files.taskbox_tasks_dir(
        active_buddy=active_buddy,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )


def _task_file(
    task_id: str,
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> Path:
    normalized_id = runtime_files.require_id(task_id, "task id")
    return _tasks_dir(
        active_buddy=active_buddy,
        instance_json=instance_json,
        instance_payload=instance_payload,
    ) / f"{normalized_id}.json"


def _validate_task(task: Mapping[str, Any]) -> dict[str, Any]:
    if _LEGACY_TASK_RUN_IDS in task or _LEGACY_TASK_LATEST_RUN in task:
        raise ValueError("legacy task run lineage fields are retired")
    forbidden = sorted(field for field in task if field in _LEGACY_TASK_FIELDS)
    if forbidden:
        raise ValueError(f"legacy task fields are retired: {', '.join(forbidden)}")
    if "buddy" in task:
        raise ValueError("task.buddy is retired; use task.owner_buddy")

    task_id = runtime_files.require_id(task.get("id", ""), "task.id")
    owner_buddy = _require_non_empty_text(task.get("owner_buddy"), "task.owner_buddy")
    title = _require_non_empty_text(task.get("title"), "task.title")
    summary = task.get("summary", "")
    if not isinstance(summary, str):
        raise ValueError("task.summary must be a string")
    status = task.get("status")
    if status not in VALID_TASK_STATUS:
        raise ValueError(f"task.status must be one of {', '.join(VALID_TASK_STATUS)}")
    priority = task.get("priority", "normal")
    if priority not in VALID_TASK_PRIORITY:
        raise ValueError(f"task.priority must be one of {', '.join(VALID_TASK_PRIORITY)}")

    track_id = task.get("track_id")
    if track_id is not None:
        runtime_files.require_id(track_id, "task.track_id")

    created_at = _require_non_empty_text(task.get("created_at"), "task.created_at")
    updated_at = _require_non_empty_text(task.get("updated_at"), "task.updated_at")
    closed_at = task.get("closed_at")
    if closed_at is not None and not isinstance(closed_at, str):
        raise ValueError("task.closed_at must be a string or null")

    return {
        "id": task_id,
        "owner_buddy": owner_buddy,
        "title": title,
        "summary": summary,
        "status": status,
        "priority": priority,
        "track_id": track_id,
        "refs": _normalize_refs(task.get("refs")),
        "created_at": created_at,
        "updated_at": updated_at,
        "closed_at": closed_at,
    }


def _history_event_for_change(
    *,
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
    changed_fields: set[str],
) -> str:
    if "status" not in changed_fields:
        return "task.update"
    old_status = str(previous.get("status"))
    new_status = str(current.get("status"))
    if new_status == "archived":
        return "task.archive"
    if old_status in {"done", "archived"} and new_status in {"active", "blocked"}:
        return "task.reopen"
    if new_status == "blocked" and old_status != "blocked":
        return "task.block"
    if new_status == "done" and old_status != "done":
        return "task.close"
    return "task.update"


def valid_task_statuses() -> tuple[str, ...]:
    return VALID_TASK_STATUS


def valid_task_priorities() -> tuple[str, ...]:
    return VALID_TASK_PRIORITY


def slugify(value: str) -> str:
    return runtime_files.slugify(value)


def list_tasks(
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    tasks_dir = _tasks_dir(
        active_buddy=active_buddy,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    if not tasks_dir.exists():
        return []
    for path in sorted(tasks_dir.glob("*.json")):
        row = _validate_task(runtime_files.read_json_object(path))
        if not include_archived and row.get("status") == "archived":
            continue
        rows.append(row)
    rows.sort(key=lambda row: str(row.get("id") or ""))
    rows.sort(key=lambda row: str(row.get("updated_at") or ""), reverse=True)
    rows.sort(key=lambda row: PRIORITY_RANK.get(str(row.get("priority") or "normal"), 1))
    return rows


def get_task(
    task_id: str,
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> dict[str, Any] | None:
    path = _task_file(
        task_id,
        active_buddy=active_buddy,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    if not path.exists():
        return None
    return _validate_task(runtime_files.read_json_object(path))


def save_task(
    task: Mapping[str, Any],
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> dict[str, Any]:
    normalized = _validate_task(task)
    runtime_files.require_runtime_workspace_write_root()
    task_path = _task_file(
        str(normalized["id"]),
        active_buddy=active_buddy,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    task_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_files.write_json_object(task_path, normalized)
    return normalized


def append_history(
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    event: str,
    task_id: str,
    fields: Mapping[str, object],
) -> None:
    history_file = runtime_files.taskbox_history_file(
        active_buddy=active_buddy,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    history_file.parent.mkdir(parents=True, exist_ok=True)
    parts = [f"{key}={json.dumps(value, ensure_ascii=True)}" for key, value in sorted(fields.items())]
    line = f"- {runtime_files.now_iso()} {event} {task_id}"
    if parts:
        line = f"{line} {' '.join(parts)}"
    with history_file.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def read_history(
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    history_file = runtime_files.taskbox_history_file(
        active_buddy=active_buddy,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    if not history_file.exists():
        return []
    lines = history_file.read_text(encoding="utf-8").splitlines()
    tail = lines[-limit:] if limit > 0 else []
    return [{"line": line} for line in tail]


def create_task(
    *,
    task_id: str,
    title: str,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    track_id: str | None,
    status: str,
    priority: str,
    summary: str,
    refs: list[dict[str, Any]],
) -> dict[str, Any]:
    runtime_files.require_id(task_id, "task id")
    if get_task(
        task_id,
        active_buddy=active_buddy,
        instance_json=instance_json,
        instance_payload=instance_payload,
    ):
        raise ValueError(f"task already exists: {task_id}")
    now = runtime_files.now_iso()
    task = {
        "id": task_id,
        "owner_buddy": active_buddy,
        "title": title,
        "summary": summary,
        "status": status,
        "priority": priority,
        "track_id": track_id,
        "refs": refs,
        "created_at": now,
        "updated_at": now,
        "closed_at": now if status in {"done", "archived"} else None,
    }
    saved = save_task(
        task,
        active_buddy=active_buddy,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    append_history(
        active_buddy=active_buddy,
        instance_json=instance_json,
        instance_payload=instance_payload,
        event="task.create",
        task_id=task_id,
        fields={"priority": priority, "status": status},
    )
    return saved


def update_task(
    task_id: str,
    patch: Mapping[str, Any],
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> tuple[dict[str, Any], bool, str | None]:
    task = get_task(
        task_id,
        active_buddy=active_buddy,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    if task is None:
        raise ValueError(f"task not found: {task_id}")

    updated = dict(task)
    changed_fields: set[str] = set()
    for key, value in patch.items():
        if key not in {"title", "summary", "status", "priority", "track_id", "refs"}:
            raise ValueError(f"unsupported task field: {key}")
        if updated.get(key) != value:
            updated[key] = value
            changed_fields.add(key)
    if not changed_fields:
        return task, False, None

    now = runtime_files.now_iso()
    if "status" in changed_fields:
        new_status = str(updated.get("status"))
        old_status = str(task.get("status"))
        if new_status in {"done", "archived"} and old_status not in {"done", "archived"}:
            updated["closed_at"] = now
        elif new_status in {"active", "blocked"}:
            updated["closed_at"] = None
    updated["updated_at"] = now

    saved = save_task(
        updated,
        active_buddy=active_buddy,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    event = _history_event_for_change(
        previous=task,
        current=saved,
        changed_fields=changed_fields,
    )
    history_fields = {field: saved.get(field) for field in sorted(changed_fields)}
    append_history(
        active_buddy=active_buddy,
        instance_json=instance_json,
        instance_payload=instance_payload,
        event=event,
        task_id=task_id,
        fields=history_fields,
    )
    return saved, True, event
