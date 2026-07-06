#!/usr/bin/env python3
"""Identity profile repository backed by runtime object files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from env.domain.identity import ActorIdentityProfile
from env.domain.identity import ExternalIdentityProfile
from . import runtime_files


def identity_root() -> Path:
    return runtime_files.OBJECTS_ROOT / "identities"


def _actor_dir() -> Path:
    return identity_root() / "actors"


def _external_dir() -> Path:
    return identity_root() / "externals"


def _profile_path(root: Path, identity_id: str, field: str) -> Path:
    return root / f"{runtime_files.require_id(identity_id, field)}.json"


def save_actor_identity_profile(payload: dict[str, Any]) -> dict[str, Any]:
    profile = ActorIdentityProfile.from_payload(payload)
    normalized = profile.to_payload()
    runtime_files.require_runtime_workspace_write_root()
    runtime_files.write_json_object(_profile_path(_actor_dir(), profile.identity.id, "actor identity id"), normalized)
    return normalized


def get_actor_identity_profile(identity_id: str) -> dict[str, Any] | None:
    path = _profile_path(_actor_dir(), identity_id, "actor identity id")
    if not path.exists():
        return None
    return ActorIdentityProfile.from_payload(runtime_files.read_json_object(path)).to_payload()


def list_actor_identity_profiles() -> list[dict[str, Any]]:
    root = _actor_dir()
    if not root.exists():
        return []
    rows = [ActorIdentityProfile.from_payload(runtime_files.read_json_object(path)).to_payload() for path in sorted(root.glob("*.json"))]
    return sorted(rows, key=lambda row: row["identity"]["id"])


def save_external_profile(payload: dict[str, Any]) -> dict[str, Any]:
    profile = ExternalIdentityProfile.from_payload(payload)
    normalized = profile.to_payload()
    runtime_files.require_central_im_write_root()
    runtime_files.write_json_object(_profile_path(_external_dir(), profile.identity.id, "external identity id"), normalized)
    return normalized


def get_external_profile(identity_id: str) -> dict[str, Any] | None:
    path = _profile_path(_external_dir(), identity_id, "external identity id")
    if not path.exists():
        return None
    return ExternalIdentityProfile.from_payload(runtime_files.read_json_object(path)).to_payload()


def list_external_profiles() -> list[dict[str, Any]]:
    root = _external_dir()
    if not root.exists():
        return []
    rows = [
        ExternalIdentityProfile.from_payload(runtime_files.read_json_object(path)).to_payload()
        for path in sorted(root.glob("*.json"))
    ]
    return sorted(rows, key=lambda row: row["identity"]["id"])
