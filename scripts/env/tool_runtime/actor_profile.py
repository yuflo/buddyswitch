#!/usr/bin/env python3
"""Runtime actor identity normalization for env.tool dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import re


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


BUDDY_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
INSTANCE_ID_PATTERN = re.compile(r"^inst-[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class AuthSubject:
    """Role-action auth subject for the current runtime actor."""

    role_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "role_id", _require_text(self.role_id, "role_id"))


@dataclass(frozen=True)
class RuntimeActorAddress:
    """Routable identity for one buddy runtime instance."""

    buddy_id: str
    instance_id: str

    def __post_init__(self) -> None:
        buddy_id = _require_text(self.buddy_id, "buddy_id")
        instance_id = _require_text(self.instance_id, "instance_id")
        if BUDDY_ID_PATTERN.fullmatch(buddy_id) is None:
            raise ValueError("buddy_id must match /^[a-z][a-z0-9-]*$/")
        if INSTANCE_ID_PATTERN.fullmatch(instance_id) is None:
            raise ValueError("instance_id must match /^inst-[A-Za-z0-9._-]+$/")
        if not instance_id.startswith(f"inst-{buddy_id}-"):
            raise ValueError("instance_id must start with inst-<buddy_id>-")
        object.__setattr__(self, "buddy_id", buddy_id)
        object.__setattr__(self, "instance_id", instance_id)

    def to_payload(self) -> dict[str, str]:
        return {
            "buddy_id": self.buddy_id,
            "instance_id": self.instance_id,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> RuntimeActorAddress:
        if not isinstance(payload, Mapping):
            raise ValueError("actor_address payload must be an object")
        extra_keys = set(payload) - {"buddy_id", "instance_id"}
        if extra_keys:
            raise ValueError(f"actor_address payload contains non-identity fields: {sorted(extra_keys)}")
        return cls(
            buddy_id=payload.get("buddy_id"),
            instance_id=payload.get("instance_id"),
        )


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
    actor_address: RuntimeActorAddress
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
    actor_address = RuntimeActorAddress(buddy_id=buddy_id, instance_id=instance_id)
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
        actor_address=actor_address,
        auth_subject=auth_subject,
        instance_record=normalized_record,
    )
