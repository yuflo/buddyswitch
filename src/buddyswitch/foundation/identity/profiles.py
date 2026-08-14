"""Identity profile storage backed by canonical runtime object files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from buddyswitch.foundation.identity.model import ActorIdentityProfile
from buddyswitch.foundation.identity.model import ExternalIdentityProfile
import buddyswitch.foundation.state.runtime as state_runtime


def _identity_root(objects_root: Path | None = None) -> Path:
    return (state_runtime.OBJECTS_ROOT if objects_root is None else objects_root) / "identities"


def _actor_dir(objects_root: Path | None = None) -> Path:
    return _identity_root(objects_root) / "actors"


def _external_dir() -> Path:
    return _identity_root() / "externals"


def _profile_path(root: Path, identity_id: str, field: str) -> Path:
    return root / f"{state_runtime.require_id(identity_id, field)}.json"


def save_actor_identity_profile(payload: dict[str, Any]) -> dict[str, Any]:
    profile = ActorIdentityProfile.from_payload(payload)
    normalized = profile.to_payload()
    state_runtime.require_runtime_workspace_write_root()
    state_runtime.write_json_object(
        _profile_path(_actor_dir(), profile.identity.id, "actor identity id"),
        normalized,
    )
    return normalized


def _load_actor_identity_profile(
    identity_id: str,
    *,
    objects_root: Path | None = None,
) -> ActorIdentityProfile | None:
    path = _profile_path(
        _actor_dir(objects_root),
        identity_id,
        "actor identity id",
    )
    if not path.exists():
        return None
    profile = ActorIdentityProfile.from_payload(state_runtime.read_json_object(path))
    if profile.identity.id != identity_id:
        raise ValueError(
            f"Actor identity profile id '{profile.identity.id}' does not match "
            f"requested actor identity id '{identity_id}'"
        )
    return profile


def get_actor_identity_profile(
    identity_id: str,
    *,
    objects_root: Path | None = None,
) -> dict[str, Any] | None:
    profile = _load_actor_identity_profile(identity_id, objects_root=objects_root)
    return profile.to_payload() if profile is not None else None


def get_actor_role_id(
    identity_id: str,
    *,
    objects_root: Path | None = None,
) -> str | None:
    """Return the canonical Role owned by one Actor Identity Profile."""

    profile = _load_actor_identity_profile(identity_id, objects_root=objects_root)
    return profile.role_id if profile is not None else None


def list_actor_identity_profiles() -> list[dict[str, Any]]:
    root = _actor_dir()
    if not root.exists():
        return []
    rows = [
        ActorIdentityProfile.from_payload(
            state_runtime.read_json_object(path)
        ).to_payload()
        for path in sorted(root.glob("*.json"))
    ]
    return sorted(rows, key=lambda row: row["identity"]["id"])


def save_external_profile(payload: dict[str, Any]) -> dict[str, Any]:
    profile = ExternalIdentityProfile.from_payload(payload)
    normalized = profile.to_payload()
    state_runtime.require_central_im_write_root()
    state_runtime.write_json_object(
        _profile_path(_external_dir(), profile.identity.id, "external identity id"),
        normalized,
    )
    return normalized


def get_external_profile(identity_id: str) -> dict[str, Any] | None:
    path = _profile_path(_external_dir(), identity_id, "external identity id")
    if not path.exists():
        return None
    return ExternalIdentityProfile.from_payload(
        state_runtime.read_json_object(path)
    ).to_payload()


def list_external_profiles() -> list[dict[str, Any]]:
    root = _external_dir()
    if not root.exists():
        return []
    rows = [
        ExternalIdentityProfile.from_payload(
            state_runtime.read_json_object(path)
        ).to_payload()
        for path in sorted(root.glob("*.json"))
    ]
    return sorted(rows, key=lambda row: row["identity"]["id"])
