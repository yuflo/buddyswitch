#!/usr/bin/env python3
"""Stable server-owned IM identity for the Web Management interface."""

from __future__ import annotations

import contextlib
import fcntl
import os
from pathlib import Path
from typing import Any, Iterator

from env.repos import runtime_files
import external_im_session


SCHEMA_VERSION = 1
CLIENT_KIND = "web-management"
DISPLAY_NAME = "BuddySwitch Web"


class WebImIdentityError(RuntimeError):
    """Raised when Web Management cannot establish its local IM identity."""


class WebImIdentityProvider:
    def __init__(
        self,
        *,
        identity_dir: Path | None = None,
        im_session: external_im_session.ExternalImSession | None = None,
    ) -> None:
        self._identity_dir = identity_dir
        self._im_session = im_session or external_im_session.ExternalImSession()

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
            authenticated = self._authenticate_record(record) if record is not None else None
            if record is not None and authenticated is not None:
                now = runtime_files.now_iso()
                created_at = record.get("created_at")
                updated = {
                    "schema_version": SCHEMA_VERSION,
                    "client_kind": CLIENT_KIND,
                    "display_name": DISPLAY_NAME,
                    "identity": authenticated["identity"],
                    "connection_key": str(record["connection_key"]).strip(),
                    "created_at": created_at if isinstance(created_at, str) and created_at.strip() else now,
                    "updated_at": now,
                }
                self._write(updated)
                updated["connection"] = authenticated["connection"]
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

    def _authenticate_record(self, record: dict[str, Any]) -> dict[str, Any] | None:
        connection_key = record.get("connection_key")
        identity = record.get("identity")
        if not isinstance(connection_key, str) or not connection_key.strip() or not isinstance(identity, dict):
            return None
        auth = self._im_session.authenticate(connection_key)
        if auth.get("ok") is not True:
            return None
        authenticated = auth.get("identity")
        connection = auth.get("connection")
        if not isinstance(authenticated, dict) or not isinstance(connection, dict):
            return None
        if _external_id(identity) != _external_id(authenticated):
            return None
        return {"identity": authenticated, "connection": connection}

    def _register_new(self) -> dict[str, Any]:
        result = self._im_session.create_connection(display_name=DISPLAY_NAME)
        if result.get("ok") is not True:
            message = result.get("error", {}).get("message") if isinstance(result.get("error"), dict) else None
            raise WebImIdentityError(str(message or "Unable to create Web Management IM connection."))
        now = runtime_files.now_iso()
        connection_key = result.get("connection_key")
        if not isinstance(connection_key, str) or not connection_key:
            raise WebImIdentityError("Web Management IM connection creation returned an invalid key.")
        authenticated = self._im_session.authenticate(connection_key)
        if authenticated.get("ok") is not True:
            raise WebImIdentityError("Web Management IM connection could not be authenticated.")
        identity = authenticated.get("identity")
        connection = authenticated.get("connection")
        if not isinstance(identity, dict) or not isinstance(connection, dict):
            raise WebImIdentityError("Web Management IM authentication returned an invalid identity.")
        record = {
            "schema_version": SCHEMA_VERSION,
            "client_kind": CLIENT_KIND,
            "display_name": DISPLAY_NAME,
            "identity": identity,
            "connection_key": connection_key,
            "created_at": now,
            "updated_at": now,
        }
        self._write(record)
        record["connection"] = connection
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


def _external_id(identity: dict[str, Any]) -> str:
    if identity.get("type") != "external":
        return ""
    value = identity.get("id")
    return value if isinstance(value, str) and value.strip() else ""
