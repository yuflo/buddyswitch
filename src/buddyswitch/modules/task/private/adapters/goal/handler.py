"""Task-owned adapter that converges one canonical Task with one native Codex Goal."""

from __future__ import annotations

from typing import Any, Mapping


import buddyswitch.foundation.app_server.runtime as app_server
from buddyswitch.foundation.daemon import contracts  # noqa: E402
import buddyswitch.foundation.state.runtime as state_runtime  # noqa: E402
from buddyswitch.modules.task.private.adapters.goal import protocol  # noqa: E402
from buddyswitch.modules.task.private.domain import task_sys  # noqa: E402

_NONCOMPLETE_GOAL_STATUSES = frozenset(
    {"active", "paused", "blocked", "usageLimited", "budgetLimited"}
)
_GOAL_NOTIFICATION_TYPES = frozenset(
    {"app_server.thread_goal_updated", "app_server.thread_goal_cleared"}
)
_MISSING_BOUND_GOAL_REASON = "The bound native Goal was cleared or missing before Task completion."


class TaskGoalInvariantError(RuntimeError):
    """Canonical Task and native Goal cannot be safely converged."""


def _actor_target(context: contracts.DaemonContext) -> dict[str, str]:
    return {
        "actor_id": state_runtime.require_id(context.actor_id, "context.actor_id"),
        "role_id": state_runtime.require_id(context.role, "context.role"),
    }


def _require_task_owner(context: contracts.DaemonContext, task: Mapping[str, Any]) -> None:
    if task.get("actor_target") != _actor_target(context):
        raise TaskGoalInvariantError(
            f"Task {task.get('id')} does not belong to daemon Actor {context.actor_id}"
        )


def _read_goal(context: contracts.DaemonContext) -> dict[str, Any] | None:
    payload = app_server.goal_get(context.socket_path, context.main_thread_id)
    if not isinstance(payload, Mapping) or "goal" not in payload:
        raise TaskGoalInvariantError("thread/goal/get returned no goal field")
    goal = payload.get("goal")
    if goal is None:
        return None
    if not isinstance(goal, Mapping):
        raise TaskGoalInvariantError("thread/goal/get returned an invalid goal")
    return dict(goal)


def _goal_status(goal: Mapping[str, Any]) -> str:
    status = goal.get("status")
    if status not in {*_NONCOMPLETE_GOAL_STATUSES, "complete"}:
        raise TaskGoalInvariantError(f"native Goal has unsupported status: {status!r}")
    return str(status)


def _goal_matches_task(
    context: contracts.DaemonContext,
    task: Mapping[str, Any],
    goal: Mapping[str, Any],
    *,
    require_binding: bool,
) -> bool:
    if goal.get("threadId") != context.main_thread_id:
        return False
    objective = task.get("objective")
    if not isinstance(objective, str) or goal.get("objective") != objective:
        return False
    binding = task.get("goal_binding")
    if not require_binding and binding is None:
        return True
    if not isinstance(binding, Mapping):
        return False
    return (
        binding.get("thread_id") == goal.get("threadId")
        and binding.get("objective_hash") == task_sys.objective_hash(objective)
        and binding.get("goal_created_at") == goal.get("createdAt")
    )


def _goal_was_consumed_by_completed_task(
    context: contracts.DaemonContext,
    goal: Mapping[str, Any],
    *,
    except_task_id: str,
) -> bool:
    goal_thread = goal.get("threadId")
    goal_created_at = goal.get("createdAt")
    objective = goal.get("objective")
    if not isinstance(objective, str):
        return False
    goal_hash = task_sys.objective_hash(objective)
    for task in task_sys.list_tasks(
        actor_target=_actor_target(context),
        statuses=(task_sys.COMPLETED,),
    ):
        if task.get("id") == except_task_id:
            continue
        binding = task.get("goal_binding")
        if not isinstance(binding, Mapping):
            continue
        if (
            binding.get("thread_id") == goal_thread
            and binding.get("objective_hash") == goal_hash
            and binding.get("goal_created_at") == goal_created_at
        ):
            return True
    return False


def _set_goal(
    context: contracts.DaemonContext,
    task: Mapping[str, Any],
) -> dict[str, Any]:
    payload = app_server.goal_set(
        context.socket_path,
        context.main_thread_id,
        objective=str(task["objective"]),
        status="active",
    )
    goal = payload.get("goal") if isinstance(payload, Mapping) else None
    if not isinstance(goal, Mapping):
        raise TaskGoalInvariantError("thread/goal/set returned no Goal snapshot")
    return dict(goal)


def _result(
    *,
    task_id: str,
    task: Mapping[str, Any],
    goal_action: str,
    state_changed: bool,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "task_id": task_id,
        "task_status": task.get("status"),
        "goal_action": goal_action,
        "goal_binding": (
            dict(task["goal_binding"])
            if isinstance(task.get("goal_binding"), Mapping)
            else None
        ),
        "state_changed": state_changed,
    }


