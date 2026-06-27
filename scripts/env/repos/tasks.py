#!/usr/bin/env python3
"""Task repository helpers backed by instance-local taskbox files."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from env.tool_runtime.actor_profile import ActorAddress
from . import runtime_files

VALID_TASK_STATUS = ("captured", "active", "blocked", "done", "archived")
VALID_TASK_PRIORITY = ("high", "normal", "low")
PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}
_LEGACY_TASK_RUN_IDS = "run" + "_ids"
_LEGACY_TASK_LATEST_RUN = "latest" + "_run_id"
_LEGACY_TASK_FIELDS = {"artifact_ids", "artifact" + "_slots"}


def _require_non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _normalize_actor(value: Any, field: str) -> dict[str, str]:
    try:
        return ActorAddress.from_payload(value).to_payload()
    except ValueError as exc:
        raise ValueError(f"{field} must be an ActorAddress payload: {exc}") from exc


def _actor_identity_id(value: Any, field: str) -> str:
    return _normalize_actor(value, field)["actor_id"]


def _identity_id(value: Any, field: str) -> str:
    if isinstance(value, str) and value.strip():
        return runtime_files.require_id(value.strip(), field)
    return _actor_identity_id(value, field)


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


def _normalize_origin(value: Any) -> dict[str, Any]:
    if value is None:
        return {"type": "manual"}
    if not isinstance(value, dict):
        raise ValueError("task.origin must be an object")
    return dict(value)


def _tasks_dir(
    *,
    active_role: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> Path:
    return runtime_files.taskbox_tasks_dir(
        active_role=active_role,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )


def _task_file(
    task_id: str,
    *,
    active_role: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> Path:
    normalized_id = runtime_files.require_id(task_id, "task id")
    return _tasks_dir(
        active_role=active_role,
        instance_json=instance_json,
        instance_payload=instance_payload,
    ) / f"{normalized_id}.json"


def _validate_task(task: Mapping[str, Any]) -> dict[str, Any]:
    if _LEGACY_TASK_RUN_IDS in task or _LEGACY_TASK_LATEST_RUN in task:
        raise ValueError("legacy task run lineage fields are retired")
    forbidden = sorted(field for field in task if field in _LEGACY_TASK_FIELDS)
    if forbidden:
        raise ValueError(f"legacy task fields are retired: {', '.join(forbidden)}")
    if "role" in task:
        raise ValueError("task.role is retired; use task.owner_identity_id")

    task_id = runtime_files.require_id(task.get("id", ""), "task.id")
    owner_identity_id = _identity_id(task.get("owner_identity_id", task.get("owner_actor")), "task.owner_identity_id")
    title = _require_non_empty_text(task.get("title"), "task.title")
    summary = task.get("summary", "")
    if not isinstance(summary, str):
        raise ValueError("task.summary must be a string")
    body = task.get("body", "")
    if not isinstance(body, str):
        raise ValueError("task.body must be a string")
    status = task.get("status")
    if status not in VALID_TASK_STATUS:
        raise ValueError(f"task.status must be one of {', '.join(VALID_TASK_STATUS)}")
    priority = task.get("priority", "normal")
    if priority not in VALID_TASK_PRIORITY:
        raise ValueError(f"task.priority must be one of {', '.join(VALID_TASK_PRIORITY)}")

    track_id = task.get("track_id")
    if track_id is not None:
        runtime_files.require_id(track_id, "task.track_id")

    progress_summary = task.get("progress_summary", task.get("summary", ""))
    if not isinstance(progress_summary, str):
        raise ValueError("task.progress_summary must be a string")

    created_at = _require_non_empty_text(task.get("created_at"), "task.created_at")
    updated_at = _require_non_empty_text(task.get("updated_at"), "task.updated_at")
    closed_at = task.get("closed_at")
    if closed_at is not None and not isinstance(closed_at, str):
        raise ValueError("task.closed_at must be a string or null")

    return {
        "id": task_id,
        "owner_identity_id": owner_identity_id,
        "title": title,
        "summary": summary,
        "body": body,
        "status": status,
        "priority": priority,
        "origin": _normalize_origin(task.get("origin")),
        "track_id": track_id,
        "refs": _normalize_refs(task.get("refs")),
        "progress_summary": progress_summary,
        "created_at": created_at,
        "updated_at": updated_at,
        "closed_at": closed_at,
    }


def valid_task_statuses() -> tuple[str, ...]:
    return VALID_TASK_STATUS


def valid_task_priorities() -> tuple[str, ...]:
    return VALID_TASK_PRIORITY


def slugify(value: str) -> str:
    return runtime_files.slugify(value)


def _history_file(
    *,
    active_role: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> Path:
    return runtime_files.taskbox_history_file(
        active_role=active_role,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )


def list_tasks(
    *,
    active_role: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    tasks_dir = _tasks_dir(
        active_role=active_role,
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
    active_role: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> dict[str, Any] | None:
    path = _task_file(
        task_id,
        active_role=active_role,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    if not path.exists():
        return None
    return _validate_task(runtime_files.read_json_object(path))


def save_task(
    task: Mapping[str, Any],
    *,
    active_role: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> dict[str, Any]:
    normalized = _validate_task(task)
    runtime_files.require_runtime_workspace_write_root()
    task_path = _task_file(
        str(normalized["id"]),
        active_role=active_role,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    task_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_files.write_json_object(task_path, normalized)
    return normalized


def append_history(
    *,
    active_role: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    event: str,
    task_id: str,
    fields: Mapping[str, object],
) -> None:
    history_file = _history_file(
        active_role=active_role,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    history_file.parent.mkdir(parents=True, exist_ok=True)
    parts = [f"{key}={json.dumps(value, ensure_ascii=True, separators=(',', ':'))}" for key, value in sorted(fields.items())]
    line = f"- {runtime_files.now_iso()} {event} {task_id}"
    if parts:
        line = f"{line} {' '.join(parts)}"
    with history_file.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def append_event(
    *,
    active_role: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    event: str,
    task_id: str,
    fields: Mapping[str, object],
) -> None:
    append_history(
        active_role=active_role,
        instance_json=instance_json,
        instance_payload=instance_payload,
        event=event,
        task_id=task_id,
        fields=fields,
    )


def read_history(
    *,
    active_role: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    history_file = _history_file(
        active_role=active_role,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    if not history_file.exists():
        return []
    lines = history_file.read_text(encoding="utf-8").splitlines()
    tail = lines[-limit:] if limit > 0 else []
    return [{"line": line} for line in tail]


def parse_history_line(line: str) -> dict[str, Any] | None:
    raw = line.strip()
    if not raw.startswith("- "):
        return None
    parts = raw[2:].split(maxsplit=3)
    if len(parts) < 3:
        return None
    timestamp, event, task_id = parts[:3]
    try:
        normalized_task_id = runtime_files.require_id(task_id, "task id")
    except ValueError:
        return None
    fields: dict[str, Any] = {}
    remainder = parts[3] if len(parts) == 4 else ""
    decoder = json.JSONDecoder()
    index = 0
    while index < len(remainder):
        while index < len(remainder) and remainder[index].isspace():
            index += 1
        if index >= len(remainder):
            break
        key_start = index
        while index < len(remainder) and remainder[index] != "=":
            index += 1
        if index >= len(remainder):
            return None
        key = remainder[key_start:index]
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            return None
        index += 1
        try:
            value, index = decoder.raw_decode(remainder, index)
        except json.JSONDecodeError:
            return None
        fields[key] = value
    return {
        "line": line,
        "timestamp": timestamp,
        "event": event,
        "task_id": normalized_task_id,
        "fields": fields,
    }


def read_history_events(
    *,
    active_role: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    history_file = _history_file(
        active_role=active_role,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    if not history_file.exists():
        return []
    lines = history_file.read_text(encoding="utf-8").splitlines()
    selected = lines[-limit:] if limit > 0 else lines
    events: list[dict[str, Any]] = []
    for line in selected:
        event = parse_history_line(line)
        if event is not None:
            events.append(event)
    return events


def next_task_id(
    title: str,
    *,
    active_role: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> str:
    slug = slugify(title)[:48].strip("-") or "task"
    tasks_dir = _tasks_dir(
        active_role=active_role,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    highest = 0
    if tasks_dir.exists():
        for path in tasks_dir.glob("task-*.json"):
            match = re.match(r"task-(\d+)-", path.stem)
            if match:
                highest = max(highest, int(match.group(1)))
    return f"task-{highest + 1:04d}-{slug}"


def next_confirmation_id(
    *,
    active_role: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> str:
    highest = 0
    for event in read_history_events(
        active_role=active_role,
        instance_json=instance_json,
        instance_payload=instance_payload,
        limit=0,
    ):
        fields = event.get("fields")
        if not isinstance(fields, dict):
            continue
        value = fields.get("confirmation_id")
        if not isinstance(value, str):
            continue
        match = re.match(r"confirm-(\d+)$", value)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"confirm-{highest + 1:04d}"


def create_task(
    *,
    task_id: str,
    title: str,
    active_role: str,
    active_actor: dict[str, Any],
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    track_id: str | None,
    status: str,
    priority: str,
    summary: str,
    refs: list[dict[str, Any]],
    origin: dict[str, Any] | None = None,
    progress_summary: str = "",
    body: str = "",
) -> dict[str, Any]:
    runtime_files.require_id(task_id, "task id")
    if get_task(
        task_id,
        active_role=active_role,
        instance_json=instance_json,
        instance_payload=instance_payload,
    ):
        raise ValueError(f"task already exists: {task_id}")
    now = runtime_files.now_iso()
    task = {
        "id": task_id,
        "owner_identity_id": _actor_identity_id(active_actor, "active_actor"),
        "title": title,
        "summary": summary,
        "body": body,
        "status": status,
        "priority": priority,
        "origin": origin or {"type": "manual"},
        "track_id": track_id,
        "refs": refs,
        "progress_summary": progress_summary or summary,
        "created_at": now,
        "updated_at": now,
        "closed_at": now if status in {"done", "archived"} else None,
    }
    saved = save_task(
        task,
        active_role=active_role,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    append_history(
        active_role=active_role,
        instance_json=instance_json,
        instance_payload=instance_payload,
        event="task.captured" if status == "captured" else "task.selected" if status == "active" else f"task.{status}",
        task_id=task_id,
        fields={"priority": priority, "status": status},
    )
    return saved
