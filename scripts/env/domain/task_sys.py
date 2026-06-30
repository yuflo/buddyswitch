#!/usr/bin/env python3
"""Minimal task sys substrate for actor-driving inbound."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping
from uuid import uuid4

from env.repos import runtime_files

TASK_STATUSES = (
    "new",
    "side_processing",
    "closed",
    "needs_parent",
    "parent_processing",
    "checkpoint",
    "runtime_failed",
    "side_no_result",
    "side_timed_out",
)
ACTIVE_TASK_STATUSES = ("new", "side_processing", "needs_parent", "parent_processing", "checkpoint")
RECOVERABLE_TASK_STATUSES = ("runtime_failed", "side_no_result", "side_timed_out")
TASK_CLOSE_STATUSES = ("side_processing", "parent_processing", "closed")
RUNTIME_INSTRUCTION_TYPES = ("start_side", "submit_parent", "interrupt_submit_parent", "no_actor_action")
INITIAL_PROCESSORS = ("side", "none", "checkpoint")
SIDE_RESULT_OUTCOMES = ("need_parent",)
CHECKPOINT_UPDATE_OUTCOMES = ("close", "continue")


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


def _normalize_initial_processor(value: Any) -> str:
    if value is None:
        return "side"
    if value not in INITIAL_PROCESSORS:
        raise ValueError(f"initial_processor must be one of {', '.join(INITIAL_PROCESSORS)}")
    return str(value)


def _normalize_side_result_outcome(value: Any) -> str:
    if value == "close":
        raise ValueError("record_side_result no longer closes tasks; use task_sys.close")
    if value not in SIDE_RESULT_OUTCOMES:
        raise ValueError(f"side result outcome must be one of {', '.join(SIDE_RESULT_OUTCOMES)}")
    return str(value)


def _normalize_checkpoint_update_outcome(value: Any) -> str:
    if value not in CHECKPOINT_UPDATE_OUTCOMES:
        raise ValueError(f"checkpoint update outcome must be one of {', '.join(CHECKPOINT_UPDATE_OUTCOMES)}")
    return str(value)


def _normalize_recoverable_task_status(value: Any) -> str:
    if value not in RECOVERABLE_TASK_STATUSES:
        raise ValueError(f"side runtime failure status must be one of {', '.join(RECOVERABLE_TASK_STATUSES)}")
    return str(value)


def _normalize_parent_handoff_params(value: Any) -> dict[str, Any]:
    params = _payload_copy(_require_mapping(value, "params"))
    allowed = {"parent_frame_context", "relation", "interrupt", "ordering"}
    unknown = sorted(key for key in params if key not in allowed)
    if unknown:
        raise ValueError(f"params has unsupported fields: {', '.join(unknown)}")
    if "parent_frame_context" in params:
        params["parent_frame_context"] = _payload_copy(_require_mapping(params["parent_frame_context"], "params.parent_frame_context"))
    if "relation" in params:
        params["relation"] = _require_text(params["relation"], "params.relation")
    if "interrupt" in params and not isinstance(params["interrupt"], bool):
        raise ValueError("params.interrupt must be a bool")
    if "ordering" in params:
        params["ordering"] = _payload_copy(_require_mapping(params["ordering"], "params.ordering"))
    if "interrupt" not in params:
        params["interrupt"] = False
    return params


def _task_sys_tasks_dir() -> Any:
    return runtime_files.OBJECTS_ROOT / "task-sys" / "tasks"


def _task_file(task_id: str) -> Any:
    return _task_sys_tasks_dir() / f"{runtime_files.require_id(task_id, 'task id')}.json"


def _new_task_id(source_type: str) -> str:
    return f"task-{runtime_files.slugify(source_type)}-{uuid4().hex[:12]}"


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
    return {
        "kind": "task_sys.parent_frame",
        "task_id": task_id,
        "source": {
            "type": source_type,
            "ref": _payload_copy(_require_mapping(record.get("source_ref"), "task.source_ref")),
        },
        "actor_target": _normalize_actor_target(record.get("actor_target")),
        "inbound_context": _payload_copy(_require_mapping(record.get("inbound_context"), "task.inbound_context")),
        "side_result": _payload_copy(_require_mapping(record.get("side_result"), "task.side_result")),
        "parent_handoff_params": _payload_copy(_require_mapping(record.get("parent_handoff_params"), "task.parent_handoff_params")),
    }


def _checkpoint_frame(record: Mapping[str, Any]) -> dict[str, Any]:
    task_id = runtime_files.require_id(_require_text(record.get("id"), "task.id"), "task id")
    metadata = _payload_copy(_require_mapping(record.get("checkpoint_metadata"), "task.checkpoint_metadata"))
    return {
        "kind": "task_sys.checkpoint",
        "task_id": task_id,
        "source": {
            "type": _require_text(record.get("source_type"), "task.source_type"),
            "ref": _payload_copy(_require_mapping(record.get("source_ref"), "task.source_ref")),
        },
        "actor_target": _normalize_actor_target(record.get("actor_target")),
        "completed_turn": _payload_copy(_require_mapping(record.get("inbound_context"), "task.inbound_context")),
        "checkpoint_state": metadata.get("state") if isinstance(metadata.get("state"), str) else record.get("status"),
        "current_task_context": _payload_copy(_require_mapping(metadata.get("current_task_context", {}), "checkpoint.current_task_context")),
        "pending_task_context": list(metadata.get("pending_task_context") if isinstance(metadata.get("pending_task_context"), list) else []),
        "legal_operations": [
            {
                "tool": "task_sys",
                "action": "checkpoint_update",
                "required_params": ["task_id", "outcome"],
                "outcomes": ["close", "continue"],
            }
        ],
        "constraints": [
            "Do not recommend the next task.",
            "Do not make decisions for Codex.",
            "Choose a legal operation based on current work state.",
        ],
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


def active_tasks_for_actor(actor_target: Mapping[str, Any]) -> list[dict[str, Any]]:
    return list_tasks(actor_target=actor_target, statuses=ACTIVE_TASK_STATUSES)


def recoverable_tasks_for_actor(actor_target: Mapping[str, Any]) -> list[dict[str, Any]]:
    return list_tasks(actor_target=actor_target, statuses=RECOVERABLE_TASK_STATUSES)


def has_active_task_for_actor(actor_target: Mapping[str, Any]) -> bool:
    return bool(active_tasks_for_actor(actor_target))


def ingest(envelope: Mapping[str, Any]) -> dict[str, Any]:
    payload = _require_mapping(envelope, "envelope")
    source = _normalize_source(payload.get("source"))
    actor_target = _normalize_actor_target(payload.get("actor_target"))
    context = _normalize_context(payload.get("context"))
    initial_processor = _normalize_initial_processor(payload.get("initial_processor"))

    task_id = _new_task_id(str(source["type"]))
    now = runtime_files.now_iso()
    if initial_processor == "none":
        status = "closed"
        active_processor = None
        checkpoint_metadata: dict[str, Any] = {}
    elif initial_processor == "checkpoint":
        status = "checkpoint"
        active_processor = "checkpoint"
        checkpoint_metadata = {"state": "awaiting_update"}
    else:
        status = "side_processing"
        active_processor = "side"
        checkpoint_metadata = {}
    record = {
        "id": task_id,
        "source_type": source["type"],
        "source_ref": _payload_copy(source["ref"]),
        "actor_target": actor_target,
        "inbound_context": context,
        "status": status,
        "active_processor": active_processor,
        "parent_handoff_params": None,
        "side_result": None,
        "checkpoint_metadata": checkpoint_metadata,
        "created_at": now,
        "updated_at": now,
    }
    persisted = _persist_task(record)

    if initial_processor == "none":
        instruction = runtime_instruction("no_actor_action", task_id=task_id, actor_target=actor_target)
    elif initial_processor == "checkpoint":
        frame = _checkpoint_frame(persisted)
        instruction = runtime_instruction("submit_parent", task_id=task_id, actor_target=actor_target, frame=frame)
    else:
        frame = _side_frame(task_id=task_id, source=source, actor_target=actor_target, context=context)
        instruction = runtime_instruction("start_side", task_id=task_id, actor_target=actor_target, frame=frame)

    return {"ok": True, "task_id": task_id, "task": persisted, "instruction": instruction}


def record_task_close(task_id: str, update: Mapping[str, Any]) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    payload = _require_mapping(update, "task close")
    record = _load_task(normalized_task_id)
    status = record.get("status")

    if status == "closed":
        return {"ok": True, "task_id": normalized_task_id, "outcome": "close", "task": record, "state_changed": False}
    if status == "checkpoint":
        raise ValueError("checkpoint tasks must be updated with task_sys.checkpoint_update")
    if status not in TASK_CLOSE_STATUSES:
        raise ValueError("task must be in side_processing or parent_processing before close")

    processor = record.get("active_processor")
    if processor not in {"side", "parent"}:
        raise ValueError("task active_processor must be side or parent before close")
    now = runtime_files.now_iso()
    close_result: dict[str, Any] = {"processor": processor, "updated_at": now}
    summary = payload.get("summary")
    if isinstance(summary, str) and summary.strip():
        close_result["summary"] = summary.strip()
    record.update(
        {
            "status": "closed",
            "active_processor": None,
            "close_result": close_result,
            "updated_at": now,
        }
    )
    if processor == "side":
        record["parent_handoff_params"] = None

    persisted = _persist_task(record)
    return {"ok": True, "task_id": normalized_task_id, "outcome": "close", "task": persisted, "state_changed": True}


def record_side_need_parent(task_id: str, result: Mapping[str, Any]) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    payload = _require_mapping(result, "side need_parent result")
    params = _normalize_parent_handoff_params(payload.get("params"))
    record = _load_task(normalized_task_id)
    if record.get("status") != "side_processing":
        raise ValueError("task must be in side_processing status before parent handoff")
    now = runtime_files.now_iso()
    record.update(
        {
            "status": "needs_parent",
            "active_processor": None,
            "parent_handoff_params": params,
            "side_result": {"outcome": "need_parent", "params": _payload_copy(params)},
            "updated_at": now,
        }
    )

    persisted = _persist_task(record)
    return {"ok": True, "task_id": normalized_task_id, "outcome": "need_parent", "task": persisted, "state_changed": True}


def record_side_result(task_id: str, result: Mapping[str, Any]) -> dict[str, Any]:
    payload = _require_mapping(result, "side result")
    _normalize_side_result_outcome(payload.get("outcome"))
    return record_side_need_parent(task_id, {"params": payload.get("params")})


def record_side_runtime_failure(task_id: str, failure: Mapping[str, Any]) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    payload = _payload_copy(_require_mapping(failure, "side runtime failure"))
    status = _normalize_recoverable_task_status(payload.pop("status", None))
    record = _load_task(normalized_task_id)
    if record.get("status") != "side_processing":
        raise ValueError("task must be in side_processing status before side runtime failure")

    now = runtime_files.now_iso()
    failure_result: dict[str, Any] = {
        "stage": _require_text(payload.get("stage"), "failure.stage"),
        "processor": _require_text(payload.get("processor", "side"), "failure.processor"),
        "error": _require_text(payload.get("error"), "failure.error"),
        "updated_at": now,
    }
    retryable = payload.get("retryable")
    if retryable is not None:
        if not isinstance(retryable, bool):
            raise ValueError("failure.retryable must be a bool")
        failure_result["retryable"] = retryable
    attempts = payload.get("attempts")
    if attempts is not None:
        if not isinstance(attempts, int) or attempts < 1:
            raise ValueError("failure.attempts must be a positive integer")
        failure_result["attempts"] = attempts
    last_side_thread_id = payload.get("last_side_thread_id")
    if isinstance(last_side_thread_id, str) and last_side_thread_id.strip():
        failure_result["last_side_thread_id"] = last_side_thread_id.strip()
    cleanup = payload.get("cleanup")
    if cleanup is not None:
        failure_result["cleanup"] = _payload_copy(_require_mapping(cleanup, "failure.cleanup"))

    record.update(
        {
            "status": status,
            "active_processor": None,
            "failure_result": failure_result,
            "updated_at": now,
        }
    )
    persisted = _persist_task(record)
    return {
        "ok": True,
        "task_id": normalized_task_id,
        "outcome": status,
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

    close_result = record.get("close_result")
    if record.get("status") == "closed" and isinstance(close_result, Mapping):
        normalized_close = _payload_copy(close_result)
        if normalized_close.get("processor") != "side":
            raise ValueError("side cleanup can only update side close results")
        normalized_close["side_thread_id"] = side_thread_id
        normalized_close["cleanup"] = cleanup
        normalized_close["updated_at"] = now
        record.update({"close_result": normalized_close, "updated_at": now})
        persisted = _persist_task(record)
        return {"ok": True, "task_id": normalized_task_id, "task": persisted, "state_changed": True}

    side_result = record.get("side_result")
    if isinstance(side_result, Mapping) and side_result.get("outcome") == "need_parent":
        normalized_side_result = _payload_copy(side_result)
        normalized_side_result["side_thread_id"] = side_thread_id
        normalized_side_result["cleanup"] = cleanup
        normalized_side_result["updated_at"] = now
        record.update({"side_result": normalized_side_result, "updated_at": now})
        persisted = _persist_task(record)
        return {"ok": True, "task_id": normalized_task_id, "task": persisted, "state_changed": True}

    raise ValueError("task must have a side close or side need_parent result before side cleanup")


def get_task(task_id: str) -> dict[str, Any]:
    return _load_task(runtime_files.require_id(task_id, "task id"))


def parent_handoff_instruction(task_id: str) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    record = _load_task(normalized_task_id)
    if record.get("status") != "needs_parent":
        raise ValueError("task must be in needs_parent status before parent handoff")
    params = _require_mapping(record.get("parent_handoff_params"), "task.parent_handoff_params")
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
    if record.get("status") != "needs_parent":
        raise ValueError("task must be in needs_parent status before parent processing starts")
    _require_mapping(record.get("parent_handoff_params"), "task.parent_handoff_params")
    now = runtime_files.now_iso()
    record.update(
        {
            "status": "parent_processing",
            "active_processor": "parent",
            "updated_at": now,
        }
    )
    persisted = _persist_task(record)
    return {"ok": True, "task_id": normalized_task_id, "task": persisted}


def record_checkpoint_update(task_id: str, update: Mapping[str, Any]) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    payload = _require_mapping(update, "checkpoint update")
    outcome = _normalize_checkpoint_update_outcome(payload.get("outcome"))
    record = _load_task(normalized_task_id)
    if record.get("status") != "checkpoint":
        raise ValueError("task must be in checkpoint status before checkpoint update")
    now = runtime_files.now_iso()
    metadata = _payload_copy(_require_mapping(record.get("checkpoint_metadata"), "task.checkpoint_metadata"))
    last_update: dict[str, Any] = {"outcome": outcome, "updated_at": now}
    summary = payload.get("summary")
    if isinstance(summary, str) and summary.strip():
        last_update["summary"] = summary.strip()
    metadata["last_update"] = last_update
    if outcome == "close":
        metadata["state"] = "closed"
        record.update({"status": "closed", "active_processor": None, "checkpoint_metadata": metadata, "updated_at": now})
    else:
        metadata["state"] = "awaiting_update"
        record.update({"status": "checkpoint", "active_processor": "checkpoint", "checkpoint_metadata": metadata, "updated_at": now})
    persisted = _persist_task(record)
    return {
        "ok": True,
        "task_id": normalized_task_id,
        "outcome": outcome,
        "task": persisted,
        "frame": _checkpoint_frame(persisted),
    }
