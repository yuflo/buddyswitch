"""External-safe read projections for the current minimal Task record."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from buddyswitch.env.domain import task_sys
from buddyswitch.env.domain.identity import ActorIdentityProfile
from buddyswitch.env.repos import runtime_files


def _resolve_actor_target(
    *,
    actor_profile: ActorIdentityProfile | None = None,
    actor_target: Mapping[str, Any] | None = None,
) -> dict[str, str] | None:
    if actor_profile is not None and actor_target is not None:
        raise ValueError("provide actor_profile or actor_target, not both")
    if actor_profile is not None:
        if not isinstance(actor_profile, ActorIdentityProfile):
            raise ValueError("actor_profile must be an ActorIdentityProfile")
        return {
            "actor_id": actor_profile.identity.id,
            "role_id": actor_profile.role_id,
        }
    if actor_target is None:
        return None
    return {
        "actor_id": runtime_files.require_id(actor_target.get("actor_id"), "actor_target.actor_id"),
        "role_id": runtime_files.require_id(actor_target.get("role_id"), "actor_target.role_id"),
    }


def external_task_projection(task: Mapping[str, Any]) -> dict[str, Any]:
    demand_ref = task.get("demand_ref")
    actor_target = task.get("actor_target")
    if not isinstance(demand_ref, Mapping) or not isinstance(actor_target, Mapping):
        raise ValueError("Task must contain Demand reference and Actor target")
    return {
        "task_id": task.get("id"),
        "demand_ref": {
            "demand_id": demand_ref.get("demand_id"),
            "demand_ref": demand_ref.get("demand_ref"),
        },
        "objective": task.get("objective"),
        "selection": dict(task.get("selection") or {}),
        "goal_binding": dict(task["goal_binding"]) if isinstance(task.get("goal_binding"), Mapping) else None,
        "status": task.get("status"),
        "result": dict(task["result"]) if isinstance(task.get("result"), Mapping) else None,
        "actor": {
            "actor_id": actor_target.get("actor_id"),
            "role_id": actor_target.get("role_id"),
        },
        "updated_at": task.get("updated_at"),
    }


def _records(
    *,
    actor_profile: ActorIdentityProfile | None = None,
    actor_target: Mapping[str, Any] | None = None,
    statuses: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    target = _resolve_actor_target(actor_profile=actor_profile, actor_target=actor_target)
    rows = task_sys.list_tasks(actor_target=target, statuses=statuses)
    rows.sort(key=lambda row: (str(row.get("updated_at") or ""), str(row.get("id") or "")), reverse=True)
    return rows


def list_external_tasks(
    *,
    actor_profile: ActorIdentityProfile | None = None,
    actor_target: Mapping[str, Any] | None = None,
    statuses: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    return [
        external_task_projection(row)
        for row in _records(actor_profile=actor_profile, actor_target=actor_target, statuses=statuses)
    ]


def get_external_task(
    task_id: str,
    *,
    actor_profile: ActorIdentityProfile | None = None,
    actor_target: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    target = _resolve_actor_target(actor_profile=actor_profile, actor_target=actor_target)
    try:
        task = task_sys.get_task(task_id)
    except ValueError:
        return None
    if target is not None and task["actor_target"] != target:
        return None
    return external_task_projection(task)


def actor_external_task_projection(*, actor_profile: ActorIdentityProfile) -> dict[str, object]:
    records = _records(actor_profile=actor_profile)
    classified = [(record, external_task_projection(record)) for record in records]
    tasks = [summary for _record, summary in classified]
    active_tasks = [summary for record, summary in classified if record["status"] == task_sys.ACTIVE]
    terminal_tasks = [
        summary
        for record, summary in classified
        if record["status"] in task_sys.TERMINAL_TASK_STATUSES
    ]
    return {
        "tasks": tasks,
        "active_tasks": active_tasks,
        "terminal_tasks": terminal_tasks,
        "task_count": len(tasks),
        "active_count": len(active_tasks),
        "terminal_count": len(terminal_tasks),
    }
