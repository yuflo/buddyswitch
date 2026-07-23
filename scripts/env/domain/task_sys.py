"""Task owner for one Demand-bound objective executed by one native Codex Goal."""

from __future__ import annotations

from copy import deepcopy
import fcntl
import hashlib
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from env.domain.identity import ActorIdentityProfile
from env.repos import runtime_files

ACTIVE = "active"
COMPLETED = "completed"
CANCELED = "canceled"

TASK_STATUSES = (ACTIVE, COMPLETED, CANCELED)
ACTIVE_TASK_STATUSES = (ACTIVE,)
TERMINAL_TASK_STATUSES = (COMPLETED, CANCELED)

_TASK_KEYS = frozenset(
    {
        "schema_version",
        "id",
        "actor_target",
        "demand_ref",
        "objective",
        "selection",
        "goal_binding",
        "status",
        "result",
        "created_at",
        "updated_at",
    }
)
_GOAL_BINDING_KEYS = frozenset({"thread_id", "objective_hash", "goal_created_at"})


class TaskSysError(ValueError):
    code = "E_TASK_SYS"


class TaskSourceConflict(TaskSysError):
    code = "E_TASK_SYS_SOURCE_CONFLICT"

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"Task source already exists with different objective or selection: {task_id}")


class TaskActiveConflict(TaskSysError):
    code = "E_TASK_SYS_ACTIVE_CONFLICT"

    def __init__(self, task_id: str, task_status: str) -> None:
        self.task_id = task_id
        self.task_status = task_status
        super().__init__(f"Actor already has active Task {task_id} in status {task_status}")


class TaskGoalConflict(TaskSysError):
    code = "E_TASK_SYS_GOAL_CONFLICT"

    def __init__(self, task_id: str, message: str) -> None:
        self.task_id = task_id
        super().__init__(f"Task {task_id} Goal conflict: {message}")


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _copy(value: Mapping[str, Any]) -> dict[str, Any]:
    return deepcopy(dict(value))


def _normalize_actor_target(value: Any) -> dict[str, str]:
    target = _require_mapping(value, "actor_target")
    if set(target) != {"actor_id", "role_id"}:
        raise ValueError("actor_target must contain exactly actor_id and role_id")
    return {
        "actor_id": runtime_files.require_id(
            _require_text(target.get("actor_id"), "actor_target.actor_id"),
            "actor_target.actor_id",
        ),
        "role_id": runtime_files.require_id(
            _require_text(target.get("role_id"), "actor_target.role_id"),
            "actor_target.role_id",
        ),
    }


def _normalize_demand_ref(value: Any) -> dict[str, Any]:
    demand_ref = _require_mapping(value, "demand_ref")
    if set(demand_ref) != {"demand_id", "basis_revision", "demand_ref"}:
        raise ValueError("demand_ref must contain exactly demand_id, basis_revision, and demand_ref")
    demand_id = runtime_files.require_id(
        _require_text(demand_ref.get("demand_id"), "demand_ref.demand_id"),
        "demand_ref.demand_id",
    )
    if not demand_id.startswith("demand-"):
        raise ValueError("demand_ref.demand_id must be a Demand id")
    basis_revision = demand_ref.get("basis_revision")
    if type(basis_revision) is not int or basis_revision < 1:
        raise ValueError("demand_ref.basis_revision must be a positive integer")
    opaque_ref = _require_text(demand_ref.get("demand_ref"), "demand_ref.demand_ref")
    if not opaque_ref.startswith("dref-"):
        raise ValueError("demand_ref.demand_ref must be an opaque Demand reference")
    return {
        "demand_id": demand_id,
        "basis_revision": basis_revision,
        "demand_ref": opaque_ref,
    }


def _actor_demand_ref(value: Any) -> dict[str, str]:
    demand_ref = _normalize_demand_ref(value)
    return {
        "demand_id": demand_ref["demand_id"],
        "demand_ref": demand_ref["demand_ref"],
    }


def objective_hash(objective: str) -> str:
    normalized = _require_text(objective, "objective")
    return f"sha256:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"


