#!/usr/bin/env python3
"""Actor-aware parent thread submit boundary."""

from __future__ import annotations

from pathlib import Path


HELPER_DIR = Path(__file__).resolve().parent
import sys

if str(HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(HELPER_DIR))

import actor_model_config  # noqa: E402
import app_server  # noqa: E402
import submit_turn  # noqa: E402


SubmitTurnError = submit_turn.SubmitTurnError


class ParentThreadSubmitError(RuntimeError):
    """Raised when actor-aware parent submit setup fails before submit."""


def submit_parent_turn(
    *,
    socket_path: Path,
    instance_json: Path,
    thread_id: str,
    text: str,
    permissions: str,
) -> dict[str, object]:
    try:
        options = actor_model_config.resolve_parent_options(instance_json)
    except actor_model_config.ActorModelConfigError as exc:
        raise ParentThreadSubmitError(f"parent model config invalid: {exc}") from exc

    if options.has_values:
        try:
            app_server.thread_settings_update(
                socket_path,
                thread_id,
                model=options.model,
                effort=options.effort,
            )
        except app_server.AppServerError as exc:
            raise ParentThreadSubmitError(f"parent settings update failed: {exc}") from exc

    return submit_turn.submit_turn(
        socket_path=socket_path,
        thread_id=thread_id,
        text=text,
        permissions=permissions,
    )
