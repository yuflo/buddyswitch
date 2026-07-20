"""Minimal task sys substrate for actor-driving inbound."""

from __future__ import annotations

from copy import deepcopy
import fcntl
from typing import Any, Mapping
from uuid import uuid4

from env.domain.identity import ActorIdentityProfile
from env.repos import runtime_files

SIDE_PROCESSING = "in_progress.side_processing"
AWAITING_PARENT = "in_progress.awaiting_parent"
PARENT_PROCESSING = "in_progress.parent_processing"
COMPLETED = "completed"
CANCELED = "canceled"

TASK_STATUSES = (SIDE_PROCESSING, AWAITING_PARENT, PARENT_PROCESSING, COMPLETED, CANCELED)
ACTIVE_TASK_STATUSES = (SIDE_PROCESSING, AWAITING_PARENT, PARENT_PROCESSING)
LEGAL_TASK_TRANSITIONS = {
    "need_parent": {SIDE_PROCESSING: AWAITING_PARENT},
    "parent_accepted": {AWAITING_PARENT: PARENT_PROCESSING},
    "close": {SIDE_PROCESSING: COMPLETED, PARENT_PROCESSING: COMPLETED},
    "cancel": {
        SIDE_PROCESSING: CANCELED,
        AWAITING_PARENT: CANCELED,
        PARENT_PROCESSING: CANCELED,
    },
}
RECOVERABLE_TASK_REASONS = ("runtime_failed", "side_no_result", "side_timed_out")
RUNTIME_INSTRUCTION_TYPES = ("start_side", "submit_parent", "interrupt_submit_parent")


class TaskSysError(ValueError):
    code = "E_TASK_SYS"


class TaskSourceConflict(TaskSysError):
    code = "E_TASK_SYS_SOURCE_CONFLICT"

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"Task source already exists with different input: {task_id}")


class TaskActiveConflict(TaskSysError):
    code = "E_TASK_SYS_ACTIVE_CONFLICT"

    def __init__(self, task_id: str, task_status: str) -> None:
        self.task_id = task_id
        self.task_status = task_status
        super().__init__(f"Actor already has active Task {task_id} in status {task_status}")


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _payload_copy(value: Mapping[str, Any]) -> dict[str, Any]:
    return deepcopy(dict(value))


def _normalize_source(value: Any) -> dict[str, Any]:
    source = _require_mapping(value, "source")
    source_type = _require_text(source.get("type"), "source.type")
    source_ref = _payload_copy(_require_mapping(source.get("ref"), "source.ref"))
    return {"type": source_type, "ref": source_ref}


def _normalize_actor_target(value: Any) -> dict[str, str]:
    target = _require_mapping(value, "actor_target")
    return {
        "role_id": runtime_files.require_id(_require_text(target.get("role_id"), "actor_target.role_id"), "actor_target.role_id"),
        "actor_id": runtime_files.require_id(_require_text(target.get("actor_id"), "actor_target.actor_id"), "actor_target.actor_id"),
    }


def _normalize_context(value: Any) -> dict[str, Any]:
    return _payload_copy(_require_mapping(value, "context"))


def _normalize_demand_ref(value: Any) -> dict[str, Any]:
    demand_ref = _require_mapping(value, "demand_ref")
    if set(demand_ref) != {"demand_id", "basis_revision"}:
        raise ValueError("demand_ref must contain exactly demand_id and basis_revision")
    demand_id = runtime_files.require_id(
        _require_text(demand_ref.get("demand_id"), "demand_ref.demand_id"),
        "demand_ref.demand_id",
    )
    if not demand_id.startswith("demand-"):
        raise ValueError("demand_ref.demand_id must be a Demand id")
    basis_revision = demand_ref.get("basis_revision")
    if type(basis_revision) is not int or basis_revision < 1:
        raise ValueError("demand_ref.basis_revision must be a positive integer")
    return {"demand_id": demand_id, "basis_revision": basis_revision}


