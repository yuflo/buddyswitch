#!/usr/bin/env python3
"""Shared identity core for product-level "who" references."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping


IdentityType = Literal["actor", "external"]
VALID_IDENTITY_TYPES = {"actor", "external"}


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class IdentityRef:
    """Stable product identity reference."""

    id: str
    type: IdentityType

    def __post_init__(self) -> None:
        identity_id = _require_text(self.id, "identity.id")
        identity_type = _require_text(self.type, "identity.type")
        if identity_type not in VALID_IDENTITY_TYPES:
            raise ValueError("identity.type must be actor or external")
        object.__setattr__(self, "id", identity_id)
        object.__setattr__(self, "type", identity_type)

    def to_payload(self) -> dict[str, str]:
        return {"id": self.id, "type": self.type}

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "IdentityRef":
        if not isinstance(payload, Mapping):
            raise ValueError("identity payload must be an object")
        extra_keys = set(payload) - {"id", "type"}
        if extra_keys:
            raise ValueError(f"identity payload contains unsupported fields: {sorted(extra_keys)}")
        return cls(id=payload.get("id"), type=payload.get("type"))


def actor_identity(actor_id: Any) -> IdentityRef:
    return IdentityRef(id=actor_id, type="actor")


def external_identity(external_id: Any) -> IdentityRef:
    return IdentityRef(id=external_id, type="external")


def identity_from_im_participant(participant: Mapping[str, Any]) -> IdentityRef:
    if not isinstance(participant, Mapping):
        raise ValueError("participant must be an object")
    kind = participant.get("kind")
    if kind == "actor":
        actor_address = participant.get("actor_address")
        if not isinstance(actor_address, Mapping):
            raise ValueError("participant.actor_address must be an object")
        return actor_identity(actor_address.get("actor_id"))
    if kind == "external":
        return external_identity(participant.get("external_id"))
    raise ValueError("participant.kind must be actor or external")
