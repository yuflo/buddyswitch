"""Host-owned runtime context passed into tool black-box entrypoints."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from buddyswitch.env.domain.identity import ActorIdentityProfile as _ActorIdentityProfile
from buddyswitch.env.domain.identity import IdentityRef as _IdentityRef
from buddyswitch.env.domain.identity import actor_identity as _actor_identity
from buddyswitch.env.repos import runtime_files
from buddyswitch.foundation.daemon import client as daemon_client
import re


__all__ = ("InvocationFact", "ToolContext")


_ROLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")


def _actor_identity_id(value: Any, field: str) -> str:
    return _actor_identity(value).id


def _role_id(value: Any, field: str) -> str:
    role_id = str(value or "").strip()
    if _ROLE_ID_PATTERN.fullmatch(role_id) is None:
        raise ValueError(f"{field} must match /^[a-z][a-z0-9-]*$/")
    return role_id


class _ActorDirectoryAccess:
    """Actor directory queries over central daemon primitives."""

    def list_online_actors(self, *, role_id: str | None = None) -> dict[str, Any]:
        return daemon_client.list_online_actors(role_id=role_id)

    def check_reachability(self, *, target_identity_id: str) -> dict[str, Any]:
        return daemon_client.check_reachability(
            target_identity_id=_actor_identity_id(target_identity_id, "target_identity_id"),
        )


class _SignalDeliveryAccess:
    """Generic signal envelope creation and delivery for product tools."""

    def __init__(self, *, current_identity: _IdentityRef, role_id: str) -> None:
        self.current_identity = current_identity
        self._role_id = role_id

    def deliver_signal(
        self,
        *,
        signal_type: str,
        target_identity_id: str,
        target_role_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        signal = {
            "signal_id": f"sig-{uuid.uuid4().hex}",
            "type": signal_type,
            "source_identity_id": self.current_identity.id,
            "source_role_id": self._role_id,
            "target_identity_id": _actor_identity_id(target_identity_id, "target_identity_id"),
            "target_role_id": _role_id(target_role_id, "target_role_id"),
            "payload": dict(payload),
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        return daemon_client.deliver_signal(signal=signal)


@dataclass(frozen=True)
class InvocationFact:
    """Host-observed identity of one native tool invocation."""

    thread_id: str | None = None
    turn_id: str | None = None
    request_id: str | None = None
    bound_capability: str | None = None


@dataclass(frozen=True)
class ToolContext(Mapping[str, Any]):
    """Host-owned runtime context object passed to each tool invoke."""

    current_identity: _IdentityRef
    current_actor_identity_profile: _ActorIdentityProfile
    role_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]
    actor_private_root: Path
    manifest_path: Path | None = None
    invocation: InvocationFact = field(default_factory=InvocationFact)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "actor_directory",
            _ActorDirectoryAccess(),
        )
        object.__setattr__(
            self,
            "signal_delivery",
            _SignalDeliveryAccess(
                current_identity=self.current_identity,
                role_id=self.role_id,
            ),
        )
    @classmethod
    def from_identity_profile(
        cls,
        *,
        actor_identity_profile: _ActorIdentityProfile,
        instance_json: Path,
        instance_payload: dict[str, Any],
        manifest: dict[str, Any],
        manifest_path: Path | None = None,
        invocation: InvocationFact | None = None,
    ) -> "ToolContext":
        return cls(
            current_identity=actor_identity_profile.identity,
            current_actor_identity_profile=actor_identity_profile,
            role_id=actor_identity_profile.role_id,
            instance_json=instance_json,
            instance_payload=instance_payload,
            manifest=manifest,
            actor_private_root=runtime_files.actor_private_dir(
                instance_payload
            ).resolve(strict=False),
            manifest_path=manifest_path,
            invocation=invocation or InvocationFact(),
        )

    def now(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def __getitem__(self, key: str) -> Any:
        if key == "current_identity":
            return self.current_identity.to_payload()
        if key == "active_role":
            return self.role_id
        if key == "instance_json":
            return self.instance_json
        if key == "instance_payload":
            return self.instance_payload
        if key == "manifest":
            return self.manifest
        if key == "manifest_path":
            return self.manifest_path
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        yield "current_identity"
        yield "active_role"
        yield "instance_json"
        yield "instance_payload"
        yield "manifest"
        yield "manifest_path"

    def __len__(self) -> int:
        return 6

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default
