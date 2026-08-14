"""Track-owned cleanup discovery for records and comments."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from buddyswitch.foundation.composition import (
    CleanupContribution,
    CleanupIndexProjection,
    OwnedStatePath,
)
import buddyswitch.foundation.identity.profiles as identity_profiles


_TRACK_RECORDS = Path("buddyswitch/objects/tracks")
_TRACK_COMMENTS = Path("buddyswitch/objects/track-comments")
_OBJECTS_ROOT = Path("buddyswitch/objects")


def _read_payload(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _role_from_identity_id(root: Path, value: object) -> str | None:
    if not isinstance(value, str) or not value.startswith("act-"):
        return None
    try:
        return identity_profiles.get_actor_role_id(
            value,
            objects_root=root / _OBJECTS_ROOT,
        )
    except (OSError, UnicodeError, ValueError):
        return None


def discover_track_records(root: Path) -> tuple[OwnedStatePath, ...]:
    directory = root / _TRACK_RECORDS
    if not directory.is_dir():
        return ()
    return tuple(
        OwnedStatePath(
            relative_path=path.relative_to(root).as_posix(),
        )
        for path in sorted(directory.glob("*.json"))
    )


def discover_track_comments(root: Path) -> tuple[OwnedStatePath, ...]:
    directory = root / _TRACK_COMMENTS
    if not directory.is_dir():
        return ()
    owned: list[OwnedStatePath] = []
    for path in sorted(directory.glob("*/*.json")):
        payload = _read_payload(path)
        object_id = (
            payload.get("id")
            if isinstance(payload, dict)
            and isinstance(payload.get("id"), str)
            and payload.get("id")
            else None
        )
        owner_role = None
        if payload is not None:
            owner_role = _role_from_identity_id(
                root,
                payload.get("by_identity_id")
            )
        warning = None
        if payload is None:
            warning = f"Malformed Track comment will be handled only by all-data cleanup: {path.relative_to(root).as_posix()}."
        elif object_id is None:
            warning = f"Track comment is missing id and cannot be role-attributed: {path.relative_to(root).as_posix()}."
        elif owner_role is None:
            warning = f"Track comment '{object_id}' has no attributable author role."
        relative_path = path.relative_to(root).as_posix()
        owned.append(
            OwnedStatePath(
                relative_path=relative_path,
                owner_roles=(owner_role,) if owner_role is not None else (),
                index_record={
                    "id": object_id,
                    "author_role": owner_role,
                    "object_path": relative_path,
                }
                if object_id is not None
                else None,
                warning=warning,
            )
        )
    return tuple(owned)


TRACK_RECORDS_CONTRIBUTION = CleanupContribution(
    category="track_objects",
    discover=discover_track_records,
    required_directories=(_TRACK_RECORDS.as_posix(),),
)
TRACK_COMMENTS_CONTRIBUTION = CleanupContribution(
    category="comment_objects",
    discover=discover_track_comments,
    required_directories=(_TRACK_COMMENTS.as_posix(),),
    index_projection=CleanupIndexProjection(
        object_ids_field="comment_object_ids",
        records_field="comment_records",
    ),
)
