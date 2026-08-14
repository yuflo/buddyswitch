"""Communication-owned Message discovery for the generic cleanup host."""

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
from buddyswitch.foundation.state.cleanup import iter_directory_files


_MESSAGE_OBJECTS = Path("im/messages")
_RETIRED_MESSAGE_OBJECTS = Path("buddyswitch/objects/messages")
_OBJECTS_ROOT = Path("buddyswitch/objects")


def _identity_id(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        identity = value.get("identity")
        if isinstance(identity, dict):
            value = identity
        identity_id = value.get("id")
        if isinstance(identity_id, str) and identity_id.strip():
            return identity_id.strip()
    return None


def _actor_role(root: Path, identity_id: str | None) -> str | None:
    if not isinstance(identity_id, str) or not identity_id.startswith("act-"):
        return None
    try:
        return identity_profiles.get_actor_role_id(
            identity_id,
            objects_root=root / _OBJECTS_ROOT,
        )
    except (OSError, UnicodeError, ValueError):
        return None


def _read_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object")
    return payload


def _warning(
    *,
    relative_path: str,
    reason: str,
) -> str:
    return (
        f"{relative_path} cannot be safely attributed to scoped role cleanup "
        "and will be skipped; all-data cleanup will delete the Message entry "
        f"({reason})."
    )


def _invalid(
    *,
    relative_path: str,
    reason: str,
) -> OwnedStatePath:
    return OwnedStatePath(
        relative_path=relative_path,
        warning=_warning(relative_path=relative_path, reason=reason),
    )


def discover(root: Path) -> tuple[OwnedStatePath, ...]:
    owned: list[OwnedStatePath] = []
    directory = root / _MESSAGE_OBJECTS
    if directory.is_symlink():
        owned.append(
            _invalid(
                relative_path=_MESSAGE_OBJECTS.as_posix(),
                reason="current Message root is a leaf symlink; its target was not inspected",
            )
        )
    elif directory.is_dir():
        for path in iter_directory_files(directory):
            relative_path = path.relative_to(root).as_posix()
            if path.is_symlink():
                owned.append(
                    _invalid(
                        relative_path=relative_path,
                        reason="Message entry is a leaf symlink; its target was not inspected",
                    )
                )
                continue
            try:
                payload = _read_payload(path)
            except (OSError, UnicodeError, ValueError) as exc:
                owned.append(
                    _invalid(
                        relative_path=relative_path,
                        reason=f"invalid message object JSON: {exc}",
                    )
                )
                continue
            message_id = payload.get("id")
            conversation_id = payload.get("conversation_id")
            sender_identity_id = _identity_id(payload.get("sender_identity"))
            target_identity_id = _identity_id(payload.get("target_identity"))
            if not isinstance(message_id, str) or not message_id:
                owned.append(
                    _invalid(
                        relative_path=relative_path,
                        reason="message object is missing id",
                    )
                )
                continue
            if not isinstance(conversation_id, str) or not conversation_id:
                owned.append(
                    _invalid(
                        relative_path=relative_path,
                        reason=f"message '{message_id}' is missing conversation_id",
                    )
                )
                continue
            if sender_identity_id is None:
                owned.append(
                    _invalid(
                        relative_path=relative_path,
                        reason=f"message '{message_id}' is missing sender_identity.id",
                    )
                )
                continue
            if target_identity_id is None:
                owned.append(
                    _invalid(
                        relative_path=relative_path,
                        reason=f"message '{message_id}' is missing target_identity.id",
                    )
                )
                continue
            sender_role = _actor_role(root, sender_identity_id)
            target_role = _actor_role(root, target_identity_id)
            owner_roles = tuple(
                dict.fromkeys(
                    role
                    for role in (sender_role, target_role)
                    if role is not None
                )
            )
            record = {
                "id": message_id,
                "conversation_id": conversation_id,
                "sender_identity_id": sender_identity_id,
                "target_identity_id": target_identity_id,
                "from_role": sender_role,
                "to_role": target_role,
                "object_path": relative_path,
            }
            owned.append(
                OwnedStatePath(
                    relative_path=relative_path,
                    owner_roles=owner_roles,
                    index_record=record,
                    warning=(
                        None
                        if owner_roles
                        else _warning(
                            relative_path=relative_path,
                            reason="valid Message has no attributable actor role",
                        )
                    ),
                )
            )

    retired = root / _RETIRED_MESSAGE_OBJECTS
    if retired.is_symlink():
        owned.append(
            _invalid(
                relative_path=_RETIRED_MESSAGE_OBJECTS.as_posix(),
                reason=(
                    "retired message object schema root is a leaf symlink; "
                    "its target was not inspected"
                ),
            )
        )
    elif retired.is_dir():
        for path in iter_directory_files(retired):
            relative_path = path.relative_to(root).as_posix()
            owned.append(
                _invalid(
                    relative_path=relative_path,
                    reason=(
                        "entry uses retired message object schema; current IM "
                        f"messages live under {_MESSAGE_OBJECTS.as_posix()}"
                    ),
                )
            )
        owned.append(
            _invalid(
                relative_path=_RETIRED_MESSAGE_OBJECTS.as_posix(),
                reason=(
                    "directory uses retired message object schema; current IM "
                    f"messages live under {_MESSAGE_OBJECTS.as_posix()}"
                ),
            )
        )
    return tuple(owned)


CONTRIBUTION = CleanupContribution(
    category="message_objects",
    discover=discover,
    required_directories=(_MESSAGE_OBJECTS.as_posix(),),
    index_projection=CleanupIndexProjection(
        object_ids_field="message_object_ids",
        records_field="message_records",
    ),
)
