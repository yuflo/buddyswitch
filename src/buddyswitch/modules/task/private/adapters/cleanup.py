"""Task-owned discovery of canonical Task records for the cleanup host."""

from __future__ import annotations

import json
from pathlib import Path

from buddyswitch.runtime_support.env_cleanup import (
    CleanupContribution,
    OwnedStatePath,
)


_TASK_RECORDS = Path("buddyswitch/objects/task-sys/tasks")


def discover(root: Path) -> tuple[OwnedStatePath, ...]:
    directory = root / _TASK_RECORDS
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
                owner_role=owner_role,
            )
        )
    return tuple(owned)


CONTRIBUTION = CleanupContribution(
    category="task_records",
    discover=discover,
)