def _normalize_execution_brief(value: Any) -> dict[str, str]:
    execution_brief = _require_mapping(value, "execution_brief")
    if set(execution_brief) != {"description", "detail"}:
        raise ValueError("execution_brief must contain exactly description and detail")
    return {
        "description": _require_text(execution_brief.get("description"), "execution_brief.description"),
        "detail": _require_text(execution_brief.get("detail"), "execution_brief.detail"),
    }


def _normalize_failure_reason(value: Any) -> str:
    if value not in RECOVERABLE_TASK_REASONS:
        raise ValueError(f"side runtime failure reason must be one of {', '.join(RECOVERABLE_TASK_REASONS)}")
    return str(value)


def _normalize_handoff_params(value: Any) -> dict[str, Any]:
    params = _payload_copy(_require_mapping(value, "params"))
    allowed = {"parent_frame_context", "interrupt", "ordering"}
    unknown = sorted(key for key in params if key not in allowed)
    if unknown:
        raise ValueError(f"params has unsupported fields: {', '.join(unknown)}")
    if "parent_frame_context" in params:
        parent_frame_context = _payload_copy(_require_mapping(params["parent_frame_context"], "params.parent_frame_context"))
    else:
        parent_frame_context = {}
    if "interrupt" in params and not isinstance(params["interrupt"], bool):
        raise ValueError("params.interrupt must be a bool")
    interrupt = params.get("interrupt") is True
    if "ordering" in params:
        ordering = _payload_copy(_require_mapping(params["ordering"], "params.ordering"))
    else:
        ordering = {}
    return {
        "parent_frame_context": parent_frame_context,
        "interrupt": interrupt,
        "ordering": ordering,
        "side_thread_id": None,
        "cleanup": {},
    }


def _new_execution(processor: str | None) -> dict[str, Any]:
    if processor not in {"side", "parent", None}:
        raise ValueError("execution.processor must be side, parent, or null")
    return {"processor": processor, "handoff": None, "result": None}


def _execution(record: Mapping[str, Any]) -> Mapping[str, Any]:
    return _require_mapping(record.get("execution"), "task.execution")


def _execution_processor(record: Mapping[str, Any]) -> str | None:
    processor = _execution(record).get("processor")
    if processor is None:
        return None
    if processor not in {"side", "parent"}:
        raise ValueError("task.execution.processor must be side, parent, or null")
    return str(processor)


def _execution_handoff(record: Mapping[str, Any]) -> Mapping[str, Any] | None:
    handoff = _execution(record).get("handoff")
    if handoff is None:
        return None
    return _require_mapping(handoff, "task.execution.handoff")


def _execution_result(record: Mapping[str, Any]) -> Mapping[str, Any] | None:
    result = _execution(record).get("result")
    if result is None:
        return None
    return _require_mapping(result, "task.execution.result")


def _is_active_task(record: Mapping[str, Any]) -> bool:
    return record.get("status") in ACTIVE_TASK_STATUSES


def _is_recoverable_task(record: Mapping[str, Any]) -> bool:
    if record.get("status") != SIDE_PROCESSING:
        return False
    result = _execution_result(record)
    return isinstance(result, Mapping) and result.get("type") == "failure" and result.get("reason") in RECOVERABLE_TASK_REASONS


def _task_sys_tasks_dir() -> Any:
    return runtime_files.OBJECTS_ROOT / "task-sys" / "tasks"


def _task_file(task_id: str) -> Any:
    return _task_sys_tasks_dir() / f"{runtime_files.require_id(task_id, 'task id')}.json"


def _actor_lock_file(actor_target: Mapping[str, str]) -> Any:
    return (
        runtime_files.LOCAL_ROOT
        / "locks"
        / "task-sys"
        / f"{actor_target['actor_id']}-{actor_target['role_id']}.lock"
    )


def _new_task_id(source_type: str) -> str:
    return f"task-{runtime_files.slugify(source_type)}-{uuid4().hex[:12]}"


