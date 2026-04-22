#!/usr/bin/env python3
"""Runtime-kernel resolve entrypoint."""

from __future__ import annotations

from typing import Any


def resolve_switch_request(text: str, *, manifest_path: "Path | None" = None) -> dict[str, Any]:
    import switch_runtime

    if manifest_path is None:
        manifest_path = switch_runtime.DEFAULT_MANIFEST
    return switch_runtime._build_resolve_context(text, manifest_path=manifest_path)
