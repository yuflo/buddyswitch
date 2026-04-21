#!/usr/bin/env python3
"""Runtime-kernel prepare-execution entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def prepare_execution_request(
    resolved: dict[str, Any],
    *,
    skill_id: str,
    manifest_path: Path,
) -> dict[str, Any]:
    import switch_runtime

    return switch_runtime._legacy_prepare_execution_payload(
        resolved,
        skill_id=skill_id,
        manifest_path=manifest_path,
    )