def _event(event_type: str, *, at: str, data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {"type": event_type, "at": at}
    if data:
        row["data"] = _payload_copy(data)
    return row


def _append_event(record: dict[str, Any], event_type: str, *, at: str, data: Mapping[str, Any] | None = None) -> None:
    events = record.get("events")
    if not isinstance(events, list):
        events = []
    record["events"] = [*events, _event(event_type, at=at, data=data)]


def _transition_status(record: dict[str, Any], action: str, *, at: str) -> str:
    transitions = LEGAL_TASK_TRANSITIONS.get(action)
    if transitions is None:
        raise ValueError(f"unsupported task lifecycle action: {action}")
    current = record.get("status")
    next_status = transitions.get(current)
    if next_status is None:
        raise ValueError(f"task status {current!r} cannot transition via {action}")
    record.update({"status": next_status, "updated_at": at})
    return next_status


def _reject_unsupported_ingest_fields(payload: Mapping[str, Any]) -> None:
    allowed = {"source", "actor_target", "context"}
    unsupported = sorted(key for key in payload if key not in allowed)
    if unsupported:
        raise ValueError(f"envelope has unsupported fields: {', '.join(unsupported)}")


def _reject_non_task_sys_ingest_source(source_type: str) -> None:
    non_task_sys_sources = (
        "{}_{}.{}".format("app", "server", "turn_completed"),
        "{}.{}".format("user", "input"),
        "{}.{}.{}".format("im", "message", "created"),
    )
    if source_type in non_task_sys_sources:
        raise ValueError(f"{source_type} is not a Task Sys ingest source")


def _side_frame(*, task_id: str, source: Mapping[str, Any], actor_target: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "kind": "task_sys.side_frame",
        "task_id": task_id,
        "source": _payload_copy(source),
        "actor_target": _payload_copy(actor_target),
        "context": _payload_copy(context),
    }


def _parent_frame(record: Mapping[str, Any]) -> dict[str, Any]:
    task_id = runtime_files.require_id(_require_text(record.get("id"), "task.id"), "task id")
    source_type = _require_text(record.get("source_type"), "task.source_type")
    handoff = _payload_copy(_require_mapping(_execution_handoff(record), "task.execution.handoff"))
    return {
        "kind": "task_sys.parent_frame",
        "task_id": task_id,
        "source": {
            "type": source_type,
            "ref": _payload_copy(_require_mapping(record.get("source_ref"), "task.source_ref")),
        },
        "actor_target": _normalize_actor_target(record.get("actor_target")),
        "inbound_context": _payload_copy(_require_mapping(record.get("inbound_context"), "task.inbound_context")),
        "execution_handoff": handoff,
    }


def runtime_instruction(
    instruction_type: str,
    *,
    task_id: str,
    actor_target: Mapping[str, Any],
    frame: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if instruction_type not in RUNTIME_INSTRUCTION_TYPES:
        raise ValueError(f"runtime instruction type must be one of {', '.join(RUNTIME_INSTRUCTION_TYPES)}")
    payload: dict[str, Any] = {
        "type": instruction_type,
        "task_id": runtime_files.require_id(task_id, "task id"),
        "actor_target": _normalize_actor_target(actor_target),
    }
    if frame is not None:
        payload["frame"] = _payload_copy(_require_mapping(frame, "frame"))
    return payload


def _persist_task(record: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _payload_copy(record)
    runtime_files.write_json_object(_task_file(str(normalized["id"])), normalized)
    return normalized


def _load_task(task_id: str) -> dict[str, Any]:
    path = _task_file(task_id)
    if not path.exists():
        raise ValueError(f"task not found: {task_id}")
    return runtime_files.read_json_object(path)


def list_tasks(
    *,
    actor_target: Mapping[str, Any] | None = None,
    statuses: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    tasks_dir = _task_sys_tasks_dir()
    if not tasks_dir.exists():
        return []
    normalized_target = _normalize_actor_target(actor_target) if actor_target is not None else None
    allowed_statuses = set(statuses) if statuses is not None else None
    rows: list[dict[str, Any]] = []
    for path in sorted(tasks_dir.glob("*.json")):
        record = runtime_files.read_json_object(path)
        if normalized_target is not None:
            target = record.get("actor_target")
            if not isinstance(target, Mapping):
                continue
            if _normalize_actor_target(target) != normalized_target:
                continue
        if allowed_statuses is not None and record.get("status") not in allowed_statuses:
            continue
        rows.append(record)
    return rows


def task_summary(task: Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical actor-visible Task summary shape."""

    task_id = task.get("id")
    source_ref = task.get("source_ref")
    execution = task.get("execution")
    events = task.get("events")
    return {
        "task_id": task_id,
        "id": task_id,
        "source_type": task.get("source_type"),
        "source_ref": _payload_copy(source_ref) if isinstance(source_ref, Mapping) else {},
        "status": task.get("status"),
        "execution": _payload_copy(execution) if isinstance(execution, Mapping) else {},
        "updated_at": task.get("updated_at"),
        "event_types": [
            str(event.get("type"))
            for event in events if isinstance(event, Mapping) and event.get("type")
        ] if isinstance(events, list) else [],
    }


def actor_task_projection(*, actor_profile: ActorIdentityProfile) -> dict[str, object]:
    """Read Task records once and return canonical actor-visible summaries."""

    if not isinstance(actor_profile, ActorIdentityProfile):
        raise ValueError("actor_profile must be an ActorIdentityProfile")
    actor_target = _normalize_actor_target(
        {"actor_id": actor_profile.identity.id, "role_id": actor_profile.role_id}
    )
    records: list[dict[str, Any]] = []
    for record in list_tasks():
        target = record.get("actor_target")
        if not isinstance(target, Mapping):
            continue
        try:
            normalized_target = _normalize_actor_target(target)
        except ValueError:
            continue
        if normalized_target == actor_target:
            records.append(record)

    classified = [(record, task_summary(record)) for record in records]
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


def _create_task(
    *,
    source: Mapping[str, Any],
    actor_target: Mapping[str, str],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    lock_path = _actor_lock_file(actor_target)
    runtime_files.require_runtime_workspace_write_root()
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            actor_tasks = list_tasks(actor_target=actor_target)
            for existing in actor_tasks:
                if (
                    existing.get("source_type") == source["type"]
                    and existing.get("source_ref") == source["ref"]
                ):
                    task_id = runtime_files.require_id(existing.get("id"), "task id")
                    if existing.get("inbound_context") != context:
                        raise TaskSourceConflict(task_id)
                    return {
                        "ok": True,
                        "task_id": task_id,
                        "task": existing,
                        "instruction": None,
                        "outcome": "existing",
                        "state_changed": False,
                    }

            for existing in actor_tasks:
                if _is_active_task(existing):
                    task_id = runtime_files.require_id(existing.get("id"), "task id")
                    task_status = _require_text(existing.get("status"), "task.status")
                    raise TaskActiveConflict(task_id, task_status)

            task_id = _new_task_id(str(source["type"]))
            now = runtime_files.now_iso()
            record = {
                "id": task_id,
                "source_type": source["type"],
                "source_ref": _payload_copy(source["ref"]),
                "actor_target": dict(actor_target),
                "inbound_context": _payload_copy(context),
                "status": SIDE_PROCESSING,
                "execution": _new_execution("side"),
                "events": [
                    _event("created", at=now),
                    _event("side_frame_started", at=now, data={"instruction": "start_side"}),
                ],
                "created_at": now,
                "updated_at": now,
            }
            persisted = _persist_task(record)
            frame = _side_frame(
                task_id=task_id,
                source=source,
                actor_target=actor_target,
                context=context,
            )
            instruction = runtime_instruction(
                "start_side",
                task_id=task_id,
                actor_target=actor_target,
                frame=frame,
            )
            return {
                "ok": True,
                "task_id": task_id,
                "task": persisted,
                "instruction": instruction,
                "outcome": "created",
                "state_changed": True,
            }
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def ingest(envelope: Mapping[str, Any]) -> dict[str, Any]:
    payload = _require_mapping(envelope, "envelope")
    _reject_unsupported_ingest_fields(payload)
    source = _normalize_source(payload.get("source"))
    _reject_non_task_sys_ingest_source(str(source["type"]))
    actor_target = _normalize_actor_target(payload.get("actor_target"))
    context = _normalize_context(payload.get("context"))
    return _create_task(source=source, actor_target=actor_target, context=context)


def create(
    *,
    actor_target: Mapping[str, Any],
    demand_ref: Mapping[str, Any],
    execution_brief: Mapping[str, Any],
) -> dict[str, Any]:
    """Create one Demand-sourced Task through the canonical side lifecycle."""

    return _create_task(
        source={"type": "demand", "ref": _normalize_demand_ref(demand_ref)},
        actor_target=_normalize_actor_target(actor_target),
        context={"execution_brief": _normalize_execution_brief(execution_brief)},
    )


def record_task_close(task_id: str, update: Mapping[str, Any]) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    payload = _require_mapping(update, "task close")
    record = _load_task(normalized_task_id)
    status = record.get("status")

    existing_result = _execution_result(record)
    if status == COMPLETED and isinstance(existing_result, Mapping) and existing_result.get("type") == "completion":
        return {"ok": True, "task_id": normalized_task_id, "outcome": "close", "task": record, "state_changed": False}
    processor = "side" if status == SIDE_PROCESSING else "parent" if status == PARENT_PROCESSING else None
    if processor is None:
        raise ValueError(f"task status {status!r} cannot transition via close")
    now = runtime_files.now_iso()
    completion_result: dict[str, Any] = {"type": "completion", "processor": processor, "updated_at": now}
    summary = payload.get("summary")
    if isinstance(summary, str) and summary.strip():
        completion_result["summary"] = summary.strip()
    execution = _payload_copy(_execution(record))
    execution["processor"] = None
    execution["result"] = completion_result
    record["execution"] = execution
    _transition_status(record, "close", at=now)
    _append_event(record, "closed", at=now, data={"processor": processor})

    persisted = _persist_task(record)
    return {"ok": True, "task_id": normalized_task_id, "outcome": "close", "task": persisted, "state_changed": True}


def record_task_cancel(task_id: str, update: Mapping[str, Any]) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    payload = _require_mapping(update, "task cancel")
    record = _load_task(normalized_task_id)
    status = record.get("status")
    existing_result = _execution_result(record)
    if status == CANCELED and isinstance(existing_result, Mapping) and existing_result.get("type") == "cancellation":
        return {"ok": True, "task_id": normalized_task_id, "outcome": "cancel", "task": record, "state_changed": False}
    if status not in ACTIVE_TASK_STATUSES:
        raise ValueError(f"task status {status!r} cannot transition via cancel")

    now = runtime_files.now_iso()
    cancellation_result: dict[str, Any] = {
        "type": "cancellation",
        "previous_status": status,
        "updated_at": now,
    }
    processor = (
        "side"
        if status in {SIDE_PROCESSING, AWAITING_PARENT}
        else "parent"
        if status == PARENT_PROCESSING
        else None
    )
    if processor is not None:
        cancellation_result["processor"] = processor
    reason = payload.get("reason")
    if isinstance(reason, str) and reason.strip():
        cancellation_result["reason"] = reason.strip()
    execution = _payload_copy(_execution(record))
    execution["processor"] = None
    execution["result"] = cancellation_result
    record["execution"] = execution
    _transition_status(record, "cancel", at=now)
    _append_event(record, "canceled", at=now, data={"previous_status": status})

    persisted = _persist_task(record)
    return {"ok": True, "task_id": normalized_task_id, "outcome": "cancel", "task": persisted, "state_changed": True}


def record_side_need_parent(task_id: str, result: Mapping[str, Any]) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    payload = _require_mapping(result, "side need_parent result")
    params = _normalize_handoff_params(payload.get("params"))
    record = _load_task(normalized_task_id)
    if record.get("status") != SIDE_PROCESSING:
        raise ValueError(f"task status {record.get('status')!r} cannot transition via need_parent")
    now = runtime_files.now_iso()
    execution = _payload_copy(_execution(record))
    execution["processor"] = None
    execution["handoff"] = params
    record["execution"] = execution
    _transition_status(record, "need_parent", at=now)
    _append_event(record, "side_parent_requested", at=now, data={"interrupt": params.get("interrupt") is True})

    persisted = _persist_task(record)
    return {"ok": True, "task_id": normalized_task_id, "outcome": "need_parent", "task": persisted, "state_changed": True}


def record_side_runtime_failure(task_id: str, failure: Mapping[str, Any]) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    payload = _payload_copy(_require_mapping(failure, "side runtime failure"))
    reason = _normalize_failure_reason(payload.pop("reason", None))
    record = _load_task(normalized_task_id)
    if record.get("status") != SIDE_PROCESSING:
        raise ValueError("task must be in side processing before side runtime failure")

    now = runtime_files.now_iso()
    result_payload: dict[str, Any] = {
        "type": "failure",
        "reason": reason,
        "stage": _require_text(payload.get("stage"), "failure.stage"),
        "processor": _require_text(payload.get("processor", "side"), "failure.processor"),
        "error": _require_text(payload.get("error"), "failure.error"),
        "updated_at": now,
    }
    retryable = payload.get("retryable")
    if retryable is not None:
        if not isinstance(retryable, bool):
            raise ValueError("failure.retryable must be a bool")
        result_payload["retryable"] = retryable
    attempts = payload.get("attempts")
    if attempts is not None:
        if not isinstance(attempts, int) or attempts < 1:
            raise ValueError("failure.attempts must be a positive integer")
        result_payload["attempts"] = attempts
    last_side_thread_id = payload.get("last_side_thread_id")
    if isinstance(last_side_thread_id, str) and last_side_thread_id.strip():
        result_payload["last_side_thread_id"] = last_side_thread_id.strip()
    cleanup = payload.get("cleanup")
    if cleanup is not None:
        result_payload["cleanup"] = _payload_copy(_require_mapping(cleanup, "failure.cleanup"))

    execution = _payload_copy(_execution(record))
    execution["processor"] = None
    execution["result"] = result_payload
    record.update({"execution": execution, "updated_at": now})
    _append_event(record, "side_runtime_failed", at=now, data={"reason": reason, "stage": result_payload["stage"]})
    persisted = _persist_task(record)
    return {
        "ok": True,
        "task_id": normalized_task_id,
        "outcome": reason,
        "task": persisted,
        "state_changed": True,
    }


def record_side_cleanup(task_id: str, update: Mapping[str, Any]) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    payload = _require_mapping(update, "side cleanup")
    side_thread_id = _require_text(payload.get("side_thread_id"), "cleanup.side_thread_id")
    cleanup = _payload_copy(_require_mapping(payload.get("cleanup"), "cleanup.cleanup"))
    record = _load_task(normalized_task_id)
    now = runtime_files.now_iso()

    execution_result = _execution_result(record)
    if (
        record.get("status") in {COMPLETED, CANCELED}
        and isinstance(execution_result, Mapping)
        and execution_result.get("type") in {"completion", "cancellation"}
    ):
        normalized_result = _payload_copy(execution_result)
        if normalized_result.get("processor") != "side":
            raise ValueError("side cleanup can only update side completion or cancellation results")
        normalized_result["side_thread_id"] = side_thread_id
        normalized_result["cleanup"] = cleanup
        normalized_result["updated_at"] = now
        execution = _payload_copy(_execution(record))
        execution["result"] = normalized_result
        record.update({"execution": execution, "updated_at": now})
        _append_event(record, "side_cleanup_recorded", at=now, data={"side_thread_id": side_thread_id})
        persisted = _persist_task(record)
        return {"ok": True, "task_id": normalized_task_id, "task": persisted, "state_changed": True}

    handoff = _execution_handoff(record)
    if isinstance(handoff, Mapping):
        normalized_handoff = _payload_copy(handoff)
        normalized_handoff["side_thread_id"] = side_thread_id
        normalized_handoff["cleanup"] = cleanup
        normalized_handoff["updated_at"] = now
        execution = _payload_copy(_execution(record))
        execution["handoff"] = normalized_handoff
        record.update({"execution": execution, "updated_at": now})
        _append_event(record, "side_cleanup_recorded", at=now, data={"side_thread_id": side_thread_id})
        persisted = _persist_task(record)
        return {"ok": True, "task_id": normalized_task_id, "task": persisted, "state_changed": True}

    raise ValueError("task must have a side completion, cancellation, or need_parent result before side cleanup")


def get_task(task_id: str) -> dict[str, Any]:
    return _load_task(runtime_files.require_id(task_id, "task id"))


def parent_handoff_instruction(task_id: str) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    record = _load_task(normalized_task_id)
    if record.get("status") != AWAITING_PARENT or _execution_handoff(record) is None:
        raise ValueError("task must be awaiting parent before parent handoff instruction")
    params = _require_mapping(_execution_handoff(record), "task.execution.handoff")
    instruction_type = "interrupt_submit_parent" if params.get("interrupt") is True else "submit_parent"
    return runtime_instruction(
        instruction_type,
        task_id=normalized_task_id,
        actor_target=_normalize_actor_target(record.get("actor_target")),
        frame=_parent_frame(record),
    )


def outcome_instruction(task_id: str) -> dict[str, Any] | None:
    """Return parent attention for one terminal Demand-sourced Task."""

    normalized_task_id = runtime_files.require_id(task_id, "task id")
    record = _load_task(normalized_task_id)
    if record.get("source_type") != "demand":
        return None
    status = record.get("status")
    expected_result_type = {
        COMPLETED: "completion",
        CANCELED: "cancellation",
    }.get(status)
    if expected_result_type is None:
        raise ValueError("Demand-sourced Task must be completed or canceled before outcome attention")
    outcome = _payload_copy(_require_mapping(_execution_result(record), "task.execution.result"))
    if outcome.get("type") != expected_result_type:
        raise ValueError(f"{status} Demand-sourced Task must have a {expected_result_type} result")
    processor = outcome.get("processor")
    if processor not in {"side", "parent"}:
        raise ValueError("Task outcome processor must be side or parent")
    _require_text(outcome.get("updated_at"), "task.execution.result.updated_at")
    demand_ref = _normalize_demand_ref(record.get("source_ref"))
    frame = {
        "kind": "task_sys.outcome_frame",
        "task_id": normalized_task_id,
        "status": status,
        "source": {"type": "demand", "ref": demand_ref},
        "evidence_ref": {
            "type": "task_sys.task",
            "ref": {"task_id": normalized_task_id},
        },
        "outcome": outcome,
    }
    return runtime_instruction(
        "submit_parent",
        task_id=normalized_task_id,
        actor_target=_normalize_actor_target(record.get("actor_target")),
        frame=frame,
    )


def record_parent_handoff_started(task_id: str) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    record = _load_task(normalized_task_id)
    if record.get("status") != AWAITING_PARENT:
        raise ValueError("task must be awaiting parent before parent processing starts")
    _require_mapping(_execution_handoff(record), "task.execution.handoff")
    now = runtime_files.now_iso()
    execution = _payload_copy(_execution(record))
    execution["processor"] = "parent"
    record["execution"] = execution
    _transition_status(record, "parent_accepted", at=now)
    _append_event(record, "parent_handoff_started", at=now)
    persisted = _persist_task(record)
    return {"ok": True, "task_id": normalized_task_id, "task": persisted}
