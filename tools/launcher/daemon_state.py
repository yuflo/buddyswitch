"""Current-only, product-neutral state for the actor instance daemon."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


CURRENT_STATE_KEYS = frozenset(
    {
        "actor_id",
        "main_thread_id",
        "ready",
        "last_error",
        "handlers",
        "scheduled_trigger_ids",
        "scheduled_triggers",
    }
)
HANDLER_STATE_FIELDS = (
    "registered",
    "enabled",
    "active",
    "last_result",
    "last_handled_at",
    "last_error",
)
SCHEDULE_STATE_KEYS = frozenset(
    {
        "schedule_id",
        "type",
        "payload",
        "source_context",
        "status",
        "created_at",
        "updated_at",
        "due_at",
        "delivered_at",
        "canceled_at",
        "last_error",
        "dispatch_result",
        "schedule_key",
    }
)


def daemon_state_file(instance_root: Path) -> Path:
    return instance_root / "runtime" / "daemon" / "state.json"


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


def _optional_non_empty_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string when provided")
    return value.strip()


def _state_payload(actor_id: str, main_thread_id: str) -> dict[str, Any]:
    return {
        "actor_id": actor_id,
        "main_thread_id": main_thread_id,
        "ready": None,
        "last_error": None,
        "handlers": {},
        "scheduled_trigger_ids": [],
        "scheduled_triggers": {},
    }


def _normalize_handlers(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        raise ValueError("daemon state handlers must be an object")
    handlers: dict[str, dict[str, Any]] = {}
    for name, raw in value.items():
        if not isinstance(name, str) or not name:
            raise ValueError("daemon handler state names must be non-empty strings")
        if not isinstance(raw, dict):
            raise ValueError(f"daemon handler state for {name} must be an object")
        unknown = set(raw) - set(HANDLER_STATE_FIELDS)
        if unknown:
            raise ValueError(f"daemon handler state for {name} contains unsupported fields: {sorted(unknown)}")
        handlers[name] = {field: raw.get(field) for field in HANDLER_STATE_FIELDS if field in raw}
    return handlers


def _normalize_schedules(ids_value: Any, schedules_value: Any) -> tuple[list[str], dict[str, dict[str, Any]]]:
    if not isinstance(ids_value, list):
        raise ValueError("daemon state scheduled_trigger_ids must be an array")
    if not isinstance(schedules_value, dict):
        raise ValueError("daemon state scheduled_triggers must be an object")
    schedule_ids: list[str] = []
    for value in ids_value:
        if not isinstance(value, str) or not value:
            raise ValueError("daemon state schedule ids must be non-empty strings")
        if value not in schedule_ids:
            schedule_ids.append(value)
    schedules: dict[str, dict[str, Any]] = {}
    for schedule_id in schedule_ids:
        raw = schedules_value.get(schedule_id)
        if not isinstance(raw, dict):
            raise ValueError(f"daemon schedule {schedule_id} must be an object")
        unknown = set(raw) - SCHEDULE_STATE_KEYS
        if unknown:
            raise ValueError(f"daemon schedule {schedule_id} contains unsupported fields: {sorted(unknown)}")
        if raw.get("schedule_id") != schedule_id:
            raise ValueError(f"daemon schedule {schedule_id} has a mismatched schedule_id")
        if raw.get("status") not in {"pending", "delivered", "failed", "canceled"}:
            raise ValueError(f"daemon schedule {schedule_id} has an invalid status")
        for field in ("type", "created_at", "updated_at", "due_at"):
            if not isinstance(raw.get(field), str) or not raw.get(field):
                raise ValueError(f"daemon schedule {schedule_id}.{field} must be a non-empty string")
        if not isinstance(raw.get("payload"), dict):
            raise ValueError(f"daemon schedule {schedule_id}.payload must be an object")
        if not isinstance(raw.get("source_context"), dict):
            raise ValueError(f"daemon schedule {schedule_id}.source_context must be an object")
        row = dict(raw)
        row["payload"] = dict(raw["payload"])
        row["source_context"] = dict(raw["source_context"])
        schedules[schedule_id] = row
    extra_schedule_ids = set(schedules_value) - set(schedule_ids)
    if extra_schedule_ids:
        raise ValueError(f"daemon state contains unindexed schedules: {sorted(extra_schedule_ids)}")
    return schedule_ids, schedules


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
        return cls._from_loaded(
            path=path,
            loaded=loaded,
            actor_id=actor_id,
            main_thread_id=main_thread_id,
        )

    @classmethod
    def _from_loaded(
        cls,
        *,
        path: Path,
        loaded: Any,
        actor_id: str,
        main_thread_id: str,
    ) -> DaemonState:
        if not isinstance(loaded, dict):
            raise ValueError("daemon state must contain an object")
        unknown = set(loaded) - CURRENT_STATE_KEYS
        if unknown:
            raise ValueError(f"daemon state contains unsupported fields: {sorted(unknown)}")
        payload = _state_payload(actor_id, main_thread_id)
        payload.update(loaded)
        payload["actor_id"] = actor_id
        payload["main_thread_id"] = main_thread_id
        ready = payload.get("ready")
        if ready is not None and not isinstance(ready, dict):
            raise ValueError("daemon state ready must be an object or null")
        last_error = payload.get("last_error")
        if last_error is not None and not isinstance(last_error, dict):
            raise ValueError("daemon state last_error must be an object or null")
        payload["handlers"] = _normalize_handlers(payload.get("handlers"))
        schedule_ids, schedules = _normalize_schedules(
            payload.get("scheduled_trigger_ids"),
            payload.get("scheduled_triggers"),
        )
        payload["scheduled_trigger_ids"] = schedule_ids
        payload["scheduled_triggers"] = schedules
        return cls(path=path, payload=payload)

    def save(self) -> None:
        unknown = set(self.payload) - CURRENT_STATE_KEYS
        if unknown:
            raise ValueError(f"daemon state contains unsupported fields: {sorted(unknown)}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        temp_path.write_text(json.dumps(self.payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(self.path)

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
        return isinstance(ready, dict) and ready.get("pid") == pid and ready.get("main_thread_id") == main_thread_id

    def handler_state(self, handler_name: str) -> dict[str, Any]:
        handlers = self.payload["handlers"]
        state = handlers.setdefault(handler_name, {})
        if not isinstance(state, dict):
            raise ValueError(f"daemon handler state for {handler_name} must be an object")
        return state

    def update_handler_state(self, handler_name: str, values: dict[str, Any]) -> None:
        unknown = set(values) - set(HANDLER_STATE_FIELDS)
        if unknown:
            raise ValueError(f"daemon handler state for {handler_name} contains unsupported fields: {sorted(unknown)}")
        self.handler_state(handler_name).update(values)
        self.save()

    def register_handlers(self, handler_names: list[str]) -> None:
        for handler_name in handler_names:
            state = self.handler_state(handler_name)
            state.update(
                {
                    "registered": True,
                    "enabled": True,
                    "active": True,
                    "last_result": state.get("last_result"),
                    "last_handled_at": state.get("last_handled_at"),
                    "last_error": state.get("last_error"),
                }
            )
        self.save()

    def record_handler_result(self, handler_name: str, result: Any, *, origin_turn_id: str | None) -> None:
        if result.status == "ignored":
            return
        values: dict[str, Any] = {"last_result": result.status}
        if result.status == "handled":
            values.update({"last_handled_at": _utc_now(), "last_error": None})
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
                },
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
        timestamp = _format_utc_timestamp(_parse_utc_timestamp(now or _utc_now()))
        due_at = _format_utc_timestamp(_parse_utc_timestamp(timestamp) + timedelta(seconds=float(delay_seconds)))
        schedule_ids = self.payload["scheduled_trigger_ids"]
        schedules = self.payload["scheduled_triggers"]
        counter = 1
        while f"schedule-{counter}" in schedules:
            counter += 1
        schedule_id = f"schedule-{counter}"
        row: dict[str, Any] = {
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
        if normalized_schedule_key is None:
            raise ValueError("schedule_key must be a non-empty string")
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
        schedules = self.payload["scheduled_triggers"]
        for schedule_id in self.payload["scheduled_trigger_ids"]:
            row = schedules[schedule_id]
            if row.get("status") == "pending" and row.get("schedule_key") == normalized_schedule_key:
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
        current = _parse_utc_timestamp(now or _utc_now())
        schedules = self.payload["scheduled_triggers"]
        return [
            dict(schedules[schedule_id])
            for schedule_id in self.payload["scheduled_trigger_ids"]
            if schedules[schedule_id].get("status") == "pending"
            and _parse_utc_timestamp(schedules[schedule_id]["due_at"]) <= current
        ]

    def _update_schedule(self, schedule_id: str, values: dict[str, Any]) -> dict[str, Any]:
        schedules = self.payload["scheduled_triggers"]
        if schedule_id not in schedules:
            raise KeyError(schedule_id)
        schedules[schedule_id].update(values)
        self.save()
        return dict(schedules[schedule_id])

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
            {"status": "canceled", "updated_at": timestamp, "canceled_at": timestamp},
        )

    def _cancel_pending_schedules_by_source_owner(
        self,
        owner: str,
        *,
        now: str | None = None,
    ) -> list[dict[str, Any]]:
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("owner must be a non-empty string")
        timestamp = _format_utc_timestamp(_parse_utc_timestamp(now or _utc_now()))
        canceled: list[dict[str, Any]] = []
        for schedule_id in self.payload["scheduled_trigger_ids"]:
            row = self.payload["scheduled_triggers"][schedule_id]
            source_context = row.get("source_context")
            if (
                row.get("status") != "pending"
                or not isinstance(source_context, dict)
                or source_context.get("owner") != owner.strip()
            ):
                continue
            row.update({"status": "canceled", "updated_at": timestamp, "canceled_at": timestamp})
            canceled.append(dict(row))
        if canceled:
            self.save()
        return canceled


def cancel_pending_schedules_by_source_owner(
    *,
    instance_root: Path,
    actor_id: str,
    main_thread_id: str | None,
    source_owner: str,
    now: str | None = None,
) -> list[dict[str, Any]]:
    """Cancel pending schedules for one exact state identity and source owner."""

    normalized_actor_id = _optional_non_empty_string(actor_id, "actor_id")
    normalized_owner = _optional_non_empty_string(source_owner, "source_owner")
    if normalized_actor_id is None or normalized_owner is None:
        raise ValueError("actor_id and source_owner are required")
    path = daemon_state_file(Path(instance_root))
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    normalized_thread_id = _optional_non_empty_string(main_thread_id, "main_thread_id")
    if normalized_thread_id is None:
        raise ValueError("main_thread_id is required for existing daemon state")
    if not isinstance(loaded, dict):
        raise ValueError("daemon state must contain an object")
    if loaded.get("actor_id") != normalized_actor_id or loaded.get("main_thread_id") != normalized_thread_id:
        return []
    state = DaemonState._from_loaded(
        path=path,
        loaded=loaded,
        actor_id=normalized_actor_id,
        main_thread_id=normalized_thread_id,
    )
    return state._cancel_pending_schedules_by_source_owner(normalized_owner, now=now)
