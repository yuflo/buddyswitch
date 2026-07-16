"""External-safe read projections for Task records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from env.domain import task_sys
from env.domain.identity import ActorIdentityProfile
from env.repos import runtime_files


def _actor_target_from_profile(actor_profile: ActorIdentityProfile) -> dict[str, str]:
    if not isinstance(actor_profile, ActorIdentityProfile):
        raise ValueError("actor_profile must be an ActorIdentityProfile")
    return {"actor_id": actor_profile.identity.id, "role_id": actor_profile.role_id}


def _actor_target_from_mapping(actor_target: Mapping[str, Any]) -> dict[str, str]:
    return {
        "actor_id": runtime_files.require_id(actor_target.get("actor_id"), "actor_target.actor_id"),
        "role_id": runtime_files.require_id(actor_target.get("role_id"), "actor_target.role_id"),
    }


def _resolve_actor_target(
    *,
    actor_profile: ActorIdentityProfile | None = None,
    actor_target: Mapping[str, Any] | None = None,
) -> dict[str, str] | None:
    if actor_profile is not None and actor_target is not None:
        raise ValueError("provide actor_profile or actor_target, not both")
    if actor_profile is not None:
        return _actor_target_from_profile(actor_profile)
    if actor_target is not None:
        return _actor_target_from_mapping(actor_target)
    return None


def _record_actor(record: Mapping[str, Any]) -> dict[str, Any]:
    target = record.get("actor_target")
    if not isinstance(target, Mapping):
        return {"actor_id": None, "role_id": None}
    return {"actor_id": target.get("actor_id"), "role_id": target.get("role_id")}


def _matches_actor(record: Mapping[str, Any], actor_target: Mapping[str, str] | None) -> bool:
    if actor_target is None:
        return True
    return _record_actor(record) == dict(actor_target)


def external_task_projection(task: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task.get("id"),
        "source_type": task.get("source_type"),
        "status": task.get("status"),
        "actor": _record_actor(task),
        "updated_at": task.get("updated_at"),
    }


def _sort_key(record: Mapping[str, Any]) -> tuple[str, str]:
    return (str(record.get("updated_at") or ""), str(record.get("id") or ""))


def _list_task_records(
    *,
    actor_profile: ActorIdentityProfile | None = None,
    actor_target: Mapping[str, Any] | None = None,
    statuses: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    normalized_actor_target = _resolve_actor_target(actor_profile=actor_profile, actor_target=actor_target)
    kwargs: dict[str, Any] = {}
    if normalized_actor_target is not None:
        kwargs["actor_target"] = normalized_actor_target
    if statuses is not None:
        kwargs["statuses"] = statuses
    records = task_sys.list_tasks(**kwargs)
    rows = [
        record
        for record in records
        if isinstance(record, Mapping)
        and _matches_actor(record, normalized_actor_target)
        and (statuses is None or record.get("status") in set(statuses))
    ]
    rows.sort(key=_sort_key, reverse=True)
    return rows


def list_external_tasks(
    *,
    actor_profile: ActorIdentityProfile | None = None,
    actor_target: Mapping[str, Any] | None = None,
    statuses: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    return [
        external_task_projection(record)
        for record in _list_task_records(actor_profile=actor_profile, actor_target=actor_target, statuses=statuses)
    ]


def get_external_task(
    task_id: str,
    *,
    actor_profile: ActorIdentityProfile | None = None,
    actor_target: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    normalized_actor_target = _resolve_actor_target(actor_profile=actor_profile, actor_target=actor_target)
    try:
        record = task_sys.get_task(task_id)
    except ValueError:
        return None
    if not _matches_actor(record, normalized_actor_target):
        return None
    return external_task_projection(record)


def _execution_result(record: Mapping[str, Any]) -> Mapping[str, Any] | None:
    execution = record.get("execution")
    if not isinstance(execution, Mapping):
        return None
    result = execution.get("result")
    return result if isinstance(result, Mapping) else None


def _is_active_task(record: Mapping[str, Any]) -> bool:
    return record.get("status") in task_sys.ACTIVE_TASK_STATUSES


def _is_recoverable_task(record: Mapping[str, Any]) -> bool:
    if record.get("status") != task_sys.SIDE_PROCESSING:
        return False
    result = _execution_result(record)
    return (
        isinstance(result, Mapping)
        and result.get("type") == "failure"
        and result.get("reason") in task_sys.RECOVERABLE_TASK_REASONS
    )


def actor_external_task_projection(*, actor_profile: ActorIdentityProfile) -> dict[str, object]:
    records = _list_task_records(actor_profile=actor_profile)
    classified = [(record, external_task_projection(record)) for record in records]
    tasks = [summary for _record, summary in classified]
    active_tasks = [summary for record, summary in classified if _is_active_task(record)]
    recoverable_tasks = [summary for record, summary in classified if _is_recoverable_task(record)]
    return {
        "tasks": tasks,
        "active_tasks": active_tasks,
        "recoverable_tasks": recoverable_tasks,
        "task_count": len(tasks),
        "active_count": len(active_tasks),
        "recoverable_count": len(recoverable_tasks),
    }
