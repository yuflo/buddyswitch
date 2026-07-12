#!/usr/bin/env python3
"""Minimal task sys substrate for actor-driving inbound."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping
from uuid import uuid4

from env.domain.identity import ActorIdentityProfile
from env.repos import runtime_files

TASK_STATUSES = ("in_progress", "completed", "canceled")
ACTIVE_TASK_STATUSES = ("in_progress",)
RECOVERABLE_TASK_REASONS = ("runtime_failed", "side_no_result", "side_timed_out")
TASK_RELATION_KINDS = ("independent", "after", "before")
RUNTIME_INSTRUCTION_TYPES = ("start_side", "submit_parent", "interrupt_submit_parent")


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


def _default_task_relation() -> dict[str, Any]:
    return {"kind": "independent", "target_task_id": None}


def _normalize_task_desc(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("task_desc must be a non-empty string shorter than 50 characters")
    normalized = value.strip()
    if not normalized:
        raise ValueError("task_desc must be a non-empty string shorter than 50 characters")
    if len(normalized) >= 50:
        raise ValueError("task_desc must be shorter than 50 characters")
    return normalized


def _normalize_task_relation(
    value: Any,
    *,
    current_task_id: str,
    actor_target: Mapping[str, Any],
) -> dict[str, Any]:
    relation = _require_mapping(value, "task_relation")
    kind = _require_text(relation.get("kind"), "task_relation.kind")
    if kind not in TASK_RELATION_KINDS:
        raise ValueError(f"task_relation.kind must be one of {', '.join(TASK_RELATION_KINDS)}")
    target_value = relation.get("target_task_id")
    if kind == "independent":
        if target_value is not None:
            raise ValueError("task_relation.target_task_id must be null for independent relation")
        return _default_task_relation()
    if not isinstance(target_value, str) or not target_value.strip():
        raise ValueError("task_relation.target_task_id is required for after or before relation")
    target_task_id = runtime_files.require_id(target_value.strip(), "task_relation.target_task_id")
    if target_task_id == current_task_id:
        raise ValueError("task_relation target_task_id cannot reference self")
    try:
        target_task = _load_task(target_task_id)
    except ValueError as exc:
        raise ValueError(f"task_relation target task not found: {target_task_id}") from exc
    target_actor = target_task.get("actor_target")
    if not isinstance(target_actor, Mapping) or _normalize_actor_target(target_actor) != _normalize_actor_target(actor_target):
        raise ValueError("task_relation target task must belong to the same actor")
    return {"kind": kind, "target_task_id": target_task_id}


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


def _recorded_task_desc(record: Mapping[str, Any]) -> str:
    value = record.get("task_desc")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("task analysis must be recorded before parent handoff")
    return value.strip()


def _recorded_task_relation(record: Mapping[str, Any]) -> dict[str, Any]:
    relation = _require_mapping(record.get("task_relation"), "task.task_relation")
    kind = relation.get("kind")
    target_task_id = relation.get("target_task_id")
    if kind not in TASK_RELATION_KINDS:
        raise ValueError("task analysis must be recorded before parent handoff")
    if kind == "independent" and target_task_id is not None:
        raise ValueError("task analysis must be recorded before parent handoff")
    if kind in {"after", "before"} and (not isinstance(target_task_id, str) or not target_task_id.strip()):
        raise ValueError("task analysis must be recorded before parent handoff")
    return {"kind": str(kind), "target_task_id": target_task_id}


def _is_active_task(record: Mapping[str, Any]) -> bool:
    if record.get("status") != "in_progress":
        return False
    result = _execution_result(record)
    return not (isinstance(result, Mapping) and result.get("type") == "failure")


def _is_recoverable_task(record: Mapping[str, Any]) -> bool:
    if record.get("status") != "in_progress":
        return False
    result = _execution_result(record)
    return isinstance(result, Mapping) and result.get("type") == "failure" and result.get("reason") in RECOVERABLE_TASK_REASONS


def _task_sys_tasks_dir() -> Any:
    return runtime_files.OBJECTS_ROOT / "task-sys" / "tasks"


def _task_file(task_id: str) -> Any:
    return _task_sys_tasks_dir() / f"{runtime_files.require_id(task_id, 'task id')}.json"


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


def _reject_unsupported_ingest_fields(payload: Mapping[str, Any]) -> None:
    allowed = {"source", "actor_target", "context"}
    unsupported = sorted(key for key in payload if key not in allowed)
    if unsupported:
        raise ValueError(f"envelope has unsupported fields: {', '.join(unsupported)}")


def _reject_retired_source(source_type: str) -> None:
    retired_source = "{}_{}.{}".format("app", "server", "turn_completed")
    if source_type == retired_source:
        raise ValueError(f"{retired_source} is not a Task Sys ingest source")


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
        "task_desc": _recorded_task_desc(record),
        "task_relation": _recorded_task_relation(record),
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
    task_relation = task.get("task_relation")
    execution = task.get("execution")
    events = task.get("events")
    return {
        "task_id": task_id,
        "id": task_id,
        "source_type": task.get("source_type"),
        "source_ref": _payload_copy(source_ref) if isinstance(source_ref, Mapping) else {},
        "status": task.get("status"),
        "task_desc": task.get("task_desc"),
        "task_relation": _payload_copy(task_relation) if isinstance(task_relation, Mapping) else None,
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


def ingest(envelope: Mapping[str, Any]) -> dict[str, Any]:
    payload = _require_mapping(envelope, "envelope")
    _reject_unsupported_ingest_fields(payload)
    source = _normalize_source(payload.get("source"))
    _reject_retired_source(str(source["type"]))
    actor_target = _normalize_actor_target(payload.get("actor_target"))
    context = _normalize_context(payload.get("context"))

    task_id = _new_task_id(str(source["type"]))
    now = runtime_files.now_iso()
    record = {
        "id": task_id,
        "source_type": source["type"],
        "source_ref": _payload_copy(source["ref"]),
        "actor_target": actor_target,
        "inbound_context": context,
        "status": "in_progress",
        "task_desc": None,
        "task_relation": _default_task_relation(),
        "execution": _new_execution("side"),
        "events": [
            _event("created", at=now),
            _event("side_frame_started", at=now, data={"instruction": "start_side"}),
        ],
        "created_at": now,
        "updated_at": now,
    }
    persisted = _persist_task(record)

    frame = _side_frame(task_id=task_id, source=source, actor_target=actor_target, context=context)
    instruction = runtime_instruction("start_side", task_id=task_id, actor_target=actor_target, frame=frame)

    return {"ok": True, "task_id": task_id, "task": persisted, "instruction": instruction}


def record_task_close(task_id: str, update: Mapping[str, Any]) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    payload = _require_mapping(update, "task close")
    record = _load_task(normalized_task_id)
    status = record.get("status")

    existing_result = _execution_result(record)
    if status == "completed" and isinstance(existing_result, Mapping) and existing_result.get("type") == "completion":
        return {"ok": True, "task_id": normalized_task_id, "outcome": "close", "task": record, "state_changed": False}
    if status != "in_progress":
        raise ValueError("task must be in progress with side or parent processor before close")

    processor = _execution_processor(record)
    if processor not in {"side", "parent"}:
        raise ValueError("task must have side or parent processor before close")
    now = runtime_files.now_iso()
    completion_result: dict[str, Any] = {"type": "completion", "processor": processor, "updated_at": now}
    summary = payload.get("summary")
    if isinstance(summary, str) and summary.strip():
        completion_result["summary"] = summary.strip()
    execution = _payload_copy(_execution(record))
    execution["processor"] = None
    execution["result"] = completion_result
    record.update({"status": "completed", "execution": execution, "updated_at": now})
    _append_event(record, "closed", at=now, data={"processor": processor})

    persisted = _persist_task(record)
    return {"ok": True, "task_id": normalized_task_id, "outcome": "close", "task": persisted, "state_changed": True}


def record_side_need_parent(task_id: str, result: Mapping[str, Any]) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    payload = _require_mapping(result, "side need_parent result")
    params = _normalize_handoff_params(payload.get("params"))
    record = _load_task(normalized_task_id)
    if record.get("status") != "in_progress" or _execution_processor(record) != "side" or _execution_result(record) is not None:
        raise ValueError("task must be in progress with side processor before parent handoff")
    _recorded_task_desc(record)
    _recorded_task_relation(record)
    now = runtime_files.now_iso()
    execution = _payload_copy(_execution(record))
    execution["processor"] = None
    execution["handoff"] = params
    record.update({"status": "in_progress", "execution": execution, "updated_at": now})
    _append_event(record, "side_parent_requested", at=now, data={"interrupt": params.get("interrupt") is True})

    persisted = _persist_task(record)
    return {"ok": True, "task_id": normalized_task_id, "outcome": "need_parent", "task": persisted, "state_changed": True}


def record_task_analysis_update(task_id: str, update: Mapping[str, Any]) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    payload = _require_mapping(update, "task analysis update")
    record = _load_task(normalized_task_id)
    task_desc = _normalize_task_desc(payload.get("task_desc"))
    task_relation = _normalize_task_relation(
        payload.get("task_relation"),
        current_task_id=normalized_task_id,
        actor_target=_normalize_actor_target(record.get("actor_target")),
    )
    now = runtime_files.now_iso()
    record.update(
        {
            "task_desc": task_desc,
            "task_relation": task_relation,
            "updated_at": now,
        }
    )
    _append_event(record, "task_analysis_updated", at=now, data={"relation_kind": task_relation["kind"]})
    persisted = _persist_task(record)
    return {
        "ok": True,
        "task_id": normalized_task_id,
        "outcome": "task_analysis_updated",
        "task": persisted,
        "state_changed": True,
    }


def record_side_runtime_failure(task_id: str, failure: Mapping[str, Any]) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    payload = _payload_copy(_require_mapping(failure, "side runtime failure"))
    reason = _normalize_failure_reason(payload.pop("reason", None))
    record = _load_task(normalized_task_id)
    if record.get("status") != "in_progress" or _execution_processor(record) != "side":
        raise ValueError("task must be in progress with side processor before side runtime failure")

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
    record.update({"status": "in_progress", "execution": execution, "updated_at": now})
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
    if record.get("status") == "completed" and isinstance(execution_result, Mapping) and execution_result.get("type") == "completion":
        normalized_result = _payload_copy(execution_result)
        if normalized_result.get("processor") != "side":
            raise ValueError("side cleanup can only update side close results")
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

    raise ValueError("task must have a side close or side need_parent result before side cleanup")


def get_task(task_id: str) -> dict[str, Any]:
    return _load_task(runtime_files.require_id(task_id, "task id"))


def parent_handoff_instruction(task_id: str) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    record = _load_task(normalized_task_id)
    if record.get("status") != "in_progress" or _execution_handoff(record) is None:
        raise ValueError("task must have parent handoff before parent handoff instruction")
    params = _require_mapping(_execution_handoff(record), "task.execution.handoff")
    instruction_type = "interrupt_submit_parent" if params.get("interrupt") is True else "submit_parent"
    return runtime_instruction(
        instruction_type,
        task_id=normalized_task_id,
        actor_target=_normalize_actor_target(record.get("actor_target")),
        frame=_parent_frame(record),
    )


def record_parent_handoff_started(task_id: str) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    record = _load_task(normalized_task_id)
    if record.get("status") != "in_progress":
        raise ValueError("task must be in progress before parent processing starts")
    _require_mapping(_execution_handoff(record), "task.execution.handoff")
    now = runtime_files.now_iso()
    execution = _payload_copy(_execution(record))
    execution["processor"] = "parent"
    record.update({"status": "in_progress", "execution": execution, "updated_at": now})
    _append_event(record, "parent_handoff_started", at=now)
    persisted = _persist_task(record)
    return {"ok": True, "task_id": normalized_task_id, "task": persisted}
