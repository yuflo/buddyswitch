#!/usr/bin/env python3
"""Runtime-kernel prepare entrypoint."""

from __future__ import annotations

from typing import Any


def prepare_turn_context_request(text: str, *, manifest_path: "Path | None" = None) -> dict[str, Any]:
    import turn_runtime

    if manifest_path is None:
        manifest_path = turn_runtime.DEFAULT_MANIFEST
    return turn_runtime.prepare_turn_context(text, manifest_path=manifest_path)
