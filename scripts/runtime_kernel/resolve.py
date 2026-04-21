#!/usr/bin/env python3
"""Runtime-kernel resolve entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def resolve_switch_request(text: str, *, manifest_path: Path) -> dict[str, Any]:
    import switch_runtime

    return switch_runtime._legacy_resolve_switch(text, manifest_path=manifest_path)
