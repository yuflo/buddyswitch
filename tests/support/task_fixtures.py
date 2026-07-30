"""Sole root-test adapter for Task-private state setup."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from typing import Any
from unittest.mock import patch

from buddyswitch.modules.task.private.adapters.goal import client as goal_client
from buddyswitch.modules.task.private import read_model
from buddyswitch.modules.task.private.domain import task_sys


ACTIVE = task_sys.ACTIVE
COMPLETED = task_sys.COMPLETED
CANCELED = task_sys.CANCELED
ACTIVE_TASK_STATUSES = task_sys.ACTIVE_TASK_STATUSES
TERMINAL_TASK_STATUSES = task_sys.TERMINAL_TASK_STATUSES


def create_task(**kwargs: Any) -> dict[str, Any]:
    return task_sys.create(**kwargs)


def bind_goal(task_id: str, goal: Mapping[str, Any]) -> dict[str, Any]:
    return task_sys.bind_goal(task_id, goal)


def record_goal_complete(
    task_id: str,
    goal: Mapping[str, Any],
) -> dict[str, Any]:
    return task_sys.record_goal_complete(task_id, goal)


def record_task_cancel(task_id: str, reason: str) -> dict[str, Any]:
    return task_sys.record_task_cancel(task_id, reason)


def get_task_record(task_id: str) -> dict[str, Any]:
    return task_sys.get_task(task_id)


def list_task_records(**kwargs: Any) -> list[dict[str, Any]]:
    return task_sys.list_tasks(**kwargs)


def validate_task_record(record: Any) -> dict[str, Any]:
    return task_sys._validate_task(record)


def task_read_model() -> Any:
    return read_model


def patch_goal_reconcile(
    *,
    return_value: Any = None,
    side_effect: Any = None,
) -> AbstractContextManager[Any]:
    kwargs: dict[str, Any] = {"autospec": True}
    if side_effect is not None:
        kwargs["side_effect"] = side_effect
    else:
        kwargs["return_value"] = return_value
    return patch.object(
        goal_client.TaskGoalClient,
        "reconcile_task",
        **kwargs,
    )


def patch_actor_task_projection(
    *,
    return_value: Any = None,
    side_effect: Any = None,
) -> AbstractContextManager[Any]:
    kwargs: dict[str, Any] = {}
    if side_effect is not None:
        kwargs["side_effect"] = side_effect
    else:
        kwargs["return_value"] = return_value
    return patch.object(
        task_sys,
        "actor_task_projection",
        **kwargs,
    )