def _normalize_goal_binding(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    binding = _require_mapping(value, "goal_binding")
    if set(binding) != _GOAL_BINDING_KEYS:
        raise ValueError("goal_binding must contain exactly thread_id, objective_hash, and goal_created_at")
    created_at = binding.get("goal_created_at")
    if type(created_at) is not int or created_at < 0:
        raise ValueError("goal_binding.goal_created_at must be a non-negative integer")
    normalized_hash = _require_text(binding.get("objective_hash"), "goal_binding.objective_hash")
    if not normalized_hash.startswith("sha256:"):
        raise ValueError("goal_binding.objective_hash must be a sha256 hash")
    return {
        "thread_id": _require_text(binding.get("thread_id"), "goal_binding.thread_id"),
        "objective_hash": normalized_hash,
        "goal_created_at": created_at,
    }


def _normalize_goal(goal: Any, *, objective: str) -> dict[str, Any]:
    value = _require_mapping(goal, "goal")
    thread_id = _require_text(value.get("threadId"), "goal.threadId")
    goal_objective = _require_text(value.get("objective"), "goal.objective")
    if goal_objective != objective:
        raise ValueError("goal.objective must exactly equal the Task objective")
    status = _require_text(value.get("status"), "goal.status")
    created_at = value.get("createdAt")
    updated_at = value.get("updatedAt")
    if type(created_at) is not int or created_at < 0:
        raise ValueError("goal.createdAt must be a non-negative integer")
    if type(updated_at) is not int or updated_at < 0:
        raise ValueError("goal.updatedAt must be a non-negative integer")
    token_budget = value.get("tokenBudget")
    if token_budget is not None and (type(token_budget) is not int or token_budget <= 0):
        raise ValueError("goal.tokenBudget must be null or a positive integer")
    tokens_used = value.get("tokensUsed")
    time_used_seconds = value.get("timeUsedSeconds")
    if type(tokens_used) is not int or tokens_used < 0:
        raise ValueError("goal.tokensUsed must be a non-negative integer")
    if type(time_used_seconds) is not int or time_used_seconds < 0:
        raise ValueError("goal.timeUsedSeconds must be a non-negative integer")
    return {
        "thread_id": thread_id,
        "objective": goal_objective,
        "status": status,
        "token_budget": token_budget,
        "tokens_used": tokens_used,
        "time_used_seconds": time_used_seconds,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _validate_result(value: Any, *, status: str) -> dict[str, Any] | None:
    if status == ACTIVE:
        if value is not None:
            raise ValueError("active Task result must be null")
        return None
    result = _require_mapping(value, "task.result")
    result_type = result.get("type")
    if status == COMPLETED:
        required = {
            "type",
            "goal_status",
            "thread_id",
            "objective_hash",
            "goal_created_at",
            "goal_updated_at",
            "token_budget",
            "tokens_used",
            "time_used_seconds",
            "recorded_at",
        }
        if set(result) != required or result_type != "goal_terminal" or result.get("goal_status") != "complete":
            raise ValueError("completed Task result must be an exact complete Goal terminal snapshot")
        _normalize_goal_binding(
            {
                "thread_id": result.get("thread_id"),
                "objective_hash": result.get("objective_hash"),
                "goal_created_at": result.get("goal_created_at"),
            }
        )
        if type(result.get("goal_updated_at")) is not int or result["goal_updated_at"] < 0:
            raise ValueError("task.result.goal_updated_at must be a non-negative integer")
        token_budget = result.get("token_budget")
        if token_budget is not None and (type(token_budget) is not int or token_budget <= 0):
            raise ValueError("task.result.token_budget must be null or a positive integer")
        for field in ("tokens_used", "time_used_seconds"):
            if type(result.get(field)) is not int or result[field] < 0:
                raise ValueError(f"task.result.{field} must be a non-negative integer")
        _require_text(result.get("recorded_at"), "task.result.recorded_at")
    elif status == CANCELED:
        if set(result) != {"type", "reason", "recorded_at"} or result_type != "actor_canceled":
            raise ValueError("canceled Task result must be an exact actor_canceled result")
        _require_text(result.get("reason"), "task.result.reason")
        _require_text(result.get("recorded_at"), "task.result.recorded_at")
    return _copy(result)


def _validate_task(record: Any) -> dict[str, Any]:
    try:
        value = _require_mapping(record, "task")
        if set(value) != _TASK_KEYS or value.get("schema_version") != 1:
            raise ValueError("Task record does not match the current schema")
        task_id = runtime_files.require_id(value.get("id"), "task.id")
        if not task_id.startswith("task-demand-"):
            raise ValueError("task.id must be a Demand Task id")
        actor_target = _normalize_actor_target(value.get("actor_target"))
        demand_ref = _normalize_demand_ref(value.get("demand_ref"))
        objective = _require_text(value.get("objective"), "task.objective")
        selection = _require_mapping(value.get("selection"), "task.selection")
        if set(selection) != {"reason", "selected_at"}:
            raise ValueError("task.selection must contain exactly reason and selected_at")
        normalized_selection = {
            "reason": _require_text(selection.get("reason"), "task.selection.reason"),
            "selected_at": _require_text(selection.get("selected_at"), "task.selection.selected_at"),
        }
        goal_binding = _normalize_goal_binding(value.get("goal_binding"))
        status = value.get("status")
        if status not in TASK_STATUSES:
            raise ValueError(f"task.status must be one of {', '.join(TASK_STATUSES)}")
        result = _validate_result(value.get("result"), status=str(status))
        if status == COMPLETED and goal_binding is None:
            raise ValueError("completed Task must have a Goal binding")
        created_at = _require_text(value.get("created_at"), "task.created_at")
        updated_at = _require_text(value.get("updated_at"), "task.updated_at")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"retired or invalid Task record: {exc}") from exc
    return {
        "schema_version": 1,
        "id": task_id,
        "actor_target": actor_target,
        "demand_ref": demand_ref,
        "objective": objective,
        "selection": normalized_selection,
        "goal_binding": goal_binding,
        "status": status,
        "result": result,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _tasks_dir() -> Path:
    return runtime_files.OBJECTS_ROOT / "task-sys" / "tasks"


def _task_file(task_id: str) -> Path:
    return _tasks_dir() / f"{runtime_files.require_id(task_id, 'task id')}.json"


def _actor_lock_file(actor_target: Mapping[str, str]) -> Path:
    return (
        runtime_files.LOCAL_ROOT
        / "locks"
        / "task-sys"
        / f"{actor_target['actor_id']}-{actor_target['role_id']}.lock"
    )


def _new_task_id() -> str:
    return f"task-demand-{uuid4().hex[:12]}"


def _persist_task(record: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _validate_task(record)
    runtime_files.write_json_object(_task_file(normalized["id"]), normalized)
    return normalized


def _load_task(task_id: str) -> dict[str, Any]:
    path = _task_file(task_id)
    if not path.exists():
        raise ValueError(f"task not found: {task_id}")
    return _validate_task(runtime_files.read_json_object(path))


def _with_actor_lock(actor_target: Mapping[str, str]):
    runtime_files.require_runtime_workspace_write_root()
    lock_path = _actor_lock_file(actor_target)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    return lock_path.open("a+", encoding="utf-8")


def list_tasks(
    *,
    actor_target: Mapping[str, Any] | None = None,
    statuses: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    tasks_dir = _tasks_dir()
    if not tasks_dir.exists():
        return []
    normalized_target = _normalize_actor_target(actor_target) if actor_target is not None else None
    allowed_statuses = set(statuses) if statuses is not None else None
    if allowed_statuses is not None and not allowed_statuses.issubset(TASK_STATUSES):
        raise ValueError("statuses contains an unsupported Task status")
    rows: list[dict[str, Any]] = []
    for path in sorted(tasks_dir.glob("*.json")):
        record = _validate_task(runtime_files.read_json_object(path))
        if normalized_target is not None and record["actor_target"] != normalized_target:
            continue
        if allowed_statuses is not None and record["status"] not in allowed_statuses:
            continue
        rows.append(record)
    return rows


def get_task(task_id: str) -> dict[str, Any]:
    return _load_task(runtime_files.require_id(task_id, "task id"))


def create(
    *,
    actor_target: Mapping[str, Any],
    demand_ref: Mapping[str, Any],
    objective: str,
    selection_reason: str,
) -> dict[str, Any]:
    normalized_target = _normalize_actor_target(actor_target)
    normalized_ref = _normalize_demand_ref(demand_ref)
    normalized_objective = _require_text(objective, "objective")
    normalized_reason = _require_text(selection_reason, "selection_reason")
    lock_file = _with_actor_lock(normalized_target)
    with lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            actor_tasks = list_tasks(actor_target=normalized_target)
            for existing in actor_tasks:
                if existing["demand_ref"] == normalized_ref:
                    if (
                        existing["objective"] != normalized_objective
                        or existing["selection"]["reason"] != normalized_reason
                    ):
                        raise TaskSourceConflict(existing["id"])
                    return {
                        "ok": True,
                        "task_id": existing["id"],
                        "task": existing,
                        "outcome": "existing",
                        "state_changed": False,
                    }
            for existing in actor_tasks:
                if existing["status"] == ACTIVE:
                    raise TaskActiveConflict(existing["id"], existing["status"])
            now = runtime_files.now_iso()
            record = {
                "schema_version": 1,
                "id": _new_task_id(),
                "actor_target": normalized_target,
                "demand_ref": normalized_ref,
                "objective": normalized_objective,
                "selection": {"reason": normalized_reason, "selected_at": now},
                "goal_binding": None,
                "status": ACTIVE,
                "result": None,
                "created_at": now,
                "updated_at": now,
            }
            persisted = _persist_task(record)
            return {
                "ok": True,
                "task_id": persisted["id"],
                "task": persisted,
                "outcome": "created",
                "state_changed": True,
            }
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def bind_goal(task_id: str, goal: Mapping[str, Any]) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    initial = _load_task(normalized_task_id)
    lock_file = _with_actor_lock(initial["actor_target"])
    with lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            record = _load_task(normalized_task_id)
            if record["status"] != ACTIVE:
                raise TaskGoalConflict(normalized_task_id, "only an active Task can bind a Goal")
            normalized_goal = _normalize_goal(goal, objective=record["objective"])
            binding = {
                "thread_id": normalized_goal["thread_id"],
                "objective_hash": objective_hash(record["objective"]),
                "goal_created_at": normalized_goal["created_at"],
            }
            existing = record["goal_binding"]
            if existing is not None:
                if existing != binding:
                    raise TaskGoalConflict(normalized_task_id, "a different Goal is already bound")
                return {
                    "ok": True,
                    "task_id": normalized_task_id,
                    "task": record,
                    "outcome": "goal_bound",
                    "state_changed": False,
                }
            record["goal_binding"] = binding
            record["updated_at"] = runtime_files.now_iso()
            persisted = _persist_task(record)
            return {
                "ok": True,
                "task_id": normalized_task_id,
                "task": persisted,
                "outcome": "goal_bound",
                "state_changed": True,
            }
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _require_bound_goal(task_id: str, record: Mapping[str, Any], goal: Mapping[str, Any]) -> dict[str, Any]:
    normalized_goal = _normalize_goal(goal, objective=str(record["objective"]))
    binding = _normalize_goal_binding(record.get("goal_binding"))
    if binding is None:
        raise TaskGoalConflict(task_id, "Task has no Goal binding")
    observed_binding = {
        "thread_id": normalized_goal["thread_id"],
        "objective_hash": objective_hash(str(record["objective"])),
        "goal_created_at": normalized_goal["created_at"],
    }
    if binding != observed_binding:
        raise TaskGoalConflict(task_id, "Goal does not match the Task binding")
    return normalized_goal


def record_goal_complete(task_id: str, goal: Mapping[str, Any]) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    initial = _load_task(normalized_task_id)
    lock_file = _with_actor_lock(initial["actor_target"])
    with lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            record = _load_task(normalized_task_id)
            normalized_goal = _require_bound_goal(normalized_task_id, record, goal)
            if normalized_goal["status"] != "complete":
                raise TaskGoalConflict(normalized_task_id, "only a complete Goal can complete a Task")
            if record["status"] == COMPLETED:
                return {
                    "ok": True,
                    "task_id": normalized_task_id,
                    "task": record,
                    "outcome": "goal_complete",
                    "state_changed": False,
                }
            if record["status"] != ACTIVE:
                raise TaskGoalConflict(normalized_task_id, f"Task status {record['status']} cannot complete")
            now = runtime_files.now_iso()
            binding = record["goal_binding"]
            record.update(
                {
                    "status": COMPLETED,
                    "result": {
                        "type": "goal_terminal",
                        "goal_status": "complete",
                        "thread_id": binding["thread_id"],
                        "objective_hash": binding["objective_hash"],
                        "goal_created_at": binding["goal_created_at"],
                        "goal_updated_at": normalized_goal["updated_at"],
                        "token_budget": normalized_goal["token_budget"],
                        "tokens_used": normalized_goal["tokens_used"],
                        "time_used_seconds": normalized_goal["time_used_seconds"],
                        "recorded_at": now,
                    },
                    "updated_at": now,
                }
            )
            persisted = _persist_task(record)
            return {
                "ok": True,
                "task_id": normalized_task_id,
                "task": persisted,
                "outcome": "goal_complete",
                "state_changed": True,
            }
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def record_task_cancel(task_id: str, reason: str) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    normalized_reason = _require_text(reason, "reason")
    initial = _load_task(normalized_task_id)
    lock_file = _with_actor_lock(initial["actor_target"])
    with lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            record = _load_task(normalized_task_id)
            if record["status"] == CANCELED:
                if record["result"]["reason"] != normalized_reason:
                    raise TaskGoalConflict(normalized_task_id, "Task was canceled with a different reason")
                return {
                    "ok": True,
                    "task_id": normalized_task_id,
                    "task": record,
                    "outcome": "actor_canceled",
                    "state_changed": False,
                }
            if record["status"] != ACTIVE:
                raise TaskGoalConflict(normalized_task_id, f"Task status {record['status']} cannot cancel")
            now = runtime_files.now_iso()
            record.update(
                {
                    "status": CANCELED,
                    "result": {
                        "type": "actor_canceled",
                        "reason": normalized_reason,
                        "recorded_at": now,
                    },
                    "updated_at": now,
                }
            )
            persisted = _persist_task(record)
            return {
                "ok": True,
                "task_id": normalized_task_id,
                "task": persisted,
                "outcome": "actor_canceled",
                "state_changed": True,
            }
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def task_summary(task: Mapping[str, Any]) -> dict[str, Any]:
    value = _validate_task(task)
    return {
        "task_id": value["id"],
        "id": value["id"],
        "demand_ref": _actor_demand_ref(value["demand_ref"]),
        "objective": value["objective"],
        "selection": _copy(value["selection"]),
        "goal_binding": _copy(value["goal_binding"]) if value["goal_binding"] is not None else None,
        "status": value["status"],
        "result": _copy(value["result"]) if value["result"] is not None else None,
        "updated_at": value["updated_at"],
    }


def actor_task_projection(*, actor_profile: ActorIdentityProfile) -> dict[str, object]:
    if not isinstance(actor_profile, ActorIdentityProfile):
        raise ValueError("actor_profile must be an ActorIdentityProfile")
    actor_target = {
        "actor_id": actor_profile.identity.id,
        "role_id": actor_profile.role_id,
    }
    records = list_tasks(actor_target=actor_target)
    classified = [(record, task_summary(record)) for record in records]
    tasks = [summary for _record, summary in classified]
    active_tasks = [summary for record, summary in classified if record["status"] == ACTIVE]
    terminal_tasks = [summary for record, summary in classified if record["status"] in TERMINAL_TASK_STATUSES]
    return {
        "tasks": tasks,
        "active_tasks": active_tasks,
        "terminal_tasks": terminal_tasks,
        "task_count": len(tasks),
        "active_count": len(active_tasks),
        "terminal_count": len(terminal_tasks),
    }


def actor_task_detail(task_id: str) -> dict[str, Any]:
    task = _load_task(runtime_files.require_id(task_id, "task id"))
    task["demand_ref"] = _actor_demand_ref(task["demand_ref"])
    return task
