"""Actor-aware side-thread creation boundary."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping


HELPER_DIR = Path(__file__).resolve().parent
if str(HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(HELPER_DIR))

import actor_capability  # noqa: E402
import side_thread_lifecycle  # noqa: E402


class ActorSideThreadError(RuntimeError):
    """Raised when actor-aware side-thread setup fails before lifecycle start."""


def start_actor_side_thread(
    *,
    socket_path: Path,
    instance_json: Path,
    actor_id: str,
    parent_thread_id: str,
    text: str,
    purpose: str,
    workspace_dir: Path,
    shared_project_workspace_dir: Path,
    permissions: str,
    capability_level: str | None = None,
    output_schema: Mapping[str, Any] | None = None,
    config_overrides: Mapping[str, Any] | None = None,
    capability_hash: str | None = None,
    binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        resolved = actor_capability.resolve_side_capability(
            instance_json,
            explicit_level=capability_level,
        )
    except actor_capability.ActorCapabilityError as exc:
        raise ActorSideThreadError(f"side capability invalid: {exc}") from exc

    payload = side_thread_lifecycle.start_side_thread(
        socket_path=socket_path,
        instance_json=instance_json,
        actor_id=actor_id,
        parent_thread_id=parent_thread_id,
        text=text,
        purpose=purpose,
        workspace_dir=workspace_dir,
        shared_project_workspace_dir=shared_project_workspace_dir,
        permissions=permissions,
        model=resolved.model,
        model_reasoning_effort=resolved.effort,
        output_schema=output_schema,
        config_overrides=config_overrides,
        capability_hash=capability_hash,
        binding=binding,
    )
    return actor_capability.apply_side_capability_metadata(payload, resolved)
