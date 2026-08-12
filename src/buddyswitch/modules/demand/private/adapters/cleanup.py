"""Demand-owned discovery of canonical aggregate files for the cleanup host."""

from __future__ import annotations

import json
from pathlib import Path

from buddyswitch.foundation.composition import (
    CleanupContribution,
    OwnedStatePath,
)


_ACTOR_AGGREGATES = Path("buddyswitch/objects/demand-sys/actors")


def discover(root: Path) -> tuple[OwnedStatePath, ...]:
    directory = root / _ACTOR_AGGREGATES
    if not directory.is_dir():
        return ()
    owned: list[OwnedStatePath] = []
    for path in sorted(directory.glob("*.json")):
        owner_role: str | None = None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            payload = None
        if isinstance(payload, dict):
            actor_target = payload.get("actor_target")
            role_id = (
                actor_target.get("role_id")
                if isinstance(actor_target, dict)
                else None
            )
            if isinstance(role_id, str) and role_id.strip():
                owner_role = role_id.strip()
        owned.append(
            OwnedStatePath(
                relative_path=path.relative_to(root).as_posix(),
                owner_roles=(owner_role,) if owner_role is not None else (),
            )
        )
    return tuple(owned)


CONTRIBUTION = CleanupContribution(
    category="demand_aggregates",
    discover=discover,
)
