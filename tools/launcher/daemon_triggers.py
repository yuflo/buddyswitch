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


class DaemonTrigger:
    def __init__(
        self,
        *,
        source: str,
        type: str,
        target_actor_address: dict[str, str],
        origin_id: str | None,
        correlation_id: str | None,
        payload: dict[str, Any],
        source_context: dict[str, Any],
    ) -> None:
        self.source = _non_empty_string(source, "source")
        self.type = _non_empty_string(type, "type")
        self.target_actor_address = _actor_address_payload(target_actor_address, "target_actor_address")
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
            "target_actor_address": dict(self.target_actor_address),
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


def _actor_address_payload(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an actor address object")
    role_id = _non_empty_string(value.get("role_id"), f"{field}.role_id")
    actor_id = _non_empty_string(value.get("actor_id"), f"{field}.actor_id")
    return {"role_id": role_id, "actor_id": actor_id}


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
    target_actor_address: dict[str, Any],
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
        target_actor_address=_actor_address_payload(target_actor_address, "target_actor_address"),
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
    source_actor_address = _actor_address_payload(signal.get("source_actor_address"), "source_actor_address")
    target_actor_address = _actor_address_payload(signal.get("target_actor_address"), "target_actor_address")
    created_at = _non_empty_string(signal.get("created_at"), "created_at")
    correlation_id = signal.get("correlation_id")
    return DaemonTrigger(
        source=MAILBOX_CROSS_ACTOR_SIGNAL,
        type=signal_type,
        target_actor_address=target_actor_address,
        origin_id=signal_id,
        correlation_id=correlation_id if isinstance(correlation_id, str) and correlation_id else None,
        payload=dict(payload),
        source_context={
            "signal_id": signal_id,
            "source_actor_address": source_actor_address,
            "created_at": created_at,
        },
    )


def normalize_local_trigger(
    *,
    trigger_type: str,
    target_actor_address: dict[str, Any],
    origin_id: str | None,
    correlation_id: str | None,
    payload: dict[str, Any],
    source_context: dict[str, Any],
) -> DaemonTrigger:
    return DaemonTrigger(
        source=MAILBOX_LOCAL_TRIGGER,
        type=trigger_type,
        target_actor_address=_actor_address_payload(target_actor_address, "target_actor_address"),
        origin_id=origin_id,
        correlation_id=correlation_id,
        payload=payload,
        source_context=source_context,
    )
