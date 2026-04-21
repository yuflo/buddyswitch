#!/usr/bin/env python3
"""Runtime-kernel persist entrypoint."""

from __future__ import annotations

from typing import Any


def persist_switch_request(
    resolved: dict[str, Any],
    *,
    skill_id: str | None,
    result: dict[str, Any],
) -> dict[str, Any]:
    import switch_runtime

    return switch_runtime._legacy_persist_switch(
        resolved,
        skill_id=skill_id,
        result=result,
    )
