#!/usr/bin/env python3
"""BuddySwitch daemon core."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol


HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import app_server  # noqa: E402
import daemon_mailbox  # noqa: E402
import daemon_triggers  # noqa: E402
import runtime_event_log  # noqa: E402
import submit_turn as launcher_submit_turn  # noqa: E402
from task_sys_runtime import cleanup_task_sys_side_lease as task_sys_cleanup_task_sys_side_lease  # noqa: E402
from task_sys_runtime import execute_instruction as task_sys_execute_instruction  # noqa: E402
from env.domain.identity import ACTOR_ID_PATTERN, ROLE_ID_PATTERN  # noqa: E402
from env.domain import task_sys  # noqa: E402
from env.repos import identities as identity_repo  # noqa: E402
from env.repos import runtime_files  # noqa: E402
from env.tool_runtime import daemon_client  # noqa: E402


MAX_DAEMON_ORIGIN_TURN_IDS = 50
MAX_DAEMON_RUNTIME_CALL_IDS = 200
DAEMON_CLIENT_NAME = "buddyswitch_daemon"
DAEMON_CLIENT_TITLE = "BuddySwitch Daemon"
DAEMON_PERMISSIONS = "buddyswitch-runtime"
DAEMON_STOP_GRACE_SECONDS = 2.0
DAEMON_POLL_SECONDS = 0.05
DAEMON_READY_TIMEOUT_SECONDS = 5.0
DAEMON_READY_POLL_SECONDS = 0.05
LEGACY_STATE_FIELDS = (
    "last_origin_turn_id",
    "last_" + "stop" + "_" + "tui" + "_turn_id",
)
HANDLER_STATUS_FIELDS = (
    "registered",
    "enabled",
    "active",
    "last_result",
    "last_handled_at",
    "last_origin_turn_id",
    "last_runtime_turn_id",
    "last_error",
)
INSTANCE_DAEMON_ENTRYPOINT = HELPER_DIR / "instance_daemon.py"


def daemon_runtime_dir(instance_root: Path) -> Path:
    return instance_root / "runtime" / "daemon"


def daemon_pid_file(instance_root: Path) -> Path:
    return daemon_runtime_dir(instance_root) / "daemon.pid"


def daemon_log_file(instance_root: Path) -> Path:
    return daemon_runtime_dir(instance_root) / "daemon.log"


def _append_daemon_event(context: "DaemonContext", event: str, **fields: Any) -> None:
    runtime_event_log.append_event(
        daemon_log_file(context.instance_root),
        service="daemon",
        event=event,
        actor_id=context.actor_id,
        **fields,
    )


def daemon_state_file(instance_root: Path) -> Path:
    return daemon_runtime_dir(instance_root) / "state.json"


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _write_text_file(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value + "\n", encoding="utf-8")


def _read_pid(path: Path) -> int | None:
    raw = _read_text_file(path)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _pid_is_live(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _remove_path(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _terminate_pid(pid: int) -> bool:
    if not _pid_is_live(pid):
        return True
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + DAEMON_STOP_GRACE_SECONDS
    while time.monotonic() < deadline:
        if not _pid_is_live(pid):
            return True
        time.sleep(DAEMON_POLL_SECONDS)
    if _pid_is_live(pid):
        os.kill(pid, signal.SIGKILL)
    return True


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty string")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_utc_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _state_payload(actor_id: str, main_thread_id: str) -> dict[str, Any]:
    return {
        "actor_id": actor_id,
        "main_thread_id": main_thread_id,
        "daemon_origin_turn_ids": [],
        "daemon_origin_turns": {},
        "daemon_runtime_call_ids": [],
        "daemon_runtime_calls": {},
        "scheduled_trigger_ids": [],
        "scheduled_triggers": {},
        "ready": None,
        "last_error": None,
        "handlers": {},
    }


def _string_field(payload: dict[str, Any], *names: str) -> str:
    for name in names:
        value = payload.get(name)
        if isinstance(value, str) and value:
            return value
    return ""


def _optional_non_empty_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string when provided")
    return value.strip()


def _notification_turn_id(notification: dict[str, Any]) -> str | None:
    params = notification.get("params")
    if not isinstance(params, dict):
        return None
    turn = params.get("turn")
    if not isinstance(turn, dict):
        return None
    turn_id = _string_field(turn, "id")
    return turn_id or None


def _turn_id_from_submit_result(result: dict[str, Any]) -> str:
    return _string_field(result, "turn_id", "turnId")


def _handler_name(handler: Any) -> str:
    name = getattr(handler, "name", None)
    if isinstance(name, str) and name:
        return name
    return type(handler).__name__


def _handler_names(handlers: list[Any] | tuple[Any, ...] | None) -> list[str]:
    names: list[str] = []
    for handler in handlers or []:
        name = _handler_name(handler)
        if name not in names:
            names.append(name)
    return names


def _schedule_row(state: "DaemonState", schedule_id: str) -> dict[str, Any] | None:
    schedules = state.payload.get("scheduled_triggers")
    if not isinstance(schedules, dict):
        return None
    row = schedules.get(schedule_id)
    if isinstance(row, dict):
        return dict(row)
    return None


def _schedule_matches_dispatch_snapshot(current: dict[str, Any] | None, snapshot: dict[str, Any]) -> bool:
    if current is None:
        return False
    fields = (
        "schedule_id",
        "type",
        "payload",
        "source_context",
        "status",
        "updated_at",
        "due_at",
        "schedule_key",
    )
    return all(current.get(field) == snapshot.get(field) for field in fields)


def _notify_subscriptions_payload(notify_subscriptions: list[str] | tuple[str, ...] | None) -> list[str]:
    names: list[str] = []
    for value in notify_subscriptions or []:
        if not isinstance(value, str):
            raise ValueError("notify subscription event types must be strings")
        name = value.strip()
        if name and name not in names:
            names.append(name)
    return names


class HandlerResult:
    def __init__(self, status: str, message: str | None = None) -> None:
        if status not in {"ignored", "handled", "failed"}:
            raise ValueError(f"invalid handler result status: {status}")
        self.status = status
        self.message = message

    @classmethod
    def ignored(cls) -> HandlerResult:
        return cls("ignored")

    @classmethod
    def handled(cls) -> HandlerResult:
        return cls("handled")

    @classmethod
    def failed(cls, message: str) -> HandlerResult:
        return cls("failed", message or "handler failed")


class DaemonHandler(Protocol):
    name: str

    def handles(self, trigger: daemon_triggers.DaemonTrigger) -> bool:
        ...

    def handle(
        self,
        context: DaemonContext,
        state: DaemonState,
        runtime: DaemonRuntime,
        trigger: daemon_triggers.DaemonTrigger,
    ) -> HandlerResult | dict[str, Any]:
        ...


class DaemonState:
    def __init__(self, *, path: Path, payload: dict[str, Any]) -> None:
        self.path = path
        self.payload = payload

    @classmethod
    def load(cls, *, instance_root: Path, actor_id: str, main_thread_id: str) -> DaemonState:
        path = daemon_state_file(instance_root)
        payload = _state_payload(actor_id, main_thread_id)
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls(path=path, payload=payload)
        if isinstance(loaded, dict):
            payload.update(loaded)
        payload["actor_id"] = actor_id
        payload["main_thread_id"] = main_thread_id
        for field in LEGACY_STATE_FIELDS:
            payload.pop(field, None)
        for field in ("daemon_" + "action_ids", "daemon_" + "action" + "s"):
            payload.pop(field, None)
        if not isinstance(payload.get("daemon_origin_turn_ids"), list):
            payload["daemon_origin_turn_ids"] = []
        payload["daemon_origin_turn_ids"] = [
            item for item in payload["daemon_origin_turn_ids"] if isinstance(item, str) and item
        ][-MAX_DAEMON_ORIGIN_TURN_IDS:]
        raw_turn_records = payload.get("daemon_origin_turns")
        if not isinstance(raw_turn_records, dict):
            raw_turn_records = {}
        turn_records: dict[str, Any] = {}
        for turn_id in payload["daemon_origin_turn_ids"]:
            raw_record = raw_turn_records.get(turn_id)
            if not isinstance(raw_record, dict):
                continue
            record_turn_id = raw_record.get("turn_id")
            if isinstance(record_turn_id, str) and record_turn_id and record_turn_id != turn_id:
                continue
            handler_name = raw_record.get("handler_name")
            if not isinstance(handler_name, str) or not handler_name:
                continue
            origin_turn_id = raw_record.get("origin_turn_id")
            if not isinstance(origin_turn_id, str) or not origin_turn_id:
                origin_turn_id = None
            created_at = raw_record.get("created_at")
            if not isinstance(created_at, str) or not created_at:
                created_at = _utc_now()
            turn_records[turn_id] = {
                "turn_id": turn_id,
                "handler_name": handler_name,
                "origin_turn_id": origin_turn_id,
                "created_at": created_at,
            }
        payload["daemon_origin_turns"] = turn_records
        if not isinstance(payload.get("daemon_runtime_call_ids"), list):
            payload["daemon_runtime_call_ids"] = []
        payload["daemon_runtime_call_ids"] = [
            item for item in payload["daemon_runtime_call_ids"] if isinstance(item, str) and item
        ][-MAX_DAEMON_RUNTIME_CALL_IDS:]
        raw_runtime_records = payload.get("daemon_runtime_calls")
        if not isinstance(raw_runtime_records, dict):
            raw_runtime_records = {}
        runtime_records: dict[str, Any] = {}
        for runtime_call_id in payload["daemon_runtime_call_ids"]:
            raw_record = raw_runtime_records.get(runtime_call_id)
            if not isinstance(raw_record, dict):
                continue
            record_runtime_call_id = raw_record.get("runtime_call_id")
            if (
                isinstance(record_runtime_call_id, str)
                and record_runtime_call_id
                and record_runtime_call_id != runtime_call_id
            ):
                continue
            runtime_method = raw_record.get("runtime_method")
            handler_name = raw_record.get("handler_name")
            status = raw_record.get("status")
            if not isinstance(runtime_method, str) or not runtime_method:
                continue
            if not isinstance(handler_name, str) or not handler_name:
                continue
            if status not in {"succeeded", "failed"}:
                continue
            created_at = raw_record.get("created_at")
            if not isinstance(created_at, str) or not created_at:
                created_at = _utc_now()
            updated_at = raw_record.get("updated_at")
            if not isinstance(updated_at, str) or not updated_at:
                updated_at = created_at
            record = {
                "runtime_call_id": runtime_call_id,
                "handler_name": handler_name,
                "origin_id": raw_record.get("origin_id") if isinstance(raw_record.get("origin_id"), str) else None,
                "runtime_method": runtime_method,
                "parent_thread_id": raw_record.get("parent_thread_id") if isinstance(raw_record.get("parent_thread_id"), str) else None,
                "side_thread_id": raw_record.get("side_thread_id") if isinstance(raw_record.get("side_thread_id"), str) else None,
                "turn_id": raw_record.get("turn_id") if isinstance(raw_record.get("turn_id"), str) else None,
                "interrupted_turn_id": raw_record.get("interrupted_turn_id") if isinstance(raw_record.get("interrupted_turn_id"), str) else None,
                "status": status,
                "error": raw_record.get("error") if isinstance(raw_record.get("error"), str) else None,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            runtime_records[runtime_call_id] = record
        payload["daemon_runtime_calls"] = runtime_records
        if not isinstance(payload.get("ready"), dict):
            payload["ready"] = None
        if "last_error" not in payload:
            payload["last_error"] = None
        if not isinstance(payload.get("handlers"), dict):
            payload["handlers"] = {}
        for handler_name, handler_payload in list(payload["handlers"].items()):
            if not isinstance(handler_name, str) or not isinstance(handler_payload, dict):
                payload["handlers"].pop(handler_name, None)
                continue
            handler_payload.pop("last_" + "action" + "_turn_id", None)
        if not isinstance(payload.get("scheduled_trigger_ids"), list):
            payload["scheduled_trigger_ids"] = []
        payload["scheduled_trigger_ids"] = [
            item for item in payload["scheduled_trigger_ids"] if isinstance(item, str) and item
        ]
        raw_schedules = payload.get("scheduled_triggers")
        if not isinstance(raw_schedules, dict):
            raw_schedules = {}
        schedules: dict[str, Any] = {}
        for schedule_id in payload["scheduled_trigger_ids"]:
            raw_schedule = raw_schedules.get(schedule_id)
            if not isinstance(raw_schedule, dict):
                continue
            if raw_schedule.get("schedule_id") != schedule_id:
                continue
            if raw_schedule.get("status") not in {"pending", "delivered", "failed", "canceled"}:
                continue
            if not isinstance(raw_schedule.get("type"), str) or not raw_schedule.get("type"):
                continue
            if not isinstance(raw_schedule.get("payload"), dict):
                continue
            if not isinstance(raw_schedule.get("source_context"), dict):
                continue
            if not isinstance(raw_schedule.get("created_at"), str) or not raw_schedule.get("created_at"):
                continue
            if not isinstance(raw_schedule.get("updated_at"), str) or not raw_schedule.get("updated_at"):
                continue
            if not isinstance(raw_schedule.get("due_at"), str) or not raw_schedule.get("due_at"):
                continue
            schedules[schedule_id] = {
                "schedule_id": schedule_id,
                "type": raw_schedule["type"],
                "payload": dict(raw_schedule["payload"]),
                "source_context": dict(raw_schedule["source_context"]),
                "status": raw_schedule["status"],
                "created_at": raw_schedule["created_at"],
                "updated_at": raw_schedule["updated_at"],
                "due_at": raw_schedule["due_at"],
                "delivered_at": raw_schedule.get("delivered_at") if isinstance(raw_schedule.get("delivered_at"), str) else None,
                "canceled_at": raw_schedule.get("canceled_at") if isinstance(raw_schedule.get("canceled_at"), str) else None,
                "last_error": raw_schedule.get("last_error") if isinstance(raw_schedule.get("last_error"), str) else None,
                "dispatch_result": raw_schedule.get("dispatch_result") if isinstance(raw_schedule.get("dispatch_result"), dict) else None,
            }
            schedule_key = raw_schedule.get("schedule_key")
            if isinstance(schedule_key, str) and schedule_key.strip():
                schedules[schedule_id]["schedule_key"] = schedule_key.strip()
        payload["scheduled_trigger_ids"] = [item for item in payload["scheduled_trigger_ids"] if item in schedules]
        payload["scheduled_triggers"] = schedules
        return cls(path=path, payload=payload)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        temp_path.write_text(json.dumps(self.payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(self.path)

    def is_daemon_origin_turn(self, turn_id: str) -> bool:
        return turn_id in self.payload.get("daemon_origin_turn_ids", [])

    def daemon_turn_record(self, turn_id: str) -> dict[str, Any] | None:
        records = self.payload.get("daemon_origin_turns")
        if not isinstance(records, dict):
            return None
        record = records.get(turn_id)
        if not isinstance(record, dict):
            return None
        return record

    def is_daemon_origin_turn_from(self, turn_id: str, handler_name: str) -> bool:
        record = self.daemon_turn_record(turn_id)
        if record is not None:
            return record.get("handler_name") == handler_name
        return self.is_daemon_origin_turn(turn_id) and handler_name == "task_checkout"

    def record_daemon_origin_turn(
        self,
        turn_id: str,
        *,
        handler_name: str | None = None,
        origin_turn_id: str | None = None,
    ) -> None:
        turn_ids = [item for item in self.payload.get("daemon_origin_turn_ids", []) if isinstance(item, str) and item]
        turn_ids = [item for item in turn_ids if item != turn_id]
        turn_ids.append(turn_id)
        self.payload["daemon_origin_turn_ids"] = turn_ids[-MAX_DAEMON_ORIGIN_TURN_IDS:]
        records = self.payload.get("daemon_origin_turns")
        if not isinstance(records, dict):
            records = {}
        records = {key: value for key, value in records.items() if key in self.payload["daemon_origin_turn_ids"]}
        if isinstance(handler_name, str) and handler_name:
            records[turn_id] = {
                "turn_id": turn_id,
                "handler_name": handler_name,
                "origin_turn_id": origin_turn_id if isinstance(origin_turn_id, str) and origin_turn_id else None,
                "created_at": _utc_now(),
            }
        else:
            records.pop(turn_id, None)
        self.payload["daemon_origin_turns"] = records
        self.save()

    def record_runtime_call(
        self,
        *,
        handler_name: str,
        origin_id: str | None,
        runtime_method: str,
        parent_thread_id: str | None = None,
        side_thread_id: str | None = None,
        turn_id: str | None = None,
        interrupted_turn_id: str | None = None,
        status: str,
        error: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(handler_name, str) or not handler_name:
            raise ValueError("handler_name is required")
        if not isinstance(runtime_method, str) or not runtime_method:
            raise ValueError("runtime_method is required")
        if status not in {"succeeded", "failed"}:
            raise ValueError(f"invalid daemon runtime call status: {status}")
        runtime_call_ids = [
            item for item in self.payload.get("daemon_runtime_call_ids", []) if isinstance(item, str) and item
        ]
        runtime_calls = self.payload.get("daemon_runtime_calls")
        if not isinstance(runtime_calls, dict):
            runtime_calls = {}
        counter = 1
        while True:
            runtime_call_id = f"daemon-runtime-call-{counter}"
            if runtime_call_id not in runtime_calls:
                break
            counter += 1
        timestamp = _utc_now()
        record = {
            "runtime_call_id": runtime_call_id,
            "handler_name": handler_name,
            "origin_id": origin_id if isinstance(origin_id, str) and origin_id else None,
            "runtime_method": runtime_method,
            "parent_thread_id": parent_thread_id if isinstance(parent_thread_id, str) and parent_thread_id else None,
            "side_thread_id": side_thread_id if isinstance(side_thread_id, str) and side_thread_id else None,
            "turn_id": turn_id if isinstance(turn_id, str) and turn_id else None,
            "interrupted_turn_id": interrupted_turn_id if isinstance(interrupted_turn_id, str) and interrupted_turn_id else None,
            "status": status,
            "error": error if isinstance(error, str) and error else None,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        runtime_call_ids = [item for item in runtime_call_ids if item != runtime_call_id]
        runtime_call_ids.append(runtime_call_id)
        runtime_call_ids = runtime_call_ids[-MAX_DAEMON_RUNTIME_CALL_IDS:]
        runtime_calls = {key: value for key, value in runtime_calls.items() if key in runtime_call_ids}
        runtime_calls[runtime_call_id] = record
        self.payload["daemon_runtime_call_ids"] = runtime_call_ids
        self.payload["daemon_runtime_calls"] = runtime_calls
        self.save()
        return record

    def record_error(self, *, origin_turn_id: str | None, message: str) -> None:
        self.payload["last_error"] = {
            "origin_turn_id": origin_turn_id,
            "message": message,
            "at": _utc_now(),
        }
        self.save()

    def record_ready(self, *, pid: int, main_thread_id: str) -> None:
        self.payload["ready"] = {
            "pid": pid,
            "main_thread_id": main_thread_id,
            "at": _utc_now(),
        }
        self.save()

    def ready_for(self, pid: int, main_thread_id: str) -> bool:
        ready = self.payload.get("ready")
        if not isinstance(ready, dict):
            return False
        ready_pid = ready.get("pid")
        ready_thread_id = ready.get("main_thread_id")
        return ready_pid == pid and ready_thread_id == main_thread_id

    def handler_state(self, handler_name: str) -> dict[str, Any]:
        handlers = self.payload.setdefault("handlers", {})
        if not isinstance(handlers, dict):
            handlers = {}
            self.payload["handlers"] = handlers
        state = handlers.setdefault(handler_name, {})
        if not isinstance(state, dict):
            state = {}
            handlers[handler_name] = state
        return state

    def update_handler_state(self, handler_name: str, values: dict[str, Any]) -> None:
        state = self.handler_state(handler_name)
        state.update(values)
        self.save()

    def register_handlers(self, handler_names: list[str]) -> None:
        for handler_name in handler_names:
            state = self.handler_state(handler_name)
            values = {
                "registered": True,
                "enabled": True,
                "active": True,
                "last_result": state.get("last_result"),
                "last_handled_at": state.get("last_handled_at"),
                "last_origin_turn_id": state.get("last_origin_turn_id"),
                "last_runtime_turn_id": state.get("last_runtime_turn_id"),
                "last_error": state.get("last_error"),
            }
            state.update(values)
        self.save()

    def record_handler_result(
        self,
        handler_name: str,
        result: HandlerResult,
        *,
        origin_turn_id: str | None,
    ) -> None:
        if result.status == "ignored":
            return
        values: dict[str, Any] = {"last_result": result.status}
        if result.status == "handled":
            values.update(
                {
                    "last_handled_at": _utc_now(),
                    "last_origin_turn_id": origin_turn_id,
                    "last_error": None,
                }
            )
        elif result.status == "failed":
            values["last_error"] = {
                "origin_turn_id": origin_turn_id,
                "message": result.message or "handler failed",
                "at": _utc_now(),
            }
        self.update_handler_state(handler_name, values)

    def record_handler_error(self, handler_name: str, *, origin_turn_id: str | None, message: str) -> None:
        self.update_handler_state(
            handler_name,
            {
                "last_result": "failed",
                "last_error": {
                    "origin_turn_id": origin_turn_id,
                    "message": message,
                    "at": _utc_now(),
                }
            },
        )

    def create_schedule(
        self,
        *,
        delay_seconds: int | float,
        trigger_type: str,
        payload: dict[str, Any],
        source_context: dict[str, Any] | None = None,
        schedule_key: str | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        if isinstance(delay_seconds, bool) or not isinstance(delay_seconds, (int, float)) or delay_seconds < 0:
            raise ValueError("delay_seconds must be a non-negative number")
        if not isinstance(trigger_type, str) or not trigger_type.strip():
            raise ValueError("trigger_type must be a non-empty string")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        if source_context is None:
            source_context = {}
        if not isinstance(source_context, dict):
            raise ValueError("source_context must be an object")
        normalized_schedule_key = _optional_non_empty_string(schedule_key, "schedule_key")
        created_at = now or _utc_now()
        created_dt = _parse_utc_timestamp(created_at)
        timestamp = _format_utc_timestamp(created_dt)
        due_at = _format_utc_timestamp(created_dt + timedelta(seconds=float(delay_seconds)))
        schedule_ids = [
            item for item in self.payload.get("scheduled_trigger_ids", []) if isinstance(item, str) and item
        ]
        schedules = self.payload.get("scheduled_triggers")
        if not isinstance(schedules, dict):
            schedules = {}
        counter = 1
        while True:
            schedule_id = f"schedule-{counter}"
            if schedule_id not in schedules:
                break
            counter += 1
        row = {
            "schedule_id": schedule_id,
            "type": trigger_type.strip(),
            "payload": dict(payload),
            "source_context": dict(source_context),
            "status": "pending",
            "created_at": timestamp,
            "updated_at": timestamp,
            "due_at": due_at,
            "delivered_at": None,
            "canceled_at": None,
            "last_error": None,
            "dispatch_result": None,
        }
        if normalized_schedule_key is not None:
            row["schedule_key"] = normalized_schedule_key
        schedule_ids.append(schedule_id)
        schedules[schedule_id] = row
        self.payload["scheduled_trigger_ids"] = schedule_ids
        self.payload["scheduled_triggers"] = schedules
        self.save()
        return dict(row)

    def upsert_schedule(
        self,
        *,
        delay_seconds: int | float,
        trigger_type: str,
        payload: dict[str, Any],
        schedule_key: str,
        source_context: dict[str, Any] | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        normalized_schedule_key = _optional_non_empty_string(schedule_key, "schedule_key")
        assert normalized_schedule_key is not None
        if isinstance(delay_seconds, bool) or not isinstance(delay_seconds, (int, float)) or delay_seconds < 0:
            raise ValueError("delay_seconds must be a non-negative number")
        if not isinstance(trigger_type, str) or not trigger_type.strip():
            raise ValueError("trigger_type must be a non-empty string")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        if source_context is None:
            source_context = {}
        if not isinstance(source_context, dict):
            raise ValueError("source_context must be an object")
        timestamp = _format_utc_timestamp(_parse_utc_timestamp(now or _utc_now()))
        due_at = _format_utc_timestamp(_parse_utc_timestamp(timestamp) + timedelta(seconds=float(delay_seconds)))
        schedule_ids = [
            item for item in self.payload.get("scheduled_trigger_ids", []) if isinstance(item, str) and item
        ]
        schedules = self.payload.get("scheduled_triggers")
        if not isinstance(schedules, dict):
            schedules = {}
        for schedule_id in schedule_ids:
            row = schedules.get(schedule_id)
            if (
                isinstance(row, dict)
                and row.get("status") == "pending"
                and row.get("schedule_key") == normalized_schedule_key
            ):
                row.update(
                    {
                        "type": trigger_type.strip(),
                        "payload": dict(payload),
                        "source_context": dict(source_context),
                        "updated_at": timestamp,
                        "due_at": due_at,
                        "last_error": None,
                        "dispatch_result": None,
                    }
                )
                schedules[schedule_id] = row
                self.payload["scheduled_triggers"] = schedules
                self.save()
                return dict(row)
        return self.create_schedule(
            delay_seconds=delay_seconds,
            trigger_type=trigger_type,
            payload=payload,
            source_context=source_context,
            schedule_key=normalized_schedule_key,
            now=timestamp,
        )

    def due_schedules(self, *, now: str | None = None) -> list[dict[str, Any]]:
        timestamp = now or _utc_now()
        current = _parse_utc_timestamp(timestamp)
        schedule_ids = [
            item for item in self.payload.get("scheduled_trigger_ids", []) if isinstance(item, str) and item
        ]
        schedules = self.payload.get("scheduled_triggers")
        schedule_items = schedules if isinstance(schedules, dict) else {}
        due: list[dict[str, Any]] = []
        for schedule_id in schedule_ids:
            row = schedule_items.get(schedule_id)
            if not isinstance(row, dict) or row.get("status") != "pending":
                continue
            due_at = row.get("due_at")
            if not isinstance(due_at, str) or not due_at:
                continue
            if _parse_utc_timestamp(due_at) <= current:
                due.append(dict(row))
        return due

    def _update_schedule(self, schedule_id: str, values: dict[str, Any]) -> dict[str, Any]:
        schedules = self.payload.get("scheduled_triggers")
        if not isinstance(schedules, dict):
            raise KeyError(schedule_id)
        row = schedules.get(schedule_id)
        if not isinstance(row, dict):
            raise KeyError(schedule_id)
        row.update(values)
        schedules[schedule_id] = row
        self.payload["scheduled_triggers"] = schedules
        self.save()
        return dict(row)

    def mark_schedule_delivered(
        self,
        schedule_id: str,
        *,
        dispatch_result: dict[str, Any],
        now: str | None = None,
    ) -> dict[str, Any]:
        timestamp = _format_utc_timestamp(_parse_utc_timestamp(now or _utc_now()))
        return self._update_schedule(
            schedule_id,
            {
                "status": "delivered",
                "updated_at": timestamp,
                "delivered_at": timestamp,
                "last_error": None,
                "dispatch_result": dict(dispatch_result),
            },
        )

    def mark_schedule_failed(
        self,
        schedule_id: str,
        *,
        message: str,
        dispatch_result: dict[str, Any] | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        timestamp = _format_utc_timestamp(_parse_utc_timestamp(now or _utc_now()))
        return self._update_schedule(
            schedule_id,
            {
                "status": "failed",
                "updated_at": timestamp,
                "last_error": message or "scheduled trigger failed",
                "dispatch_result": dict(dispatch_result) if isinstance(dispatch_result, dict) else None,
            },
        )

    def cancel_schedule(self, schedule_id: str, *, now: str | None = None) -> dict[str, Any]:
        timestamp = _format_utc_timestamp(_parse_utc_timestamp(now or _utc_now()))
        return self._update_schedule(
            schedule_id,
            {
                "status": "canceled",
                "updated_at": timestamp,
                "canceled_at": timestamp,
            },
        )

    def cancel_pending_schedules_by_source_owner(self, owner: str, *, now: str | None = None) -> list[dict[str, Any]]:
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("owner must be a non-empty string")
        normalized_owner = owner.strip()
        timestamp = _format_utc_timestamp(_parse_utc_timestamp(now or _utc_now()))
        schedule_ids = [
            item for item in self.payload.get("scheduled_trigger_ids", []) if isinstance(item, str) and item
        ]
        schedules = self.payload.get("scheduled_triggers")
        if not isinstance(schedules, dict):
            schedules = {}
        canceled: list[dict[str, Any]] = []
        for schedule_id in schedule_ids:
            row = schedules.get(schedule_id)
            if not isinstance(row, dict):
                continue
            source_context = row.get("source_context")
            if not isinstance(source_context, dict):
                continue
            if row.get("status") != "pending" or source_context.get("owner") != normalized_owner:
                continue
            row.update(
                {
                    "status": "canceled",
                    "updated_at": timestamp,
                    "canceled_at": timestamp,
                }
            )
            schedules[schedule_id] = row
            canceled.append(dict(row))
        if canceled:
            self.payload["scheduled_triggers"] = schedules
            self.save()
        return canceled


class DaemonContext:
    def __init__(
        self,
        *,
        instance_json: Path,
        instance_payload: dict[str, Any],
        actor_id: str,
        instance_root: Path,
        main_thread_id: str,
        role: str,
        workspace_dir: Path,
        project_workspace_dir: Path,
        socket_path: Path,
        permissions: str = DAEMON_PERMISSIONS,
    ) -> None:
        self.instance_json = instance_json
        self.instance_payload = instance_payload
        self.actor_id = actor_id
        self.instance_root = instance_root
        self.main_thread_id = main_thread_id
        self.role = role
        self.workspace_dir = workspace_dir
        self.project_workspace_dir = project_workspace_dir
        self.socket_path = socket_path
        self.permissions = permissions


class DaemonRuntime:
    def __init__(self, *, context: DaemonContext, state: DaemonState, client: Any | None = None) -> None:
        self.context = context
        self.state = state
        self.client = client

    def execute_task_sys_instruction(self, instruction: dict[str, Any]) -> dict[str, Any]:
        return task_sys_execute_instruction(self.context, instruction)

    def cleanup_task_sys_side_lease(self, task_id: str) -> dict[str, Any]:
        return task_sys_cleanup_task_sys_side_lease(self.context, task_id)

    def parent_activity(self) -> dict[str, Any]:
        try:
            result = app_server.thread_read(self.context.socket_path, self.context.main_thread_id, include_turns=False)
            thread = result.get("thread")
            if not isinstance(thread, dict):
                raise app_server.AppServerProtocolError("thread/read did not return a thread object")
            status_kind = app_server._thread_status_kind(thread.get("status"))
            if status_kind == "idle":
                return {"status": "idle", "active_turn_id": None}
            if status_kind == "active":
                return {
                    "status": "running",
                    "active_turn_id": app_server.active_turn_id(self.context.socket_path, self.context.main_thread_id),
                }
            raise app_server.AppServerUnavailableError(
                f"thread {self.context.main_thread_id} is not active or idle"
            )
        except Exception as exc:
            return {"status": "unavailable", "error": str(exc)}

    def _record_runtime_call(
        self,
        *,
        handler_name: str,
        origin_id: str | None,
        runtime_method: str,
        status: str,
        side_thread_id: str | None = None,
        turn_id: str | None = None,
        interrupted_turn_id: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        return self.state.record_runtime_call(
            handler_name=handler_name,
            origin_id=origin_id,
            runtime_method=runtime_method,
            parent_thread_id=self.context.main_thread_id,
            side_thread_id=side_thread_id,
            turn_id=turn_id,
            interrupted_turn_id=interrupted_turn_id,
            status=status,
            error=error,
        )

    def _submit_parent_once(self, text: str, *, handler_name: str, origin_id: str | None) -> str:
        try:
            result = launcher_submit_turn.submit_turn(
                socket_path=self.context.socket_path,
                thread_id=self.context.main_thread_id,
                text=text,
                permissions=self.context.permissions,
            )
            turn_id = _turn_id_from_submit_result(result)
            if not turn_id:
                raise launcher_submit_turn.SubmitTurnError("submit_turn did not return a turn id")
        except Exception as exc:
            self._record_runtime_call(
                handler_name=handler_name,
                origin_id=origin_id,
                runtime_method="parent_submit",
                status="failed",
                error=str(exc),
            )
            raise
        self._record_runtime_call(
            handler_name=handler_name,
            origin_id=origin_id,
            runtime_method="parent_submit",
            status="succeeded",
            turn_id=turn_id,
        )
        self.state.record_daemon_origin_turn(
            turn_id,
            handler_name=handler_name,
            origin_turn_id=origin_id,
        )
        self.state.update_handler_state(
            handler_name,
            {
                "last_origin_turn_id": origin_id,
                "last_runtime_turn_id": turn_id,
                "last_error": None,
            },
        )
        return turn_id

    def _interrupt_parent(self, *, handler_name: str, origin_id: str | None) -> dict[str, Any]:
        try:
            result = app_server.interrupt_turn(self.context.socket_path, self.context.main_thread_id)
            interrupted_turn_id = _string_field(result, "turn_id", "turnId")
            if not interrupted_turn_id:
                raise app_server.AppServerProtocolError("turn/interrupt did not return a turn id")
        except Exception as exc:
            self._record_runtime_call(
                handler_name=handler_name,
                origin_id=origin_id,
                runtime_method="parent_interrupt",
                status="failed",
                error=str(exc),
            )
            raise
        self._record_runtime_call(
            handler_name=handler_name,
            origin_id=origin_id,
            runtime_method="parent_interrupt",
            status="succeeded",
            interrupted_turn_id=interrupted_turn_id,
        )
        return {"interrupted_turn_id": interrupted_turn_id}

    def _wait_for_parent_idle(self) -> None:
        max_polls = max(1, int(1.0 / DAEMON_POLL_SECONDS))
        last_activity: dict[str, Any] | None = None
        for poll_index in range(max_polls):
            activity = self.parent_activity()
            last_activity = activity
            if activity.get("status") == "idle":
                return
            if activity.get("status") == "unavailable":
                error = activity.get("error")
                detail = error if isinstance(error, str) and error else "parent thread became unavailable"
                raise app_server.AppServerUnavailableError(
                    f"parent thread {self.context.main_thread_id} became unavailable while waiting to become idle: {detail}"
                )
            if poll_index + 1 < max_polls:
                time.sleep(DAEMON_POLL_SECONDS)
        detail = "unknown state"
        if isinstance(last_activity, dict):
            status = last_activity.get("status")
            if isinstance(status, str) and status:
                detail = status
            error = last_activity.get("error")
            if isinstance(error, str) and error:
                detail = error
        raise app_server.AppServerUnavailableError(
            f"parent thread {self.context.main_thread_id} did not become idle before submit: {detail}"
        )

    @staticmethod
    def _is_no_active_turn_race(exc: Exception) -> bool:
        return "has no active in-progress turn" in str(exc)

    def _ensure_parent_stopped(self, *, handler_name: str, origin_id: str | None) -> str | None:
        activity = self.parent_activity()
        status = activity.get("status")
        if status == "idle":
            return None
        if status == "unavailable":
            error = activity.get("error")
            detail = error if isinstance(error, str) and error else "parent thread is unavailable"
            raise app_server.AppServerUnavailableError(
                f"parent thread {self.context.main_thread_id} is unavailable for parent handoff: {detail}"
            )
        if status != "running":
            raise app_server.AppServerUnavailableError(
                f"parent thread {self.context.main_thread_id} returned unexpected activity status: {status}"
            )

        interrupted_turn_id: str | None = None
        try:
            interrupted = self._interrupt_parent(handler_name=handler_name, origin_id=origin_id)
            value = interrupted.get("interrupted_turn_id")
            interrupted_turn_id = value if isinstance(value, str) and value else None
        except Exception as exc:
            if not self._is_no_active_turn_race(exc):
                raise

        self._wait_for_parent_idle()
        return interrupted_turn_id

    def submit_parent_prompt(
        self,
        text: str,
        *,
        handler_name: str,
        origin_id: str | None,
        interrupt_policy: str = "none",
    ) -> dict[str, Any]:
        if interrupt_policy not in {"none", "before_submit", "ensure_stopped"}:
            raise ValueError(f"invalid interrupt_policy: {interrupt_policy}")
        interrupted_turn_id: str | None = None
        if interrupt_policy == "before_submit":
            interrupted = self._interrupt_parent(handler_name=handler_name, origin_id=origin_id)
            value = interrupted.get("interrupted_turn_id")
            interrupted_turn_id = value if isinstance(value, str) and value else None
        elif interrupt_policy == "ensure_stopped":
            interrupted_turn_id = self._ensure_parent_stopped(handler_name=handler_name, origin_id=origin_id)
        turn_id = self._submit_parent_once(text, handler_name=handler_name, origin_id=origin_id)
        result: dict[str, Any] = {"turn_id": turn_id}
        if interrupted_turn_id is not None:
            result["interrupted_turn_id"] = interrupted_turn_id
        return result


def load_daemon_context(instance_json: Path) -> DaemonContext:
    payload = json.loads(instance_json.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"instance JSON must contain an object: {instance_json}")
    actor_id = _string_field(payload, "actor_id")
    role = _string_field(payload, "role")
    main_thread_id = _string_field(payload, "thread_id")
    instance_root_text = _string_field(payload, "instance_root")
    workspace_dir_text = _string_field(payload, "workspace_dir")
    if not actor_id or not role or not main_thread_id or not instance_root_text or not workspace_dir_text:
        raise ValueError(f"instance JSON is missing daemon fields: {instance_json}")
    instance_root = Path(instance_root_text)
    workspace_dir = Path(workspace_dir_text)
    project_workspace_dir = instance_root.parent.parent / "project" / "workspace"
    socket_text = _string_field(payload, "app_server_socket")
    socket_path = (
        Path(socket_text)
        if socket_text
        else app_server.effective_socket_path(actor_id, instance_root, app_server.marker_file(instance_root))
    )
    return DaemonContext(
        instance_json=instance_json,
        instance_payload=payload,
        actor_id=actor_id,
        instance_root=instance_root,
        main_thread_id=main_thread_id,
        role=role,
        workspace_dir=workspace_dir,
        project_workspace_dir=project_workspace_dir,
        socket_path=socket_path,
    )


def derive_daemon_runtime_env(context: DaemonContext) -> dict[str, str]:
    shared_root = context.instance_root.parent.parent
    return {
        "BUDDYSWITCH_SHARED_ROOT": str(shared_root),
        "BUDDYSWITCH_STATE_ROOT": str(shared_root / "state"),
        "BUDDYSWITCH_INSTANCE_ROOT": str(context.instance_root),
        "BUDDYSWITCH_INSTANCE_JSON": str(context.instance_json),
        "BUDDYSWITCH_WORKSPACE_DIR": str(context.workspace_dir),
        "BUDDYSWITCH_ACTOR_ID": context.actor_id,
        "BUDDYSWITCH_ROLE_ID": context.role,
    }


def identity_route_payload(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    extra_keys = set(value) - {"identity_id", "role_id"}
    if extra_keys:
        raise ValueError(f"{field} contains unsupported fields: {sorted(extra_keys)}")
    identity_id = value.get("identity_id")
    role_id = value.get("role_id")
    if not isinstance(identity_id, str) or ACTOR_ID_PATTERN.fullmatch(identity_id.strip()) is None:
        raise ValueError(f"{field}.identity_id must be a valid actor identity id")
    if not isinstance(role_id, str) or ROLE_ID_PATTERN.fullmatch(role_id.strip()) is None:
        raise ValueError(f"{field}.role_id must be a valid role id")
    return {"identity_id": identity_id.strip(), "role_id": role_id.strip()}


def identity_route_for_context(context: DaemonContext) -> dict[str, str]:
    return identity_route_payload(
        {"identity_id": context.actor_id, "role_id": context.role},
        "context.identity_route",
    )


def ensure_actor_identity_profile(context: DaemonContext, identity_route: dict[str, str]) -> dict[str, Any]:
    existing = identity_repo.get_actor_identity_profile(identity_route["identity_id"])
    if isinstance(existing, dict):
        if existing.get("role_id") != identity_route["role_id"]:
            raise ValueError(
                "actor identity profile role mismatch: "
                f"{identity_route['identity_id']} has {existing.get('role_id')}, "
                f"instance has {identity_route['role_id']}"
            )
        return existing
    return identity_repo.save_actor_identity_profile(
        {
            "identity": {"id": identity_route["identity_id"], "type": "actor"},
            "role_id": identity_route["role_id"],
        }
    )


def central_daemon_socket_path(context: DaemonContext) -> Path:
    raw_socket = os.environ.get("BUDDYSWITCH_CENTRAL_DAEMON_SOCKET")
    if isinstance(raw_socket, str) and raw_socket.strip():
        return Path(raw_socket.strip()).expanduser().resolve(strict=False)
    raw_shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
    if isinstance(raw_shared_root, str) and raw_shared_root.strip():
        shared_root = Path(raw_shared_root.strip()).expanduser().resolve(strict=False)
    else:
        shared_root = context.instance_root.parent.parent
    return daemon_client.central_daemon_socket_path_for_shared_root(shared_root)


def register_daemon_actor(
    context: DaemonContext,
    identity_route: dict[str, str],
    *,
    notify_subscriptions: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    endpoint: dict[str, Any] = {
        "kind": "daemon_mailbox_socket",
        "socket_path": str(daemon_mailbox.mailbox_socket_path(context.instance_root)),
    }
    subscriptions = _notify_subscriptions_payload(notify_subscriptions)
    if subscriptions:
        endpoint["subscriptions"] = subscriptions
    return daemon_client.register_actor(
        identity_id=identity_route["identity_id"],
        role_id=identity_route["role_id"],
        endpoint=endpoint,
        heartbeat={"kind": "central_daemon_rpc"},
        socket_path=central_daemon_socket_path(context),
    )


def unregister_daemon_actor(
    context: DaemonContext,
    identity_route: dict[str, str],
) -> dict[str, Any]:
    return daemon_client.unregister_actor(
        identity_id=identity_route["identity_id"],
        role_id=identity_route["role_id"],
        socket_path=central_daemon_socket_path(context),
    )


def safe_unregister_daemon_actor(
    context: DaemonContext,
    identity_route: dict[str, str],
    *,
    state: DaemonState | None = None,
) -> dict[str, Any]:
    try:
        result = unregister_daemon_actor(context, identity_route)
    except Exception as exc:
        message = str(exc)
        if state is not None and state.payload.get("last_error") is None:
            state.record_error(origin_turn_id=None, message=message)
        return {
            "unregister_status": "failed",
            "unregister_error": message,
        }
    return {
        "unregister_status": "ok",
        "unregister_result": result,
    }


def heartbeat_daemon_actor(
    context: DaemonContext,
    identity_route: dict[str, str],
) -> dict[str, Any]:
    return daemon_client.heartbeat_actor(
        identity_id=identity_route["identity_id"],
        socket_path=central_daemon_socket_path(context),
    )


def _dispatch_task_sys_mailbox_command(
    context: DaemonContext,
    state: DaemonState,
    action: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    runtime = DaemonRuntime(context=context, state=state)
    if action == "execute_instruction":
        instruction = params.get("instruction")
        if not isinstance(instruction, dict):
            raise ValueError("instruction must be an object")
        return runtime.execute_task_sys_instruction(instruction)
    if action == "cleanup_side_lease":
        task_id = params.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        return runtime.cleanup_task_sys_side_lease(task_id)
    raise ValueError(f"unsupported Task Sys mailbox action: {action}")


def start_daemon_mailbox(
    *,
    context: DaemonContext,
    state: DaemonState,
    identity_route: dict[str, str],
    handlers: list[Any] | tuple[Any, ...],
) -> daemon_mailbox.DaemonMailboxServer:
    server = daemon_mailbox.DaemonMailboxServer(
        socket_path=daemon_mailbox.mailbox_socket_path(context.instance_root),
        local_identity_id=identity_route["identity_id"],
        local_role_id=identity_route["role_id"],
        handlers=handlers,
        context=context,
        state=state,
        trigger_dispatcher=lambda trigger: dispatch_trigger(
            context,
            state,
            DaemonRuntime(context=context, state=state),
            trigger,
            handlers,
        ),
        task_sys_dispatcher=lambda action, params: _dispatch_task_sys_mailbox_command(context, state, action, params),
    )
    thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
    thread.start()
    deadline = time.monotonic() + DAEMON_READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if daemon_mailbox.mailbox_socket_path(context.instance_root).exists():
            return server
        time.sleep(DAEMON_READY_POLL_SECONDS)
    server.close()
    raise RuntimeError(f"daemon mailbox did not become ready for {context.actor_id}")


def bind_main_thread(context: DaemonContext, client: Any) -> None:
    result = client.request(
        "thread/resume",
        {
            "threadId": context.main_thread_id,
            "cwd": str(context.workspace_dir),
            "runtimeWorkspaceRoots": [
                str(context.workspace_dir),
                str(context.project_workspace_dir),
            ],
            "permissions": context.permissions,
            "excludeTurns": True,
        },
    )
    thread = result.get("thread")
    if not isinstance(thread, dict) or _string_field(thread, "id") != context.main_thread_id:
        raise app_server.AppServerProtocolError(
            f"thread/resume returned unexpected thread id for {context.actor_id}"
        )


def dispatch_notification(
    context: DaemonContext,
    state: DaemonState,
    client: Any,
    notification: dict[str, Any],
    handlers: list[Any] | tuple[Any, ...],
) -> bool:
    runtime = DaemonRuntime(context=context, state=state, client=client)
    trigger = daemon_triggers.normalize_app_server_notification(
        notification,
        target_identity_id=context.actor_id,
        target_role_id=context.role,
    )
    _append_daemon_event(
        context,
        "notification_received",
        trigger_type=trigger.type,
        origin_id=_trigger_origin_id(trigger),
    )
    result = dispatch_trigger(context, state, runtime, trigger, handlers)
    handled_count = result.get("handled_count")
    return isinstance(handled_count, int) and handled_count > 0


def _trigger_origin_id(trigger: Any) -> str | None:
    origin_id = getattr(trigger, "origin_id", None)
    return origin_id if isinstance(origin_id, str) and origin_id else None


def dispatch_trigger(
    context: DaemonContext,
    state: DaemonState,
    runtime: Any,
    trigger: daemon_triggers.DaemonTrigger,
    handlers: list[Any] | tuple[Any, ...],
) -> dict[str, Any]:
    handled = 0
    matched = 0
    errors: list[str] = []
    origin_id = _trigger_origin_id(trigger)
    for handler in handlers:
        handler_name = _handler_name(handler)
        handles = getattr(handler, "handles", None)
        if not callable(handles):
            continue
        try:
            if handles(trigger) is not True:
                continue
        except Exception as exc:
            errors.append(str(exc))
            state.record_handler_error(handler_name, origin_turn_id=origin_id, message=str(exc))
            _append_daemon_event(
                context,
                "handler_failed",
                handler=handler_name,
                trigger_type=trigger.type,
                origin_id=origin_id,
                error_type=type(exc).__name__,
            )
            continue
        matched += 1
        handle = getattr(handler, "handle", None)
        if not callable(handle):
            message = f"handler {handler_name} has no unified handle method"
            errors.append(message)
            state.record_handler_error(handler_name, origin_turn_id=origin_id, message=message)
            _append_daemon_event(
                context,
                "handler_failed",
                handler=handler_name,
                trigger_type=trigger.type,
                origin_id=origin_id,
                error_type="missing_handle",
            )
            continue
        try:
            result = handle(context, state, runtime, trigger)
        except Exception as exc:
            errors.append(str(exc))
            state.record_handler_error(handler_name, origin_turn_id=origin_id, message=str(exc))
            _append_daemon_event(
                context,
                "handler_failed",
                handler=handler_name,
                trigger_type=trigger.type,
                origin_id=origin_id,
                error_type=type(exc).__name__,
            )
            continue
        status = getattr(result, "status", None)
        message = getattr(result, "message", None)
        if isinstance(result, dict):
            status = result.get("status")
            message = result.get("message")
        if status not in {"ignored", "handled", "failed"}:
            message = f"handler returned invalid result: {type(result).__name__}"
            errors.append(message)
            state.record_handler_error(handler_name, origin_turn_id=origin_id, message=message)
            _append_daemon_event(
                context,
                "handler_failed",
                handler=handler_name,
                trigger_type=trigger.type,
                origin_id=origin_id,
                error_type="invalid_result",
            )
            continue
        normalized = HandlerResult(status, str(message) if status == "failed" and message else None)
        state.record_handler_result(handler_name, normalized, origin_turn_id=origin_id)
        _append_daemon_event(
            context,
            "handler_result",
            handler=handler_name,
            trigger_type=trigger.type,
            origin_id=origin_id,
            result=normalized.status,
        )
        if status == "handled":
            handled += 1
        elif status == "failed":
            errors.append(str(message or "handler failed"))
    if errors:
        return {
            "accepted": True,
            "handled_count": handled,
            "matched_count": matched,
            "handling_status": "failed",
            "handling_error": "; ".join(errors),
            "trigger": trigger.to_payload(),
        }
    return {
        "accepted": True,
        "handled_count": handled,
        "matched_count": matched,
        "handling_status": "handled" if handled > 0 else "ignored",
        "trigger": trigger.to_payload(),
    }


def sweep_due_scheduled_triggers(
    context: DaemonContext,
    state: DaemonState,
    runtime: Any,
    handlers: list[Any] | tuple[Any, ...],
    *,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = _format_utc_timestamp(_parse_utc_timestamp(now or _utc_now()))
    identity_route = identity_route_for_context(context)
    swept_count = 0
    delivered_count = 0
    failed_count = 0
    results: list[dict[str, Any]] = []
    for schedule in state.due_schedules(now=timestamp):
        schedule_id = schedule["schedule_id"]
        trigger = daemon_triggers.normalize_scheduled_trigger(
            schedule,
            target_identity_id=identity_route["identity_id"],
            target_role_id=identity_route["role_id"],
        )
        dispatch_result = dispatch_trigger(context, state, runtime, trigger, handlers)
        swept_count += 1
        if (
            dispatch_result.get("handling_status") == "handled"
            and isinstance(dispatch_result.get("handled_count"), int)
            and dispatch_result.get("handled_count") > 0
        ):
            current_schedule = _schedule_row(state, schedule_id)
            if _schedule_matches_dispatch_snapshot(current_schedule, schedule):
                updated = state.mark_schedule_delivered(schedule_id, dispatch_result=dispatch_result, now=timestamp)
                delivered_count += 1
            else:
                updated = current_schedule if current_schedule is not None else schedule
        else:
            error = dispatch_result.get("handling_error")
            if not isinstance(error, str) or not error:
                error = "scheduled trigger had no matching handler"
            current_schedule = _schedule_row(state, schedule_id)
            if _schedule_matches_dispatch_snapshot(current_schedule, schedule):
                updated = state.mark_schedule_failed(
                    schedule_id,
                    message=error,
                    dispatch_result=dispatch_result,
                    now=timestamp,
                )
                failed_count += 1
            else:
                updated = current_schedule if current_schedule is not None else schedule
        results.append(updated)
    return {
        "swept_count": swept_count,
        "delivered_count": delivered_count,
        "failed_count": failed_count,
        "schedules": results,
    }


def _handler_status_payload(
    state: DaemonState,
    handlers: list[Any] | tuple[Any, ...] | None,
    *,
    include_unregistered: bool = True,
    excluded_persisted_names: set[str] | None = None,
) -> dict[str, Any]:
    registered = _handler_names(handlers)
    excluded = excluded_persisted_names or set()
    persisted = state.payload.get("handlers")
    persisted_handlers = persisted if isinstance(persisted, dict) else {}
    names = list(registered)
    if include_unregistered:
        for name in sorted(persisted_handlers):
            if name not in names and name not in excluded:
                names.append(name)
    else:
        for name in sorted(persisted_handlers):
            if name in registered and name not in names:
                names.append(name)

    items: dict[str, Any] = {}
    for name in names:
        raw_state = persisted_handlers.get(name)
        handler_state = dict(raw_state) if isinstance(raw_state, dict) else {}
        is_registered = name in registered
        item = {
            "registered": is_registered,
            "enabled": is_registered,
            "active": is_registered,
            "result_scope": "trigger_dispatch",
            "last_result": None,
            "last_handled_at": None,
            "last_origin_turn_id": None,
            "last_runtime_turn_id": None,
            "last_error": None,
        }
        for field in HANDLER_STATUS_FIELDS:
            if field in handler_state and field not in {"registered", "enabled", "active"}:
                item[field] = handler_state[field]
        items[name] = item
    return {"registered": registered, "items": items}


def _runtime_status_payload(state: DaemonState) -> dict[str, Any]:
    runtime_call_ids = [
        item for item in state.payload.get("daemon_runtime_call_ids", []) if isinstance(item, str) and item
    ]
    runtime_calls = state.payload.get("daemon_runtime_calls")
    runtime_items = runtime_calls if isinstance(runtime_calls, dict) else {}
    items = {
        runtime_call_id: runtime_items[runtime_call_id]
        for runtime_call_id in runtime_call_ids
        if runtime_call_id in runtime_items
    }
    return {"ids": list(items), "items": items}


def _schedule_status_payload(state: DaemonState) -> dict[str, Any]:
    schedule_ids = [
        item for item in state.payload.get("scheduled_trigger_ids", []) if isinstance(item, str) and item
    ]
    schedules = state.payload.get("scheduled_triggers")
    schedule_items = schedules if isinstance(schedules, dict) else {}
    items = {
        schedule_id: schedule_items[schedule_id]
        for schedule_id in schedule_ids
        if schedule_id in schedule_items and isinstance(schedule_items[schedule_id], dict)
    }
    counts = {"pending": 0, "delivered": 0, "failed": 0, "canceled": 0}
    for item in items.values():
        status = item.get("status")
        if status in counts:
            counts[status] += 1
    return {"ids": list(items), "items": items, "counts": counts}


def _task_sys_status_payload(context: DaemonContext) -> dict[str, Any]:
    actor_target = {"actor_id": context.actor_id, "role_id": context.role}
    tasks_dir = context.instance_root.parent.parent / "state" / "buddyswitch" / "objects" / "task-sys" / "tasks"
    active_tasks: list[dict[str, Any]] = []
    recoverable_tasks: list[dict[str, Any]] = []
    if tasks_dir.exists():
        for path in sorted(tasks_dir.glob("*.json")):
            try:
                record = runtime_files.read_json_object(path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            target = record.get("actor_target")
            if not isinstance(target, dict):
                continue
            if target.get("actor_id") != actor_target["actor_id"] or target.get("role_id") != actor_target["role_id"]:
                continue
            if record.get("status") in task_sys.ACTIVE_TASK_STATUSES:
                active_tasks.append(record)
            elif record.get("status") in task_sys.RECOVERABLE_TASK_STATUSES:
                recoverable_tasks.append(record)

    def _summaries(records: list[dict[str, Any]], *, include_failure: bool = False) -> tuple[dict[str, int], list[dict[str, Any]]]:
        by_status: dict[str, int] = {}
        summaries: list[dict[str, Any]] = []
        for record in records:
            status = record.get("status")
            status_key = status if isinstance(status, str) and status else "unknown"
            by_status[status_key] = by_status.get(status_key, 0) + 1
            source_ref = record.get("source_ref")
            row = {
                "task_id": record.get("id"),
                "source_type": record.get("source_type"),
                "source_ref": dict(source_ref) if isinstance(source_ref, dict) else {},
                "status": status,
                "active_processor": record.get("active_processor"),
                "updated_at": record.get("updated_at"),
            }
            if include_failure:
                failure_result = record.get("failure_result")
                row["failure_result"] = dict(failure_result) if isinstance(failure_result, dict) else {}
            summaries.append(row)
        return by_status, summaries

    by_status, summaries = _summaries(active_tasks)
    recoverable_by_status, recoverable_summaries = _summaries(recoverable_tasks, include_failure=True)
    return {
        "scope": "task_sys_state_projection",
        "active_count": len(summaries),
        "recoverable_count": len(recoverable_summaries),
        "by_status": by_status,
        "recoverable_by_status": recoverable_by_status,
        "active_tasks": summaries,
        "recoverable_tasks": recoverable_summaries,
    }


def daemon_status(
    instance_json: Path,
    *,
    handlers: list[Any] | tuple[Any, ...] | None = None,
    notify_subscriptions: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    context = load_daemon_context(instance_json)
    runtime = daemon_runtime_dir(context.instance_root)
    pid_path = daemon_pid_file(context.instance_root)
    log_path = daemon_log_file(context.instance_root)
    state_path = daemon_state_file(context.instance_root)
    pid = _read_pid(pid_path)
    pid_live = pid is not None and _pid_is_live(pid)
    if pid is not None and not pid_live:
        _remove_path(pid_path)
        pid = None
    state = DaemonState.load(
        instance_root=context.instance_root,
        actor_id=context.actor_id,
        main_thread_id=context.main_thread_id,
    )
    ready = bool(pid is not None and pid_live and state.ready_for(pid, context.main_thread_id))
    ready_payload = state.payload.get("ready")
    ready_main_thread_id = ready_payload.get("main_thread_id") if isinstance(ready_payload, dict) else None
    return {
        "live": bool(pid_live),
        "pid": pid,
        "pid_live": bool(pid_live),
        "ready": ready,
        "ready_main_thread_id": ready_main_thread_id,
        "runtime_dir": str(runtime),
        "pid_file": str(pid_path),
        "log_path": str(log_path),
        "log": runtime_event_log.log_metadata(log_path),
        "state_path": str(state_path),
        "last_error": state.payload.get("last_error"),
        "runtime": _runtime_status_payload(state),
        "schedules": _schedule_status_payload(state),
        "handlers": _handler_status_payload(state, handlers),
        "task_sys": _task_sys_status_payload(context),
        "notify": {"subscriptions": _notify_subscriptions_payload(notify_subscriptions)},
    }


def start_daemon(
    instance_json: Path,
    *,
    handlers: list[Any] | tuple[Any, ...] | None = None,
    notify_subscriptions: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    context = load_daemon_context(instance_json)
    runtime = daemon_runtime_dir(context.instance_root)
    pid_path = daemon_pid_file(context.instance_root)
    log_path = daemon_log_file(context.instance_root)
    runtime.mkdir(parents=True, exist_ok=True)
    log_path.touch(exist_ok=True)
    state = DaemonState.load(
        instance_root=context.instance_root,
        actor_id=context.actor_id,
        main_thread_id=context.main_thread_id,
    )
    state.register_handlers(_handler_names(handlers))
    state.save()

    pid = _read_pid(pid_path)
    if pid is not None and _pid_is_live(pid):
        if state.ready_for(pid, context.main_thread_id):
            status = daemon_status(instance_json, handlers=handlers, notify_subscriptions=notify_subscriptions)
            status["started"] = False
            return status
        _terminate_pid(pid)
        _remove_path(pid_path)
    if pid is not None:
        _remove_path(pid_path)
    state.payload["ready"] = None
    state.save()

    command = [
        sys.executable,
        str(INSTANCE_DAEMON_ENTRYPOINT.resolve()),
        "run",
        "--instance-json",
        str(instance_json),
    ]
    child_env = os.environ.copy()
    child_env.update(derive_daemon_runtime_env(context))
    with log_path.open("ab") as log_handle:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=str(context.instance_root),
            env=child_env,
        )
    _write_text_file(pid_path, str(process.pid))
    _append_daemon_event(context, "daemon_started", pid=process.pid, main_thread_id=context.main_thread_id)
    deadline = time.monotonic() + DAEMON_READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        wait_state = DaemonState.load(
            instance_root=context.instance_root,
            actor_id=context.actor_id,
            main_thread_id=context.main_thread_id,
        )
        if wait_state.ready_for(process.pid, context.main_thread_id):
            status = daemon_status(instance_json, handlers=handlers, notify_subscriptions=notify_subscriptions)
            status["started"] = True
            status["pid"] = process.pid
            status["pid_live"] = _pid_is_live(process.pid)
            status["live"] = bool(status["pid_live"])
            return status
        if process.poll() is not None:
            _remove_path(pid_path)
            raise RuntimeError(f"daemon exited before ready for {context.actor_id}; see {log_path}")
        time.sleep(DAEMON_READY_POLL_SECONDS)
    _terminate_pid(process.pid)
    _remove_path(pid_path)
    raise RuntimeError(f"daemon did not become ready for {context.actor_id}; see {log_path}")


def stop_daemon(instance_json: Path) -> dict[str, Any]:
    context = load_daemon_context(instance_json)
    identity_route = identity_route_for_context(context)
    state = DaemonState.load(
        instance_root=context.instance_root,
        actor_id=context.actor_id,
        main_thread_id=context.main_thread_id,
    )
    pid_path = daemon_pid_file(context.instance_root)
    pid = _read_pid(pid_path)
    terminated = True
    if pid is not None and _pid_is_live(pid):
        terminated = _terminate_pid(pid)
    _remove_path(pid_path)
    unregister = safe_unregister_daemon_actor(context, identity_route, state=state)
    _append_daemon_event(context, "daemon_stopped", pid=pid, terminated=bool(terminated))
    payload = {
        "ok": True,
        "pid": pid,
        "terminated": bool(terminated),
        "pid_file": str(pid_path),
    }
    payload.update(unregister)
    return payload


def run_daemon(
    instance_json: Path,
    *,
    handlers: list[Any] | None = None,
    notify_subscriptions: list[str] | tuple[str, ...] | None = None,
) -> int:
    context = load_daemon_context(instance_json)
    os.environ.update(derive_daemon_runtime_env(context))
    runtime_files.refresh_runtime_roots_from_env()
    identity_route = identity_route_for_context(context)
    ensure_actor_identity_profile(context, identity_route)
    state = DaemonState.load(
        instance_root=context.instance_root,
        actor_id=context.actor_id,
        main_thread_id=context.main_thread_id,
    )
    state.save()
    daemon_handlers = list(handlers or [])
    state.register_handlers(_handler_names(daemon_handlers))
    registered = False
    mailbox_server: daemon_mailbox.DaemonMailboxServer | None = None
    try:
        with app_server.AppServerClient(
            context.socket_path,
            timeout_seconds=app_server.DEFAULT_RPC_TIMEOUT_SECONDS,
            client_name=DAEMON_CLIENT_NAME,
            client_title=DAEMON_CLIENT_TITLE,
        ) as client:
            bind_main_thread(context, client)
            state.record_ready(pid=os.getpid(), main_thread_id=context.main_thread_id)
            _append_daemon_event(context, "daemon_ready", pid=os.getpid(), main_thread_id=context.main_thread_id)
            mailbox_server = start_daemon_mailbox(
                context=context,
                state=state,
                identity_route=identity_route,
                handlers=daemon_handlers,
            )
            if notify_subscriptions is None:
                register_daemon_actor(context, identity_route)
            else:
                register_daemon_actor(context, identity_route, notify_subscriptions=notify_subscriptions)
            registered = True
            while True:
                try:
                    notification = client.read_notification()
                except app_server.AppServerTimeoutError:
                    sweep_due_scheduled_triggers(
                        context,
                        state,
                        DaemonRuntime(context=context, state=state, client=client),
                        daemon_handlers,
                    )
                    heartbeat_daemon_actor(context, identity_route)
                    continue
                except app_server.AppServerError as exc:
                    state.record_error(origin_turn_id=None, message=str(exc))
                    return 1
                dispatch_notification(context, state, client, notification, daemon_handlers)
                sweep_due_scheduled_triggers(
                    context,
                    state,
                    DaemonRuntime(context=context, state=state, client=client),
                    daemon_handlers,
                )
    except app_server.AppServerError as exc:
        state.record_error(origin_turn_id=None, message=str(exc))
        return 1
    finally:
        if registered:
            safe_unregister_daemon_actor(context, identity_route, state=state)
        if mailbox_server is not None:
            mailbox_server.close()
    return 0