def reconcile_task(
    context: contracts.DaemonContext,
    task_id: str,
) -> dict[str, Any]:
    normalized_id = state_runtime.require_id(task_id, "task_id")
    task = task_sys.get_task(normalized_id)
    _require_task_owner(context, task)

    if task["status"] == task_sys.COMPLETED:
        return _result(
            task_id=normalized_id,
            task=task,
            goal_action="already_completed",
            state_changed=False,
        )

    goal = _read_goal(context)

    if task["status"] == task_sys.CANCELED:
        if goal is None:
            return _result(
                task_id=normalized_id,
                task=task,
                goal_action="goal_absent",
                state_changed=False,
            )
        if not _goal_matches_task(
            context,
            task,
            goal,
            require_binding=task.get("goal_binding") is not None,
        ):
            raise TaskGoalInvariantError(
                f"Canceled Task {normalized_id} cannot clear a mismatched native Goal"
            )
        app_server.goal_clear(context.socket_path, context.main_thread_id)
        return _result(
            task_id=normalized_id,
            task=task,
            goal_action="cleared_canceled",
            state_changed=False,
        )

    binding = task.get("goal_binding")
    if binding is not None:
        if goal is None:
            canceled = task_sys.record_task_cancel(normalized_id, _MISSING_BOUND_GOAL_REASON)
            return _result(
                task_id=normalized_id,
                task=canceled["task"],
                goal_action="canceled_missing_goal",
                state_changed=bool(canceled["state_changed"]),
            )
        if not _goal_matches_task(context, task, goal, require_binding=True):
            raise TaskGoalInvariantError(
                f"Active Task {normalized_id} is bound to a different native Goal"
            )
        if _goal_status(goal) == "complete":
            completed = task_sys.record_goal_complete(normalized_id, goal)
            return _result(
                task_id=normalized_id,
                task=completed["task"],
                goal_action="completed",
                state_changed=bool(completed["state_changed"]),
            )
        return _result(
            task_id=normalized_id,
            task=task,
            goal_action="unchanged",
            state_changed=False,
        )

    action = "bound_existing"
    if goal is None:
        goal = _set_goal(context, task)
        action = "set_and_bound"
    else:
        status = _goal_status(goal)
        matches = _goal_matches_task(context, task, goal, require_binding=False)
        consumed = (
            status == "complete"
            and _goal_was_consumed_by_completed_task(
                context,
                goal,
                except_task_id=normalized_id,
            )
        )
        if status == "complete" and (not matches or consumed):
            app_server.goal_clear(context.socket_path, context.main_thread_id)
            goal = _set_goal(context, task)
            action = "replaced_terminal_and_bound"
        elif not matches:
            raise TaskGoalInvariantError(
                f"Active Task {normalized_id} conflicts with an unfinished native Goal"
            )

    bound = task_sys.bind_goal(normalized_id, goal)
    if _goal_status(goal) == "complete":
        completed = task_sys.record_goal_complete(normalized_id, goal)
        return _result(
            task_id=normalized_id,
            task=completed["task"],
            goal_action="completed",
            state_changed=True,
        )
    return _result(
        task_id=normalized_id,
        task=bound["task"],
        goal_action=action,
        state_changed=bool(bound["state_changed"]),
    )


def _current_reconciliation_task(
    context: contracts.DaemonContext,
) -> dict[str, Any] | None:
    tasks = task_sys.list_tasks(actor_target=_actor_target(context))
    active = [task for task in tasks if task["status"] == task_sys.ACTIVE]
    if len(active) > 1:
        raise TaskGoalInvariantError("Actor has more than one active Task")
    if active:
        return active[0]
    canceled_bound = [
        task
        for task in tasks
        if task["status"] == task_sys.CANCELED and task.get("goal_binding") is not None
    ]
    if not canceled_bound:
        return None
    return max(
        canceled_bound,
        key=lambda task: (str(task.get("updated_at") or ""), str(task.get("id") or "")),
    )


def _handler_result(result: Mapping[str, Any] | None) -> contracts.HandlerResult:
    if result is None or result.get("goal_action") in {
        "unchanged",
        "goal_absent",
        "already_completed",
    }:
        return contracts.HandlerResult.ignored()
    return contracts.HandlerResult.handled()


class TaskGoalHandler:
    """Notification acceleration plus startup/poll recovery from canonical state."""

    name = "task_goal"

    def handles(self, trigger: Any) -> bool:
        return getattr(trigger, "type", None) in _GOAL_NOTIFICATION_TYPES

    def handle(
        self,
        context: contracts.DaemonContext,
        state: Any,
        runtime: Any,
        trigger: Any,
    ) -> contracts.HandlerResult:
        del state, runtime
        source_context = getattr(trigger, "source_context", None)
        if not isinstance(source_context, Mapping):
            return contracts.HandlerResult.ignored()
        if source_context.get("thread_id") != context.main_thread_id:
            return contracts.HandlerResult.ignored()
        task = _current_reconciliation_task(context)
        if task is None:
            return contracts.HandlerResult.ignored()
        return _handler_result(reconcile_task(context, str(task["id"])))

    def reconcile(
        self,
        context: contracts.DaemonContext,
        state: Any,
        runtime: Any,
    ) -> contracts.HandlerResult:
        del state, runtime
        task = _current_reconciliation_task(context)
        if task is None:
            return contracts.HandlerResult.ignored()
        return _handler_result(reconcile_task(context, str(task["id"])))


def command_handlers(
    context: contracts.DaemonContext,
) -> Mapping[str, contracts.ApplicationCommand]:
    def reconcile(params: Mapping[str, object]) -> Mapping[str, object]:
        if set(params) != {"task_id"}:
            raise ValueError("task_goal.reconcile_task accepts exactly task_id")
        task_id = params.get("task_id")
        if not isinstance(task_id, str):
            raise ValueError("task_id must be a string")
        return reconcile_task(context, task_id)

    return {protocol.RECONCILE_TASK: reconcile}
