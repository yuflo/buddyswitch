#!/usr/bin/env python3
"""Runtime-kernel persist entrypoint."""

from __future__ import annotations

from typing import Any


def persist_buddy_run_request(
    context: dict[str, Any],
    *,
    result: dict[str, Any],
    manifest_path: "Path | None" = None,
) -> dict[str, Any]:
    import turn_runtime

    if manifest_path is None:
        manifest_path = turn_runtime.DEFAULT_MANIFEST
    return turn_runtime.persist_buddy_run(
        context,
        result=result,
        manifest_path=manifest_path,
    )
