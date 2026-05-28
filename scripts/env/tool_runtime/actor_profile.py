#!/usr/bin/env python3
"""Runtime actor identity normalization for env.tool dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class AuthSubject:
    """Role-action auth subject for the current runtime actor."""

    role_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "role_id", _require_text(self.role_id, "role_id"))


@dataclass(frozen=True)
class RuntimeInstanceRecord:
    """Trusted local runtime instance identity record."""

    instance_id: str
    buddy_id: str
    instance_json: Path
    payload: dict[str, Any]


@dataclass(frozen=True)
class RuntimeActorProfile:
    """Normalized actor profile for one local runtime instance."""

    instance_id: str
    active_buddy: str
    auth_subject: AuthSubject
    instance_record: RuntimeInstanceRecord


def runtime_instance_record_from_dispatch(
    *,
    instance_id: str,
    active_buddy: str,
    instance_json: Path,
    instance_payload: Mapping[str, Any] | None,
) -> RuntimeInstanceRecord:
    return RuntimeInstanceRecord(
        instance_id=instance_id,
        buddy_id=active_buddy,
        instance_json=instance_json,
        payload=dict(instance_payload or {}),
    )


def resolve_runtime_actor_profile(record: RuntimeInstanceRecord) -> RuntimeActorProfile:
    instance_id = _require_text(record.instance_id, "instance_id")
    buddy_id = _require_text(record.buddy_id, "buddy_id")
    normalized_record = RuntimeInstanceRecord(
        instance_id=instance_id,
        buddy_id=buddy_id,
        instance_json=Path(record.instance_json),
        payload=dict(record.payload),
    )
    auth_subject = AuthSubject(role_id=buddy_id)
    return RuntimeActorProfile(
        instance_id=instance_id,
        active_buddy=buddy_id,
        auth_subject=auth_subject,
        instance_record=normalized_record,
    )
