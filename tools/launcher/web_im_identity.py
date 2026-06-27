#!/usr/bin/env python3
"""Stable server-owned IM identity for the Web Management interface."""

from __future__ import annotations

import contextlib
import fcntl
import os
from pathlib import Path
from typing import Any, Iterator

from env.repos import runtime_files
from env.services import messages as message_service


SCHEMA_VERSION = 1
CLIENT_KIND = "web-management"
DISPLAY_NAME = "BuddySwitch Web"


class WebImIdentityError(RuntimeError):
    """Raised when Web Management cannot establish its local IM identity."""


class WebImIdentityProvider:
    def __init__(self, *, identity_dir: Path | None = None) -> None:
        self._identity_dir = identity_dir

    @property
    def identity_dir(self) -> Path:
        return self._identity_dir or runtime_files.LOCAL_ROOT / "web-management"

    @property
    def identity_path(self) -> Path:
        return self.identity_dir / "im-session.json"

    @property
    def lock_path(self) -> Path:
        return self.identity_dir / "im-session.lock"

    def ensure(self) -> dict[str, Any]:
        runtime_files.require_central_im_write_root()
        with self._lock():
            record = self._read_existing()
            if record is not None and self._is_valid(record):
                updated = dict(record)
                updated["updated_at"] = runtime_files.now_iso()
                self._write(updated)
                return updated
            return self._register_new()

    def _read_existing(self) -> dict[str, Any] | None:
        path = self.identity_path
        if not path.exists():
            return None
        try:
            payload = runtime_files.read_json_object(path)
        except ValueError:
            return None
        return payload

    def _is_valid(self, record: dict[str, Any]) -> bool:
        token = record.get("participant_token")
        participant = record.get("participant")
        if not isinstance(token, str) or not token.strip() or not isinstance(participant, dict):
            return False
        auth = message_service.authenticate_im_token(token)
        if auth.get("ok") is not True:
            return False
        authenticated = auth.get("participant")
        if not isinstance(authenticated, dict):
            return False
        return _external_id(participant) == _external_id(authenticated)

    def _register_new(self) -> dict[str, Any]:
        result = message_service.register_external_participant(
            client_kind=CLIENT_KIND,
            display_name=DISPLAY_NAME,
        )
        if result.get("ok") is not True:
            message = result.get("error", {}).get("message") if isinstance(result.get("error"), dict) else None
            raise WebImIdentityError(str(message or "Unable to register Web Management IM participant."))
        now = runtime_files.now_iso()
        participant = result.get("participant")
        token = result.get("participant_token")
        if not isinstance(participant, dict) or not isinstance(token, str) or not token:
            raise WebImIdentityError("Web Management IM registration returned an invalid identity.")
        record = {
            "schema_version": SCHEMA_VERSION,
            "client_kind": CLIENT_KIND,
            "display_name": DISPLAY_NAME,
            "participant": participant,
            "participant_token": token,
            "event_cursor": result.get("event_cursor") or "imev-000000000000",
            "created_at": now,
            "updated_at": now,
        }
        self._write(record)
        return record

    def _write(self, record: dict[str, Any]) -> None:
        runtime_files.write_json_object(self.identity_path, record)
        try:
            os.chmod(self.identity_path, 0o600)
        except OSError:
            pass

    @contextlib.contextmanager
    def _lock(self) -> Iterator[None]:
        self.identity_dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, "r+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _external_id(participant: dict[str, Any]) -> str:
    if participant.get("kind") != "external":
        return ""
    value = participant.get("external_id")
    return value if isinstance(value, str) and value.strip() else ""
