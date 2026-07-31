"""Artifact-owned cleanup discovery for records and attachment bytes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from buddyswitch.runtime_support.env_cleanup import (
    CleanupContribution,
    OwnedStatePath,
)


_ARTIFACT_RECORDS = Path("buddyswitch/objects/artifacts")
_ARTIFACT_ATTACHMENTS = Path("buddyswitch/objects/artifact-attachments")


def _read_payload(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _role_from_identity_id(value: object) -> str | None:
    if not isinstance(value, str) or not value.startswith("act-"):
        return None
    role, separator, _suffix = value.removeprefix("act-").partition("-")
    return role if separator and role else None


def _artifact_owner_role(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    owner_role = _role_from_identity_id(
        payload.get("created_by_identity_id")
    )
    if owner_role is not None:
        return owner_role
    created_by_actor = payload.get("created_by_actor")
    role_id = (
        created_by_actor.get("role_id")
        if isinstance(created_by_actor, dict)
        else None
    )
    return role_id if isinstance(role_id, str) and role_id else None


def _owner_roles_by_artifact(root: Path) -> dict[str, str | None]:
    directory = root / _ARTIFACT_RECORDS
    if not directory.is_dir():
        return {}
    return {
        path.stem: _artifact_owner_role(_read_payload(path))
        for path in sorted(directory.glob("*.json"))
    }


def discover_artifact_records(root: Path) -> tuple[OwnedStatePath, ...]:
    directory = root / _ARTIFACT_RECORDS
    if not directory.is_dir():
        return ()
    owned: list[OwnedStatePath] = []
    for path in sorted(directory.glob("*.json")):
        payload = _read_payload(path)
        artifact_id = (
            payload.get("id")
            if isinstance(payload, dict)
            and isinstance(payload.get("id"), str)
            and payload.get("id")
            else None
        )
        owner_role = _artifact_owner_role(payload)
        warning = None
        if payload is None:
            warning = f"Malformed Artifact will be handled only by all-data cleanup: {path.relative_to(root).as_posix()}."
        elif artifact_id is None:
            warning = f"Artifact is missing id and cannot be role-attributed: {path.relative_to(root).as_posix()}."
        elif owner_role is None:
            warning = f"Artifact '{artifact_id}' has no attributable producer role."
        owned.append(
            OwnedStatePath(
                relative_path=path.relative_to(root).as_posix(),
                owner_role=owner_role,
                object_id=artifact_id,
                warning=warning,
            )
        )
    return tuple(owned)


def discover_attachment_bytes(root: Path) -> tuple[OwnedStatePath, ...]:
    directory = root / _ARTIFACT_ATTACHMENTS
    if not directory.is_dir():
        return ()
    owners = _owner_roles_by_artifact(root)
    return tuple(
        OwnedStatePath(
            relative_path=path.relative_to(root).as_posix(),
            owner_role=owners.get(path.parent.name),
        )
        for path in sorted(directory.glob("*/*"))
        if path.is_file() or path.is_symlink()
    )


ARTIFACT_RECORDS_CONTRIBUTION = CleanupContribution(
    category="artifact_objects",
    discover=discover_artifact_records,
    required_directories=(_ARTIFACT_RECORDS.as_posix(),),
)
ARTIFACT_ATTACHMENTS_CONTRIBUTION = CleanupContribution(
    category="artifact_attachments",
    discover=discover_attachment_bytes,
    required_directories=(_ARTIFACT_ATTACHMENTS.as_posix(),),
)
