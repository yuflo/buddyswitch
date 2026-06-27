#!/usr/bin/env python3
"""Actor Identity normalization for env.tool dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import re

from env.domain.identity import IdentityRef


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


ROLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
ACTOR_ID_PATTERN = re.compile(r"^act-[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class Role:
    """Capability and responsibility class."""

    role_id: str

    def __post_init__(self) -> None:
        role_id = _require_text(self.role_id, "role_id")
        if ROLE_ID_PATTERN.fullmatch(role_id) is None:
            raise ValueError("role_id must match /^[a-z][a-z0-9-]*$/")
        object.__setattr__(self, "role_id", role_id)


@dataclass(frozen=True)
class Actor:
    """Concrete runtime participant."""

    actor_id: str
    role_id: str

    def __post_init__(self) -> None:
        actor_id = _require_text(self.actor_id, "actor_id")
        if ACTOR_ID_PATTERN.fullmatch(actor_id) is None:
            raise ValueError("actor_id must match /^act-[A-Za-z0-9._-]+$/")
        role = Role(self.role_id)
        object.__setattr__(self, "actor_id", actor_id)
        object.__setattr__(self, "role_id", role.role_id)

    def to_payload(self) -> dict[str, str]:
        return {"actor_id": self.actor_id, "role_id": self.role_id}


@dataclass(frozen=True)
class AuthSubject:
    """Role-action auth subject for the current runtime actor."""

    role_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "role_id", Role(self.role_id).role_id)


@dataclass(frozen=True)
class ActorAddress:
    """Routeable identity for one concrete Actor."""

    actor_id: str
    role_id: str

    def __post_init__(self) -> None:
        actor = Actor(actor_id=self.actor_id, role_id=self.role_id)
        object.__setattr__(self, "actor_id", actor.actor_id)
        object.__setattr__(self, "role_id", actor.role_id)

    def to_payload(self) -> dict[str, str]:
        return {"actor_id": self.actor_id, "role_id": self.role_id}

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ActorAddress":
        if not isinstance(payload, Mapping):
            raise ValueError("actor_address payload must be an object")
        extra_keys = set(payload) - {"actor_id", "role_id"}
        if extra_keys:
            raise ValueError(f"actor_address payload contains non-identity fields: {sorted(extra_keys)}")
        missing = [key for key in ("actor_id", "role_id") if key not in payload]
        if missing:
            raise ValueError(f"actor_address payload missing required fields: {missing}")
        return cls(actor_id=payload.get("actor_id"), role_id=payload.get("role_id"))


@dataclass(frozen=True)
class RuntimeActorRecord:
    """Trusted local runtime Actor identity record."""

    actor_id: str
    role_id: str
    instance_json: Path
    payload: dict[str, Any]


@dataclass(frozen=True)
class ActorProfile:
    """Normalized actor profile for one local runtime actor."""

    actor_id: str
    role_id: str
    current_identity: IdentityRef
    active_actor: Actor
    active_role: Role
    actor_address: ActorAddress
    auth_subject: AuthSubject
    actor_record: RuntimeActorRecord


def runtime_actor_record_from_dispatch(
    *,
    actor_id: str,
    role_id: str,
    instance_json: Path,
    instance_payload: Mapping[str, Any] | None,
) -> RuntimeActorRecord:
    return RuntimeActorRecord(
        actor_id=actor_id,
        role_id=role_id,
        instance_json=instance_json,
        payload=dict(instance_payload or {}),
    )


def resolve_actor_profile(record: RuntimeActorRecord) -> ActorProfile:
    actor = Actor(actor_id=record.actor_id, role_id=record.role_id)
    role = Role(actor.role_id)
    actor_address = ActorAddress(actor_id=actor.actor_id, role_id=actor.role_id)
    normalized_record = RuntimeActorRecord(
        actor_id=actor.actor_id,
        role_id=role.role_id,
        instance_json=Path(record.instance_json),
        payload=dict(record.payload),
    )
    auth_subject = AuthSubject(role_id=role.role_id)
    return ActorProfile(
        actor_id=actor.actor_id,
        role_id=role.role_id,
        current_identity=IdentityRef(id=actor.actor_id, type="actor"),
        active_actor=actor,
        active_role=role,
        actor_address=actor_address,
        auth_subject=auth_subject,
        actor_record=normalized_record,
    )


def actor_identity_to_address(identity: IdentityRef, *, role_id: str) -> ActorAddress:
    if not isinstance(identity, IdentityRef) or identity.type != "actor":
        raise ValueError("actor identity is required for actor routing projection")
    return ActorAddress(actor_id=identity.id, role_id=role_id)
