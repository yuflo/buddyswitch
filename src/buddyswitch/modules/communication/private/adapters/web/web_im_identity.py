"""Communication-owned stable IM identity for Web Management."""

from __future__ import annotations

import contextlib
import fcntl
import os
from pathlib import Path
from typing import Any, Iterator

import buddyswitch.foundation.state.runtime as state_runtime
from buddyswitch.modules.communication.private.adapters.web import (
    external_im_session,
)


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
        return self._identity_dir or state_runtime.LOCAL_ROOT / "web-management"

    @property
    def identity_path(self) -> Path:
        return self.identity_dir / "im-session.json"

    @property
    def lock_path(self) -> Path:
        return self.identity_dir / "im-session.lock"

    def ensure(self) -> dict[str, Any]:
        state_runtime.require_central_im_write_root()
        with self._lock():
            record = self._read_existing()
            authenticated = self._authenticate_record(record) if record is not None else None
            if record is not None and authenticated is not None:
                now = state_runtime.now_iso()
                created_at = record.get("created_at")
                updated = {
                    "schema_version": SCHEMA_VERSION,
                    "client_kind": CLIENT_KIND,
                    "display_name": DISPLAY_NAME,
                    "identity": authenticated["identity"],
                    "external_session_key": str(record["external_session_key"]).strip(),
                    "created_at": created_at if isinstance(created_at, str) and created_at.strip() else now,
                    "updated_at": now,
                }
                self._write(updated)
                updated["external_session"] = authenticated["external_session"]
                return updated
            return self._register_new()

    def _read_existing(self) -> dict[str, Any] | None:
        path = self.identity_path
        if not path.exists():
            return None
        try:
            payload = state_runtime.read_json_object(path)
        except ValueError:
            return None
        return payload

    def _authenticate_record(self, record: dict[str, Any]) -> dict[str, Any] | None:
        external_session_key = record.get("external_session_key")
        identity = record.get("identity")
        if not isinstance(external_session_key, str) or not external_session_key.strip() or not isinstance(identity, dict):
            return None
        auth = self._im_session.authenticate_external_session_key(external_session_key)
        if auth.get("ok") is not True:
            return None
        authenticated = auth.get("identity")
        external_session = auth.get("external_session")
        if not isinstance(authenticated, dict) or not isinstance(external_session, dict):
            return None
        if _external_id(identity) != _external_id(authenticated):
            return None
        return {"identity": authenticated, "external_session": external_session}

    def _register_new(self) -> dict[str, Any]:
        result = self._im_session.create_external_session(display_name=DISPLAY_NAME)
        if result.get("ok") is not True:
            message = result.get("error", {}).get("message") if isinstance(result.get("error"), dict) else None
            raise WebImIdentityError(str(message or "Unable to create Web Management IM external session."))
        now = state_runtime.now_iso()
        external_session_key = result.get("external_session_key")
        if not isinstance(external_session_key, str) or not external_session_key:
            raise WebImIdentityError("Web Management IM external session creation returned an invalid key.")
        authenticated = self._im_session.authenticate_external_session_key(external_session_key)
        if authenticated.get("ok") is not True:
            raise WebImIdentityError("Web Management IM external session could not be authenticated.")
        identity = authenticated.get("identity")
        external_session = authenticated.get("external_session")
        if not isinstance(identity, dict) or not isinstance(external_session, dict):
            raise WebImIdentityError("Web Management IM authentication returned an invalid identity.")
        record = {
            "schema_version": SCHEMA_VERSION,
            "client_kind": CLIENT_KIND,
            "display_name": DISPLAY_NAME,
            "identity": identity,
            "external_session_key": external_session_key,
            "created_at": now,
            "updated_at": now,
        }
        self._write(record)
        record["external_session"] = external_session
        return record

    def _write(self, record: dict[str, Any]) -> None:
        state_runtime.write_json_object(self.identity_path, record)
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
