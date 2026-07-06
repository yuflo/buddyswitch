#!/usr/bin/env python3
"""Daemon trigger normalization helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


APP_SERVER_NOTIFICATION = "app_server_notification"
MAILBOX_CROSS_ACTOR_SIGNAL = "mailbox_cross_actor_signal"
MAILBOX_LOCAL_TRIGGER = "mailbox_local_trigger"
SCHEDULED_TRIGGER = "scheduled_trigger"


class DaemonTrigger:
    def __init__(
        self,
        *,
        source: str,
        type: str,
        target_identity_id: str,
        target_role_id: str,
        origin_id: str | None,
        correlation_id: str | None,
        payload: dict[str, Any],
        source_context: dict[str, Any],
    ) -> None:
        self.source = _non_empty_string(source, "source")
        self.type = _non_empty_string(type, "type")
        self.target_identity_id = _non_empty_string(target_identity_id, "target_identity_id")
        self.target_role_id = _non_empty_string(target_role_id, "target_role_id")
        self.origin_id = _optional_string(origin_id, "origin_id")
        self.correlation_id = _optional_string(correlation_id, "correlation_id")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        if not isinstance(source_context, dict):
            raise ValueError("source_context must be an object")
        self.payload = dict(payload)
        self.source_context = dict(source_context)

    def to_payload(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "type": self.type,
            "target_identity_id": self.target_identity_id,
            "target_role_id": self.target_role_id,
            "origin_id": self.origin_id,
            "correlation_id": self.correlation_id,
            "payload": dict(self.payload),
            "source_context": dict(self.source_context),
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DaemonTrigger):
            return False
        return self.to_payload() == other.to_payload()

    def __repr__(self) -> str:
        return f"DaemonTrigger({self.to_payload()!r})"


def _non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string when provided")
    return value.strip()


def _route_payload(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an identity route object")
    return {
        "identity_id": _non_empty_string(value.get("identity_id"), f"{field}.identity_id"),
        "role_id": _non_empty_string(value.get("role_id"), f"{field}.role_id"),
    }


def _string_field(payload: dict[str, Any], *names: str) -> str | None:
    for name in names:
        value = payload.get(name)
        if isinstance(value, str) and value:
            return value
    return None


def _trigger_type_for_app_server_method(method: str) -> str:
    return f"app_server.{method.replace('/', '_')}"


def normalize_app_server_notification(
    notification: dict[str, Any],
    *,
    target_identity_id: str,
    target_role_id: str,
    correlation_id: str | None = None,
) -> DaemonTrigger:
    if not isinstance(notification, dict):
        raise ValueError("app-server notification must be an object")
    method = _non_empty_string(notification.get("method"), "method")
    params = notification.get("params")
    if not isinstance(params, dict):
        params = {}
    turn = params.get("turn")
    turn_payload = turn if isinstance(turn, dict) else {}
    thread_id = _string_field(params, "threadId", "thread_id")
    turn_id = _string_field(turn_payload, "id", "turn_id", "turnId")
    turn_status = _string_field(turn_payload, "status")
    source_context: dict[str, Any] = {"method": method}
    if thread_id is not None:
        source_context["thread_id"] = thread_id
    if turn_id is not None:
        source_context["turn_id"] = turn_id
    if turn_status is not None:
        source_context["turn_status"] = turn_status
    return DaemonTrigger(
        source=APP_SERVER_NOTIFICATION,
        type=_trigger_type_for_app_server_method(method),
        target_identity_id=target_identity_id,
        target_role_id=target_role_id,
        origin_id=turn_id,
        correlation_id=correlation_id,
        payload=dict(params),
        source_context=source_context,
    )


def normalize_cross_actor_signal(signal: dict[str, Any]) -> DaemonTrigger:
    if not isinstance(signal, dict):
        raise ValueError("daemon signal must be an object")
    payload = signal.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("signal payload must be an object")
    signal_id = _non_empty_string(signal.get("signal_id"), "signal_id")
    signal_type = _non_empty_string(signal.get("type"), "type")
    source_identity_id = _non_empty_string(signal.get("source_identity_id"), "source_identity_id")
    source_role_id = _non_empty_string(signal.get("source_role_id"), "source_role_id")
    target_identity_id = _non_empty_string(signal.get("target_identity_id"), "target_identity_id")
    target_role_id = _non_empty_string(signal.get("target_role_id"), "target_role_id")
    created_at = _non_empty_string(signal.get("created_at"), "created_at")
    correlation_id = signal.get("correlation_id")
    return DaemonTrigger(
        source=MAILBOX_CROSS_ACTOR_SIGNAL,
        type=signal_type,
        target_identity_id=target_identity_id,
        target_role_id=target_role_id,
        origin_id=signal_id,
        correlation_id=correlation_id if isinstance(correlation_id, str) and correlation_id else None,
        payload=dict(payload),
        source_context={
            "signal_id": signal_id,
            "source_identity_id": source_identity_id,
            "source_role_id": source_role_id,
            "created_at": created_at,
        },
    )


def normalize_local_trigger(
    *,
    trigger_type: str,
    target_identity_id: str,
    target_role_id: str,
    origin_id: str | None,
    correlation_id: str | None,
    payload: dict[str, Any],
    source_context: dict[str, Any],
) -> DaemonTrigger:
    return DaemonTrigger(
        source=MAILBOX_LOCAL_TRIGGER,
        type=trigger_type,
        target_identity_id=target_identity_id,
        target_role_id=target_role_id,
        origin_id=origin_id,
        correlation_id=correlation_id,
        payload=payload,
        source_context=source_context,
    )


def normalize_scheduled_trigger(
    schedule: dict[str, Any],
    *,
    target_identity_id: str,
    target_role_id: str,
) -> DaemonTrigger:
    if not isinstance(schedule, dict):
        raise ValueError("schedule must be an object")
    schedule_id = _non_empty_string(schedule.get("schedule_id"), "schedule_id")
    trigger_type = _non_empty_string(schedule.get("type"), "type")
    payload = schedule.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("schedule payload must be an object")
    raw_source_context = schedule.get("source_context")
    source_context = dict(raw_source_context) if isinstance(raw_source_context, dict) else {}
    source_context["schedule_id"] = schedule_id
    due_at = schedule.get("due_at")
    if isinstance(due_at, str) and due_at:
        source_context["due_at"] = due_at
    created_at = schedule.get("created_at")
    if isinstance(created_at, str) and created_at:
        source_context["created_at"] = created_at
    return DaemonTrigger(
        source=SCHEDULED_TRIGGER,
        type=trigger_type,
        target_identity_id=target_identity_id,
        target_role_id=target_role_id,
        origin_id=schedule_id,
        correlation_id=None,
        payload=dict(payload),
        source_context=source_context,
    )
