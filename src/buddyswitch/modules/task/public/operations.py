"""Exact current cross-component Task operations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from buddyswitch.env.domain.identity import ActorIdentityProfile
from buddyswitch.modules.task.private.domain import task_sys
from buddyswitch.modules.task.public.contracts import (
    TaskCompletionEvidenceError,
)


def actor_task_projection(
    actor_profile: ActorIdentityProfile,
) -> dict[str, object]:
    return task_sys.actor_task_projection(actor_profile=actor_profile)


def has_active_task(actor_profile: ActorIdentityProfile) -> bool:
    projection = actor_task_projection(actor_profile)
    return projection["active_count"] != 0


def demand_attention(
    actor_target: Mapping[str, Any],
) -> dict[str, object]:
    active = task_sys.list_tasks(
        actor_target=actor_target,
        statuses=task_sys.ACTIVE_TASK_STATUSES,
    )
    if len(active) > 1:
        raise ValueError("Demand orchestration requires at most one active Task")
    terminal = task_sys.list_tasks(
        actor_target=actor_target,
        statuses=task_sys.TERMINAL_TASK_STATUSES,
    )
    return {
        "active_task_id": active[0]["id"] if active else None,
        "terminal_task_ids": sorted(str(row["id"]) for row in terminal),
    }


def require_completed_task_for_demand(
    *,
    task_id: str,
    actor_target: Mapping[str, Any],
    demand_id: str,
) -> dict[str, Any]:
    try:
        return task_sys.require_completed_task_for_demand(
            task_id=task_id,
            actor_target=actor_target,
            demand_id=demand_id,
        )
    except task_sys.TaskCompletionEvidenceError as exc:
        raise TaskCompletionEvidenceError(str(exc)) from exc
