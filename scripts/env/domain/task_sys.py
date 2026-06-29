#!/usr/bin/env python3
"""Minimal task sys substrate for actor-driving inbound."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping
from uuid import uuid4

from env.repos import runtime_files

TASK_STATUSES = ("new", "side_processing", "closed", "needs_parent", "parent_processing", "checkpoint")
ACTIVE_TASK_STATUSES = ("new", "side_processing", "needs_parent", "parent_processing", "checkpoint")
RUNTIME_INSTRUCTION_TYPES = ("start_side", "submit_parent", "interrupt_submit_parent", "no_actor_action")
INITIAL_PROCESSORS = ("side", "none", "checkpoint")
SIDE_RESULT_OUTCOMES = ("close", "need_parent")
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
    if value not in SIDE_RESULT_OUTCOMES:
        raise ValueError(f"side result outcome must be one of {', '.join(SIDE_RESULT_OUTCOMES)}")
    return str(value)


def _normalize_checkpoint_update_outcome(value: Any) -> str:
    if value not in CHECKPOINT_UPDATE_OUTCOMES:
        raise ValueError(f"checkpoint update outcome must be one of {', '.join(CHECKPOINT_UPDATE_OUTCOMES)}")
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


def record_side_result(task_id: str, result: Mapping[str, Any]) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    payload = _require_mapping(result, "side result")
    outcome = _normalize_side_result_outcome(payload.get("outcome"))
    record = _load_task(normalized_task_id)
    now = runtime_files.now_iso()

    if outcome == "close":
        summary_value = payload.get("summary")
        side_result: dict[str, Any] = {"outcome": "close"}
        if isinstance(summary_value, str) and summary_value.strip():
            side_result["summary"] = summary_value.strip()
        record.update(
            {
                "status": "closed",
                "active_processor": None,
                "parent_handoff_params": None,
                "side_result": side_result,
                "updated_at": now,
            }
        )
    else:
        params = _normalize_parent_handoff_params(payload.get("params"))
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
    return {"ok": True, "task_id": normalized_task_id, "outcome": outcome, "task": persisted}


def get_task(task_id: str) -> dict[str, Any]:
    return _load_task(runtime_files.require_id(task_id, "task id"))


def parent_handoff_instruction(task_id: str) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task id")
    record = _load_task(normalized_task_id)
    if record.get("status") != "needs_parent":
        raise ValueError("task must be in needs_parent status before parent handoff")
    params = _require_mapping(record.get("parent_handoff_params"), "task.parent_handoff_params")
    instruction_type = "interrupt_submit_parent" if params.get("interrupt") is True else "submit_parent"
    now = runtime_files.now_iso()
    record.update(
        {
            "status": "parent_processing",
            "active_processor": "parent",
            "updated_at": now,
        }
    )
    persisted = _persist_task(record)
    return runtime_instruction(
        instruction_type,
        task_id=normalized_task_id,
        actor_target=_normalize_actor_target(persisted.get("actor_target")),
        frame=_parent_frame(persisted),
    )


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
