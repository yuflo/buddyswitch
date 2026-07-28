"""Small append-only JSONL runtime breadcrumb helper."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _format_mtime(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def append_event(log_path: Path, *, service: str, event: str, **fields: Any) -> None:
    if not isinstance(service, str) or not service.strip():
        raise ValueError("service must be a non-empty string")
    if not isinstance(event, str) or not event.strip():
        raise ValueError("event must be a non-empty string")
    row: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "service": service.strip(),
        "event": event.strip(),
    }
    row.update(fields)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def log_metadata(log_path: Path) -> dict[str, Any]:
    try:
        stat = log_path.stat()
    except FileNotFoundError:
        return {
            "path": str(log_path),
            "exists": False,
            "size_bytes": 0,
            "mtime": None,
            "last_event": None,
        }

    last_event: dict[str, Any] | None = None
    try:
        for line in log_path.read_text(encoding="utf-8").splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and isinstance(payload.get("service"), str) and isinstance(payload.get("event"), str):
                last_event = payload
    except OSError:
        last_event = None

    return {
        "path": str(log_path),
        "exists": True,
        "size_bytes": stat.st_size,
        "mtime": _format_mtime(stat.st_mtime),
        "last_event": last_event,
    }
