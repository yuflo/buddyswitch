"""Shared identity core for product-level "who" references."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Literal, Mapping


IdentityType = Literal["actor", "external"]
VALID_IDENTITY_TYPES = {"actor", "external"}
ROLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
ACTOR_ID_PATTERN = re.compile(r"^act-[A-Za-z0-9._-]+$")
EXTERNAL_ID_PATTERN = re.compile(r"^ext-[A-Za-z0-9._-]+$")


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _require_optional_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _require_text(value, field)


def _require_role_id(value: Any, field: str = "role_id") -> str:
    role_id = _require_text(value, field)
    if ROLE_ID_PATTERN.fullmatch(role_id) is None:
        raise ValueError(f"{field} must match /^[a-z][a-z0-9-]*$/")
    return role_id


def _require_actor_identity_id(value: Any, field: str = "actor identity id") -> str:
    identity_id = _require_text(value, field)
    if ACTOR_ID_PATTERN.fullmatch(identity_id) is None:
        raise ValueError(f"{field} must match /^act-[A-Za-z0-9._-]+$/")
    return identity_id


def _require_external_identity_id(value: Any, field: str = "external identity id") -> str:
    identity_id = _require_text(value, field)
    if EXTERNAL_ID_PATTERN.fullmatch(identity_id) is None:
        raise ValueError(f"{field} must match /^ext-[A-Za-z0-9._-]+$/")
    return identity_id


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
        if identity_type == "actor":
            identity_id = _require_actor_identity_id(identity_id, "actor identity id")
        if identity_type == "external":
            identity_id = _require_external_identity_id(identity_id, "external identity id")
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


@dataclass(frozen=True)
class ActorIdentityProfile:
    """Static identity profile for one actor identity."""

    identity: IdentityRef
    role_id: str
    label: str | None = None
    created_at: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.identity, IdentityRef) or self.identity.type != "actor":
            raise ValueError("ActorIdentityProfile.identity must be an actor identity")
        object.__setattr__(self, "role_id", _require_role_id(self.role_id))
        object.__setattr__(self, "label", _require_optional_text(self.label, "label"))
        object.__setattr__(self, "created_at", _require_optional_text(self.created_at, "created_at"))

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "identity": self.identity.to_payload(),
            "role_id": self.role_id,
        }
        if self.label is not None:
            payload["label"] = self.label
        if self.created_at is not None:
            payload["created_at"] = self.created_at
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ActorIdentityProfile":
        if not isinstance(payload, Mapping):
            raise ValueError("actor identity profile payload must be an object")
        extra_keys = set(payload) - {"identity", "role_id", "label", "created_at"}
        if extra_keys:
            raise ValueError(f"actor identity profile contains unsupported fields: {sorted(extra_keys)}")
        identity_payload = payload.get("identity")
        if not isinstance(identity_payload, Mapping):
            raise ValueError("actor identity profile identity must be an object")
        return cls(
            identity=IdentityRef.from_payload(identity_payload),
            role_id=payload.get("role_id"),
            label=payload.get("label"),
            created_at=payload.get("created_at"),
        )


@dataclass(frozen=True)
class ExternalIdentityProfile:
    """Static identity profile for one external identity."""

    identity: IdentityRef
    display_name: str | None = None
    created_at: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.identity, IdentityRef) or self.identity.type != "external":
            raise ValueError("ExternalIdentityProfile.identity must be an external identity")
        object.__setattr__(self, "display_name", _require_optional_text(self.display_name, "display_name"))
        object.__setattr__(self, "created_at", _require_optional_text(self.created_at, "created_at"))

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"identity": self.identity.to_payload()}
        if self.display_name is not None:
            payload["display_name"] = self.display_name
        if self.created_at is not None:
            payload["created_at"] = self.created_at
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ExternalIdentityProfile":
        if not isinstance(payload, Mapping):
            raise ValueError("external identity profile payload must be an object")
        extra_keys = set(payload) - {"identity", "display_name", "created_at"}
        if extra_keys:
            raise ValueError(f"external identity profile contains unsupported fields: {sorted(extra_keys)}")
        identity_payload = payload.get("identity")
        if not isinstance(identity_payload, Mapping):
            raise ValueError("external identity profile identity must be an object")
        return cls(
            identity=IdentityRef.from_payload(identity_payload),
            display_name=payload.get("display_name"),
            created_at=payload.get("created_at"),
        )
