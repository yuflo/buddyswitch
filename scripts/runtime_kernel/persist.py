#!/usr/bin/env python3
"""Runtime-kernel persist entrypoint."""

from __future__ import annotations

from typing import Any


def persist_buddy_run_request(
    context: dict[str, Any],
    *,
    result: dict[str, Any],
    manifest_path: "Path | None" = None,
    idempotency_key: str | None = None,
    result_hash: str | None = None,
) -> dict[str, Any]:
    from env.services import runs as run_service

    if manifest_path is None:
        import turn_runtime

        manifest_path = turn_runtime.DEFAULT_MANIFEST
    return run_service.commit_buddy_run(
        context,
        result=result,
        manifest_path=manifest_path,
        idempotency_key=idempotency_key,
        result_hash=result_hash,
    )
