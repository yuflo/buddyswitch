#!/usr/bin/env python3
"""Runtime-kernel persist entrypoint."""

from __future__ import annotations

from typing import Any


def persist_skill_result_request(
    context: dict[str, Any],
    *,
    skill_id: str,
    result: dict[str, Any],
    manifest_path: "Path | None" = None,
) -> dict[str, Any]:
    import turn_runtime

    if manifest_path is None:
        manifest_path = turn_runtime.DEFAULT_MANIFEST
    return turn_runtime.persist_skill_result(
        context,
        skill_id=skill_id,
        result=result,
        manifest_path=manifest_path,
    )
